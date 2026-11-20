"""Roles already in the person's own notes: the application tracker and the leads inbox.

A posting counts as known when its job id appears anywhere in those files, or when
one line names both the company and the exact title.

Separately, ``employer_line`` finds an application record for the same employer, because
Dima applies to one role per company. Only tracker records count: a table row that starts
with an application number (``| 117 | WalkMe — ...``) or a numbered heading
(``### 21. Unframe — ...``). Matching the company name anywhere would flag short names such
as Via or Rise on unrelated lines.
"""

from __future__ import annotations

import re
from pathlib import Path

from job_scout.models import Posting
from job_scout.text import normalize


_RECORD = re.compile(r"^\s*(?:\|\s*\d{1,4}\s*\||#{2,4}\s+\d{1,4}\.)")


class KnownIndex:
    def __init__(self, texts: list[str]) -> None:
        self._raw = "\n".join(texts)
        self._lines = [normalize(line) for line in self._raw.splitlines() if line.strip()]
        self._records = [
            (normalize(line), " ".join(line.split())[:200]) for line in self._raw.splitlines() if _RECORD.match(line)
        ]

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

    def employer_line(self, company: str) -> str:
        """The first application record that names this employer, or an empty string."""
        name = normalize(company)
        if not name:
            return ""
        pattern = re.compile(rf"\b{re.escape(name)}\b")
        for normalized, original in self._records:
            if pattern.search(normalized):
                return original
        return ""
