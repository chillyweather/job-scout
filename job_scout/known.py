"""Roles already in the person's own notes: the application tracker and the leads inbox.

A posting counts as known when its job id appears anywhere in those files, or when
one line names both the company and the exact title.
"""

from __future__ import annotations

from pathlib import Path

from job_scout.models import Posting
from job_scout.text import normalize


class KnownIndex:
    def __init__(self, texts: list[str]) -> None:
        self._raw = "\n".join(texts)
        self._lines = [normalize(line) for line in self._raw.splitlines() if line.strip()]

    @classmethod
    def from_files(cls, paths: list[Path]) -> "KnownIndex":
        return cls([p.read_text(encoding="utf-8", errors="replace") for p in paths])

    def reason(self, posting: Posting) -> str:
        if len(posting.job_id) >= 6 and posting.job_id in self._raw:
            return "job id found in notes"
        company = normalize(posting.company)
        title = normalize(posting.title)
        if company and title:
            for line in self._lines:
                if company in line and title in line:
                    return "company and title found on one line in notes"
        return ""
