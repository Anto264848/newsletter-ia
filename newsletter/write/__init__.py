"""Rédaction : 2 appels IA par numéro (1. classement des candidats, 2. rédaction complète en JSON).

Les liens ne viennent JAMAIS de l'IA : chaque texte est rattaché à son article d'origine par identifiant.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from string import Template
from typing import Any

from ..config import Settings
from ..models import Article, IssueContent, SelectionResult
from ..paths import PROMPTS_DIR
from ..state import History
from ..textutils import normalize, word_count
from .llm import LLMError, LLMRouter

log = logging.getLogger(__name__)

FR_MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
             "septembre", "octobre", "novembre", "décembre"]


class NotEnoughContent(Exception):
    """Pas assez d'actus valides pour publier un numéro."""


def fr_date(d: date) -> str:
    return f"{d.day} {FR_MONTHS[d.month - 1]} {d.year}"


def load_prompt(name: str, **values: Any) -> str:
    text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    return Template(text).safe_substitute(**{k: str(v) for k, v in values.items()})


def _article_block(a: Article, include_coverage: bool = True) -> str:
    cov = f" (sujet couvert par {a.coverage} médias)" if include_coverage and a.coverage > 1 else ""
    return (
        f"- id: {a.id}\n"
        f"  titre: {a.title}\n"
        f"  source: {a.source_name}{cov}\n"
        f"  date: {a.published.date().isoformat()}\n"
        f"  langue: {a.lang}\n"
        f"  extrait: {a.excerpt or '(pas d’extrait)'}"
    )


def pick_tool(settings: Settings, history: History) -> dict[str, Any] | None:
    for tool in settings.tools:
        if not history.seen_tool(tool["name"]):
            return tool
    log.warning(
        "⚠️  Tous les outils de config/tools.yaml ont déjà été présentés : l'IA va en proposer un "
        "(sans lien). Pensez à compléter config/tools.yaml."
    )
    return None


def select_stories(router: LLMRouter, candidates: list[Article], settings: Settings, system: str) -> tuple[Article, list[Article]]:
    """Appel IA n°1 : choisit l'info de la semaine et les brèves. Repli sur le score si l'IA échoue."""
    cfg = settings.select
    bmin, bmax = int(cfg.get("briefs_min", 4)), int(cfg.get("briefs_max", 6))
    by_id = {a.id: a for a in candidates}
    needed_briefs = max(1, min(bmin, len(candidates) - 1))

    def check(res: SelectionResult) -> None:
        if res.top not in by_id:
            raise ValueError(f"« top » doit être un des identifiants fournis (reçu {res.top!r})")
        unknown = [b for b in res.briefs if b not in by_id]
        if unknown:
            raise ValueError(f"identifiants inconnus dans « briefs » : {unknown}")
        valid = [b for b in res.briefs if b != res.top]
        if len(valid) < needed_briefs:
            raise ValueError(f"il faut au moins {needed_briefs} brèves différentes de « top »")

    prompt = load_prompt(
        "select",
        count=len(candidates),
        briefs_min=bmin,
        briefs_max=bmax,
        candidates="\n".join(_article_block(a) for a in candidates),
    )
    try:
        res = router.generate_json(system, prompt, SelectionResult, check)
        top = by_id[res.top]
        briefs = [by_id[b] for b in res.briefs if b != res.top][:bmax]
        log.info("Sélection par l'IA : top=%s, %d brèves", top.id, len(briefs))
    except LLMError as exc:
        log.warning("Sélection IA impossible (%s) → repli sur le classement par score.", exc)
        top, briefs = candidates[0], candidates[1 : 1 + bmax]
    return top, briefs


