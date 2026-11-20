"""Hebrew-language requirement, read from the posting text.

Dima's standing rule (tracker, 16 September 2026): skip openings that declare high-level or
native Hebrew as a requirement. His Hebrew is fluent spoken, reading proficient, writing limited,
so "fluent Hebrew" alone is not a blocker and stays in the report, tagged.

Tags:

- ``high_required``: native, mother-tongue, excellent, high-level or business-level Hebrew is
  required. The only tag that removes a posting (when the profile says so).
- ``hebrew_posting``: the description is written mostly in Hebrew. Usually means strong written
  Hebrew, but some of these were worth applying to (Madanes #123), so it is a tag, not a drop.
- ``mentioned``: Hebrew is mentioned otherwise: fluent, an advantage, a plus.
- ``unstated``: nothing found.

As with work permits, a requirement phrased as an advantage ("native Hebrew - an advantage")
is not a requirement.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

HIGH_REQUIRED = "high_required"
HEBREW_POSTING = "hebrew_posting"
MENTIONED = "mentioned"
UNSTATED = "unstated"

TAGS = (HIGH_REQUIRED, HEBREW_POSTING, MENTIONED, UNSTATED)

_LEVEL = (
    r"(?:native|mother[- ]?tongue|excellent|exceptional|perfect|very high|high|high[- ]level|"
    r"business[- ]level|business[- ]fluent|professional[- ]level|full professional|outstanding|superb|strong written)"
)
# "Native Hebrew", "excellent Hebrew and English", "excellent English and Hebrew", "Hebrew: native",
# "Hebrew at a native level".
_HIGH = [
    rf"\b{_LEVEL}\b[^.\n;]{{0,40}}\bhebrew\b",
    rf"\bhebrew\b[^.\n;]{{0,25}}\b{_LEVEL}\b",
]
_SOFT = re.compile(r"\b(?:advantage|advantageous|a plus|plus|nice to have|preferred|bonus|benefit)\b", re.IGNORECASE)
_ANY = re.compile(r"\bhebrew\b|עברית", re.IGNORECASE)
_HIGH_HEBREW_SCRIPT = re.compile(r"עברית\s*(?:ברמת\s*)?(?:שפת\s*אם|ברמה\s*גבוהה|גבוהה|מצוינת|ברמה\s*מצוינת)")
_C_HIGH = [re.compile(p, re.IGNORECASE) for p in _HIGH]
_HEBREW_LETTER = re.compile(r"[֐-׿]")
_LATIN_LETTER = re.compile(r"[A-Za-z]")


@dataclass(frozen=True)
class HebrewSignal:
    tag: str
    evidence: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"tag": self.tag, "evidence": self.evidence}


def _sentence(text: str, start: int, end: int) -> str:
    left = max(text.rfind(".", 0, start), text.rfind("\n", 0, start)) + 1
    right_candidates = [i for i in (text.find(".", end), text.find("\n", end)) if i != -1]
    right = min(right_candidates) if right_candidates else len(text)
    return " ".join(text[left:right].split())[:240]


def _mostly_hebrew(text: str) -> bool:
    hebrew = len(_HEBREW_LETTER.findall(text))
    latin = len(_LATIN_LETTER.findall(text))
    return hebrew >= 40 and hebrew > latin


def classify(text: str) -> HebrewSignal:
    for match in sorted((m for p in _C_HIGH for m in p.finditer(text)), key=lambda m: m.start()):
        sentence = _sentence(text, match.start(), match.end())
        if not _SOFT.search(sentence):
            return HebrewSignal(HIGH_REQUIRED, sentence)
    script = _HIGH_HEBREW_SCRIPT.search(text)
    if script:
        sentence = _sentence(text, script.start(), script.end())
        if "יתרון" not in sentence:  # "advantage"
            return HebrewSignal(HIGH_REQUIRED, sentence)
    if _mostly_hebrew(text):
        return HebrewSignal(HEBREW_POSTING)
    mention = _ANY.search(text)
    if mention:
        return HebrewSignal(MENTIONED, _sentence(text, mention.start(), mention.end()))
    return HebrewSignal(UNSTATED)
