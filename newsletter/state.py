"""État persistant dans data/ : historique, verrous anti double envoi, numéros publiés."""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .paths import DATA_DIR
from .textutils import normalize, title_similarity

log = logging.getLogger(__name__)

MAX_HISTORY = 2000


def iso_week_id(d: date) -> str:
    """Identifiant de semaine ISO, ex. « 2026-W47 »."""
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    tmp.replace(path)


class History:
    """URL, sujets, mots et outils déjà publiés (pour ne jamais se répéter)."""

    def __init__(self, data_dir: Path = DATA_DIR):
        self.path = data_dir / "history.json"
        raw = _read_json(self.path, {})
        self.urls: list[str] = raw.get("urls", [])
        self.topics: list[str] = raw.get("topics", [])
        self.words: list[str] = raw.get("words", [])
        self.tools: list[str] = raw.get("tools", [])

    def seen_url(self, url: str) -> bool:
        return url.rstrip("/") in {u.rstrip("/") for u in self.urls}

    def seen_topic(self, title: str, threshold: float) -> bool:
        return any(title_similarity(title, t) >= threshold for t in self.topics)

    def seen_word(self, term: str) -> bool:
        n = normalize(term)
        return any(normalize(w) == n for w in self.words)

    def seen_tool(self, name: str) -> bool:
        n = normalize(name)
        return any(normalize(t) == n for t in self.tools)

    def add_issue(self, urls: list[str], topics: list[str], word: str, tool: str) -> None:
        self.urls = (self.urls + urls)[-MAX_HISTORY:]
        self.topics = (self.topics + topics)[-MAX_HISTORY:]
        if word:
            self.words.append(word)
        if tool:
            self.tools.append(tool)

    def save(self) -> None:
        _write_json(
            self.path,
            {"urls": self.urls, "topics": self.topics, "words": self.words, "tools": self.tools},
        )


class SendLock:
    """Verrou par semaine ISO : empêche d'envoyer deux fois le même numéro."""

    def __init__(self, week_id: str, data_dir: Path = DATA_DIR):
        self.week_id = week_id
        self.path = data_dir / "locks" / f"{week_id}.json"

    def exists(self) -> bool:
        return self.path.exists()

    def read(self) -> dict[str, Any]:
        return _read_json(self.path, {})

    def acquire(self, info: dict[str, Any]) -> None:
        if self.exists():
            raise RuntimeError(f"Le numéro de la semaine {self.week_id} a déjà été envoyé.")
        payload = {"week": self.week_id, "sent_at": datetime.now(timezone.utc).isoformat(), **info}
        _write_json(self.path, payload)


class IssueStore:
    """Numéros publiés, stockés en JSON dans data/issues/ (source du site d'archives)."""

    def __init__(self, data_dir: Path = DATA_DIR):
        self.dir = data_dir / "issues"

    def all(self) -> list[dict[str, Any]]:
        if not self.dir.exists():
            return []
        issues = [_read_json(p, None) for p in sorted(self.dir.glob("*.json"))]
        issues = [i for i in issues if i]
        return sorted(issues, key=lambda i: i["number"], reverse=True)

    def next_number(self) -> int:
        issues = self.all()
        return (max(i["number"] for i in issues) + 1) if issues else 1

    def save(self, issue: dict[str, Any]) -> Path:
        path = self.dir / f"{issue['week']}.json"
        _write_json(path, issue)
        return path
