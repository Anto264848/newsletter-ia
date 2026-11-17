"""Structures de données et schémas de validation du JSON renvoyé par l'IA."""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


@dataclass
class Article:
    """Un article collecté."""

    title: str
    url: str
    source_id: str
    source_name: str
    published: datetime
    excerpt: str = ""
    lang: str = "en"
    weight: float = 1.0
    # Remplis par la sélection :
    id: str = ""
    score: float = 0.0
    coverage: int = 1
    related_sources: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.id:
            self.id = "a" + hashlib.sha1(self.url.encode("utf-8")).hexdigest()[:8]

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["published"] = self.published.isoformat()
        return d


# ---------- Schémas du JSON de l'IA (validation stricte) ----------

class _Strict(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class SelectionResult(_Strict):
    top: str = Field(min_length=1)
    briefs: list[str] = Field(min_length=1)

    @field_validator("briefs")
    @classmethod
    def _unique(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for x in v:
            if x not in out:
                out.append(x)
        return out


class TopStory(_Strict):
    id: str = Field(min_length=1)
    headline: str = Field(min_length=3)
    summary: str = Field(min_length=200)
    why_it_matters: str = Field(min_length=40)


class Brief(_Strict):
    id: str = Field(min_length=1)
    headline: str = Field(min_length=3)
    summary: str = Field(min_length=80)


class WordOfWeek(_Strict):
    term: str = Field(min_length=2, max_length=80)
    explanation: str = Field(min_length=80)


class ToolOfWeek(_Strict):
    name: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=60)


class IssueContent(_Strict):
    title: str = Field(min_length=5, max_length=160)
    intro: str = Field(min_length=30)
    top_story: TopStory
    briefs: list[Brief] = Field(min_length=1)
    word_of_the_week: WordOfWeek
    tool_of_the_week: ToolOfWeek
    conclusion: str = Field(min_length=10)
