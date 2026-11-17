"""Validation du JSON de l'IA, retries / backoff / fallback, et absence de liens inventés."""
from __future__ import annotations

import json
from datetime import date

import pytest
from conftest import FakeResponse, FakeSession, make_article
from pydantic import ValidationError

from newsletter.config import Secrets
from newsletter.models import IssueContent, SelectionResult
from newsletter.state import History
from newsletter.write import NotEnoughContent, write_issue
from newsletter.write.llm import (
    BudgetExceeded,
    GeminiProvider,
    LLMError,
    LLMRouter,
    OpenAICompatProvider,
    RetryableError,
    build_router,
    extract_json,
)
from newsletter.write.mock import MockProvider


class ScriptedProvider:
    """Fournisseur qui renvoie une suite de réponses / exceptions prédéfinies."""

    def __init__(self, label, script):
        self.label = label
        self.script = list(script)
        self.prompts = []

    def complete(self, system, user):
        self.prompts.append(user)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item if isinstance(item, str) else json.dumps(item)


def no_sleep(_):
    pass


# ---------- extraction / schéma ----------

def test_extract_json_variants():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('```json\n{"a": 2}\n```') == {"a": 2}
    assert extract_json('Voici : {"a": 3} merci') == {"a": 3}
    with pytest.raises(ValueError):
        extract_json("pas de json")
    with pytest.raises(ValueError):
        extract_json("[1, 2]")


def test_issue_schema_rejects_missing_or_short_fields():
    with pytest.raises(ValidationError):
        IssueContent.model_validate({"title": "Titre ok"})
    good = json.loads(MockProvider().complete(
        "", '- id: a1\n  titre: T\nid « a1 » dans cet ordre : ["b1"] Termes INTERDITS (x) : []'))
    IssueContent.model_validate(good)
    bad = dict(good, top_story=dict(good["top_story"], summary="trop court"))
    with pytest.raises(ValidationError):
        IssueContent.model_validate(bad)


def test_selection_dedupes_briefs():
    assert SelectionResult.model_validate({"top": "a", "briefs": ["b", "b", "c"]}).briefs == ["b", "c"]


# ---------- routeur : retries, backoff, fallback ----------

def test_router_retries_invalid_json_with_feedback():
    p = ScriptedProvider("p", ["pas du json", {"top": "a", "briefs": ["b"]}])
    r = LLMRouter([p], sleep=no_sleep)
    res = r.generate_json("sys", "user", SelectionResult)
    assert res.top == "a" and r.calls == 2
    assert "invalide" in p.prompts[1]


def test_router_backoff_on_429_then_success():
    sleeps = []
    p = ScriptedProvider("p", [RetryableError("429"), RetryableError("429"), {"top": "a", "briefs": ["b"]}])
    r = LLMRouter([p], sleep=sleeps.append, base_delay=2)
    r.generate_json("s", "u", SelectionResult)
    assert sleeps == [2, 4]  # backoff exponentiel


def test_router_falls_back_to_second_provider():
    p1 = ScriptedProvider("gemini", [RetryableError("429")] * 3)
    p2 = ScriptedProvider("groq", [{"top": "a", "briefs": ["b"]}])
    r = LLMRouter([p1, p2], sleep=no_sleep, max_calls=10)
    r.generate_json("s", "u", SelectionResult)
    assert r.used == ["groq"] and r.calls == 4


def test_router_budget_is_enforced():
    p = ScriptedProvider("p", [RetryableError("429")] * 10)
    r = LLMRouter([p], sleep=no_sleep, max_calls=2, attempts_per_provider=5)
    with pytest.raises(BudgetExceeded):
        r.generate_json("s", "u", SelectionResult)
    assert r.calls == 2


def test_router_raises_when_all_fail():
    p = ScriptedProvider("p", ["nope"] * 3)
    with pytest.raises(LLMError):
        LLMRouter([p], sleep=no_sleep).generate_json("s", "u", SelectionResult)


def test_gemini_provider_parses_response_and_skips_thoughts():
    body = {"candidates": [{"content": {"parts": [{"text": "réflexion", "thought": True}, {"text": '{"ok": 1}'}]}}]}
    session = FakeSession({"https://generativelanguage.googleapis.com": FakeResponse(200, json_data=body)})
    out = GeminiProvider("KEY", "gemini-test", session=session).complete("sys", "user")
    assert out == '{"ok": 1}'
    method, url, kw = session.calls[0]
    assert "models/gemini-test:generateContent" in url
    assert kw["headers"]["x-goog-api-key"] == "KEY"
    assert kw["json"]["generationConfig"]["responseMimeType"] == "application/json"


