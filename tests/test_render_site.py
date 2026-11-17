from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from conftest import sample_issue

from newsletter.render import BREVO_UNSUBSCRIBE_TAG, render_email
from newsletter.site import build_site


def test_email_html_is_mail_client_friendly():
    html, text = render_email(sample_issue(), "L'IA sans jargon", "https://ex.github.io/nl")
    assert "<script" not in html.lower()
    assert 'width="600"' in html and "max-width:600px" in html
    # Lien de désinscription Brevo, archives et version en ligne
    assert f'href="{BREVO_UNSUBSCRIBE_TAG}"' in html
    assert "https://ex.github.io/nl/archives/" in html
    assert "https://ex.github.io/nl/archives/2026-W47/" in html
    # Échappement HTML du contenu généré, liens d'origine conservés
    assert "&lt;vraiment&gt;" in html
    assert 'href="https://exemple.com/top?x=1&amp;y=2"' in html
    for i in range(4):
        assert f"https://exemple.com/b{i}" in html
    # Mention IA dans le footer
    assert "intelligence artificielle" in html
    # Les styles sont inline (chaque balise de texte porte un style)
    assert len(re.findall(r'<p style="', html)) > 10


def test_email_text_version():
    _, text = render_email(sample_issue(), "L'IA sans jargon", "https://ex.github.io/nl")
    assert "<" not in text.replace("<vraiment>", "")
    assert "L'INFO DE LA SEMAINE" in text and "EN BREF" in text
    assert "https://exemple.com/top?x=1&y=2" in text
    assert BREVO_UNSUBSCRIBE_TAG in text


def test_build_site(settings, tmp_path):
    settings.raw["site"]["subscribe_form_url"] = "https://form.sibforms.test/serve/ABC"
    issues = [sample_issue(2, "2026-W48"), sample_issue(1, "2026-W47")]
    # Une page obsolète doit disparaître lors de la reconstruction
    (tmp_path / "archives" / "2020-W01").mkdir(parents=True)
    build_site(issues, settings, tmp_path)

    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "L&#39;IA sans jargon" in index or "L'IA sans jargon" in index
    assert 'src="https://form.sibforms.test/serve/ABC"' in index
    assert 'property="og:title"' in index and 'rel="canonical"' in index
    assert "archives/2026-W48/" in index

    assert (tmp_path / "archives" / "index.html").exists()
    page = (tmp_path / "archives" / "2026-W47" / "index.html").read_text(encoding="utf-8")
    assert "https://exemple.com/b3" in page and "../../assets/style.css" in page
    assert not (tmp_path / "archives" / "2020-W01").exists()
    assert (tmp_path / ".nojekyll").exists() and (tmp_path / "assets" / "style.css").exists()

    feed = ET.parse(tmp_path / "feed.xml").getroot()
    items = feed.findall("./channel/item")
    assert len(items) == 2
    assert items[0].find("link").text == "https://exemple.github.io/newsletter/archives/2026-W48/"

    sitemap = ET.parse(tmp_path / "sitemap.xml").getroot()
    assert len(sitemap) == 4
    assert "Sitemap: https://exemple.github.io/newsletter/sitemap.xml" in (tmp_path / "robots.txt").read_text()


def test_build_site_without_issues_or_form(settings, tmp_path):
    settings.raw["site"]["subscribe_form_url"] = ""
    build_site([], settings, tmp_path)
    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "arrive très bientôt" in index
    ET.parse(tmp_path / "feed.xml")


def test_site_url_from_github_repository(settings, monkeypatch):
    settings.raw["site"]["url"] = ""
    monkeypatch.setenv("GITHUB_REPOSITORY", "Camille/ma-newsletter")
    assert settings.site_url == "https://camille.github.io/ma-newsletter"
    monkeypatch.setenv("GITHUB_REPOSITORY", "camille/camille.github.io")
    assert settings.site_url == "https://camille.github.io"
