"""Clients IA gratuits : Google Gemini (principal) et un fournisseur compatible OpenAI (secours, ex. Groq).

``LLMRouter.generate_json`` :
- appelle le fournisseur, exige du JSON, le valide avec un schéma pydantic ;
- réessaie avec backoff exponentiel (429 / 5xx / JSON invalide) ;
- passe au modèle / fournisseur suivant si ça échoue encore ;
- respecte un plafond global d'appels par numéro (économie de quota).
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Callable, TypeVar

import requests
from pydantic import BaseModel, ValidationError

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Erreur générique d'un fournisseur IA."""


class RetryableError(LLMError):
    """Erreur temporaire (quota 429, surcharge 5xx, coupure réseau) : on réessaie après une pause."""

    def __init__(self, msg: str, retry_after: float | None = None):
        super().__init__(msg)
        self.retry_after = retry_after


class ModelUnavailable(LLMError):
    """Le modèle n'existe plus / n'est pas accessible : inutile de réessayer, on passe au suivant."""


class BudgetExceeded(LLMError):
    """Plafond d'appels IA atteint pour ce numéro."""


def _retry_after(resp: requests.Response) -> float | None:
    """Délai conseillé par le serveur : en-tête Retry-After, ou champ « retryDelay » de Gemini."""
    val = resp.headers.get("Retry-After")
    try:
        if val:
            return min(float(val), 120.0)
    except ValueError:
        pass
    m = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', resp.text or "")
    return min(float(m.group(1)) + 1, 120.0) if m else None


def _raise_for_status(resp: requests.Response, provider: str) -> None:
    if resp.status_code < 400:
        return
    snippet = resp.text[:300].replace("\n", " ")
    if resp.status_code == 429 or resp.status_code >= 500:
        raise RetryableError(f"{provider} HTTP {resp.status_code}: {snippet}", _retry_after(resp))
    if resp.status_code in (400, 403, 404) and re.search(r"model|not found|NOT_FOUND|deprecat", snippet, re.I):
        raise ModelUnavailable(f"{provider} HTTP {resp.status_code}: {snippet}")
    raise LLMError(f"{provider} HTTP {resp.status_code}: {snippet}")


