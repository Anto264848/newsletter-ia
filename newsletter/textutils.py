"""Petites fonctions de traitement de texte (sans dépendance lourde)."""
from __future__ import annotations

import html
import re
import unicodedata
from difflib import SequenceMatcher

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

STOPWORDS = {
    # français
    "le", "la", "les", "un", "une", "des", "de", "du", "d", "l", "et", "ou", "a", "au", "aux", "en",
    "pour", "par", "sur", "dans", "avec", "sans", "ce", "cette", "ces", "son", "sa", "ses", "qui",
    "que", "quoi", "est", "sont", "plus", "moins", "pas", "ne", "se", "s", "il", "elle", "ils", "elles",
    "on", "nous", "vous", "leur", "leurs", "comme", "mais", "tout", "tous", "fait", "va", "vont",
    # anglais
    "the", "an", "and", "or", "of", "to", "in", "on", "for", "with", "by", "at", "from", "is", "are",
    "was", "be", "its", "it", "this", "that", "as", "new", "how", "why", "what", "now", "your", "you",
    "can", "will", "has", "have", "into", "about", "after", "over", "just", "says", "say", "s",
}


def strip_html(text: str) -> str:
    """Retire les balises HTML et décode les entités."""
    if not text:
        return ""
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    return _WS_RE.sub(" ", text).strip()


def truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rsplit(" ", 1)[0]
    return cut.rstrip(" ,.;:") + "…"


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")


def normalize(text: str) -> str:
    """Minuscules, sans accents, sans ponctuation, espaces simples."""
    text = strip_accents(text.lower())
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return text.strip()


def tokens(text: str) -> set[str]:
    return {t for t in normalize(text).split() if t not in STOPWORDS and len(t) > 1}


# Mots trop fréquents dans les titres tech pour indiquer un même sujet.
GENERIC_TITLE_WORDS = {
    "ai", "ia", "introducing", "announcing", "announces", "announce", "launches", "launch", "lance",
    "devoile", "annonce", "nouveau", "nouvelle", "nouvelles", "via", "here", "more", "today",
}


def title_tokens(text: str) -> set[str]:
    return tokens(text) - GENERIC_TITLE_WORDS


def title_similarity(a: str, b: str) -> float:
    """Similarité entre deux titres (0 à 1), basée sur les mots significatifs en commun.

    - Jaccard des mots ;
    - chevauchement relatif au plus court titre (capte « titre court inclus dans un titre long ») ;
    - ratio de séquence de caractères, retenu seulement s'il est très élevé (fautes, ponctuation).
    """
    ta, tb = title_tokens(a), title_tokens(b)
    if not ta or not tb:
        return 0.0
    common = len(ta & tb)
    jaccard = common / len(ta | tb)
    shortest = min(len(ta), len(tb))
    # Chevauchement compté si au moins 3 mots communs (ou 2 pour un titre très court).
    overlap = common / shortest * 0.85 if common >= 3 or (common >= 2 and shortest <= 3) else 0.0
    seq = SequenceMatcher(None, normalize(a), normalize(b)).ratio()
    return max(jaccard, overlap, seq if seq >= 0.85 else 0.0)


def keyword_text(text: str) -> str:
    """Texte préparé pour la recherche de mots-clés : minuscules, ponctuation -> espaces, bordé d'espaces."""
    text = text.lower().replace("’", "'")
    text = re.sub(r"[^\w']+", " ", text)
    return f" {text} "


def contains_any(text: str, keywords: list[str]) -> bool:
    hay = keyword_text(text)
    return any(_kw_in(hay, k) for k in keywords)


def count_matches(text: str, keywords: list[str]) -> int:
    hay = keyword_text(text)
    return sum(1 for k in keywords if _kw_in(hay, k))


def _kw_in(hay: str, keyword: str) -> bool:
    """``hay`` vient de keyword_text(). Un mot-clé entouré d'espaces (« ia ») = mot entier."""
    core = keyword_text(keyword).strip()
    if not core:
        return False
    if keyword.startswith(" ") or keyword.endswith(" "):
        return f" {core} " in hay
    return core in hay


def word_count(text: str) -> int:
    return len(re.findall(r"\w+(?:['’-]\w+)*", text))
