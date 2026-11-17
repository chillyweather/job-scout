"""Work-permission signal for roles outside the country you can already work in.

Read from the posting text in code, never decided by it. The tag says what the posting
states; a person or the agent decides what to do with it.

Tags, strongest evidence first:

- ``permit_required``: the posting says you must already be allowed to work there, or that
  it does not sponsor.
- ``residence_required``: a remote role that must be done from inside named countries.
- ``conditional``: it offers sponsorship in some cases and requires a permit in others,
  e.g. "we sponsor visas to Germany; elsewhere you need the right to work". Read the evidence.
- ``sponsors``: visa sponsorship or relocation support is offered.
- ``remote_contract``: contractor, employer-of-record, or work-from-anywhere hiring.
- ``unstated``: none of the above was found. Most postings land here.

A blocker outranks relocation help: "relocation support, but no visa sponsorship" is
``permit_required``. A blocker next to an explicit sponsorship offer is ``conditional``, because
real postings say both (n8n, 2026-11-17).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

PERMIT_REQUIRED = "permit_required"
RESIDENCE_REQUIRED = "residence_required"
CONDITIONAL = "conditional"
SPONSORS = "sponsors"
REMOTE_CONTRACT = "remote_contract"
UNSTATED = "unstated"

TAGS = (PERMIT_REQUIRED, RESIDENCE_REQUIRED, CONDITIONAL, SPONSORS, REMOTE_CONTRACT, UNSTATED)

_BLOCKERS = [
    r"(?:no|not|unable to|cannot|can ?not|can't|won't|will not|do not|does not|don't)\b[^.\n;]{0,40}\bsponsor",
    r"sponsorship (?:is |will |can )?(?:not |n't |un)(?:be )?(?:available|offered|provided|possible)",
    r"without (?:the need for )?(?:visa )?sponsorship",
    r"(?:must|should|need to|required to) (?:already )?(?:have|hold|possess) (?:the |a |full |valid |existing )*(?:right|permission|authori[sz]ation|eligibility|permit) to work",
    r"(?:must|should) be (?:legally )?(?:eligible|authori[sz]ed|entitled|permitted) to work",
    r"(?:valid|existing|current) (?:eu |uk |swiss )?work (?:permit|visa|authori[sz]ation) (?:is )?(?:required|needed|mandatory)",
    r"right to work in the (?:eu|uk|united kingdom|european union|netherlands|germany)",
    r"(?:eu|eea|uk|european) (?:citizenship|passport|nationality) (?:is )?(?:required|needed|mandatory)",
]

_RESIDENCE = [
    r"(?:must|should|need to|required to) (?:be )?(?:based|located|living|reside|resident)\b[^.\n]{0,25}\bin\b",
    r"(?:only|exclusively) (?:open to|considering) (?:candidates|applicants) (?:based|located|residing) in",
    r"remote,? (?:but )?(?:only )?within (?:the )?(?:eu|uk|europe)",
]

# An explicit offer to sponsor. A match inside a blocker ("unable to offer visa sponsorship") does not count.
_SPONSORSHIP = [
    r"(?:visa|work permit|blue card) sponsorship",
    r"\b(?:we|can|will|happy to|able to) sponsor\b",
    r"\bsponsor (?:your |a |the )?(?:visa|work permit)",
    r"\beu blue card\b",
]

_RELOCATION = [
    r"relocation (?:package|support|assistance|bonus|budget|help)",
    r"(?:help|support|assist) (?:you )?(?:with )?(?:your )?relocat",
]

_REMOTE_CONTRACT = [
    r"\bindependent contractor\b",
    r"\bcontractor (?:basis|agreement|role|position)\b",
    r"\b(?:b2b|freelance) contract\b",
    r"\bemployer of record\b",
    r"\bEOR\b",
    r"\b(?:via|through) (?:deel|remote\.com|oyster|rippling)\b",
    r"\bwork from anywhere\b",
    r"\banywhere in the world\b",
    r"\b(?:fully )?remote[ ,-]+(?:worldwide|globally|global)\b",
]


def _compile(patterns: list[str]) -> list[re.Pattern[str]]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


_C_BLOCKERS = _compile(_BLOCKERS)
_C_RESIDENCE = _compile(_RESIDENCE)
_C_SPONSORSHIP = _compile(_SPONSORSHIP)
_C_RELOCATION = _compile(_RELOCATION)
_C_REMOTE_CONTRACT = _compile(_REMOTE_CONTRACT)


@dataclass(frozen=True)
class PermitSignal:
    tag: str
    evidence: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"tag": self.tag, "evidence": self.evidence}


def _sentence(text: str, start: int, end: int) -> str:
    left = max(text.rfind(".", 0, start), text.rfind("\n", 0, start)) + 1
    right_candidates = [i for i in (text.find(".", end), text.find("\n", end)) if i != -1]
    right = min(right_candidates) if right_candidates else len(text)
    return " ".join(text[left:right].split())[:240]


def _matches(patterns: list[re.Pattern[str]], text: str) -> list[re.Match[str]]:
    found = [m for p in patterns for m in p.finditer(text)]
    return sorted(found, key=lambda m: m.start())


def _evidence(text: str, matches: list[re.Match[str]]) -> str:
    sentences: list[str] = []
    for m in matches:
        sentence = _sentence(text, m.start(), m.end())
        if sentence not in sentences:
            sentences.append(sentence)
    return " / ".join(sentences[:2])


def classify(text: str) -> PermitSignal:
    blockers = _matches(_C_BLOCKERS, text)
    spans = [(m.start(), m.end()) for m in blockers]
    offers = [
        m for m in _matches(_C_SPONSORSHIP, text)
        if not any(m.start() < end and start < m.end() for start, end in spans)
    ]
    if blockers and offers:
        return PermitSignal(CONDITIONAL, _evidence(text, sorted(offers + blockers, key=lambda m: m.start())))
    if blockers:
        return PermitSignal(PERMIT_REQUIRED, _evidence(text, blockers))
    residence = _matches(_C_RESIDENCE, text)
    if residence:
        return PermitSignal(RESIDENCE_REQUIRED, _evidence(text, residence))
    sponsors = offers + _matches(_C_RELOCATION, text)
    if sponsors:
        return PermitSignal(SPONSORS, _evidence(text, sorted(sponsors, key=lambda m: m.start())))
    contract = _matches(_C_REMOTE_CONTRACT, text)
    if contract:
        return PermitSignal(REMOTE_CONTRACT, _evidence(text, contract))
    return PermitSignal(UNSTATED)
