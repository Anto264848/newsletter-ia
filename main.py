#!/usr/bin/env python3
"""Orchestrateur de la newsletter : collecte → sélection → rédaction IA → rendu → envoi → site.

Exemples :
    python main.py --dry-run            # génère le numéro dans output/ sans rien envoyer
    python main.py --dry-run --mock     # idem, sans appeler d'IA (texte de simulation)
    python main.py                      # vrai run : envoie aux abonnés et met à jour docs/ et data/
    python main.py --site-only          # régénère seulement le site à partir de data/issues/
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime, timezone

from newsletter.collect import collect_all
from newsletter.config import Secrets, load_settings
from newsletter.paths import DOCS_DIR, OUTPUT_DIR
from newsletter.render import preheader, render_email
from newsletter.select import shortlist
from newsletter.send import BrevoClient, BrevoError, send_issue
from newsletter.site import build_site
from newsletter.state import History, IssueStore, SendLock, iso_week_id
from newsletter.write import NotEnoughContent, issue_topics, issue_urls, write_issue
from newsletter.write.llm import LLMError, LLMRouter, build_router
from newsletter.write.mock import MockProvider

log = logging.getLogger("newsletter")

EXIT_OK, EXIT_FAIL, EXIT_CONFIG = 0, 1, 2


def setup_logging(verbose: bool = False) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # emojis et accents lisibles partout (Windows inclus)
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def step_summary(markdown: str) -> None:
    """Résumé affiché sur la page du run GitHub Actions."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(markdown + "\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="génère le numéro dans output/ sans l'envoyer")
    p.add_argument("--mock", action="store_true", help="n'appelle pas d'IA (texte de simulation)")
    p.add_argument("--force", action="store_true", help="ignore le verrou anti double envoi de la semaine")
    p.add_argument("--site-only", action="store_true", help="régénère uniquement le site (docs/)")
    p.add_argument("--date", help="date de référence AAAA-MM-JJ (tests)")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def run(args: argparse.Namespace) -> int:
    settings = load_settings()
    secrets = Secrets.from_env()
    store = IssueStore()

    if args.site_only:
        build_site(store.all(), settings, DOCS_DIR)
        return EXIT_OK

    now = datetime.now(timezone.utc)
    if args.date:
        d = date.fromisoformat(args.date)
        now = datetime(d.year, d.month, d.day, 6, 0, tzinfo=timezone.utc)
    today = now.date()
    week_id = iso_week_id(today)
    lock = SendLock(week_id)
    mode = "DRY-RUN (aucun envoi)" if args.dry_run else "ENVOI RÉEL"
    log.info("=== %s — numéro de la semaine %s — %s ===", settings.name, week_id, mode)

    # 1. Garde-fous avant de consommer du quota
    if not args.dry_run:
        if lock.exists() and not args.force:
            info = lock.read()
            log.info("✅ Le numéro %s a déjà été envoyé le %s : rien à faire.", week_id, info.get("sent_at"))
            step_summary(f"Numéro {week_id} déjà envoyé ({info.get('sent_at')}) : rien à faire.")
            return EXIT_OK
        missing = secrets.missing_for_send()
        if missing:
            log.error("Secrets manquants pour l'envoi : %s (voir SETUP.md)", ", ".join(missing))
            return EXIT_CONFIG
        if not secrets.brevo_list_id.isdigit():
            log.error("BREVO_LIST_ID doit être un nombre (ex. 2), reçu : %r", secrets.brevo_list_id)
            return EXIT_CONFIG

    router: LLMRouter | None = None if args.mock else build_router(settings, secrets)
    if router is None:
        if not args.dry_run:
            log.error("Aucune clé IA (GEMINI_API_KEY ou FALLBACK_API_KEY) : impossible de rédiger le numéro.")
            return EXIT_CONFIG
        log.warning("⚠️  MODE SIMULATION : aucune IA appelée, les textes sont factices (--mock ou pas de clé).")
        router = LLMRouter([MockProvider()], max_calls=6)

    # 2. Collecte et sélection
    history = History()
    articles = collect_all(settings, now=now)
    candidates = shortlist(articles, settings, history, now=now)

    # 3. Rédaction
    try:
        issue = write_issue(router, candidates, settings, history, store.next_number(), week_id, today)
    except NotEnoughContent as exc:
        log.error("❌ Pas assez d'actus valides cette semaine (%s) : aucun envoi.", exc)
        step_summary(f"## ❌ Numéro {week_id} non envoyé\n\nPas assez d'actus valides : {exc}")
        return EXIT_FAIL
    except LLMError as exc:
        log.error("❌ L'IA n'a pas pu rédiger le numéro : %s", exc)
        step_summary(f"## ❌ Numéro {week_id} non envoyé\n\nÉchec de l'IA : {exc}")
        return EXIT_FAIL
    if args.mock or router.used == ["mock"]:
        issue["ai"]["mock"] = True
    log.info("Numéro rédigé avec %d appel(s) IA (%s)", router.calls, ", ".join(router.used))

    # 4. Rendu (toujours écrit dans output/ pour inspection)
    html, text = render_email(issue, settings.name, settings.site_url)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "issue.html").write_text(html, encoding="utf-8")
    (OUTPUT_DIR / "issue.txt").write_text(text, encoding="utf-8")
    (OUTPUT_DIR / "issue.json").write_text(json.dumps(issue, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Aperçu : %s", OUTPUT_DIR / "issue.html")

    summary = (
        f"## {'🧪 Dry-run' if args.dry_run else '📬 Envoi'} — n°{issue['number']} ({week_id})\n\n"
        f"**{issue['title']}**\n\n- Info de la semaine : {issue['top']['headline']} ({issue['top']['source']})\n"
        + "".join(f"- En bref : {b['headline']} ({b['source']})\n" for b in issue["briefs"])
        + f"- Mot : {issue['word']['term']}\n- Outil : {issue['tool']['name']}\n"
        f"- IA : {', '.join(router.used)} ({router.calls} appels)\n"
    )

    if args.dry_run:
        preview = [i for i in store.all() if i["week"] != week_id]
        build_site([issue, *preview], settings, OUTPUT_DIR / "site")
        log.info("✅ Dry-run terminé : rien n'a été envoyé. Ouvrez output/issue.html et output/site/index.html")
        step_summary(summary)
        return EXIT_OK

    # 5. Envoi
    client = BrevoClient(secrets.brevo_api_key)
    try:
        if args.force:
            log.warning("--force : vérification anti-doublon ignorée.")
        campaign_id = send_issue(
            client if not args.force else _ForceClient(client),
            issue, html,
            newsletter_name=settings.name,
            sender_name=settings.sender_name,
            sender_email=secrets.brevo_sender_email,
            list_id=int(secrets.brevo_list_id),
            preview_text=preheader(issue),
        )
    except BrevoError as exc:
        log.error("❌ Envoi impossible : %s", exc)
        step_summary(f"## ❌ Envoi du numéro {week_id} impossible\n\n{exc}")
        return EXIT_FAIL

    # 6. Verrou + historique + archives (immédiatement après l'envoi)
    if args.force and lock.exists():
        lock.path.unlink()
    lock.acquire({"number": issue["number"], "campaign_id": campaign_id, "title": issue["title"]})
    history.add_issue(issue_urls(issue), issue_topics(issue), issue["word"]["term"], issue["tool"]["name"])
    history.save()
    store.save(issue)
    build_site(store.all(), settings, DOCS_DIR)
    log.info("✅ Numéro %d envoyé et archivé.", issue["number"])
    step_summary(summary + f"\nCampagne Brevo : {campaign_id}\n")
    return EXIT_OK


class _ForceClient:
    """Enveloppe qui désactive la détection de doublon Brevo (option --force uniquement)."""

    def __init__(self, inner: BrevoClient):
        self._inner = inner

    def already_sent(self, marker: str):
        return None

    def __getattr__(self, item):
        return getattr(self._inner, item)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    setup_logging(args.verbose)
    try:
        return run(args)
    except Exception:  # dernier filet : log lisible + code d'erreur (GitHub envoie alors un email)
        log.exception("Erreur inattendue")
        return EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
