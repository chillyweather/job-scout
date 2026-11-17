"""Greenhouse job board API: https://developers.greenhouse.io/job-board.html

The same endpoint serves boards hosted on job-boards.greenhouse.io and on
job-boards.eu.greenhouse.io; ``absolute_url`` points at the right one.
"""

from __future__ import annotations

from typing import Any

from job_scout.http import Fetcher
from job_scout.models import Board, Posting
from job_scout.text import html_to_text


def url(board: Board) -> str:
    return f"https://boards-api.greenhouse.io/v1/boards/{board.slug}/jobs?content=true"


def fetch(board: Board, fetcher: Fetcher) -> list[Posting]:
    return parse(board, fetcher(url(board)))


def parse(board: Board, data: Any) -> list[Posting]:
    postings = []
    for job in data.get("jobs", []):
        offices = [o.get("location") or o.get("name") or "" for o in job.get("offices") or []]
        postings.append(
            Posting(
                board_key=board.key,
                company=board.company,
                job_id=str(job["id"]),
                title=(job.get("title") or "").strip(),
                location=((job.get("location") or {}).get("name") or "").strip(),
                extra_locations=[o for o in offices if o],
                url=job.get("absolute_url") or "",
                published_at=job.get("first_published") or job.get("updated_at") or "",
                description=html_to_text(job.get("content") or ""),
                department=", ".join(d.get("name", "") for d in job.get("departments") or []),
            )
        )
    return postings
