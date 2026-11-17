"""Fixtures partagées. Aucun test n'accède au réseau : les sessions HTTP sont simulées."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from newsletter.config import Settings, load_settings  # noqa: E402
from newsletter.models import Article  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 11, 17, 6, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Sécurité : tout appel réseau réel fait échouer le test."""
    import requests

    def boom(*a, **k):
        raise RuntimeError("Accès réseau interdit pendant les tests")

    monkeypatch.setattr(requests.Session, "request", boom)
    monkeypatch.setattr(requests, "post", boom)
    monkeypatch.setattr(requests, "get", boom)
    # Pas de variables d'environnement parasites
    for var in ("GEMINI_API_KEY", "FALLBACK_API_KEY", "BREVO_API_KEY", "GITHUB_REPOSITORY", "SITE_URL",
                "GITHUB_STEP_SUMMARY"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def settings() -> Settings:
    s = load_settings()
    s.raw.setdefault("site", {})["url"] = "https://exemple.github.io/newsletter"
    return s


class FakeResponse:
    def __init__(self, status: int = 200, content: bytes | str = b"", json_data: Any = None, headers=None):
        self.status_code = status
        if isinstance(content, str):
            content = content.encode("utf-8")
        self.content = content if json_data is None else json.dumps(json_data).encode()
        self.text = self.content.decode("utf-8", "replace")
        self._json = json_data
        self.headers = headers or {}

    def json(self):
        return self._json if self._json is not None else json.loads(self.text)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    """Session HTTP simulée : associe un préfixe d'URL à une réponse (ou une exception)."""

    def __init__(self, routes: dict[str, Any]):
        self.routes = routes
        self.calls: list[tuple[str, str, dict]] = []

    def _match(self, url: str):
        for prefix, resp in self.routes.items():
            if url.startswith(prefix):
                if isinstance(resp, Exception):
                    raise resp
                if isinstance(resp, list):
                    return resp.pop(0)
                return resp
        raise RuntimeError(f"URL non simulée : {url}")

    def get(self, url, **kw):
        self.calls.append(("GET", url, kw))
        return self._match(url)

    def post(self, url, **kw):
        self.calls.append(("POST", url, kw))
        return self._match(url)

    def request(self, method, url, **kw):
        self.calls.append((method, url, kw))
        return self._match(url)


DISTINCT_TITLES = [
    "OpenAI lance un assistant vocal gratuit",
    "Google ajoute Gemini dans Maps",
    "L'Europe précise les règles de l'AI Act",
    "Mistral ouvre un bureau à Singapour",
    "Une école teste un tuteur virtuel en maths",
    "Les centres de données consomment plus d'électricité",
    "Meta dévoile des lunettes connectées",
    "Une arnaque au deepfake vise les retraités",
    "Apple renforce Siri sur iPhone",
    "Nvidia publie ses résultats trimestriels",
]


def make_article(i: int, title: str | None = None, source: str = "src", weight: float = 1.0, days_ago: float = 1) -> Article:
    from datetime import timedelta

    return Article(
        title=title or DISTINCT_TITLES[(i - 1) % len(DISTINCT_TITLES)],
        url=f"https://exemple.com/article-{i}",
        source_id=source,
        source_name=source.capitalize(),
        published=NOW - timedelta(days=days_ago),
        excerpt=f"Extrait de l'article {i}. Une entreprise annonce quelque chose d'important.",
        weight=weight,
    )


def sample_issue(number: int = 1, week: str = "2026-W47") -> dict[str, Any]:
    return {
        "number": number,
        "week": week,
        "date": "2026-11-16",
        "date_label": "16 novembre 2026",
        "title": "L'IA qui parle <vraiment> comme nous",
        "intro": "Une semaine riche en annonces. Voici l'essentiel, sans jargon.",
        "top": {
            "id": "a1", "headline": "Un assistant vocal pour tous", "summary": "Résumé " * 130,
            "why_it_matters": "Parce que vous l'utiliserez peut-être demain.",
            "url": "https://exemple.com/top?x=1&y=2", "source": "Exemple", "related_sources": ["Autre"],
            "original_title": "Titre original top",
        },
        "briefs": [
            {"id": f"b{i}", "headline": f"Brève {i}", "summary": "Texte de brève " * 8,
             "url": f"https://exemple.com/b{i}", "source": "Source", "original_title": f"Titre {i}"}
            for i in range(4)
        ],
        "word": {"term": "Hallucination", "explanation": "Quand l'IA invente."},
        "tool": {"name": "NotebookLM", "description": "Un outil pour vos documents.", "url": "https://notebooklm.google.com/"},
        "conclusion": "À lundi !",
        "ai": {"providers": ["mock"], "calls": 2},
        "generated_at": "2026-11-16T06:00:00+00:00",
    }
