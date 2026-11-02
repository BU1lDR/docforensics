"""Value normalisers. What cannot be read comes back as None (similarities as 0.0) and is never repaired by guessing: an O
inside a number stays an O, and a date that reads two ways says so. Only ASCII digits and letters are read."""
import re
import unicodedata
from datetime import date
from decimal import Decimal
from difflib import SequenceMatcher

MAX_LEN = 40         # no amount or date on a page is longer; a longer string is not one
MAX_WORDS_LEN = 300  # nor an amount in words

_MINUS, _RUPEE = chr(0x2212), chr(0x20B9)
_DASHES = "".join(chr(c) for c in range(0x2010, 0x2016))  # hyphen to horizontal bar: text layers use them inside words
# 123,456 (Western), 1,23,456 (Indian) or no grouping, then an optional fraction
_NUM = r"(?:\d{1,3}(?:,\d{3})+|\d{1,2}(?:,\d{2})+,\d{3}|\d+)(?:\.\d+)?"
_AMOUNT = re.compile(
    rf"(?P<neg1>[-{_MINUS}])?\s*(?:{_RUPEE}|rs\.?|inr)?\s*(?P<open>\()?\s*(?P<neg2>[-{_MINUS}])?\s*(?P<n>{_NUM})"
    r"\s*(?P<neg3>-)?\s*(?(open)\))\s*(?:/-)?\s*(?P<side>dr|cr)?\.?", re.I | re.A)
_NUMDATE = re.compile(r"(\d{1,4})([/.-])(\d{1,2})\2(\d{1,4})", re.A)
_DMY = re.compile(r"(\d{1,2})(?:st|nd|rd|th)?[\s/.-]+([a-z]+)\.?[\s/.,-]*(\d{4}|\d{2})", re.I | re.A)
_MDY = re.compile(r"([a-z]+)\.?\s*(\d{1,2})(?:st|nd|rd|th)?\s*,?\s*(\d{4}|\d{2})", re.I | re.A)
_MONTHS = "january february march april may june july august september october november december".split()

