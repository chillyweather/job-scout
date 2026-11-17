"""Loading the config file and the watchlist."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from job_scout import permit as permit_module
from job_scout.adapters import ADAPTERS
from job_scout.filters import Filters
from job_scout.models import Board


class ConfigError(ValueError):
    pass


@dataclass
class Config:
    watchlist: list[Board]
    filters: Filters
    state_db: Path
    known_files: list[Path] = field(default_factory=list)
    max_description_chars: int = 8000
    name: str = "default"
    permit_tagging: bool = False
    permit_exclude: list[str] = field(default_factory=list)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{path}: invalid JSON: {exc}") from exc


def load_watchlist(path: Path | list[Path]) -> list[Board]:
    """One watchlist file, or several merged in order. A board listed twice is an error."""
    paths = path if isinstance(path, list) else [path]
    boards: list[Board] = []
    seen: set[str] = set()
    for one in paths:
        boards.extend(_load_one_watchlist(one, seen))
    return boards


def _load_one_watchlist(path: Path, seen: set[str]) -> list[Board]:
    data = _read_json(path)
    boards = []
    for index, entry in enumerate(data.get("boards", [])):
        try:
            board = Board(
                company=entry["company"],
                ats=entry["ats"],
                slug=entry["slug"],
                region=entry.get("region", ""),
                note=entry.get("note", ""),
            )
        except KeyError as exc:
            raise ConfigError(f"{path}: board #{index} lacks {exc}") from exc
        if board.ats not in ADAPTERS:
            raise ConfigError(f"{path}: board #{index} has unknown ats '{board.ats}'")
        if entry.get("disabled"):
            continue
        if board.key in seen:
            raise ConfigError(f"{path}: duplicate board {board.key}")
        seen.add(board.key)
        boards.append(board)
    return boards


def load(path: Path, extra_known: list[Path] | None = None, state_db: Path | None = None) -> Config:
    """Paths inside the config resolve against the config file's folder.

    ``config.local.json`` beside it, when present, overrides top-level keys of every
    profile. It is gitignored and is where machine-specific paths such as the vault
    files go. Each profile (``config.json``, ``config.europe.json``) names its own
    ``state_db``, so profiles never share seen-state.
    """
    data = _read_json(path)
    local = path.with_name("config.local.json")
    if local.exists():
        data.update(_read_json(local))
    base = path.parent

    def resolve(value: str) -> Path:
        candidate = Path(value).expanduser()
        return candidate if candidate.is_absolute() else base / candidate

    known = [resolve(p) for p in data.get("known_files", [])] + list(extra_known or [])
    watchlist = data.get("watchlist", "watchlist.json")
    watchlist_paths = [resolve(w) for w in watchlist] if isinstance(watchlist, list) else resolve(watchlist)
    permit = data.get("work_permit", {})
    unknown_tags = [t for t in permit.get("exclude", []) if t not in permit_module.TAGS]
    if unknown_tags:
        raise ConfigError(f"{path}: unknown work_permit tag(s): {', '.join(unknown_tags)}")
    missing = [str(p) for p in known if not p.exists()]
    if missing:
        raise ConfigError("known file not found: " + ", ".join(missing))
    return Config(
        watchlist=load_watchlist(watchlist_paths),
        filters=Filters.from_config(data.get("filters", {})),
        state_db=state_db or resolve(data.get("state_db", "state/job-scout.sqlite")),
        known_files=known,
        max_description_chars=int(data.get("max_description_chars", 8000)),
        name=data.get("name", path.stem),
        permit_tagging=bool(permit.get("tag", False)),
        permit_exclude=list(permit.get("exclude", [])),
    )
