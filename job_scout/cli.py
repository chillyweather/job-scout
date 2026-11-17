"""Command line entry point."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from job_scout import config as config_module
from job_scout.adapters import board_url
from job_scout.poll import fetch_all, run
from job_scout.state import State


def _config_path(value: str | None) -> Path:
    return Path(value or os.environ.get("JOB_SCOUT_CONFIG") or "config.json")


def _markdown(report: dict[str, Any]) -> str:
    counts = report["counts"]
    boards = report["boards"]
    lines = [
        f"# job-scout {report['mode']} — {report['run_at']}",
        "",
        f"Boards: {boards['ok']} of {boards['total']} read. "
        f"New {counts['new']}, updated {counts['updated']}, reopened {counts['reopened']}. "
        f"Skipped: {counts['outside_location']} outside location, {counts['title_filtered']} by title, "
        f"{counts['known_in_notes']} already in notes.",
    ]
    if boards["failed"]:
        lines += ["", "## Boards that failed", ""]
        lines += [f"- {f['company']} ({f['board']}): {f['error']}" for f in boards["failed"]]
    if report["postings"]:
        lines += ["", "## Postings", ""]
        for p in report["postings"]:
            published = (p["published_at"] or "")[:10] or "no date"
            lines.append(f"- [{p['company']} — {p['title']}]({p['url']}) · {p['location']} · {published} · {p['change']}")
    if report["closed_since_last_run"]:
        lines += ["", "## Closed since last run (previously reported)", ""]
        lines += [f"- {c['company']} — {c['title']}" for c in report["closed_since_last_run"]]
    return "\n".join(lines) + "\n"


def cmd_poll(args: argparse.Namespace) -> int:
    cfg = config_module.load(_config_path(args.config), [Path(p) for p in args.known], Path(args.db) if args.db else None)
    state = State(cfg.state_db)
    try:
        report = run(cfg, state, dry_run=args.dry_run, baseline=args.baseline).to_dict()
    finally:
        state.close()
    output = json.dumps(report, ensure_ascii=False, indent=2) if args.format == "json" else _markdown(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output if output.endswith("\n") else output + "\n")
    # Exit 2 when every board failed, so a scheduler notices a dead run.
    return 2 if report["boards"]["total"] and report["boards"]["ok"] == 0 else 0


def cmd_check(args: argparse.Namespace) -> int:
    cfg = config_module.load(_config_path(args.config))
    failed = 0
    for result in fetch_all(cfg.watchlist, _fetcher()):
        board = result.board
        if result.error:
            failed += 1
            print(f"FAIL  {board.company:<24} {board.key:<36} {result.error}")
            continue
        local = [p for p in result.postings if cfg.filters.location_ok(p)]
        matching = [p for p in local if not cfg.filters.title_reason(p)]
        print(f"ok    {board.company:<24} {board.key:<36} {len(result.postings):>4} open, {len(local):>3} in location, {len(matching):>3} match titles")
    return 1 if failed else 0


def cmd_boards(args: argparse.Namespace) -> int:
    cfg = config_module.load(_config_path(args.config))
    for board in cfg.watchlist:
        print(f"{board.company:<24} {board.key:<36} {board_url(board)}")
    return 0


def _fetcher():  # indirection so tests can patch it
    from job_scout.http import fetch_json

    return fetch_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="job-scout", description=__doc__)
    parser.add_argument("--config", help="config file (default: $JOB_SCOUT_CONFIG or ./config.json)")
    sub = parser.add_subparsers(dest="command", required=True)

    poll = sub.add_parser("poll", help="fetch all boards and report postings new since the last run")
    poll.add_argument("--format", choices=["json", "markdown"], default="json")
    poll.add_argument("--output", help="write the report to this file instead of stdout")
    poll.add_argument("--known", action="append", default=[], help="extra notes file to dedupe against (repeatable)")
    poll.add_argument("--db", help="state database path (overrides config)")
    mode = poll.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="compute the report, write no state")
    mode.add_argument("--baseline", action="store_true", help="mark everything currently open as seen, report nothing")
    poll.set_defaults(func=cmd_poll)

    check = sub.add_parser("check", help="fetch every board once and print counts; writes no state")
    check.set_defaults(func=cmd_check)

    boards = sub.add_parser("boards", help="list the watchlist with API URLs")
    boards.set_defaults(func=cmd_boards)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except config_module.ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