def write_issue(
    router: LLMRouter,
    candidates: list[Article],
    settings: Settings,
    history: History,
    issue_number: int,
    week_id: str,
    today: date,
) -> dict[str, Any]:
    """Produit le contenu complet d'un numéro (dict prêt à rendre). Lève NotEnoughContent si besoin."""
    min_items = int(settings.select.get("min_valid_items", 4))
    if len(candidates) < min_items:
        raise NotEnoughContent(f"seulement {len(candidates)} actus candidates (minimum {min_items})")

    system = load_prompt("system", newsletter_name=settings.name)
    top, briefs = select_stories(router, candidates, settings, system)
    selected = {a.id: a for a in [top, *briefs]}

    tool = pick_tool(settings, history)
    if tool:
        tool_instruction = (
            f"Présente l'outil « {tool['name']} ». Informations fiables à utiliser (n'invente rien "
            f"d'autre) : {tool.get('facts', '')} Garde exactement ce nom dans « name »."
        )
    else:
        tool_instruction = (
            "Choisis un outil d'IA gratuit, grand public et très connu, qui n'est PAS dans cette liste : "
            f"{json.dumps(history.tools, ensure_ascii=False)}. Ne donne pas de lien."
        )

    brief_ids = [b.id for b in briefs]

    def check(c: IssueContent) -> None:
        if c.top_story.id != top.id:
            raise ValueError(f"top_story.id doit valoir {top.id!r}")
        got = [b.id for b in c.briefs]
        unknown = [i for i in got if i not in brief_ids]
        if unknown:
            raise ValueError(f"identifiants de brèves inconnus : {unknown}. Utilise exactement : {brief_ids}")
        if len(set(got)) + 1 < min_items:
            raise ValueError(f"il faut une brève pour chacun de ces identifiants : {brief_ids}")
        if history.seen_word(c.word_of_the_week.term):
            raise ValueError(f"le mot « {c.word_of_the_week.term} » a déjà été expliqué, choisis-en un autre")
        if not tool and history.seen_tool(c.tool_of_the_week.name):
            raise ValueError(f"l'outil « {c.tool_of_the_week.name} » a déjà été présenté")

    prompt = load_prompt(
        "write",
        issue_number=issue_number,
        week_label=f"du {fr_date(today)}",
        top_id=top.id,
        articles="\n\n".join(
            ("### INFO DE LA SEMAINE\n" if a.id == top.id else "### BRÈVE\n") + _article_block(a, False)
            for a in selected.values()
        ),
        brief_ids=json.dumps(brief_ids),
        banned_words=json.dumps(history.words, ensure_ascii=False),
        tool_instruction=tool_instruction,
    )
    content = router.generate_json(system, prompt, IssueContent, check)
    _warn_lengths(content)

    # Association texte ↔ article par identifiant : les URL viennent uniquement de la collecte.
    seen: set[str] = set()
    brief_items = []
    for b in content.briefs:
        if b.id in seen or b.id not in selected or b.id == top.id:
            continue
        seen.add(b.id)
        art = selected[b.id]
        brief_items.append({
            "id": art.id, "headline": b.headline, "summary": b.summary,
            "url": art.url, "source": art.source_name, "original_title": art.title,
        })

    if 1 + len(brief_items) < min_items:
        raise NotEnoughContent(f"seulement {1 + len(brief_items)} actus valides après rédaction")

    return {
        "number": issue_number,
        "week": week_id,
        "date": today.isoformat(),
        "date_label": fr_date(today),
        "title": content.title,
        "intro": content.intro,
        "top": {
            "id": top.id,
            "headline": content.top_story.headline,
            "summary": content.top_story.summary,
            "why_it_matters": content.top_story.why_it_matters,
            "url": top.url,
            "source": top.source_name,
            "related_sources": top.related_sources,
            "original_title": top.title,
        },
        "briefs": brief_items,
        "word": {"term": content.word_of_the_week.term, "explanation": content.word_of_the_week.explanation},
        "tool": {
            "name": tool["name"] if tool else content.tool_of_the_week.name,
            "description": content.tool_of_the_week.description,
            "url": tool["url"] if tool else None,
        },
        "conclusion": content.conclusion,
        "ai": {"providers": router.used, "calls": router.calls},
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _warn_lengths(c: IssueContent) -> None:
    """Contrôle souple des longueurs demandées (log seulement, n'empêche pas l'envoi)."""
    n = word_count(c.top_story.summary)
    if not 100 <= n <= 220:
        log.warning("Longueur de l'info de la semaine hors cible : %d mots (cible 120-180)", n)
    for b in c.briefs:
        n = word_count(b.summary)
        if not 30 <= n <= 90:
            log.warning("Brève %s : %d mots (cible 40-70)", b.id, n)


def issue_topics(issue: dict[str, Any]) -> list[str]:
    return [issue["top"]["original_title"], *[b["original_title"] for b in issue["briefs"]]]


def issue_urls(issue: dict[str, Any]) -> list[str]:
    return [issue["top"]["url"], *[b["url"] for b in issue["briefs"]]]


__all__ = ["write_issue", "NotEnoughContent", "issue_topics", "issue_urls", "fr_date", "normalize"]
