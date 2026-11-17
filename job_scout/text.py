"""Small text helpers."""

from __future__ import annotations

import html
import re

_TAG = re.compile(r"<[^>]+>")
_BLOCK_END = re.compile(r"</(p|div|li|h[1-6]|ul|ol|tr)>|<br\s*/?>", re.IGNORECASE)
_SPACES = re.compile(r"[ \t ]+")
_BLANK_LINES = re.compile(r"\n\s*\n+")


def html_to_text(value: str) -> str:
    """Plain text from a job description. Greenhouse double-escapes its HTML."""
    if not value:
        return ""
    text = html.unescape(value)
    if "&lt;" in text or "&amp;" in text:
        text = html.unescape(text)
    text = _BLOCK_END.sub("\n", text)
    text = _TAG.sub("", text)
    text = _SPACES.sub(" ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    return _BLANK_LINES.sub("\n\n", text).strip()


def normalize(value: str) -> str:
    """Lowercase, punctuation folded to spaces, for loose matching."""
    value = value.lower().replace("&", " and ")
    value = re.sub(r"[^\w]+", " ", value)
    return " ".join(value.split())
