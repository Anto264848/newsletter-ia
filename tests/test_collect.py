from __future__ import annotations

from conftest import FIXTURES, NOW, FakeResponse, FakeSession

from newsletter.collect import collect_all
from newsletter.collect.hackernews import parse_hits
from newsletter.collect.rss import parse_feed

SRC = {"id": "ex", "name": "Exemple", "lang": "fr", "weight": 1.2}


def test_parse_rss_strips_html_and_skips_undated():
    arts = parse_feed((FIXTURES / "sample_rss.xml").read_bytes(), SRC)
    titles = [a.title for a in arts]
    assert "Article sans date" not in titles
    assert len(arts) == 3
    first = arts[0]
    assert first.title.startswith("OpenAI lance")
    assert first.excerpt == "L'entreprise OpenAI a présenté un assistant vocal & gratuit."
    assert first.source_name == "Exemple" and first.weight == 1.2 and first.lang == "fr"
    assert first.published.tzinfo is not None
    assert first.id.startswith("a") and len(first.id) == 9


def test_parse_atom_uses_content_and_updated():
    arts = parse_feed((FIXTURES / "sample_atom.xml").read_bytes(), {"id": "atom"})
    assert [a.url for a in arts] == ["https://example-ai.com/gemini-search", "https://example-ai.com/datacenters"]
    assert "electricity" in arts[1].excerpt
    assert arts[1].published.day == 13


def test_parse_hn_skips_ask_hn():
    import json

    payload = json.loads((FIXTURES / "hn_search.json").read_text())
    arts = parse_hits(payload, {"id": "hackernews", "name": "Hacker News"})
    assert [a.url for a in arts] == ["https://example.org/llm", "https://example.org/privacy"]
    assert "420 points" in arts[0].excerpt
    assert arts[1].excerpt == "Discussion about privacy ."


def test_collect_all_survives_broken_source_and_filters(settings):
    settings.sources = [
        {"id": "ok_rss", "name": "OK", "type": "rss", "url": "https://ok.test/feed", "lang": "fr"},
        {"id": "broken", "name": "Cassé", "type": "rss", "url": "https://broken.test/feed"},
        {"id": "garbage", "name": "Pas un flux", "type": "rss", "url": "https://garbage.test/feed"},
        {"id": "generic", "name": "Généraliste", "type": "rss", "url": "https://generic.test/feed", "filter": True},
        {"id": "hackernews", "name": "Hacker News", "type": "hackernews", "queries": ["AI"]},
    ]
    session = FakeSession({
        "https://ok.test": FakeResponse(200, (FIXTURES / "sample_atom.xml").read_bytes()),
        "https://broken.test": ConnectionError("timeout"),
        "https://garbage.test": FakeResponse(500, b"oops"),
        "https://generic.test": FakeResponse(200, (FIXTURES / "sample_rss.xml").read_bytes()),
        "https://hn.algolia.com": FakeResponse(200, (FIXTURES / "hn_search.json").read_bytes()),
    })
    arts = collect_all(settings, now=NOW, session=session)
    by_source = {}
    for a in arts:
        by_source.setdefault(a.source_id, []).append(a.title)
    # Les sources en panne sont ignorées sans faire planter la collecte
    assert "broken" not in by_source and "garbage" not in by_source
    assert len(by_source["ok_rss"]) == 2
    # Flux généraliste : seul l'article qui parle d'IA est gardé ; l'article trop ancien est exclu
    assert by_source["generic"] == ["OpenAI lance un nouvel assistant vocal pour les smartphones"]
    assert len(by_source["hackernews"]) == 2
    # Le filtre de date côté API Hacker News est bien envoyé
    hn_call = [c for c in session.calls if "algolia" in c[1]][0]
    assert "created_at_i>" in hn_call[2]["params"]["numericFilters"]
