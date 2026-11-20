"""One polling run: fetch every board, filter, diff against state, drop what the notes already hold."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from job_scout import hebrew as hebrew_module
from job_scout.adapters import ADAPTERS
from job_scout.config import Config
from job_scout.http import Fetcher, fetch_json
from job_scout.known import KnownIndex
from job_scout.models import Board, Posting
from job_scout.permit import classify
from job_scout.state import State
from job_scout.text import normalize

MAX_WORKERS = 6


@dataclass
class BoardResult:
    board: Board
    postings: list[Posting] = field(default_factory=list)
    error: str = ""


@dataclass
class RunReport:
    run_at: str
    mode: str
    profile: str = "default"
    boards_total: int = 0
    boards_ok: int = 0
    failed_boards: list[dict[str, Any]] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    postings: list[dict[str, Any]] = field(default_factory=list)
    known: list[dict[str, str]] = field(default_factory=list)
    excluded: list[dict[str, str]] = field(default_factory=list)
    closed: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_at": self.run_at,
            "mode": self.mode,
            "profile": self.profile,
            "boards": {"total": self.boards_total, "ok": self.boards_ok, "failed": self.failed_boards},
            "counts": self.counts,
            "postings": self.postings,
            "known_in_notes": self.known,
            "excluded_by_rule": self.excluded,
            "closed_since_last_run": self.closed,
        }


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def fetch_board(board: Board, fetcher: Fetcher) -> BoardResult:
    try:
        return BoardResult(board, ADAPTERS[board.ats](board, fetcher))
    except Exception as exc:  # one broken board must not stop the run
        return BoardResult(board, error=f"{type(exc).__name__}: {exc}"[:300])


def fetch_all(boards: list[Board], fetcher: Fetcher) -> list[BoardResult]:
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        return list(pool.map(lambda b: fetch_board(b, fetcher), boards))


def run(
    config: Config,
    state: State,
    fetcher: Fetcher = fetch_json,
    *,
    dry_run: bool = False,
    baseline: bool = False,
    now: str | None = None,
) -> RunReport:
    """``baseline`` records everything as seen and reports nothing: use it once on a fresh state.

    ``dry_run`` computes the report and writes nothing.
    """
    now = now or now_iso()
    mode = "baseline" if baseline else ("dry-run" if dry_run else "poll")
    report = RunReport(run_at=now, mode=mode, profile=config.name, boards_total=len(config.watchlist))
    known = KnownIndex.from_files(config.known_files)
    counts = dict.fromkeys(
        [
            "fetched",
            "outside_location",
            "title_filtered",
            "known_in_notes",
            "blocked_company",
            "hebrew_excluded",
            "permit_excluded",
            "already_reported",
            "new",
            "updated",
            "reopened",
            "closed",
        ],
        0,
    )

    blocked = {normalize(c) for c in config.blocked_companies}

    for result in fetch_all(config.watchlist, fetcher):
        board = result.board
        if result.error:
            failures = state.board_failed(board.key, result.error, now)
            report.failed_boards.append(
                {
                    "company": board.company,
                    "board": board.key,
                    "error": result.error,
                    "consecutive_failures": failures,
                }
            )
            continue

        report.boards_ok += 1
        first_poll = not state.board_seen_before(board.key)
        state.board_ok(board.key, now)
        present: set[str] = set()

        for posting in result.postings:
            counts["fetched"] += 1
            present.add(posting.key)
            previous = state.get(posting.key)
            content_hash = posting.content_hash()
            state.upsert(posting.key, board.key, board.company, posting.title, posting.url, content_hash, now)

            if not config.filters.location_ok(posting):
                counts["outside_location"] += 1
                continue
            if config.filters.title_reason(posting):
                counts["title_filtered"] += 1
                continue
            reason = known.reason(posting)
            if reason:
                counts["known_in_notes"] += 1
                report.known.append({"company": posting.company, "title": posting.title, "reason": reason})
                continue

            if normalize(posting.company) in blocked:
                counts["blocked_company"] += 1
                continue

            permit = classify(posting.description) if config.permit_tagging else None
            if permit is not None and permit.tag in config.permit_exclude:
                counts["permit_excluded"] += 1
                continue

            if previous is not None and previous["closed_at"]:
                change = "reopened"
            elif previous is None or not previous["reported_hash"]:
                change = "new"
            elif previous["reported_hash"] != content_hash:
                change = "updated"
            else:
                counts["already_reported"] += 1
                continue

            if baseline:
                state.mark_reported(posting.key, content_hash, now)
                counts["already_reported"] += 1
                continue

            hebrew = hebrew_module.classify(posting.description) if config.hebrew_tagging else None
            if hebrew is not None and hebrew.tag in config.hebrew_exclude:
                # Recorded as reported so it is listed once, not every day. Listed, not silent:
                # a wrong match must be visible to the person.
                state.mark_reported(posting.key, content_hash, now)
                counts["hebrew_excluded"] += 1
                report.excluded.append(
                    {"company": posting.company, "title": posting.title, "url": posting.url,
                     "rule": f"hebrew:{hebrew.tag}", "evidence": hebrew.evidence}
                )
                continue

            counts[change] += 1
            state.mark_reported(posting.key, content_hash, now)
            item = posting.to_dict()
            item["description"] = posting.description[: config.max_description_chars]
            item["change"] = change
            item["first_poll_of_board"] = first_poll
            if permit is not None:
                item["work_permit"] = permit.to_dict()
            if hebrew is not None:
                item["hebrew"] = hebrew.to_dict()
            employer = known.employer_line(posting.company)
            if employer:
                item["employer_in_tracker"] = employer
            if previous is not None and previous["reported_at"]:
                item["previously_reported_at"] = previous["reported_at"]
            report.postings.append(item)

        for row in state.close_missing(board.key, present, now):
            counts["closed"] += 1
            if row["reported_at"]:
                report.closed.append({"company": row["company"], "title": row["title"], "url": row["url"]})

    report.counts = counts
    report.postings.sort(key=lambda p: (p["published_at"] or "", p["key"]), reverse=True)
    report.failed_boards.sort(key=lambda f: f["board"])
    if dry_run:
        state.rollback()
    else:
        state.commit()
    return report
