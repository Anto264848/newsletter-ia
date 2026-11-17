"""Verrou anti double envoi (local + vérification côté Brevo) et orchestration de main.py."""
from __future__ import annotations

import functools
from datetime import date

import pytest
from conftest import FakeResponse, FakeSession, make_article, sample_issue

import main
from newsletter.send.brevo import BrevoClient, BrevoError, send_issue
from newsletter.state import History, IssueStore, SendLock, iso_week_id


def test_iso_week_id():
    assert iso_week_id(date(2026, 11, 16)) == "2026-W47"
    assert iso_week_id(date(2027, 1, 1)) == "2026-W53"


def test_lock_prevents_second_acquire(tmp_path):
    lock = SendLock("2026-W47", tmp_path)
    assert not lock.exists()
    lock.acquire({"number": 1})
    assert lock.exists() and lock.read()["number"] == 1
    with pytest.raises(RuntimeError):
        SendLock("2026-W47", tmp_path).acquire({"number": 1})
    assert not SendLock("2026-W48", tmp_path).exists()


def test_history_and_store_roundtrip(tmp_path):
    h = History(tmp_path)
    h.add_issue(["https://a.com/x"], ["Un titre"], "Hallucination", "NotebookLM")
    h.save()
    h2 = History(tmp_path)
    assert h2.seen_url("https://a.com/x/") and h2.seen_word("hallucination") and h2.seen_tool("notebooklm")
    store = IssueStore(tmp_path)
    assert store.next_number() == 1
    store.save(sample_issue(1, "2026-W47"))
    store.save(sample_issue(2, "2026-W48"))
    assert store.next_number() == 3 and [i["number"] for i in store.all()] == [2, 1]


def _brevo(campaigns):
    """Client Brevo branché sur une fausse API qui connaît la liste ``campaigns``."""
    session = FakeSession({})

    def request(method, url, **kw):
        session.calls.append((method, url, kw))
        if method == "GET":
            return FakeResponse(200, json_data={"campaigns": campaigns})
        if method == "POST" and url.endswith("/emailCampaigns"):
            return FakeResponse(201, json_data={"id": 42})
        if method == "POST" and url.endswith("/sendNow"):
            return FakeResponse(204, b"")
        if method == "DELETE":
            return FakeResponse(204, b"")
        raise AssertionError(url)

    session.request = request
    return BrevoClient("KEY", session=session, sleep=lambda s: None), session


def test_brevo_send_creates_and_sends():
    client, session = _brevo([{"id": 7, "name": "Autre [2026-W46]", "status": "sent"},
                              {"id": 8, "name": "NL n°1 [2026-W47]", "status": "draft"}])
    cid = send_issue(client, sample_issue(), "<html>contenu</html>", newsletter_name="NL", sender_name="NL",
                     sender_email="moi@exemple.fr", list_id=3, preview_text="pré")
    assert cid == 42
    calls = [(m, u.rsplit("/", 1)[-1]) for m, u, _ in session.calls]
    assert ("DELETE", "8") in calls  # brouillon d'un essai précédent nettoyé
    assert calls[-1] == ("POST", "sendNow")
    create = [kw for m, u, kw in session.calls if m == "POST" and u.endswith("/emailCampaigns")][0]["json"]
    assert create["recipients"] == {"listIds": [3]}
    assert create["name"].endswith("[2026-W47]")
    assert create["sender"] == {"name": "NL", "email": "moi@exemple.fr"}
    assert session.calls[0][2]["headers"]["api-key"] == "KEY"


def test_brevo_refuses_if_week_already_sent():
    client, session = _brevo([{"id": 9, "name": "NL n°1 [2026-W47]", "status": "sent"}])
    with pytest.raises(BrevoError):
        send_issue(client, sample_issue(), "<html>x</html>", newsletter_name="NL", sender_name="NL",
                   sender_email="a@b.c", list_id=1, preview_text="")
    assert not any(m == "POST" for m, *_ in session.calls)


# ---------- main.py ----------

@pytest.fixture
def isolated_main(monkeypatch, tmp_path, settings):
    """main.py avec data/, docs/ et output/ redirigés vers un dossier temporaire et sans réseau."""
    monkeypatch.setattr(main, "SendLock", functools.partial(SendLock, data_dir=tmp_path))
    monkeypatch.setattr(main, "History", functools.partial(History, data_dir=tmp_path))
    monkeypatch.setattr(main, "IssueStore", functools.partial(IssueStore, data_dir=tmp_path))
    monkeypatch.setattr(main, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(main, "DOCS_DIR", tmp_path / "docs")
    monkeypatch.setattr(main, "load_settings", lambda: settings)
    arts = [make_article(i) for i in range(1, 10)]
    monkeypatch.setattr(main, "collect_all", lambda s, now=None: arts)
    return tmp_path


def test_main_dry_run_with_mock_writes_output(isolated_main):
    rc = main.main(["--dry-run", "--date", "2026-11-16"])  # pas de clé -> mock automatique
    assert rc == 0
    out = isolated_main / "output"
    assert (out / "issue.html").exists() and (out / "issue.txt").exists()
    assert (out / "site" / "index.html").exists()
    # Un dry-run n'écrit ni verrou, ni historique, ni archives
    assert not (isolated_main / "locks").exists()
    assert not (isolated_main / "docs").exists()


def test_main_skips_when_week_already_sent(isolated_main, monkeypatch):
    SendLock("2026-W47", isolated_main).acquire({"number": 1})
    called = []
    monkeypatch.setattr(main, "collect_all", lambda *a, **k: called.append(1) or [])
    assert main.main(["--date", "2026-11-16"]) == 0
    assert called == []  # rien n'est collecté ni envoyé


def test_main_real_send_requires_secrets(isolated_main):
    assert main.main(["--date", "2026-11-16"]) == main.EXIT_CONFIG


def test_main_fails_cleanly_with_too_few_items(isolated_main, monkeypatch):
    monkeypatch.setattr(main, "collect_all", lambda s, now=None: [make_article(1), make_article(2)])
    assert main.main(["--dry-run", "--date", "2026-11-16"]) == main.EXIT_FAIL


def test_main_real_send_locks_and_archives(isolated_main, monkeypatch):
    for k, v in {"GEMINI_API_KEY": "x", "BREVO_API_KEY": "k", "BREVO_LIST_ID": "2",
                 "BREVO_SENDER_EMAIL": "moi@exemple.fr"}.items():
        monkeypatch.setenv(k, v)
    from newsletter.write.llm import LLMRouter
    from newsletter.write.mock import MockProvider

    monkeypatch.setattr(main, "build_router", lambda s, sec: LLMRouter([MockProvider()]))
    sent = []
    monkeypatch.setattr(main, "send_issue", lambda client, issue, html, **kw: sent.append(issue["week"]) or 99)
    assert main.main(["--date", "2026-11-16"]) == 0
    assert sent == ["2026-W47"]
    assert SendLock("2026-W47", isolated_main).read()["campaign_id"] == 99
    assert (isolated_main / "docs" / "archives" / "2026-W47" / "index.html").exists()
    assert History(isolated_main).urls  # historique mis à jour
    # Second lancement la même semaine : aucun nouvel envoi
    assert main.main(["--date", "2026-11-18"]) == 0
    assert sent == ["2026-W47"]
