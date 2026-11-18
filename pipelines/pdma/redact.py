"""Remove personal names from PDMA incident text before it leaves this machine.

PDMA reports name victims and house owners in several forms:
- "<name> s/o <father> r/o <place>" (s/o, d/o, w/o = son, daughter, wife of;
  r/o = resident of), often after an honorific ("Mr.", "Mst.");
- "<name> resident of <place>";
- "<name> (Age 13 years)";
- numbered lists of names ("Houses damaged: 1. <name> 2. <name>").

We replace the person part with "[person]" and keep places. Numbered list
items are kept only when they match a known place in that district's
gazetteer; anything else in a list is treated as a name.

This is a best-effort filter, not a guarantee. Two further safeguards apply
downstream: the LLM form has no field for names, and no free text is stored.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Collection

# A "name word": letters, apostrophes or dots, not a stop word that starts a new clause.
_STOP = (
    r"(?:and|the|a|an|in|on|at|of|to|from|due|was|were|is|are|has|had|died|drowned|injured|"
    r"while|when|who|whose|near|village|tehsil|district|resultantly|one|two|three|child|"
    r"children|boy|girl|man|woman|person|persons|people|aged|age|years|year|old|resident|"
    r"his|her|their|wife|son|daughter|also|with|by|for|following|reported|damaged|house)"
)
# A word boundary first (never start mid-word), then not a stop word and not
# the start of a relation marker like "r/o" or "s/o".
_WORD = rf"\b(?!{_STOP}\b)(?![RrSsDdWw]\s*/\s*[Oo0]\b)[A-Za-z][A-Za-z'.\-]*"
_CAP = rf"\b(?!{_STOP}\b)[A-Z][A-Za-z'\-]*\.?"  # capitalised name word (case-sensitive)
# s/o, d/o, w/o, also "s/0" and scan errors "Slo"; may be glued to the name ("Ullahs/o").
_REL = (r"(?:\b|(?<=[a-z]))[SsDdWw]\s*/\s*[Oo0]\b|\b[SsDdWw]lo\b|"
        r"\b(?:son|daughter|wife)\s+of\b")
_LOWER = rf"(?!{_STOP}\b)[a-z][a-z'\-]*"  # a lowercase word that is not a stop word
# Words that mark a phrase as a place, not a person ("Umar Khel", "Aziz Abad").
_PLACE_WORDS = {
    "khel", "kheil", "abad", "kili", "killi", "killay", "kalay", "kalai", "kaly", "kot", "dheri",
    "dherai", "banda", "pur", "garhi", "gari", "colony", "town", "arang", "qila", "masjid", "baba",
    "bazar", "bazaar", "chowk", "kacha", "pakka", "mohallah", "mohalla", "khwar", "nullah", "nala",
    "dara", "darra", "sar", "ghundai", "mena", "bandi", "maira", "kandao", "road", "bridge", "uc",
    "mouza", "mauza", "camp", "school", "hospital", "kas", "shumali", "janubi", "payeen", "bala",
}
# Damage words: a numbered item containing one is a description, not a name.
_DAMAGE_WORDS = {
    "roof", "room", "rooms", "wall", "walls", "collapsed", "damaged", "partially", "fully",
    "veranda", "boundary", "shop", "shops", "house", "houses", "cattle", "shed", "bridge",
    "road", "crops", "crop", "school", "mosque", "solar", "washed", "injured", "died", "dead",
}

_AGE = r"(?:\(\s*(?:age[d]?\s*)?\d{1,3}\s*(?:years?|yrs?)?\s*\)\s*|,?\s*aged?\s*\d{1,3}\s*(?:years?|yrs?)?\s*,?\s*)?"

# "[0-4 name words] [(age)] s/o <1-4 name words>" up to "r/o", punctuation or a stop word.
_PERSON = re.compile(
    rf"(?:(?:Mr|Mrs|Mst|Ms|Miss|Master|Malik|Haji)\.?\s+)?"
    rf"(?:{_WORD}\s+){{0,4}}{_AGE}(?:{_REL})\s*(?:{_WORD}\s*){{1,4}}",
    re.IGNORECASE,
)
_HONORIFIC = re.compile(rf"\b(?:Mr|Mrs|Mst|Ms|Miss)\.?\s*(?:{_WORD}\s*){{1,3}}", re.IGNORECASE)
# "house of <Name>", "namely <Name>, <Name>": the words after the cue are a name.
_CUE = re.compile(
    rf"\b(house|houses|shop|shops|property|crops|land|lands)\s+(of\s+)(?:{_WORD}\s*){{1,3}}{_AGE}"
    rf"(?:,\s*(?:{_WORD}\s*){{1,3}}{_AGE})*"
    rf"|\b(namely|named|owned\s+by|belonging\s+to)\s+()(?:{_WORD}\s*){{1,3}}{_AGE}"
    rf"(?:,\s*(?:{_WORD}\s*){{1,3}}{_AGE})*",
    re.IGNORECASE,
)
_RO = re.compile(r"\b[Rr]\s*/\s*[Oo0]\b|\bRio\b")
# Family relations: "sons of <Name>", "widow of <Name>", "children of <Name>".
_RELATION_OF = re.compile(
    rf"\b(sons?|daughters?|children|widow|husband|brother|sister|father|mother|wife)\s+of\s+"
    rf"(?:{_CAP}\s*){{1,4}}", re.IGNORECASE)
# "<Name Name> house" (possessive without "of"), "Bi Bi" written apart.
_BEFORE_HOUSE = re.compile(rf"(?:{_CAP}\s+){{1,3}}(?=(?:house|home)\b)")
_BIBI = re.compile(rf"(?:{_CAP}\s+)?\bBi\s+Bi\b(?:\s+{_CAP})?")
# "[person] of <Name Name> of <Place>": the middle part is a parent's name.
_PERSON_OF_NAME_OF = re.compile(rf"(?<=\[person\]\s)of\s+(?:{_CAP}\s*){{1,3}}(?=of\b)")
# Leftover of a mangled marker: "[person] /o Khan Alam Khan".
_SLASH_O = re.compile(rf"/\s*[Oo0]\s+(?:{_CAP}\s*){{1,4}}")
# A second name joined to a removed one: "[person] and Sher Nazim", "[person] , Noor Hakeem".
_AFTER_PERSON_AND = re.compile(rf"(?<=\[person\]\s)(and|&|,)\s+((?:{_CAP}\s*)(?:{_CAP}\s*|{_LOWER}\s+){{0,2}})")
# "<Name name> resident of": a capitalised word (then up to 2 more words) right before "resident of".
_BEFORE_RESIDENT = re.compile(rf"{_CAP}\s+(?:(?:{_CAP}|{_LOWER})\s+){{0,3}}(?=[-–]?\s*resident\s+of\b)")
# "<Name Name> (Age 13 years)" or "<Name>, aged 40".
_BEFORE_AGE = re.compile(rf"(?:{_CAP}\s+){{1,4}}(?=\(\s*(?:[Aa]ge[d]?\s*)?\d{{1,3}}|,?\s*[Aa]ged?\s+\d)")
# "<Name Name> was flooded away / drowned / swept away".
_BEFORE_VERB = re.compile(
    rf"(?:{_CAP}\s+){{1,3}}(?=(?:was|were|got|has\s+been)\s+(?:flooded|drowned|swept|died|killed|"
    rf"injured|washed|carried|trapped|missing))"
)
# Numbered list item: a capitalised word plus up to 3 words, up to the next item or punctuation.
_LIST_ITEM = re.compile(
    rf"(?<![\d.])(\d{{1,3}}\s*[.):-]\s*)([A-Z][A-Za-z'\-]*\.?(?:\s+[A-Za-z][A-Za-z'\-]*\.?){{0,3}}?)"
    rf"(?=\s*(?:\(|,|;|\.|$|\d{{1,3}}\s*[.):-]|[-–]?\s*resident\b|\[person\]))"
)
# Groups of capitalised words containing a common name word.
_NAME_WORDS = (
    "Muhammad|Mohammad|Muhammed|Mohammed|Syed|Sayed|Sayyed|Abdul|Abdur|Abdus|Bibi|Begum|Hazrat|"
    "Fazal|Gul|Ullah|Ullahs|Uddin|Ud-Din|Rehman|Rahman|Zada|Zaman|Khan|Shah|Ali|Ahmad|Ahmed|"
    "Hussain|Husain|Noor|Nur|Sher|Bakht|Akbar|Aziz|Iqbal|Jan|Zeb|Malik|Amin|Khalid|Tariq|Imran|"
    "Bilal|Usman|Umar|Ayaz|Ijaz|Ajmal|Akram|Aslam|Saleem|Naeem|Shahid|Zubair|Farooq|Javed|"
    "Asif|Arif|Hashim|Wali|Zahir|Nazir|Hameed|Rashid|Manzoor|Hakeem|Hakim"
)
_NAME_GROUP = re.compile(
    rf"(?:\b[A-Z][a-z'\-]+\s+){{0,3}}\b(?:{_NAME_WORDS})\b(?:\s+[A-Za-z][a-z'\-]+){{0,3}}"
)


def _looks_like_place(phrase: str, is_place: Callable[[str], bool], following: str = "") -> bool:
    words = {w.lower().strip(".,") for w in phrase.split()}
    next_word = following.split()[0].lower().strip(".,") if following.split() else ""
    return is_place(phrase) or bool(words & _PLACE_WORDS) or next_word in _PLACE_WORDS


def _keep_if_place(is_place: Callable[[str], bool], replacement: str = "[person]"):
    def sub(match: re.Match) -> str:
        words = match.group(0)
        following = match.string[match.end():match.end() + 30]
        return words if _looks_like_place(words, is_place, following) else replacement + " "
    return sub


def _name_group_sub(is_place: Callable[[str], bool]):
    """Remove a name-word group, but keep it when it is (part of) a place."""

    def sub(match: re.Match) -> str:
        words = match.group(0)
        before = match.string[max(0, match.start() - 25):match.start()].lower()
        following = match.string[match.end():match.end() + 30]
        if _looks_like_place(words, is_place, following):
            return words
        if re.search(r"(?:village|mauza|mouza|uc|at|of|in|near)\s*$", before) and not re.search(
            r"(?:house|crops|land|shop)s?\s+of\s*$", before
        ):
            return words  # "village Wali Abad", "in Mir Khan Arang": likely a place
        return "[person] "
    return sub


def redact_names(text: str, is_place: Callable[[str], bool] | None = None) -> str:
    """Replace names with "[person]". `is_place(text)` says if a phrase is a known place."""

    is_place = is_place or (lambda _: False)
    text = _PERSON.sub("[person] ", text)
    text = _HONORIFIC.sub("[person] ", text)
    text = _CUE.sub(lambda m: f"{m.group(1) or m.group(3)} {m.group(2) or ''}[person] ", text)
    text = _RO.sub("resident of", text)
    text = _SLASH_O.sub("[person] ", text)
    text = _RELATION_OF.sub(lambda m: f"{m.group(1)} of [person] ", text)
    text = _BIBI.sub("[person] ", text)
    text = _BEFORE_HOUSE.sub(_keep_if_place(is_place), text)
    text = _BEFORE_RESIDENT.sub(_keep_if_place(is_place), text)
    text = _BEFORE_AGE.sub(_keep_if_place(is_place), text)
    text = _BEFORE_VERB.sub(_keep_if_place(is_place), text)

    def list_item(m: re.Match) -> str:
        item = m.group(2)
        words = {w.lower().strip(".,") for w in item.split()}
        following = m.string[m.end():m.end() + 30]
        if not item.strip() or words & _DAMAGE_WORDS or _looks_like_place(item, is_place, following):
            return m.group(0)
        return f"{m.group(1)}[person] "

    text = _LIST_ITEM.sub(list_item, text)
    text = _NAME_GROUP.sub(_name_group_sub(is_place), text)
    text = _PERSON_OF_NAME_OF.sub("of [person] ", text)
    for _ in range(3):  # chains: "[person] , A B and C D"
        text = _AFTER_PERSON_AND.sub(
            lambda m: m.group(0) if _looks_like_place(m.group(2), is_place)
            else f"{m.group(1)} [person] ", text)
    return re.sub(r"\s{2,}", " ", text).strip()


_MARKER_WINDOW = re.compile(
    rf"(?:\S+\s+){{0,4}}\S*(?:{_REL}|\b(?:Mr|Mrs|Mst)\.?\s)\S*(?:\s+\S+){{0,4}}", re.IGNORECASE
)


def safe_redact(text: str, is_place: Callable[[str], bool] | None = None) -> str:
    """`redact_names`, then wipe 4 words either side of any marker that is left.

    The result never contains a name marker, so it is safe to send out.
    """

    text = redact_names(text, is_place)
    for _ in range(10):
        if not has_name_markers(text):
            return text
        text = _MARKER_WINDOW.sub("[person]", text, count=1)
    return "[text withheld: could not remove names]"


NAME_MARKERS = re.compile(rf"{_REL}|\b(?:Mr|Mrs|Mst)\.?\s+[A-Z]", re.IGNORECASE)


def has_name_markers(text: str) -> bool:
    """True if text still contains s/o-style markers or honorifics followed by a name."""

    return bool(NAME_MARKERS.search(text))


def place_checker(place_keys: Collection[str], key_fn: Callable[[str], str]) -> Callable[[str], bool]:
    """Build `is_place` from a set of gazetteer name keys."""

    keys = set(place_keys)
    return lambda phrase: bool(key_fn(phrase)) and key_fn(phrase) in keys
