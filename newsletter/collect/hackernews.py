"""Hacker News via l'API publique Algolia (gratuite, sans authentification)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from ..models import Article
from ..textutils import strip_html, truncate

log = logging.getLogger(__name__)

API = "https://hn.algolia.com/api/v1/search"


def parse_hits(payload: dict[str, Any], source: dict[str, Any], excerpt_chars: int = 600) -> list[Article]:
    articles = []
    for hit in payload.get("hits", []):
        title = strip_html(hit.get("title") or "")
        url = hit.get("url") or ""
        if not title or not url.startswith("http"):
            continue  # « Ask HN » & co : pas d'article source à résumer
        ts = hit.get("created_at_i")
        if not ts:
            continue
        points = hit.get("points") or 0
        comments = hit.get("num_comments") or 0
        excerpt = strip_html(hit.get("story_text") or "") or (
            f"Article partagé sur Hacker News ({points} points, {comments} commentaires)."
        )
        articles.append(
            Article(
                title=title,
                url=url,
                source_id=source["id"],
                source_name=source.get("name", "Hacker News"),
                published=datetime.fromtimestamp(int(ts), tz=timezone.utc),
                excerpt=truncate(excerpt, excerpt_chars),
                lang=source.get("lang", "en"),
                weight=float(source.get("weight", 1.0)),
            )
        )
    return articles


def fetch_hackernews(
    session, source: dict[str, Any], since: datetime, timeout: int, excerpt_chars: int
) -> list[Article]:
    min_points = int(source.get("min_points", 100))
    seen: dict[str, Article] = {}
    errors = 0
    queries = source.get("queries", ["AI"])
    for query in queries:
        params = {
            "query": query,
            "tags": "story",
            "numericFilters": f"created_at_i>{int(since.timestamp())},points>={min_points}",
            "hitsPerPage": 30,
        }
        try:
            resp = session.get(API, params=params, timeout=timeout)
            resp.raise_for_status()
            for a in parse_hits(resp.json(), source, excerpt_chars):
                seen.setdefault(a.url, a)
        except Exception as exc:  # une requête ratée n'annule pas les autres
            errors += 1
            log.warning("Hacker News : requête « %s » en échec (%s)", query, exc)
    if errors == len(queries):
        raise RuntimeError("toutes les requêtes Hacker News ont échoué")
    return list(seen.values())
