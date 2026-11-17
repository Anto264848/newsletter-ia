"""Génération du site statique GitHub Pages : landing, archives, une page par numéro, RSS, sitemap."""
from __future__ import annotations

import logging
import shutil
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from ..config import Settings
from ..paths import TEMPLATES_DIR
from ..render import make_env

log = logging.getLogger(__name__)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _issue_datetime(issue: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(issue["date"]).replace(hour=6, tzinfo=timezone.utc)


def build_feed(issues: list[dict[str, Any]], settings: Settings, site_url: str) -> str:
    base = site_url or "."
    items = []
    for i in issues[:30]:
        link = f"{base}/archives/{i['week']}/"
        desc = f"{i['intro']}\n\nL'info de la semaine : {i['top']['headline']} — {i['top']['summary']}"
        items.append(
            "    <item>\n"
            f"      <title>{escape(i['title'])}</title>\n"
            f"      <link>{escape(link)}</link>\n"
            f"      <guid isPermaLink=\"true\">{escape(link)}</guid>\n"
            f"      <pubDate>{format_datetime(_issue_datetime(i))}</pubDate>\n"
            f"      <description>{escape(desc)}</description>\n"
            "    </item>"
        )
    last = format_datetime(_issue_datetime(issues[0])) if issues else format_datetime(datetime.now(timezone.utc))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        "  <channel>\n"
        f"    <title>{escape(settings.name)}</title>\n"
        f"    <link>{escape(base)}/</link>\n"
        f"    <atom:link href=\"{escape(base)}/feed.xml\" rel=\"self\" type=\"application/rss+xml\"/>\n"
        f"    <description>{escape(settings.tagline)}</description>\n"
        "    <language>fr-fr</language>\n"
        f"    <lastBuildDate>{last}</lastBuildDate>\n"
        + "\n".join(items)
        + ("\n" if items else "")
        + "  </channel>\n</rss>\n"
    )


def build_sitemap(issues: list[dict[str, Any]], site_url: str) -> str:
    urls = [(f"{site_url}/", issues[0]["date"] if issues else None),
            (f"{site_url}/archives/", issues[0]["date"] if issues else None)]
    urls += [(f"{site_url}/archives/{i['week']}/", i["date"]) for i in issues]
    body = "\n".join(
        f"  <url><loc>{escape(u)}</loc>" + (f"<lastmod>{d}</lastmod>" if d else "") + "</url>" for u, d in urls
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n</urlset>\n"
    )


def build_site(issues: list[dict[str, Any]], settings: Settings, out_dir: Path) -> list[Path]:
    """Génère tout le site dans ``out_dir``. ``issues`` doit être trié du plus récent au plus ancien."""
    env = make_env()
    site_url = settings.site_url
    common = {
        "name": settings.name,
        "tagline": settings.tagline,
        "form_url": settings.subscribe_form_url,
    }
    written: list[Path] = []

    def page(rel: str, template: str, root: str, canonical_path: str, **ctx: Any) -> None:
        html = env.get_template(template).render(
            **common, root=root, canonical=f"{site_url}{canonical_path}" if site_url else "", **ctx
        )
        _write(out_dir / rel, html)
        written.append(out_dir / rel)

    page(
        "index.html", "site/index.html.j2", "", "/",
        page_title=f"{settings.name} — la newsletter IA & data sans jargon",
        description=settings.tagline,
        latest=issues[0] if issues else None,
        issues=issues,
    )
    page(
        "archives/index.html", "site/archives.html.j2", "../", "/archives/",
        page_title=f"Archives — {settings.name}",
        description=f"Tous les numéros de {settings.name} : {settings.tagline}",
        issues=issues,
    )

    # Pages des numéros (on reconstruit le dossier d'archives pour refléter exactement data/issues/)
    archives_dir = out_dir / "archives"
    if archives_dir.exists():
        for child in archives_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
    for idx, issue in enumerate(issues):
        page(
            f"archives/{issue['week']}/index.html", "site/issue.html.j2", "../../",
            f"/archives/{issue['week']}/",
            page_title=f"{issue['title']} — {settings.name} n°{issue['number']}",
            description=issue["intro"][:300],
            og_type="article",
            issue=issue,
            newer=issues[idx - 1] if idx > 0 else None,
            older=issues[idx + 1] if idx + 1 < len(issues) else None,
        )

    _write(out_dir / "assets" / "style.css", (TEMPLATES_DIR / "site" / "style.css").read_text(encoding="utf-8"))
    _write(out_dir / "feed.xml", build_feed(issues, settings, site_url))
    if site_url:
        _write(out_dir / "sitemap.xml", build_sitemap(issues, site_url))
        _write(out_dir / "robots.txt", f"User-agent: *\nAllow: /\nSitemap: {site_url}/sitemap.xml\n")
    else:
        log.warning("URL du site inconnue : sitemap.xml et robots.txt non générés (définissez site.url).")
        _write(out_dir / "robots.txt", "User-agent: *\nAllow: /\n")
    _write(out_dir / ".nojekyll", "")
    written += [out_dir / "feed.xml", out_dir / "assets" / "style.css"]
    log.info("Site généré dans %s (%d numéros)", out_dir, len(issues))
    return written
