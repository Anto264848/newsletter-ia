"""Sélection : déduplication, exclusion de l'historique, score, puis top N candidats pour l'IA."""
from __future__ import annotations

import logging
from datetime import datetime

from ..config import Settings
from ..models import Article
from ..state import History
from .dedup import canonical_url, dedupe
from .scoring import rank

log = logging.getLogger(__name__)

__all__ = ["shortlist", "dedupe", "rank", "canonical_url"]


def shortlist(articles: list[Article], settings: Settings, history: History, now: datetime | None = None) -> list[Article]:
    cfg = settings.select
    threshold = float(cfg.get("similarity_threshold", 0.5))

    fresh = [
        a for a in articles
        if not history.seen_url(a.url) and not history.seen_url(canonical_url(a.url))
        and not history.seen_topic(a.title, max(threshold, 0.6))
    ]
    log.info("Historique : %d articles déjà traités écartés", len(articles) - len(fresh))

    unique = dedupe(fresh, threshold)
    log.info("Déduplication : %d sujets distincts (sur %d articles)", len(unique), len(fresh))

    ranked = rank(unique, cfg.get("general_public_keywords", []), now, int(settings.collect.get("days", 7)))
    top = ranked[: int(cfg.get("candidates_for_ai", 25))]
    for a in top[:10]:
        log.info("  %.2f  [%s] %s (x%d)", a.score, a.source_name, a.title[:90], a.coverage)
    return top
