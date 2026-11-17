"""One adapter per job-board vendor. Each turns a vendor response into Postings."""

from __future__ import annotations

from typing import Callable

from job_scout.http import Fetcher
from job_scout.models import Board, Posting

from . import ashby, greenhouse, lever

Adapter = Callable[[Board, Fetcher], list[Posting]]

ADAPTERS: dict[str, Adapter] = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "ashby": ashby.fetch,
}


def board_url(board: Board) -> str:
    return {
        "greenhouse": greenhouse.url,
        "lever": lever.url,
        "ashby": ashby.url,
    }[board.ats](board)
