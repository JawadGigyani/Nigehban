"""Remove personal names from PDMA incident text before it leaves this machine.

PDMA reports name victims in a standard pattern: "<name> s/o <father> r/o
<place>" (s/o, d/o, w/o = son, daughter, wife of; r/o = resident of), often
after an honorific ("Mr.", "Mst."). We replace the person part with
"[person]" and keep "r/o <place>", which is a location we need.

This is a best-effort filter, not a guarantee: a name written without these
markers can survive. Two further safeguards apply downstream: the LLM schema
has no field for names, and no free text is stored, only structured fields.
"""

from __future__ import annotations

import re

# A "name word": letters, apostrophes or dots, not a stop word that starts a new clause.
_STOP = (
    r"(?:and|the|a|an|in|on|at|of|to|from|due|was|were|is|are|has|had|died|drowned|injured|"
    r"while|when|who|whose|near|village|tehsil|district|resultantly|one|two|three|child|"
    r"children|boy|girl|man|woman|person|persons|people|aged|age|years|year|old|resident)"
)
# A word boundary first (never start mid-word), then not a stop word and not
# the start of a relation marker like "r/o" or "s/o".
_WORD = rf"\b(?!{_STOP}\b)(?![RrSsDdWw]\s*/\s*[Oo]\b)[A-Za-z][A-Za-z'.\-]*"
_REL = r"\b[SsDdWw]\s*/\s*[Oo]\b|\b(?:son|daughter|wife)\s+of\b"

_AGE = r"(?:\(\s*(?:age[d]?\s*)?\d{1,3}\s*(?:years?|yrs?)?\s*\)\s*|,?\s*aged?\s*\d{1,3}\s*(?:years?|yrs?)?\s*,?\s*)?"

# "[0-4 name words] [(age)] s/o <1-4 name words>" up to "r/o", punctuation or a stop word.
_PERSON = re.compile(
    rf"(?:(?:Mr|Mrs|Mst|Ms|Miss|Master|Malik|Haji)\.?\s+)?"
    rf"(?:{_WORD}\s+){{0,4}}{_AGE}(?:{_REL})\s*(?:{_WORD}\s*){{1,4}}",
    re.IGNORECASE,
)
_HONORIFIC = re.compile(rf"\b(?:Mr|Mrs|Mst|Ms|Miss)\.?\s+(?:{_WORD}\s*){{1,3}}", re.IGNORECASE)
# "house of <Name>", "namely <Name>, <Name>": the words after the cue are a name.
_CUE = re.compile(
    rf"\b(house|shop|property|namely|named)\s+(of\s+)?(?:{_WORD}\s*){{1,3}}{_AGE}"
    rf"(?:,\s*(?:{_WORD}\s*){{1,3}}{_AGE})*",
    re.IGNORECASE,
)
_RO = re.compile(r"\b[Rr]\s*/\s*[Oo]\b")

NAME_MARKERS = re.compile(rf"{_REL}|\b(?:Mr|Mrs|Mst)\.?\s+[A-Z]", re.IGNORECASE)


def redact_names(text: str) -> str:
    text = _PERSON.sub("[person] ", text)
    text = _HONORIFIC.sub("[person] ", text)
    text = _CUE.sub(lambda m: f"{m.group(1)} {m.group(2) or ''}[person] ", text)
    text = _RO.sub("resident of", text)
    return re.sub(r"\s{2,}", " ", text).strip()


_MARKER_WINDOW = re.compile(
    rf"(?:\S+\s+){{0,4}}\S*(?:{_REL}|\b(?:Mr|Mrs|Mst)\.?\s)\S*(?:\s+\S+){{0,4}}", re.IGNORECASE
)


def safe_redact(text: str) -> str:
    """`redact_names`, then wipe 4 words either side of any marker that is left.

    The result never contains a name marker, so it is safe to send out.
    """

    text = redact_names(text)
    for _ in range(10):
        if not has_name_markers(text):
            return text
        text = _MARKER_WINDOW.sub("[person]", text, count=1)
    return "[text withheld: could not remove names]"


def has_name_markers(text: str) -> bool:
    """True if text still contains s/o-style markers or honorifics followed by a name."""

    return bool(NAME_MARKERS.search(text))
