"""Lever postings API: https://github.com/lever/postings-api

Boards on jobs.eu.lever.co are served by api.eu.lever.co; set ``region: "eu"``.
Lever gives a creation time, not a publish time.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from job_scout.http import Fetcher
from job_scout.models import Board, Posting
from job_scout.text import html_to_text


def url(board: Board) -> str:
    host = "api.eu.lever.co" if board.region == "eu" else "api.lever.co"
    return f"https://{host}/v0/postings/{board.slug}?mode=json"


def fetch(board: Board, fetcher: Fetcher) -> list[Posting]:
    return parse(board, fetcher(url(board)))


def _iso_from_millis(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return ""
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat()


def _description(job: dict[str, Any]) -> str:
    parts = [job.get("descriptionPlain") or html_to_text(job.get("description") or "")]
    for section in job.get("lists") or []:
        parts.append(section.get("text", ""))
        parts.append(html_to_text(section.get("content", "")))
    parts.append(job.get("additionalPlain") or "")
    return "\n\n".join(p.strip() for p in parts if p and p.strip())


def parse(board: Board, data: Any) -> list[Posting]:
    if isinstance(data, dict):  # Lever answers an unknown slug with {"ok": false, ...}
        raise ValueError(data.get("error") or "unexpected response")
    postings = []
    for job in data:
        categories = job.get("categories") or {}
        location = (categories.get("location") or "").strip()
        others = [loc for loc in categories.get("allLocations") or [] if loc and loc != location]
        postings.append(
            Posting(
                board_key=board.key,
                company=board.company,
                job_id=str(job["id"]),
                title=(job.get("text") or "").strip(),
                location=location,
                extra_locations=others,
                url=job.get("hostedUrl") or "",
                published_at=_iso_from_millis(job.get("createdAt")),
                description=_description(job),
                department=categories.get("team") or categories.get("department") or "",
                workplace=job.get("workplaceType") or "",
            )
        )
    return postings
