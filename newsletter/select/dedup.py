"""Déduplication : même URL, ou titres très proches (même sujet couvert par plusieurs médias)."""
from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ..models import Article
from ..textutils import title_similarity, title_tokens as tokens

_TRACKING_PREFIXES = ("utm_", "mc_", "fbclid", "gclid", "ref", "cmp", "xtor")


def canonical_url(url: str) -> str:
    """URL normalisée : sans paramètres de tracking, sans fragment, sans « / » final, sans « www. »."""
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith(_TRACKING_PREFIXES)]
    netloc = parts.netloc.lower().removeprefix("www.")
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("https", netloc, path, urlencode(query), ""))


def dedupe(articles: list[Article], threshold: float = 0.5) -> list[Article]:
    """Regroupe les doublons et garde un représentant par sujet.

    Le représentant est l'article de la source au plus fort poids (puis le plus récent).
    Son champ ``coverage`` indique combien de sources différentes couvrent le sujet.
    """
    # 1) Doublons exacts d'URL
    by_url: dict[str, Article] = {}
    for a in articles:
        key = canonical_url(a.url)
        if key not in by_url:
            by_url[key] = a
    unique = list(by_url.values())

    # 2) Regroupement par similarité de titres (union-find simple, O(n²) : n reste petit)
    parent = list(range(len(unique)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    toks = [tokens(a.title) for a in unique]
    for i in range(len(unique)):
        for j in range(i + 1, len(unique)):
            # Pré-filtre rapide : deux titres sans aucun mot commun ne peuvent pas être le même sujet.
            if not (toks[i] & toks[j]):
                continue
            if title_similarity(unique[i].title, unique[j].title) >= threshold:
                parent[find(j)] = find(i)

    groups: dict[int, list[Article]] = {}
    for i, a in enumerate(unique):
        groups.setdefault(find(i), []).append(a)

    result: list[Article] = []
    for members in groups.values():
        members.sort(key=lambda a: (a.weight, a.published), reverse=True)
        rep = members[0]
        sources = sorted({m.source_name for m in members})
        rep.coverage = len(sources)
        rep.related_sources = [s for s in sources if s != rep.source_name]
        result.append(rep)
    return result
