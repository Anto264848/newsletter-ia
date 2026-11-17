"""Chargement de la configuration (fichiers YAML publics + variables d'environnement secrètes)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .paths import CONFIG_DIR


def load_yaml(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


@dataclass
class Settings:
    raw: dict[str, Any]
    sources: list[dict[str, Any]]
    tools: list[dict[str, Any]]

    # Raccourcis pratiques
    @property
    def name(self) -> str:
        return self.raw["newsletter"]["name"]

    @property
    def tagline(self) -> str:
        return self.raw["newsletter"]["tagline"]

    @property
    def sender_name(self) -> str:
        return self.raw["newsletter"].get("sender_name") or self.name

    @property
    def collect(self) -> dict[str, Any]:
        return self.raw.get("collect", {})

    @property
    def select(self) -> dict[str, Any]:
        return self.raw.get("select", {})

    @property
    def ai(self) -> dict[str, Any]:
        return self.raw.get("ai", {})

    @property
    def site_url(self) -> str:
        """URL publique du site, sans « / » final.

        Ordre : variable SITE_URL > settings.yaml > déduite de GITHUB_REPOSITORY.
        """
        url = os.environ.get("SITE_URL") or self.raw.get("site", {}).get("url") or ""
        if not url:
            repo = os.environ.get("GITHUB_REPOSITORY", "")
            if "/" in repo:
                owner, name = repo.split("/", 1)
                if name.lower() == f"{owner.lower()}.github.io":
                    url = f"https://{owner.lower()}.github.io"
                else:
                    url = f"https://{owner.lower()}.github.io/{name}"
        return url.rstrip("/")

    @property
    def subscribe_form_url(self) -> str:
        return (self.raw.get("site", {}).get("subscribe_form_url") or "").strip()


def load_settings(config_dir: Path = CONFIG_DIR) -> Settings:
    raw = load_yaml(config_dir / "settings.yaml")
    sources = [
        s for s in load_yaml(config_dir / "sources.yaml").get("sources", []) if s.get("enabled", True)
    ]
    tools_path = config_dir / "tools.yaml"
    tools = load_yaml(tools_path).get("tools", []) if tools_path.exists() else []
    return Settings(raw=raw, sources=sources, tools=tools)


@dataclass
class Secrets:
    """Secrets lus dans l'environnement (GitHub Secrets). Jamais écrits dans le dépôt."""

    gemini_api_key: str = ""
    gemini_model: str = ""
    fallback_api_key: str = ""
    fallback_base_url: str = ""
    fallback_model: str = ""
    brevo_api_key: str = ""
    brevo_list_id: str = ""
    brevo_sender_email: str = ""
    extra: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "Secrets":
        g = lambda k: os.environ.get(k, "").strip()  # noqa: E731
        return cls(
            gemini_api_key=g("GEMINI_API_KEY"),
            gemini_model=g("GEMINI_MODEL"),
            fallback_api_key=g("FALLBACK_API_KEY"),
            fallback_base_url=g("FALLBACK_BASE_URL"),
            fallback_model=g("FALLBACK_MODEL"),
            brevo_api_key=g("BREVO_API_KEY"),
            brevo_list_id=g("BREVO_LIST_ID"),
            brevo_sender_email=g("BREVO_SENDER_EMAIL"),
        )

    def missing_for_send(self) -> list[str]:
        missing = []
        for env, val in (
            ("BREVO_API_KEY", self.brevo_api_key),
            ("BREVO_LIST_ID", self.brevo_list_id),
            ("BREVO_SENDER_EMAIL", self.brevo_sender_email),
        ):
            if not val:
                missing.append(env)
        return missing
