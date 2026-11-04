"""The guard on what a language model may say (design 7.7). Its wording is used only if it cites ids it was given, states no number
or date that the evidence it saw does not hold, and passes no verdict. Anything else is dropped and the template wording stays.
Numbers written out in words are not read: the prompt asks for digits, and the capabilities list says this is a limit."""
import re
from datetime import date
from decimal import Decimal

from ..understand.normalise import parse_date

MAX_CHARS = 1200
_ID = re.compile(r"\bF-\d+\b|\bD\d+(?:-f\d+)?\b", re.I)  # a finding (F-004), a document (D2) or a field (D2-f12)
_MON = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
_DATE = re.compile(  # 2026-10-03, 03/10/2026, 3 October 2026, October 3rd, 2026
    rf"\b\d{{1,4}}([/.-])\d{{1,2}}\1\d{{1,4}}\b|\b\d{{1,2}}(?:st|nd|rd|th)?\s+{_MON}\s*,?\s*\d{{4}}\b"
    rf"|\b{_MON}\s+\d{{1,2}}(?:st|nd|rd|th)?\s*,?\s*\d{{4}}\b", re.I | re.A)
_NUMBER = re.compile(r"\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?", re.A)  # 82,000.00 or 1,23,456 or 52000
_VERDICT = re.compile(r"fraud|forg|fake|counterfeit|tamper|falsif|fabricat|doctored", re.I)


def _facts(text: str) -> tuple[set[date], set[Decimal]]:
    """The dates and the numbers a text states. An id is no figure, and a date is one fact, not three numbers."""
    dates: set[date] = set()

    def take(m: re.Match) -> str:
        d = parse_date(m[0])[0]
        if d is None:
            return m[0]  # not a date after all: its digits are read as numbers
        dates.add(d)
        return " "

    text = _DATE.sub(take, _ID.sub(" ", text))
    return dates, {Decimal(n.replace(",", "")) for n in _NUMBER.findall(text)}


def check(output: object, evidence_ids: set[str], evidence_text: str) -> str | None:
    """Why `output` may not be used, or None if it may."""
    if not (isinstance(output, dict) and set(output) == {"text", "cites"} and isinstance(output["text"], str) and output["text"].strip()
            and isinstance(output["cites"], list) and all(isinstance(c, str) for c in output["cites"])):
        return "malformed"
    text, cites = output["text"], output["cites"]
    if len(text) > MAX_CHARS:
        return "too long"
    if not cites:
        return "no citation"
    known = {i.casefold() for i in evidence_ids}
    if any(c.casefold() not in known for c in cites + _ID.findall(text)):
        return "unknown id"
    if _VERDICT.search(text):
        return "verdict wording"
    if any(c.isdigit() and not c.isascii() for c in text):  # digits of another script would slip past the number check
        return "number not in the evidence"
    dates, numbers = _facts(text)
    seen_dates, seen_numbers = _facts(evidence_text)
    if not dates <= seen_dates:
        return "date not in the evidence"
    if not numbers <= seen_numbers:
        return "number not in the evidence"
    return None


def guard(output: dict, evidence_ids: set[str], evidence_text: str) -> bool:
    """True if the model's output may be shown (design 7.7)."""
    return check(output, evidence_ids, evidence_text) is None
