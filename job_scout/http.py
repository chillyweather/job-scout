"""The one place that performs network requests, so tests can replace it."""

from __future__ import annotations

import json
from typing import Any, Callable
from urllib.request import Request, urlopen

USER_AGENT = "job-scout/0.1 (+personal job board poller)"
TIMEOUT_SECONDS = 20
MAX_BYTES = 20_000_000

Fetcher = Callable[[str], Any]


class FetchError(RuntimeError):
    pass


def fetch_json(url: str) -> Any:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read(MAX_BYTES + 1)
    except Exception as exc:  # urllib raises several unrelated types
        raise FetchError(f"{type(exc).__name__}: {exc}") from exc
    if len(body) > MAX_BYTES:
        raise FetchError(f"response larger than {MAX_BYTES} bytes")
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise FetchError(f"not JSON: {exc}") from exc