def test_gemini_429_uses_retry_delay_and_404_means_model_gone():
    from newsletter.write.llm import ModelUnavailable

    r429 = FakeResponse(429, '{"error": {"details": [{"retryDelay": "17s"}]}}')
    session = FakeSession({"https://generativelanguage.googleapis.com": r429})
    with pytest.raises(RetryableError) as exc:
        GeminiProvider("K", "m", session=session).complete("s", "u")
    assert exc.value.retry_after == 18
    session = FakeSession({"https://generativelanguage.googleapis.com": FakeResponse(404, "models/m is not found")})
    with pytest.raises(ModelUnavailable):
        GeminiProvider("K", "m", session=session).complete("s", "u")


def test_openai_compat_provider():
    body = {"choices": [{"message": {"content": '{"x": 1}'}}]}
    session = FakeSession({"https://api.groq.com": FakeResponse(200, json_data=body)})
    p = OpenAICompatProvider("K", "https://api.groq.com/openai/v1", "model-x", session=session)
    assert p.complete("s", "u") == '{"x": 1}'
    assert session.calls[0][2]["json"]["response_format"] == {"type": "json_object"}


def test_build_router_chain(settings, monkeypatch):
    assert build_router(settings, Secrets()) is None
    r = build_router(settings, Secrets(gemini_api_key="g", gemini_model="gemini-custom", fallback_api_key="f"))
    labels = [p.label for p in r.providers]
    assert labels[0] == "gemini:gemini-custom"
    assert labels[-1].startswith("fallback:")
    r = build_router(settings, Secrets(fallback_api_key="f"))
    assert [p.label for p in r.providers] == ["fallback:openai/gpt-oss-120b"]


# ---------- rédaction complète : liens jamais inventés ----------

def test_write_issue_links_come_from_collected_data(settings, tmp_path):
    arts = [make_article(i) for i in range(1, 8)]
    top_id, brief_ids = arts[0].id, [a.id for a in arts[1:5]]
    content = json.loads(MockProvider().complete(
        "", "\n".join(f"- id: {a.id}\n  titre: {a.title}" for a in arts)
        + f'\nid « {top_id} » dans cet ordre : {json.dumps(brief_ids)} Termes INTERDITS (x) : []'))
    # L'IA tente d'injecter un lien et un identifiant inconnu : ils doivent être ignorés / refusés.
    content["top_story"]["url"] = "https://site-invente.example/fake"
    p = ScriptedProvider("ai", [
        {"top": top_id, "briefs": brief_ids},
        dict(content, briefs=content["briefs"] + [{"id": "zzz", "headline": "x", "summary": "y" * 100}]),
        content,
    ])
    router = LLMRouter([p], sleep=no_sleep)
    issue = write_issue(router, arts, settings, History(tmp_path), 1, "2026-W47", date(2026, 11, 16))
    assert router.calls == 3  # 1 sélection + 1 rédaction refusée (id inconnu) + 1 correcte
    assert issue["top"]["url"] == arts[0].url
    assert [b["url"] for b in issue["briefs"]] == [a.url for a in arts[1:5]]
    assert "site-invente" not in json.dumps(issue)
    assert issue["tool"]["url"] == settings.tools[0]["url"]


def test_write_issue_rejects_repeated_word(settings, tmp_path):
    history = History(tmp_path)
    history.words = ["Modèle de langage (LLM)"]
    arts = [make_article(i) for i in range(1, 7)]
    router = LLMRouter([MockProvider()], sleep=no_sleep)
    issue = write_issue(router, arts, settings, history, 2, "2026-W48", date(2026, 11, 23))
    assert issue["word"]["term"] != "Modèle de langage (LLM)"


def test_write_issue_skips_used_tools(settings, tmp_path):
    history = History(tmp_path)
    history.tools = [settings.tools[0]["name"]]
    arts = [make_article(i) for i in range(1, 7)]
    issue = write_issue(LLMRouter([MockProvider()]), arts, settings, history, 2, "2026-W48", date(2026, 11, 23))
    assert issue["tool"]["name"] == settings.tools[1]["name"]


def test_write_issue_not_enough_content(settings, tmp_path):
    arts = [make_article(i) for i in range(1, 4)]
    with pytest.raises(NotEnoughContent):
        write_issue(LLMRouter([MockProvider()]), arts, settings, History(tmp_path), 1, "2026-W47", date(2026, 11, 16))


def test_selection_failure_falls_back_to_score_order(settings, tmp_path):
    arts = [make_article(i) for i in range(1, 9)]
    brief_ids = [a.id for a in arts[1:7]]  # briefs_max = 6, dans l'ordre du score
    content = json.loads(MockProvider().complete(
        "", f'id « {arts[0].id} » dans cet ordre : {json.dumps(brief_ids)} Termes INTERDITS (x) : []'))
    p = ScriptedProvider("ai", ["invalide"] * 3 + [content])
    router = LLMRouter([p], sleep=no_sleep, max_calls=10)
    issue = write_issue(router, arts, settings, History(tmp_path), 1, "2026-W47", date(2026, 11, 16))
    assert issue["top"]["url"] == arts[0].url
    assert len(issue["briefs"]) == 6 and router.calls == 4
