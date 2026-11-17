"""Collecte : interroge toutes les sources, sans jamais planter si l'une d'elles est en panne."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from ..config import Settings
from ..models import Article
from ..textutils import contains_any
from .hackernews import fetch_hackernews
from .http import make_session
from .rss import fetch_rss

log = logging.getLogger(__name__)


def collect_all(settings: Settings, now: datetime | None = None, session=None) -> list[Article]:
    now = now or datetime.now(timezone.utc)
    cfg = settings.collect
    days = int(cfg.get("days", 7))
    timeout = int(cfg.get("timeout", 20))
    excerpt_chars = int(cfg.get("excerpt_chars", 600))
    since = now - timedelta(days=days)
    session = session or make_session(int(cfg.get("retries", 3)))
    topic_kw = settings.select.get("topic_keywords", [])

    all_articles: list[Article] = []
    ok, failed = 0, []
    for source in settings.sources:
        sid = source.get("id", "?")
        try:
            if source.get("type") == "hackernews":
                items = fetch_hackernews(session, source, since, timeout, excerpt_chars)
            else:
                items = fetch_rss(session, source, timeout, excerpt_chars)
        except Exception as exc:
            failed.append(sid)
            log.warning("⚠️  Source « %s » ignorée : %s", sid, exc)
            continue
        # On tolère quelques heures d'avance (fuseaux horaires mal déclarés par certains flux).
        recent = [a for a in items if since <= a.published <= now + timedelta(hours=6)]
        if source.get("filter"):
            recent = [a for a in recent if contains_any(f"{a.title} {a.excerpt}", topic_kw)]
        ok += 1
        log.info("  %-28s %3d articles récents (sur %d)", sid, len(recent), len(items))
        all_articles.extend(recent)

    log.info(
        "Collecte terminée : %d articles, %d sources OK, %d en échec %s",
        len(all_articles), ok, len(failed), failed or "",
    )
    return all_articles
