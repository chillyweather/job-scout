"""Ashby public job board API: https://developers.ashbyhq.com/docs/public-job-posting-api"""

from __future__ import annotations

from typing import Any

from job_scout.http import Fetcher
from job_scout.models import Board, Posting
from job_scout.text import html_to_text


def url(board: Board) -> str:
    return f"https://api.ashbyhq.com/posting-api/job-board/{board.slug}"


def fetch(board: Board, fetcher: Fetcher) -> list[Posting]:
    return parse(board, fetcher(url(board)))


def _country(address: Any) -> str:
    if not isinstance(address, dict):
        return ""
    postal = address.get("postalAddress") or {}
    return postal.get("addressCountry") or ""


def parse(board: Board, data: Any) -> list[Posting]:
    postings = []
    for job in data.get("jobs", []):
        if job.get("isListed") is False:
            continue
        extra = [_country(job.get("address"))]
        for secondary in job.get("secondaryLocations") or []:
            extra.append(secondary.get("location") or "")
            extra.append(_country(secondary.get("address")))
        location = (job.get("location") or "").strip()
        postings.append(
            Posting(
                board_key=board.key,
                company=board.company,
                job_id=str(job["id"]),
                title=(job.get("title") or "").strip(),
                location=location,
                extra_locations=sorted({e for e in extra if e and e != location}),
                url=job.get("jobUrl") or "",
                published_at=job.get("publishedAt") or "",
                description=job.get("descriptionPlain") or html_to_text(job.get("descriptionHtml") or ""),
                department=job.get("department") or "",
                workplace=job.get("workplaceType") or "",
            )
        )
    return postings
