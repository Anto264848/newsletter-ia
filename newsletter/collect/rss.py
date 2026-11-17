"""Lecture des flux RSS / Atom."""
from __future__ import annotations

import calendar
import logging
from datetime import datetime, timezone
from typing import Any

import feedparser

from ..models import Article
from ..textutils import strip_html, truncate

log = logging.getLogger(__name__)


def _entry_date(entry: Any) -> datetime | None:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        st = entry.get(key)
        if st:
            return datetime.fromtimestamp(calendar.timegm(st), tz=timezone.utc)
    return None


def parse_feed(content: bytes, source: dict[str, Any], excerpt_chars: int = 600) -> list[Article]:
    """Transforme le contenu brut d'un flux en articles. Ne fait aucun appel réseau."""
    parsed = feedparser.parse(content)
    if not parsed.entries:
        if parsed.bozo:
            raise ValueError(f"flux illisible : {parsed.get('bozo_exception')}")
        return []
    articles: list[Article] = []
    for entry in parsed.entries:
        title = strip_html(entry.get("title", ""))
        url = (entry.get("link") or "").strip()
        published = _entry_date(entry)
        if not title or not url.startswith("http") or published is None:
            continue
        summary = entry.get("summary") or ""
        if not summary and entry.get("content"):
            summary = entry["content"][0].get("value", "")
        articles.append(
            Article(
                title=title,
                url=url,
                source_id=source["id"],
                source_name=source.get("name", source["id"]),
                published=published,
                excerpt=truncate(strip_html(summary), excerpt_chars),
                lang=source.get("lang", "en"),
                weight=float(source.get("weight", 1.0)),
            )
        )
    return articles


def fetch_rss(session, source: dict[str, Any], timeout: int, excerpt_chars: int) -> list[Article]:
    resp = session.get(source["url"], timeout=timeout)
    resp.raise_for_status()
    return parse_feed(resp.content, source, excerpt_chars)
