"""Score des articles : récence, couverture multi-sources, poids de la source, mots-clés grand public."""
from __future__ import annotations

import math
from datetime import datetime, timezone

from ..models import Article
from ..textutils import count_matches


def score_article(article: Article, now: datetime, keywords: list[str], window_days: int = 7) -> float:
    age_days = max(0.0, (now - article.published).total_seconds() / 86400)
    recency = max(0.0, 1.0 - age_days / max(window_days, 1))          # 0 à 1
    coverage = math.log2(1 + article.coverage)                          # 1 source = 1, 3 sources = 2
    kw = min(count_matches(f"{article.title} {article.excerpt}", keywords), 4) * 0.25  # 0 à 1
    return round(article.weight * (1.0 + recency + 1.5 * coverage + kw), 4)


def rank(articles: list[Article], keywords: list[str], now: datetime | None = None, window_days: int = 7) -> list[Article]:
    now = now or datetime.now(timezone.utc)
    for a in articles:
        a.score = score_article(a, now, keywords, window_days)
    return sorted(articles, key=lambda a: a.score, reverse=True)
