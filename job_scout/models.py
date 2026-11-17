"""Shared data shapes."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Board:
    """One company's job board, as listed in the watchlist."""

    company: str
    ats: str  # greenhouse | lever | ashby
    slug: str
    region: str = ""  # "eu" for Lever's EU instance; Greenhouse and Ashby ignore it
    note: str = ""

    @property
    def key(self) -> str:
        return f"{self.ats}:{self.slug}"


@dataclass
class Posting:
    """One open role, normalized across job-board vendors."""

    board_key: str
    company: str
    job_id: str
    title: str
    location: str
    url: str
    published_at: str = ""  # ISO 8601 when the vendor provides it
    description: str = ""
    department: str = ""
    workplace: str = ""
    extra_locations: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.board_key}:{self.job_id}"

    @property
    def all_locations(self) -> list[str]:
        return [loc for loc in [self.location, *self.extra_locations] if loc]

    def content_hash(self) -> str:
        """Changes when what a reader would judge the role on changes."""
        text = "\n".join([self.title, " | ".join(self.all_locations), self.description])
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["key"] = self.key
        return data