@dataclass
class GeminiProvider:
    api_key: str
    model: str
    temperature: float = 0.7
    timeout: int = 120
    session: requests.Session | None = None

    @property
    def label(self) -> str:
        return f"gemini:{self.model}"

    def complete(self, system: str, user: str) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": self.temperature,
                "responseMimeType": "application/json",
            },
        }
        http = self.session or requests
        try:
            resp = http.post(
                url,
                json=body,
                headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise RetryableError(f"Gemini réseau : {exc}") from exc
        _raise_for_status(resp, "Gemini")
        data = resp.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise RetryableError(f"Gemini : réponse vide ({data.get('promptFeedback')})")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        if not text.strip():
            raise RetryableError(f"Gemini : texte vide (finishReason={candidates[0].get('finishReason')})")
        return text


@dataclass
class OpenAICompatProvider:
    """Fournisseur compatible API OpenAI /chat/completions (Groq, OpenRouter, ...)."""

    api_key: str
    base_url: str
    model: str
    temperature: float = 0.7
    timeout: int = 120
    session: requests.Session | None = None

    @property
    def label(self) -> str:
        return f"fallback:{self.model}"

    def complete(self, system: str, user: str) -> str:
        url = self.base_url.rstrip("/") + "/chat/completions"
        body = {
            "model": self.model,
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        http = self.session or requests
        try:
            resp = http.post(
                url,
                json=body,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise RetryableError(f"Fallback réseau : {exc}") from exc
        _raise_for_status(resp, "Fallback")
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError) as exc:
            raise RetryableError(f"Fallback : réponse inattendue {str(data)[:200]}") from exc


def extract_json(text: str) -> dict:
    """Extrait un objet JSON d'une réponse (tolère les balises ```json ... ``` ou du texte autour)."""
    text = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.S)
    if fence:
        text = fence.group(1)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise
        obj = json.loads(text[start : end + 1])
    if not isinstance(obj, dict):
        raise ValueError("la réponse JSON n'est pas un objet")
    return obj


class LLMRouter:
    def __init__(
        self,
        providers: list,
        max_calls: int = 6,
        attempts_per_provider: int = 3,
        base_delay: float = 5.0,
        max_delay: float = 90.0,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if not providers:
            raise ValueError("Aucun fournisseur IA configuré")
        self.providers = providers
        self.max_calls = max_calls
        self.attempts = attempts_per_provider
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.sleep = sleep
        self.calls = 0
        self.used: list[str] = []

    def generate_json(
        self,
        system: str,
        user: str,
        schema: type[T],
        check: Callable[[T], None] | None = None,
    ) -> T:
        """Renvoie un objet validé par ``schema`` (et par ``check`` si fourni, qui lève ValueError)."""
        last_error: Exception | None = None
        for provider in list(self.providers):
            feedback = ""
            for attempt in range(1, self.attempts + 1):
                if self.calls >= self.max_calls:
                    raise BudgetExceeded(
                        f"plafond de {self.max_calls} appels IA atteint (dernière erreur : {last_error})"
                    )
                self.calls += 1
                log.info("Appel IA n°%d → %s (tentative %d)", self.calls, provider.label, attempt)
                try:
                    raw = provider.complete(system, user + feedback)
                    obj = schema.model_validate(extract_json(raw))
                    if check:
                        check(obj)
                    if provider.label not in self.used:
                        self.used.append(provider.label)
                    return obj
                except ModelUnavailable as exc:
                    log.warning("Modèle indisponible, on passe au suivant : %s", exc)
                    last_error = exc
                    # Le modèle n'existe plus : inutile de l'interroger encore dans ce run.
                    if provider in self.providers:
                        self.providers.remove(provider)
                    break
                except RetryableError as exc:
                    last_error = exc
                    delay = exc.retry_after or min(self.max_delay, self.base_delay * 2 ** (attempt - 1))
                    log.warning("Erreur temporaire (%s). Nouvel essai dans %.0fs", exc, delay)
                    if attempt < self.attempts:
                        self.sleep(delay)
                except (ValueError, ValidationError) as exc:  # JSON invalide ou non conforme
                    last_error = exc
                    msg = str(exc)[:800]
                    log.warning("Réponse IA invalide : %s", msg.replace("\n", " | ")[:300])
                    feedback = (
                        "\n\nATTENTION : ta réponse précédente était invalide pour la raison suivante :\n"
                        f"{msg}\nCorrige-la et renvoie UNIQUEMENT le JSON demandé."
                    )
                    if attempt < self.attempts:
                        self.sleep(min(self.max_delay, self.base_delay * 2 ** (attempt - 1)))
                except LLMError as exc:  # erreur non récupérable (clé invalide...)
                    log.error("Erreur du fournisseur %s : %s", provider.label, exc)
                    last_error = exc
                    break
            log.warning("Fournisseur %s abandonné, bascule sur le suivant s'il existe.", provider.label)
        raise LLMError(f"Tous les fournisseurs IA ont échoué. Dernière erreur : {last_error}")


def build_router(settings, secrets, session: requests.Session | None = None) -> LLMRouter | None:
    """Construit la chaîne Gemini → modèles Gemini de secours → fournisseur de secours (si clé)."""
    ai = settings.ai
    temp = float(ai.get("temperature", 0.7))
    providers: list = []
    if secrets.gemini_api_key:
        models = [secrets.gemini_model or ai.get("gemini_model", "gemini-3.6-flash")]
        for m in ai.get("gemini_backup_models", []) or []:
            if m and m not in models:
                models.append(m)
        providers += [GeminiProvider(secrets.gemini_api_key, m, temp, session=session) for m in models]
    if secrets.fallback_api_key:
        providers.append(
            OpenAICompatProvider(
                secrets.fallback_api_key,
                secrets.fallback_base_url or ai.get("fallback_base_url", "https://api.groq.com/openai/v1"),
                secrets.fallback_model or ai.get("fallback_model", "openai/gpt-oss-120b"),
                temp,
                session=session,
            )
        )
    if not providers:
        return None
    return LLMRouter(providers, max_calls=int(ai.get("max_calls", 6)))
