"""Rendu de l'email : HTML compatible clients mail (CSS inline, 600 px, sans JavaScript) + version texte."""
from __future__ import annotations

from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from ..paths import TEMPLATES_DIR

# Balise remplacée par Brevo, au moment de l'envoi, par le lien de désinscription propre à chaque abonné.
BREVO_UNSUBSCRIBE_TAG = "{{ unsubscribe }}"


def make_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "j2"], default_for_string=True),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def preheader(issue: dict[str, Any]) -> str:
    return issue["intro"].split(". ")[0][:140]


def render_email(issue: dict[str, Any], name: str, site_url: str = "", unsubscribe_url: str | None = None) -> tuple[str, str]:
    """Renvoie (html, texte). Par défaut, le lien de désinscription est la balise Brevo."""
    env = make_env()
    archives_url = f"{site_url}/archives/" if site_url else ""
    web_url = f"{site_url}/archives/{issue['week']}/" if site_url else ""
    ctx = {
        "issue": issue,
        "name": name,
        "preheader": preheader(issue),
        "archives_url": archives_url,
        "web_url": web_url,
        "unsubscribe_url": unsubscribe_url or BREVO_UNSUBSCRIBE_TAG,
        "unsubscribe_label": "Se désinscrire",
    }
    html = env.get_template("email/issue.html.j2").render(**ctx)
    text_env = make_env()
    text_env.autoescape = False
    text = text_env.get_template("email/issue.txt.j2").render(**ctx)
    return html, text