_ONES = {w: i for i, w in enumerate("one two three four five six seven eight nine".split(), 1)}
_TEENS = {w: i for i, w in enumerate(
    "ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split(), 10)}
_TENS = {w: i * 10 for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split(), 2)}
_SMALL = _ONES | _TEENS | _TENS
_SCALES = (("crore", 10**7), ("lakh", 10**5), ("thousand", 10**3))
_ALIAS = {"fourty": "forty", "lakhs": "lakh", "lac": "lakh", "lacs": "lakh", "crores": "crore", "paisa": "paise",
          "rupee": "rupees"}
_TITLES = {"mr", "mrs", "ms", "miss", "mx", "dr", "prof", "shri", "smt"}


def _match(s: str) -> re.Match | None:
    t = " ".join(s.split())  # no-break and other spaces become plain ones
    return _AMOUNT.fullmatch(t) if len(t) <= MAX_LEN else None


def parse_amount(s: str) -> Decimal | None:
    """'1,23,456.78', '123,456.78', 'Rs. 5,000/-', '(1,200.00)' as a Decimal; None unless the whole string is an amount."""
    m = _match(s)
    if not m:
        return None
    v = Decimal(m["n"].replace(",", ""))
    return -v if any(m[g] for g in ("neg1", "open", "neg2", "neg3")) else v


def fmt_amount(v: Decimal) -> str | None:
    """'52000.00', the stored form of an amount. None when cents would be lost (1.005 is not rounded) or the number is too
    big to be money."""
    if not v:
        return "0.00"  # also -0.00
    whole, _, frac = format(v, "f").partition(".")
    if frac[2:].strip("0") or len(whole) > 15:
        return None
    return f"{whole}.{frac[:2].ljust(2, '0')}"


def amount_side(s: str) -> str | None:
    """'dr' or 'cr' from a trailing Dr/Cr marker on a readable amount."""
    m = _match(s)
    return m["side"].lower() if m and m["side"] else None


def _ymd(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def _year(y: str) -> int:
    """Two-digit years: 00-68 are 20xx, 69-99 are 19xx."""
    return int(y) if len(y) == 4 else 2000 + int(y) if int(y) < 69 else 1900 + int(y)


def _month(word: str) -> int | None:
    """1-12 from 'jan', 'Sept' or 'January'; under three letters, or not the start of a month name, is no month."""
    w = word.lower()
    return next((i for i, m in enumerate(_MONTHS, 1) if len(w) >= 3 and m.startswith(w)), None)


def parse_date(s: str) -> tuple[date | None, bool]:
    """(date, ambiguous). Day comes first: 04/05/2026 is 4 May and ambiguous, as it also reads 5 April. A month over 12 is
    not read as month-first: 03/13/2026 is (None, False). Year-first and month-name dates are never ambiguous."""
    t = " ".join(s.split())
    if len(t) > MAX_LEN:
        return None, False
    if m := _NUMDATE.fullmatch(t):
        a, _, b, c = m.groups()
        if len(a) == 4 and len(c) <= 2:  # 2026-03-12
            return _ymd(int(a), int(b), int(c)), False
        if len(a) > 2 or len(c) not in (2, 4):
            return None, False
        y = _year(c)
        dm, md = _ymd(y, int(b), int(a)), _ymd(y, int(a), int(b))
        return (dm, md is not None and md != dm) if dm else (None, False)
    for pat, day_first in ((_DMY, True), (_MDY, False)):
        if m := pat.fullmatch(t):
            x, y_, z = m.groups()
            day, name = (x, y_) if day_first else (y_, x)
            month = _month(name)
            return (_ymd(_year(z), month, int(day)) if month else None), False
    return None, False


def _group(ws: list[str]) -> int | None:
    """1-999 from words: 'six hundred and fifty', 'twenty five', 'nine'."""
    n = 0
    if "hundred" in ws:
        if ws.index("hundred") != 1 or ws[0] not in _ONES:
            return None
        n, ws = _ONES[ws[0]] * 100, ws[2:]
        if ws[:1] == ["and"] and len(ws) > 1:
            ws = ws[1:]
    if not ws:
        return n or None
    if len(ws) == 1:
        v = _SMALL.get(ws[0])
    elif len(ws) == 2 and ws[0] in _TENS and ws[1] in _ONES:
        v = _TENS[ws[0]] + _ONES[ws[1]]
    else:
        return None
    return None if v is None else n + v


def _whole(ws: list[str]) -> int | None:
    """A whole number from words, largest scale first: 'two crore five lakh', 'five thousand and fifty'."""
    total = 0
    for name, scale in _SCALES:  # each scale at most once and in this order: a stray one is left in the words and fails
        if name in ws:
            i = ws.index(name)
            g = _group(ws[:i])
            if g is None:
                return None
            total, ws = total + g * scale, ws[i + 1:]
            if ws[:1] == ["and"]:
                ws = ws[1:]
                if not ws:
                    return None
    if ws or not total:
        g = _group(ws)
        if g is None:
            return None
        total += g
    return total


def amount_in_words(s: str) -> Decimal | None:
    """'Rupees One Lakh Twenty Thousand Only' or 'Five Thousand and Fifty Paise' (Indian system) as a Decimal; None unless
    the words are one well-formed amount. Paise need an 'and' after the rupees."""
    if len(s) > MAX_WORDS_LEN:
        return None
    ws = [_ALIAS.get(w, w) for w in re.sub(f"[-,.{_DASHES}]", " ", s.lower()).split()]
    ws = [w for w in ws if w not in ("rupees", "rs", "inr")]
    if ws[-1:] == ["only"]:
        ws.pop()
    paise = 0
    if ws[-1:] == ["paise"]:
        if "and" not in ws:
            return None
        i = len(ws) - 1 - ws[::-1].index("and")
        paise = _group(ws[i + 1:-1])
        if paise is None or paise > 99:
            return None
        ws = ws[:i]
    whole = _whole(ws)
    return None if whole is None else Decimal(whole) + Decimal(paise) / 100


def _ratio(a: str, b: str) -> float:
    """difflib's ratio, made symmetric by always comparing the pair in the same order."""
    a, b = sorted((a, b))
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def _name_tokens(s: str) -> list[str]:
    return [t for t in re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", s).casefold()) if t not in _TITLES]


def _expand(ts: list[str], other: list[str]) -> list[str]:
    """An initial becomes the full name it starts in the other list (each full name used once)."""
    pool = [t for t in other if len(t) > 1]
    out = []
    for t in ts:
        full = next((p for p in pool if len(t) == 1 and p.startswith(t)), None)
        if full:
            pool.remove(full)
        out.append(full or t)
    return out


def name_similarity(a: str, b: str) -> float:
    """0..1. Order, case, titles and punctuation do not matter and an initial matches the name it starts. 0.0 if either
    side has no name left once titles are dropped."""
    ta, tb = _name_tokens(a), _name_tokens(b)
    if not ta or not tb:
        return 0.0
    return _ratio(" ".join(sorted(_expand(ta, tb))), " ".join(sorted(_expand(tb, ta))))


def text_similarity(a: str, b: str) -> float:
    """0..1 on text with case, spacing and line breaks ignored; 0.0 if either side is empty."""
    x, y = (" ".join(unicodedata.normalize("NFKC", s).casefold().split()) for s in (a, b))
    return _ratio(x, y) if x and y else 0.0
