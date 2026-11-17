"""Hard filters applied in code before anything reaches a model or a person."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from job_scout.models import Posting
from job_scout.text import normalize


def _pattern(terms: list[str]) -> re.Pattern[str] | None:
    cleaned = [normalize(t) for t in terms if normalize(t)]
    if not cleaned:
        return None
    alternatives = "|".join(re.escape(t) for t in sorted(cleaned, key=len, reverse=True))
    return re.compile(rf"\b(?:{alternatives})\b")


@dataclass
class Filters:
    location_include: list[str] = field(default_factory=list)
    location_exclude: list[str] = field(default_factory=list)
    title_include: list[str] = field(default_factory=list)
    title_exclude: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._loc_in = _pattern(self.location_include)
        self._loc_out = _pattern(self.location_exclude)
        self._title_in = _pattern(self.title_include)
        self._title_out = _pattern(self.title_exclude)

    @classmethod
    def from_config(cls, data: dict[str, Any]) -> "Filters":
        locations = data.get("locations", {})
        titles = data.get("titles", {})
        return cls(
            location_include=locations.get("include", []),
            location_exclude=locations.get("exclude", []),
            title_include=titles.get("include", []),
            title_exclude=titles.get("exclude", []),
        )

    def location_ok(self, posting: Posting) -> bool:
        text = normalize(" | ".join(posting.all_locations))
        if self._loc_out and self._loc_out.search(text):
            return False
        return self._loc_in is None or bool(self._loc_in.search(text))

    def title_reason(self, posting: Posting) -> str:
        """Empty string when the title passes, otherwise why it did not."""
        title = normalize(posting.title)
        if self._title_out:
            hit = self._title_out.search(title)
            if hit:
                return f"title excluded by '{hit.group(0)}'"
        if self._title_in and not self._title_in.search(title):
            return "title matches no included term"
        return ""
