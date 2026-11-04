"""Drawing helpers shared by the layouts. Text is placed absolutely; every run given a key has its box recorded in the 200-DPI
pixels the reader reports, computed from the font metrics (they match the text layer to about 0.1 px)."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation

import pymupdf

PX = 200 / 72
PAGE = (595, 842)  # A4 in points
_FONT = {False: ("helv", pymupdf.Font("helv")), True: ("hebo", pymupdf.Font("hebo"))}
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")  # fixed names: strftime would follow the machine's language
_ONES = ("", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen",
         "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen")
_TENS = ("", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety")


@dataclass
class Drawn:
    pdf: bytes
    truth: dict  # type, layout, fields {name: value}, boxes {key: [page, x0, y0, x1, y1]}, rows [{date, ..., balance}]


def money(v) -> str:
    """12,34,567.50: two decimals and Indian grouping (the last three digits, then pairs)."""
    whole, frac = f"{abs(Decimal(v)):.2f}".split(".")
    head, groups = whole[:-3], []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return f"{'-' if Decimal(v) < 0 else ''}{','.join(groups + [whole[-3:]])}.{frac}"


def text_width(s: str, size: float, bold: bool = False) -> float:
    """The width in points of s set in the layouts' font."""
    return _FONT[bold][1].text_length(s, fontsize=size)


def _under_hundred(n: int) -> str:
    return _ONES[n] if n < 20 else _TENS[n // 10] + (f" {_ONES[n % 10]}" if n % 10 else "")


def words(n: int) -> str:
    """'Rupees Forty Seven Thousand Two Hundred Only': whole rupees in the Indian system (crore, lakh, thousand), written
    here without the reader's code so the two can disagree."""
    if not 0 <= n < 10**9:
        raise ValueError(f"cannot write {n} in words")
    parts = []
    for name, size in (("Crore", 10**7), ("Lakh", 10**5), ("Thousand", 10**3)):
        q, n = divmod(n, size)
        if q:
            parts.append(f"{_under_hundred(q)} {name}")
    h, n = divmod(n, 100)
    if h:
        parts.append(f"{_ONES[h]} Hundred")
    if n:
        parts.append(_under_hundred(n))
    return f"Rupees {' '.join(parts) or 'Zero'} Only"


def norm(kind: str, text: str, date_fmt: str | tuple[str, ...] = "%d/%m/%Y") -> str | None:
    """What a reader should make of drawn text: the stored form of an amount, or of a date in the first of date_fmt that fits;
    None when it is neither. Other kinds come back as drawn."""
    try:
        if kind == "amount":
            v = Decimal(text.replace(",", ""))
            return f"{v:.2f}" if v.is_finite() else None
        if kind == "date":
            for fmt in (date_fmt,) if isinstance(date_fmt, str) else date_fmt:
                try:
                    return datetime.strptime(text, fmt).date().isoformat()
                except ValueError:
                    pass
            return None
    except InvalidOperation:
        return None
    return text


class Sheet:
    """A PDF being drawn page by page. Producer and creation date go into the metadata, as a real issuer's software would."""

    def __init__(self, producer: str, created: datetime) -> None:
        self.doc = pymupdf.open()
        stamp = created.strftime("D:%Y%m%d%H%M%S+05'30'")
        self.doc.set_metadata({"producer": producer, "creator": producer, "creationDate": stamp, "modDate": stamp})
        self.page: pymupdf.Page
        self.boxes: dict[str, list[float]] = {}

    def new_page(self) -> None:
        self.page = self.doc.new_page(width=PAGE[0], height=PAGE[1])

    def text(self, x: float, y: float, s: str, size: float = 9.0, bold: bool = False, align: str = "left",
             key: str | dict[int, str] | None = None) -> None:
        """One run of text with its baseline at y. `key` names the box of the whole run, or {word index: name} per word."""
        name, font = _FONT[bold]

        def width(t: str) -> float:
            return text_width(t, size, bold)

        if align == "right":
            x -= width(s)
        self.page.insert_text((x, y), s, fontname=name, fontsize=size)
        words = s.split(" ")
        spans = {k: (x, x + width(s)) for k in [key]} if isinstance(key, str) else {
            k: (x + (width(" ".join(words[:i]) + " ") if i else 0), x + (width(" ".join(words[:i]) + " ") if i else 0) + width(words[i]))
            for i, k in (key or {}).items()}
        top, bottom = (y - font.ascender * size) * PX, (y - font.descender * size) * PX
        for k, (x0, x1) in spans.items():
            self.boxes[k] = [self.doc.page_count, round(x0 * PX, 2), round(top, 2), round(x1 * PX, 2), round(bottom, 2)]

    def region(self, key: str, x0: float, y0: float, x1: float, y1: float) -> None:
        """The box of something drawn that is not text (a stamp, a signature), given in points."""
        self.boxes[key] = [self.doc.page_count, round(x0 * PX, 2), round(y0 * PX, 2), round(x1 * PX, 2), round(y1 * PX, 2)]

    def pdf(self) -> bytes:
        data = self.doc.tobytes()
        self.doc.close()
        return data
