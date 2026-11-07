"""Extraction (design 7.3): header fields found by their label, table cells by their column heading and row, and for a type
we have no spec for, the generic path. A field that cannot be found is still returned, empty and at confidence 0, so a gap
never passes unseen."""
import re
from dataclasses import dataclass
from itertools import count

from ..config import Thresholds
from ..findings import add_findings, doc_evidence, limitation
from ..model import Box, Case, Document, Field, Word
from ..pipeline import Ctx, guarded
from .confidence import field_conf
from .layout import LINE_TOL, Line, find_phrase, issuer_line, lines_of, similar, straightened, text_of, unturned, union
from .normalise import amount_side, fmt_amount, parse_amount, parse_date
from .specs import ColumnSpec, FieldSpec, TableSpec, TypeSpec, load_specs

TITLE_SCORE = 0.9     # the biggest line on page 1 is the institution, until a label says otherwise
GENERIC_SCORE = 0.8   # a "label: value" pair on a page of an unsupported type: the label is not one we know
DATE_AMBIGUOUS = 0.5  # validator for 04/05/2026: 4 May or 5 April
DATE_INFERRED = 0.9   # ... in a document whose other dates are day-first
BELOW_REACH = 2.5     # line heights: how far under its label a value may sit
BELOW_SCORE = 0.9     # a value read from under its label is trusted a little less than one beside it
WRAP_REACH = 1.8      # line heights, centre to centre: how close under the line before a wrapped line sits
WRAP_ALIGN = 0.5      # line heights: how far a wrapped line's left edge may be from the first line's
PITCH_TOL = 0.3       # share of the line pitch: how far the spacing of lines above a centred label may differ from that below it
BAND = 3              # lines a table heading may be set over: 'Withdrawal' over 'Amount' over '(INR)' in a narrow column
BAND_TALL = 0.3       # share of a heading line's height: how much taller or shorter the line under it may be and still be part of it
ROW_MARGIN = 1.3      # a line between two table rows goes to the nearer one only if the other is this many times farther away
ROW_DOUBT = 0.5       # confidence of a text cell next to a line that could be the rest of it or of the row after (below the review line)
GENERIC_NOTE = "unsupported type: generic extraction"
UNSUPPORTED = "Unsupported document type: generic extraction only, no document-specific checks"
_SEPARATORS = {":", "-", chr(0x2013), "="}
_LABEL_TAIL = {"name", "number", "no", "id", "code", "date", "amount", "amt", "details", "required", "optional", "in", "months",
               "inr", "rs", chr(0x20B9)}  # words that go on a label ('Account Holder Name', 'Amount (INR)'), and never start a value
_NUM_DATE = re.compile(r"(\d{1,2})([/.-])(\d{1,2})\2(\d{2}|\d{4})", re.A)
_CENTS = re.compile(r"\d\.\d\d(?!\d)", re.A)
_MISREAD = re.compile(r"(?=(?:\D*\d){4})\d[\d.,]*[.,][\d.,]*\d", re.A)  # four digits or more with separators, and no amount: '57.500.00'
_DATEISH = re.compile(r"[\dOoIl|SB]{1,4}(?P<sep>[/.-])[\dOoIl|SB]{1,2}(?P=sep)[\dOoIl|SB]{2,4}", re.A)  # the shape of a numeric date, digits or what they are misread as
_CURRENCY = re.compile(rf"{chr(0x20B9)}|\brs\b|\binr\b|/-", re.I)
_UNIT = re.compile(rf"\s*\((?:in\s+)?(?:inr|rs\.?|rupees|{chr(0x20B9)})\)\s*$", re.I)  # '(INR)' after a heading: the currency, not the name
_AMOUNT = ColumnSpec(name="amount", kind="amount", headers=[])  # the two columns of a table that marks its amounts Dr or Cr (TableSpec.marked)
_MARK = ColumnSpec(name="marker", kind="text", headers=[])


def _said(text: str) -> str:
    """The letters of a mark in lower case: 'Dr', 'DR.' and '(dr)' read the same."""
    return re.sub(r"[^a-z]", "", text.casefold())


@dataclass
class _Head:
    x0: float
    x1: float
    col: str | None  # the column this heading names, None if no known wording matched
    score: float
    text: str = ""  # the heading as printed, without its unit


def _day_first_proven(doc: Document) -> bool:
    """True if some date in the document can only be day-first (13/05/2026): then 04/05/2026 is day-first too."""
    for page in doc.pages:
        for w in page.words:
            m = _NUM_DATE.fullmatch(w.text)
            if m and int(m[1]) > 12 and parse_date(w.text)[0] is not None:
                return True
    return False


def _date_runs(words: list[Word]) -> list[list[Word]]:
    """The runs of 1-4 words that read as a date, left to right. Four is a weekday and a date: 'Mon 03 Nov 2025'."""
    out, i = [], 0
    while i < len(words):
        for n in (4, 3, 2, 1):
            if i + n <= len(words) and parse_date(text_of(words[i:i + n]))[0] is not None:
                out.append(words[i:i + n])
                i += n
                break
        else:
            i += 1
    return out


def _joined(words: list[Word]) -> str:
    """The words as one text, but a line that goes on from a word ending in a hyphen or a slash is joined to it without a space:
    a browser breaks a long reference there ('...-4471-' over 'ONLINE'), and the reference has none."""
    out = words[0].text if words else ""
    for prev, w in zip(words, words[1:]):
        new_line = (w.box[1] + w.box[3] - prev.box[1] - prev.box[3]) / 2 > LINE_TOL * (prev.box[3] - prev.box[1])
        out += ("" if new_line and len(prev.text) > 1 and prev.text[-1] in "-/" else " ") + w.text
    return out


def _reads(kind: str, text: str) -> bool:
    if kind == "date":
        return parse_date(text)[0] is not None
    if kind == "amount":
        return parse_amount(text) is not None
    return bool(text.strip())


def _holds(kind: str, text: str) -> bool:
    """Whether the cell of an anchor column holds what a row has there: a value that reads, or one that does not but has the shape of
    it: in an amount column a number ('57.500.00', where a scan at low resolution turned the comma of '57,500.00' into a point), in a
    date column a date ('O3/05/2026', the letter for the digit, or a month over 12). That line is a row whose cell is unreadable, and
    not a line left out as if it were not there: a sum or a balance chain over the rows that were read would then be short of it."""
    return (_reads(kind, text) or (kind == "amount" and _MISREAD.fullmatch(text) is not None)
            or (kind == "date" and _DATEISH.fullmatch(text) is not None))


def _under(words: list[Word], heads: list["_Head"]) -> int:
    """The heading a run of words goes under: the one it overlaps most, or else the one nearest sideways."""
    x0, x1 = min(w.box[0] for w in words), max(w.box[2] for w in words)
    gaps = [max(h.x0 - x1, x0 - h.x1) for h in heads]  # negative: the overlap
    return gaps.index(min(gaps))


def _leading_date(cell: list[Word], heads: list["_Head"], dates: tuple[int, ...]) -> int:
    """How many words at the start of a cell are a date that stands under a date heading when the cell as a whole goes under another
    (0 if none). OCR boxes run wider than their text, so a date whose box is within the cell gap of the narration beside it reads as one
    cell with it; the row then has no date in its first column and was left out, amounts and all."""
    n = next((n for n in (4, 3, 2, 1) if n < len(cell) and _holds("date", text_of(cell[:n]))), 0)
    own = _under(cell[:n], heads) if n else -1
    return n if own in dates and _under(cell, heads) != own else 0


def _parts(line: Line, heads: list["_Head"], dates: tuple[int, ...]) -> list[list[Word]]:
    """The cells of a line, with a date at the start of a cell split off where it stands under a date heading (see _leading_date)."""
    out: list[list[Word]] = []
    for cell in line.cells:
        n = _leading_date(cell, heads, dates)
        out += [cell[:n], cell[n:]] if n else [cell]
    return out


def _amount_like(text: str) -> bool:
    """An amount with cents or a currency mark: a bare 5 or 411001 is not one."""
    return parse_amount(text) is not None and bool(_CENTS.search(text) or _CURRENCY.search(text))


def _finishes_label(word: Word) -> bool:
    return word.text.casefold().strip("().,") in _LABEL_TAIL


def _segments(line: Line) -> list[list[Word]]:
    """The words of a line cut before every cell but the first that holds a word ending in a colon: 'Invoice No: 417' beside a
    name, or 'Date: 12 Oct' beside another pair, is a pair of its own, and its label does not take in the text beside it."""
    out: list[list[Word]] = [[]]
    for i, cell in enumerate(line.cells):
        if i and any(w.text.endswith(":") for w in cell):
            out.append([])
        out[-1] += cell
    return out


def _label_value(words: list[Word]) -> tuple[str, list[Word]] | None:
    """('quote date', value words) for 'Quote Date: 31/03/2026' and for 'Quoted Total 45,000.00' (a date or an amount at the
    end of the words); None for any other words. A label has no digits, so table rows never read as pairs."""
    colon = next((i for i, w in enumerate(words) if w.text.endswith(":")), None)
    if colon is not None:
        split = colon + 1
    else:
        split = next((len(words) - m for m in (3, 2, 1) if m < len(words)
                      and (parse_date(text_of(words[-m:]))[0] is not None or _amount_like(text_of(words[-m:])))), None)
    if split is None:
        return None
    value = words[split:]
    while value and value[0].text in _SEPARATORS:
        value = value[1:]
    label = " ".join(text_of(words[:split]).replace(":", " ").split())
    if not value or len(label) > 40 or len(label.split()) > 6 or any(c.isdigit() for c in label) \
            or sum(c.isalpha() for c in label) < 2:
        return None
    return label, value


class _Extractor:
    def __init__(self, doc: Document, th: Thresholds, spec: TypeSpec | None = None):
        self.doc, self.th = doc, th
        self.tspec = spec.table if spec else None
        self.stops = [label for f in spec.fields for label in f.labels if f.name in spec.table.ends_at] if spec and spec.table else []
        self._headings: set[int] | None = None
        self.labels = [] if spec is None else [*(label for f in spec.fields for label in (*f.labels, *f.colon_labels)),
                                               *(h for c in (spec.table.columns if spec.table else []) for h in c.headers)]
        straight = {p.n: straightened(p) for p in doc.pages}  # a scan is read as the page would stand upright
        self.lines = {n: lines_of(page) for n, (page, _) in straight.items()}
        self.turn = {n: deg for n, (_, deg) in straight.items()}
        self.page_class = {p.n: p.quality_class for p in doc.pages}
        self.dayfirst = _day_first_proven(doc)
        self.ids = count(1)

    # --- building fields

    def make(self, name: str, kind: str, words: list[Word], page: int, box: Box, value: str | None, validator: float,
             score: float, *, row: int | None = None, role: str = "", note: str = "") -> Field:
        conf = field_conf([w.conf for w in words], self.page_class.get(page, "text-layer"), score, validator, self.th)
        return Field(id=f"{self.doc.id}-f{next(self.ids)}", doc=self.doc.id, name=name, raw=text_of(words), value=value,
                     kind=kind, conf=conf, word_ids=[w.id for w in words], page=page, box=box, row=row, role=role, note=note)

    def missing(self, name: str, kind: str, note: str, *, page: int = 0, box: Box = (0.0, 0.0, 0.0, 0.0),
                row: int | None = None, role: str = "") -> Field:
        return self.make(name, kind, [], page, box, None, 1.0, 0.0, row=row, role=role, note=note)

    def read(self, kind: str, text: str, signed: bool = False) -> tuple[str | None, float, str]:
        """(stored value, validator, note). A value that does not read as its kind is None, at validator 0, and says so. `signed`:
        an amount marked Dr is minus (a balance in overdraft); the Cr of a balance and the marker of a debit are no sign."""
        if kind == "amount":
            v = parse_amount(text)
            if v is not None and signed and amount_side(text) == "dr":
                v = -v
            v = None if v is None else fmt_amount(v)
            return (v, 1.0, "") if v is not None else (None, 0.0, "not a readable amount")
        if kind == "date":
            d, ambiguous = parse_date(text)
            if d is None:
                return None, 0.0, "not a readable date"
            if not ambiguous:
                return d.isoformat(), 1.0, ""
            if self.dayfirst:
                return d.isoformat(), DATE_INFERRED, "DD/MM, as the document's other dates show"
            return d.isoformat(), DATE_AMBIGUOUS, "ambiguous DD/MM or MM/DD"
        t = "".join(text.split()) if kind == "id" else " ".join(text.split())
        return (t, 1.0, "") if t else (None, 0.0, "empty")

    # --- header fields

    def title(self) -> tuple[Line, list[Word], list[Word], float, str] | None:
        lines = self.lines.get(self.doc.pages[0].n, []) if self.doc.pages else []
        line = issuer_line(lines)  # the topmost of the lines about as tall as the tallest that reads as a name
        return None if line is None else (line, [], line.words, TITLE_SCORE, "")

    def headings(self) -> set[int]:
        """The lines that are the table's heading, one a page (see find_header): the words on them name columns, not fields."""
        if self._headings is None:
            found = [(self.find_header(self.lines[p.n], self.tspec), self.lines[p.n]) for p in self.doc.pages] if self.tspec else []
            self._headings = {id(ln) for hit, lines in found if hit for ln in lines[hit[0]:hit[1] + 1]}
        return self._headings

    @staticmethod
    def plausible(kind: str, words: list[Word]) -> bool:
        """Whether the words could be a value of the kind: an amount or a date has to read as one; text and ids may be anything."""
        return not ((kind == "amount" and parse_amount(text_of(words)) is None) or (kind == "date" and not _date_runs(words)))

    def label_like(self, words: list[Word]) -> bool:
        """A cell that ends in a colon or reads as one of the type's labels or headings: the next label, not a value."""
        text = text_of(words)
        return text.endswith(":") or any(similar(text.replace(":", " "), label, self.th.label_sim) for label in self.labels)

    @staticmethod
    def colon_after(words: list[Word], hit: tuple[int, int, float]) -> bool:
        i, n, _ = hit
        return words[i + n - 1].text.endswith(":") or (i + n < len(words) and words[i + n].text.startswith(":"))

    def labelled(self, fs: FieldSpec) -> tuple[Line, list[Word], list[Word], float, str] | None:
        best = None  # (line, (start, count, similarity)); the closest wins, then the one that spans more words ('Employer Name' is
        skip = self.headings()  # 'employer' with 'Name' left over for a value), then the earliest page and topmost line
        for p in self.doc.pages:
            for line in self.lines[p.n]:
                if id(line) in skip:  # 'Closing Balance' over a column of balances is a heading, not the field of that name
                    continue
                for label in (*fs.labels, *fs.colon_labels):
                    hit = find_phrase(line.words, label, self.th.label_sim)
                    if hit and label in fs.colon_labels and not self.colon_after(line.words, hit):
                        continue
                    if hit and (best is None or (hit[2], hit[1]) > (best[1][2], best[1][1])):
                        best = (line, hit)
        if best is None:
            return None
        line, (i, n, score) = best
        label_words, rest = line.words[i:i + n], line.words[i + n:]
        cell_of = {w.id: k for k, cell in enumerate(line.cells) for w in cell}
        own = cell_of[label_words[-1].id]
        while rest and (rest[0].text in _SEPARATORS or (cell_of[rest[0].id] == own and _finishes_label(rest[0]))):
            rest = rest[1:]  # the colon, and the rest of a label that the type knows only in part ('Name', 'No.', '(INR)')
        # the value is the cell it starts in: what follows a label inside one cell, or else the next cell
        right = [] if fs.position == "below" or not rest else [w for w in rest if cell_of[w.id] == cell_of[rest[0].id]]
        right = [] if self.label_like(right) else right  # the next label is not a value
        value, how = right, ""
        if not (right and self.plausible(fs.kind, right)):  # nothing readable beside the label: the value may stand under it
            under = self.below(line, label_words)
            if under and not self.label_like(under) and (not right or self.plausible(fs.kind, under)):
                value = under
                if fs.position != "below":
                    how, score = "value read from under the label", score * BELOW_SCORE
            elif not right and fs.lines > 1 and fs.position != "below":  # no cell on its row: perhaps centred against a value of several lines
                block = self.centred(line, label_words, fs.lines)
                return line, label_words, block, score * BELOW_SCORE, "value read from beside the label" if block else ""
        if value and fs.lines > 1:
            value = self.wrapped(line.page, value, fs.lines - 1, centred=value is right)  # a new list: `value` may be a cell of the page's lines
        return line, label_words, value, score, how

    def below(self, line: Line, label_words: list[Word]) -> list[Word]:
        """The first cell under the label that overlaps it sideways, within BELOW_REACH line heights."""
        lx0, lx1 = min(w.box[0] for w in label_words), max(w.box[2] for w in label_words)
        mid = (line.box[1] + line.box[3]) / 2
        for cand in self.lines[line.page]:
            dy = (cand.box[1] + cand.box[3]) / 2 - mid
            if dy <= 0:
                continue
            if dy > BELOW_REACH * line.height:
                break
            for cell in cand.cells:
                if min(max(w.box[2] for w in cell), lx1) > max(min(w.box[0] for w in cell), lx0):
                    return cell
        return []

    @staticmethod
    def gap(a: Line, b: Line) -> float:
        """Centre to centre, in pixels."""
        return abs((a.box[1] + a.box[3]) - (b.box[1] + b.box[3])) / 2

    def run(self, page: int, k: int, x0: float, step: int, most: int, pitch: float | None = None) -> list[Line]:
        """The lines after line k, going down (step 1) or up (-1) for at most `most`, that carry on a value whose left edge is x0:
        each sits close to the one before it (about `pitch` from it, if that is given), starts where the value does, and is not
        another label. Anything else ends the run."""
        lines, out, prev, j = self.lines[page], [], self.lines[page][k], k + step
        while 0 <= j < len(lines) and len(out) < most:
            ln, gap = lines[j], self.gap(lines[j], prev)
            first = ln.cells[0]
            if (gap > WRAP_REACH * prev.height or abs(min(w.box[0] for w in first) - x0) > WRAP_ALIGN * prev.height
                    or self.label_like(first) or (pitch is not None and abs(gap - pitch) > PITCH_TOL * pitch)):
                break
            out.append(ln)
            prev, j = ln, j + step
        return out

    def wrapped(self, page: int, value: list[Word], more: int, centred: bool = False) -> list[Word]:
        """`value` with the lines it goes on over: on each next line the first cell, if it starts where the value does, sits close
        under the line before it and is not another label. Anything else, a label to its left included, ends the value. For a value
        on its label's row (`centred`) that has as many such lines above it as below, the label stands on the middle one of them
        (a table cell is centred against its row unless it says otherwise): the lines above belong to it as well."""
        lines = self.lines[page]
        k = next(k for k, ln in enumerate(lines) if any(w.id == value[0].id for w in ln.words))
        x0 = min(w.box[0] for w in value)
        down = self.run(page, k, x0, 1, more)
        up = self.run(page, k, x0, -1, len(down), self.gap(lines[k], down[0])) if centred and down else []
        if len(up) != len(down):
            up = []
        return [*(w for ln in reversed(up) for w in ln.cells[0]), *value, *(w for ln in down for w in ln.cells[0])]

    def centred(self, line: Line, label_words: list[Word], lines: int) -> list[Word]:
        """The value of a label with no cell on its row, standing between the two middle lines of a value of 2 or 4 lines: the line
        above and the line below it start in one column right of the label, and as many lines carry on each way, at the same pitch.
        Empty if that is not what the page shows."""
        page, all_lines = line.page, self.lines[line.page]
        k = next(k for k, ln in enumerate(all_lines) if ln is line)
        if k == 0 or k + 1 >= len(all_lines):
            return []
        above, below = all_lines[k - 1], all_lines[k + 1]
        x0, lx1 = min(w.box[0] for w in below.cells[0]), max(w.box[2] for w in label_words)
        pitch = self.gap(above, below)
        if (pitch > WRAP_REACH * below.height or x0 < lx1 or abs(min(w.box[0] for w in above.cells[0]) - x0) > WRAP_ALIGN * below.height
                or self.label_like(above.cells[0]) or self.label_like(below.cells[0])):
            return []
        up, down = self.run(page, k - 1, x0, -1, lines, pitch), self.run(page, k + 1, x0, 1, lines, pitch)
        if len(up) != len(down) or 2 * (1 + len(down)) > lines:
            return []
        block = [*reversed(up), above, below, *down]
        return [w for ln in block for w in ln.cells[0]]

    def header(self, fs: FieldSpec) -> Field:
        found = self.title() if fs.position == "title" else self.labelled(fs)
        if found is None:
            return self.missing(fs.name, fs.kind, "label not found", role=fs.role)
        line, label_words, value_words, score, how = found
        if not value_words:  # the label is there, its value is not: keep the label as the place to look
            where = "under" if fs.position == "below" else "next to"
            return self.missing(fs.name, fs.kind, f"value not found {where} the label", page=line.page,
                                box=union(w.box for w in label_words), role=fs.role)
        words = value_words
        if fs.kind == "date":
            runs = _date_runs(value_words)
            words = runs[fs.index] if fs.index < len(runs) else value_words  # a period holds two dates
        value, validator, note = self.read(fs.kind, text_of(words), fs.signed)
        return self.make(fs.name, fs.kind, words, line.page, union(w.box for w in words), value, validator, score,
                         role=fs.role, note="; ".join(filter(None, [note, how])))

    # --- table

    def head(self, cell: list[Word], tb: TableSpec) -> _Head:
        text = _UNIT.sub("", text_of(cell))
        score, col = max(((similar(text, h, self.th.label_sim), c.name) for c in tb.columns for h in c.headers),
                         default=(0.0, None))
        box = union(w.box for w in cell)
        return _Head(box[0], box[2], col if score else None, score, text)

    def band(self, lines: list[Line], idx: int) -> list[tuple[int, list[list[Word]]]]:
        """The heading that starts on line idx, read over one line, then over two, then three (BAND at most): (last line, cells). A
        further line belongs to it if it holds no digit, stands close under the one before it and is as tall. Each of its words joins
        the cell of the heading it stands under, so that 'Value' over 'Date' reads 'Value Date' and two columns whose last line ran
        together ('Amount (INR) Amount (INR)') are told apart; words over no cell (a heading of one line, centred between those
        of two) make a cell of their own."""
        cells = [list(c) for c in lines[idx].cells]
        out = [(idx, cells)]
        for j in range(idx + 1, min(idx + BAND, len(lines))):
            prev, line = lines[j - 1], lines[j]
            if (any(c.isdigit() for w in line.words for c in w.text) or self.gap(prev, line) > WRAP_REACH * prev.height
                    or abs(line.height - prev.height) > BAND_TALL * prev.height):
                break
            spans = [(min(w.box[0] for w in c), max(w.box[2] for w in c)) for c in cells]
            cells = [list(c) for c in cells]
            for cell in line.cells:
                fresh = []
                for w in cell:
                    over = [min(w.box[2], b) - max(w.box[0], a) for a, b in spans]
                    if max(over) > 0:
                        cells[over.index(max(over))].append(w)
                    else:
                        fresh.append(w)
                if fresh:
                    cells.append(fresh)
            out.append((j, cells))
        return out

    def heads_of(self, cells: list[list[Word]], tb: TableSpec) -> list[_Head]:
        """What the cells of a heading name. A column that two of them claim goes to the closer wording (the leftmost, on a tie). A
        heading that no column claims but a column's shared wording reads ('Amount') names that column if it is the heading right
        after the one the column follows (Earnings, Amount, Deductions, Amount). A table with no debit and no credit heading may have
        a column of amounts and a column of marks instead (marked_heads)."""
        heads = [self.head(cell, tb) for cell in cells]
        order = sorted(range(len(heads)), key=lambda k: heads[k].x0 + heads[k].x1)  # left to right
        best: dict[str, int] = {}
        for k in order:
            if heads[k].col and (heads[k].col not in best or heads[k].score > heads[best[heads[k].col]].score):
                best[heads[k].col] = k
        beside = set()
        for k, h in enumerate(heads):
            if h.col and best[h.col] != k:
                w = best[h.col]
                if abs(order.index(k) - order.index(w)) == 1:  # the heading next to it, with none between (value date, transaction date)
                    heads[w].x0, heads[w].x1 = min(heads[w].x0, h.x0), max(heads[w].x1, h.x1)  # is the same column, set wider
                    beside.add(k)
                h.col = None
        heads = [h for k, h in enumerate(heads) if k not in beside]
        left_to_right = sorted(heads, key=lambda h: h.x0 + h.x1)
        for c in tb.columns:
            at = next((k for k, h in enumerate(left_to_right) if c.after and h.col == c.after), None)
            if at is None or at + 1 == len(left_to_right) or any(h.col == c.name for h in heads):
                continue
            nxt = left_to_right[at + 1]
            if score := max((similar(nxt.text, w, self.th.label_sim) for w in c.shared), default=0.0):
                nxt.col, nxt.score = c.name, score
        if tb.marked and not any(h.col in ("debit", "credit") for h in heads):
            self.marked_heads(heads, tb)
        return heads

    def marked_heads(self, heads: list[_Head], tb: TableSpec) -> None:
        """When both are there, the heading that no column claims and a wording of TableSpec.marked reads names the column of amounts
        (the best wording, the leftmost on a tie) and the one nearest to it the column of marks. One of the two alone names nothing."""
        def named(wordings: list[str]) -> list[tuple[float, int]]:
            return [(s, k) for k, h in enumerate(heads)
                    if h.col is None and (s := max((similar(h.text, w, self.th.label_sim) for w in wordings), default=0.0))]

        def centre(k: int) -> float:
            return heads[k].x0 + heads[k].x1

        amounts = named(tb.marked.amount)
        if not amounts:
            return
        sa, ka = max(amounts, key=lambda t: (t[0], -centre(t[1])))
        marks = [(s, k) for s, k in named(tb.marked.marker) if k != ka]
        if not marks:
            return
        sm, km = min(marks, key=lambda t: (-t[0], abs(centre(t[1]) - centre(ka))))
        heads[ka].col, heads[ka].score = "amount", sa
        heads[km].col, heads[km].score = "marker", sm

    def find_header(self, lines: list[Line], tb: TableSpec) -> tuple[int, int, list[_Head]] | None:
        """(first line, last line, headings) of the first line of three or more digit-free cells whose heading, read alone or with the
        lines under it (see band), holds the heading of the first column (the one that anchors the rows). Of those readings the one
        that names most columns, the longest on a tie (the whole of the heading); failing any, the first line read alone with any known column heading. A
        row of labels (Opening Balance, Closing Balance, ...) above the table is therefore not taken for its heading."""
        fallback = None
        for idx, line in enumerate(lines):
            if sum(not any(c.isdigit() for c in text_of(cell)) for cell in line.cells) < 3:
                continue
            best = None
            for last, cells in self.band(lines, idx):
                heads = self.heads_of(cells, tb)
                named = len({h.col for h in heads if h.col})
                if any(h.col == tb.columns[0].name for h in heads) and (best is None or named >= best[0]):
                    best = named, last, heads
                if fallback is None and last == idx and any(h.col for h in heads):
                    fallback = idx, last, heads
            if best:
                return idx, best[1], best[2]
        return fallback

    @staticmethod
    def assign(line: Line, heads: list[_Head], dates: tuple[int, ...] = ()) -> dict[int, list[Word]]:
        """Each cell of a row goes to the heading it overlaps most, or else the one nearest sideways. Under a heading that
        is not a known column the words are kept out of every column: missing, not misplaced. A date at the start of a cell that
        stands under one of the date headings `dates` goes to it, and the rest of the cell where it would have gone."""
        out: dict[int, list[Word]] = {}
        for part in _parts(line, heads, dates):
            out.setdefault(_under(part, heads), []).extend(part)
        for words in out.values():
            words.sort(key=lambda w: w.box[0])
        return out

    @staticmethod
    def stretch(rows: list[Line], heads: list[_Head], dates: tuple[int, ...] = ()) -> None:
        """A column is where its cells stand. A heading set centred over text that starts at the left edge of its column says only
        where its own words are, so each heading takes in the cells of the rows that overlap it: a short line of a narration then
        goes with the narration, not with the heading of the column beside it."""
        grow: dict[int, tuple[float, float]] = {}
        for line in rows:
            for cell in _parts(line, heads, dates):
                x0, x1 = min(w.box[0] for w in cell), max(w.box[2] for w in cell)
                gaps = [max(h.x0 - x1, x0 - h.x1) for h in heads]
                if min(gaps) < 0:
                    k = gaps.index(min(gaps))
                    a, b = grow.get(k, (x0, x1))
                    grow[k] = min(a, x0), max(b, x1)
        for k, (x0, x1) in grow.items():
            heads[k].x0, heads[k].x1 = min(heads[k].x0, x0), max(heads[k].x1, x1)

    @staticmethod
    def first_date(kind: str, words: list[Word]) -> tuple[list[Word], int]:
        """(the words, how many dates they hold): a cell of a date column that holds several is read as its first."""
        runs = _date_runs(words) if kind == "date" else []
        return (runs[0], len(runs)) if len(runs) > 1 else (words, len(runs))

    def cell(self, tb: TableSpec, col: ColumnSpec, page: int, line: Line, row: int, heads: list[_Head],
             cells: dict[int, list[Word]], over: dict[int, int], doubt: set[int]) -> Field:
        """The cell of a column in a row. `over`: for a cell read over several lines, how many; `doubt`: the columns in which a
        line stands as near to this row as to its neighbour, so the cell may be only part of what it holds."""
        name = f"{tb.prefix}.{col.name}"
        k = next((k for k, h in enumerate(heads) if h.col == col.name), None)
        if k is None:
            return self.missing(name, col.kind, "column not found in the table header", page=page, box=line.box, row=row)
        words = cells.get(k, [])
        unsure = "a line between this row and a neighbour could belong to either"
        if not words:  # found empty, at the place the cell would be
            box = (heads[k].x0, line.box[1], heads[k].x1, line.box[3])
            if k in doubt:  # what it holds may be on that line
                return self.missing(name, col.kind, unsure, page=page, box=box, row=row)
            return self.make(name, col.kind, [], page, box, None, 1.0, heads[k].score, row=row)
        words, dates = self.first_date(col.kind, words)
        value, validator, note = self.read(col.kind, _joined(words), col.signed)
        notes = [note, f"the cell holds {dates} dates; the first is read" if dates > 1 else "",
                 f"read over {over[k]} lines" if k in over else "", unsure if k in doubt else ""]
        return self.make(name, col.kind, words, page, union(w.box for w in words), value, validator,
                         min(heads[k].score, ROW_DOUBT) if k in doubt else heads[k].score, row=row, note="; ".join(filter(None, notes)))

    def marked(self, tb: TableSpec, page: int, line: Line, row: int, heads: list[_Head], cells: dict[int, list[Word]],
               over: dict[int, int], doubt: set[int]) -> list[Field]:
        """The debit, the credit and the mark of a row of a table that has one column of amounts and, beside it, a column that marks each
        amount Dr or Cr (TableSpec.marked). The amount goes to the side its mark names, with the words and the place of the amount alone,
        and the other side is found empty. A row with neither an amount nor a mark moved nothing. Anything else leaves both sides
        unread and says why: a mark that is neither Dr nor Cr is not guessed at, nor is an amount with no mark."""
        amount = self.cell(tb, _AMOUNT, page, line, row, heads, cells, over, doubt)
        mark = self.cell(tb, _MARK, page, line, row, heads, cells, over, doubt)
        ka, km = (next(k for k, h in enumerate(heads) if h.col == c) for c in ("amount", "marker"))
        box = (heads[ka].x0, line.box[1], heads[ka].x1, line.box[3])
        col = heads[km].text

        def state(f: Field) -> str:  # a value, found empty (see within.py), or not read
            return "value" if f.value is not None else "empty" if not f.word_ids and f.conf > 0 else "unread"

        def empty(name: str) -> Field:
            return self.make(name, "amount", [], page, box, None, 1.0, heads[ka].score, row=row)

        names = f"{tb.prefix}.debit", f"{tb.prefix}.credit"
        sa, sm = state(amount), state(mark)
        said = _said(mark.value or "")
        side = next((i for i, ws in enumerate((tb.marked.debit, tb.marked.credit)) if said in [_said(w) for w in ws]), None)
        if sa == "empty" and sm == "empty":
            return [empty(names[0]), empty(names[1]), mark]
        if sa == "value" and sm == "value" and side is not None:
            note = "; ".join(filter(None, [f"a {('debit', 'credit')[side]}: the {col} column of this row reads {mark.raw!r}", amount.note, mark.note]))
            got = amount.model_copy(update={"name": names[side], "conf": min(amount.conf, mark.conf), "note": note})
            return [got, empty(names[1]), mark] if side == 0 else [empty(names[0]), got, mark]
        why = (f"the amount of this row: {amount.note}" if sa == "unread"
               else f"the {col} column of this row: {mark.note}" if sm == "unread"
               else f"a mark, {mark.raw!r}, stands in the {col} column of this row with no amount beside it" if sa == "empty"
               else f"the {col} column of this row is empty, so the amount is neither a debit nor a credit" if sm == "empty"
               else f"the {col} column of this row reads {mark.raw!r}, which is neither Dr nor Cr")
        return [*(self.missing(n, "amount", why, page=page, box=box, row=row) for n in names), mark]

    @staticmethod
    def aligned(cells: dict[int, list[Word]], mine: dict[int, list[Word]], height: float) -> bool:
        """In each column the two lines share, the words of `cells` start where those of `mine` do, or stand centred on them."""
        for k, words in cells.items():
            if k in mine:
                (a0, a1), (b0, b1) = (min(w.box[0] for w in words), max(w.box[2] for w in words)), \
                    (min(w.box[0] for w in mine[k]), max(w.box[2] for w in mine[k]))
                if abs(a0 - b0) > WRAP_ALIGN * height and abs(a0 + a1 - b0 - b1) / 2 > WRAP_ALIGN * height:
                    return False
        return True

    def continuations(self, body: list[tuple[Line, dict[int, list[Word]]]], rows: list[int], heads: list[_Head],
                      text: set[str]) -> tuple[dict[int, list[int]], dict[int, set[int]]]:
        """The lines of a table body that are not rows and hold words in columns of text only (a narration that wraps). Going down
        and up from a row, the lines that follow one another within WRAP_REACH line heights and start where the row's own text does
        are its. A line that two rows reach goes to the nearer, unless the other is less than ROW_MARGIN times farther: then it goes
        to neither. Returns {row line: [its continuation lines]} and {row line: columns it may have lost a line from}. Every other
        line (a total, a footer, a line with a number in it) is left out, as it always was."""
        isrow = set(rows)
        near: dict[int, dict[int, float]] = {}  # line -> {the rows that reach it: how far}
        for i in rows:
            for step in (1, -1):
                prev, j = i, i + step
                while (0 <= j < len(body) and j not in isrow and body[j][1] and all(heads[k].col in text for k in body[j][1])
                       and self.gap(body[j][0], body[prev][0]) <= WRAP_REACH * body[prev][0].height):
                    near.setdefault(j, {})[i] = self.gap(body[j][0], body[i][0])
                    prev, j = j, j + step
        taken: dict[int, list[int]] = {}
        doubt: dict[int, set[int]] = {}
        for j, owners in sorted(near.items()):
            fit = {i: d for i, d in owners.items() if self.aligned(body[j][1], body[i][1], body[j][0].height)}
            if not fit:
                continue
            best = min(fit, key=fit.__getitem__)
            if len(fit) > 1 and max(fit.values()) < ROW_MARGIN * fit[best]:
                for i in fit:
                    doubt.setdefault(i, set()).update(body[j][1])
            else:
                taken.setdefault(best, []).append(j)
        return taken, doubt

    def ends(self, line: Line) -> bool:
        """Whether the line holds the label of a total (TableSpec.ends_at), with or without its amount after it."""
        for cell in line.cells:
            text = text_of([w for w in cell if parse_amount(w.text) is None]).replace(":", " ")
            if any(similar(text, label, self.th.label_sim) for label in self.stops):
                return True
        return False

    def table(self, tb: TableSpec) -> list[Field]:
        """Rows are the lines that read as a value in the first column (or in a column marked as an anchor), under the last
        heading seen (a page without its own heading continues the previous page's columns), down to the line that holds the label
        of a total. Row numbers count from 1 through the document. A table that marks its amounts Dr or Cr, with no debit and no
        credit column, gets both from the amount and its mark (marked)."""
        out: list[Field] = []
        heads, row, first = None, 0, tb.columns[0]
        for p in self.doc.pages:
            lines, start = self.lines[p.n], 0
            if found := self.find_header(lines, tb):
                start, heads = found[1] + 1, found[2]
            if heads is None:
                continue
            if not any(h.col == first.name for h in heads):  # no way to tell a row from any other line
                continue
            anchors = [(k, c.kind) for k, h in enumerate(heads) for c in tb.columns if h.col == c.name and (c is first or c.anchor)]
            dates = tuple(k for k, kind in anchors if kind == "date")
            marked = bool(tb.marked) and any(h.col == "amount" for h in heads)
            end = next((i for i in range(start, len(lines)) if self.ends(lines[i])), len(lines))
            for stretched in (False, True):  # the second time with each column as wide as its cells (see stretch)
                body = [(line, self.assign(line, heads, dates)) for line in lines[start:end]]
                rows = [i for i, (_, cells) in enumerate(body)
                        if any(_holds(kind, text_of(self.first_date(kind, cells.get(k, []))[0])) for k, kind in anchors)]
                if not stretched:
                    self.stretch([body[i][0] for i in rows], heads, dates)
            taken, doubt = self.continuations(body, rows, heads, {c.name for c in tb.columns if c.kind == "text"})
            for i in rows:
                row += 1
                line, cells, over = body[i][0], dict(body[i][1]), {}
                for k in {k for j in taken.get(i, []) for k in body[j][1]}:  # a cell over several lines, read top to bottom
                    pieces = sorted([(body[j][0].box[1], body[j][1][k]) for j in taken[i] if k in body[j][1]]
                                    + ([(line.box[1], cells[k])] if cells.get(k) else []), key=lambda piece: piece[0])
                    cells[k], over[k] = [w for _, words in pieces for w in words], len(pieces)
                args = (p.n, line, row, heads, cells, over, doubt.get(i, set()))
                for col in tb.columns:
                    if marked and col.name == "debit":
                        out += self.marked(tb, *args)  # the debit, the credit and the mark of the row
                    elif not (marked and col.name == "credit"):
                        out.append(self.cell(tb, col, *args))
        return out

    def restore(self, fields: list[Field]) -> list[Field]:
        """Boxes back to where the words stand on the page as given: a field with words takes the box around them, one without
        (a missing value, an empty cell) takes the box around its place on the straightened page."""
        pages = {p.n: p for p in self.doc.pages}
        words = {w.id: w for p in self.doc.pages for w in p.words}
        for f in fields:
            if f.word_ids:
                f.box = union(words[i].box for i in f.word_ids)
            elif self.turn.get(f.page) and any(f.box):
                f.box = unturned(f.box, pages[f.page], self.turn[f.page])
        return fields

    # --- unknown types

    @staticmethod
    def guess(text: str) -> str:
        """The kind a value reads as: a date, an amount with cents or a currency mark, else text."""
        return "date" if parse_date(text)[0] is not None else "amount" if _amount_like(text) else "text"

    def generic(self) -> list[Field]:
        out = []
        for p in self.doc.pages:
            for seg in (s for line in self.lines[p.n] for s in _segments(line)):
                if not (hit := _label_value(seg)):
                    continue
                label, words = hit
                text = text_of(words)
                kind = self.guess(text)
                value, validator, note = self.read(kind, text)
                out.append(self.make(re.sub(r"\W+", "_", label.casefold()).strip("_"), kind, words, p.n,
                                     union(w.box for w in words), value, validator, GENERIC_SCORE,
                                     note="; ".join(filter(None, [note, GENERIC_NOTE]))))
        return out


def extract_document(doc: Document, spec: TypeSpec | None, th: Thresholds) -> list[Field]:
    ex = _Extractor(doc, th, spec)
    if spec is None:
        return ex.restore(ex.generic())
    out = [ex.header(fs) for fs in spec.fields]
    return ex.restore(out + (ex.table(spec.table) if spec.table else []))


def _extract(doc: Document, spec: TypeSpec | None, ctx: Ctx) -> None:
    doc.fields = extract_document(doc, spec, ctx.th)
    ctx.audit.append("system", "doc_extracted", {"doc": doc.id, "type": doc.doc_type, "fields": len(doc.fields),
                                                 "empty": sum(f.value is None for f in doc.fields)})


def extract_stage(case: Case, ctx: Ctx) -> None:
    from .model_read import ModelReader  # it imports this module
    reader = ModelReader(case, ctx) if ctx.llm is not None else None  # --llm: the model also reads what has no spec
    specs = load_specs()
    for doc in case.documents:
        if not doc.pages:  # never read: the read step has already reported it
            continue
        spec = specs.get(doc.doc_type)
        guarded(ctx, case, "extract", lambda doc=doc, spec=spec: _extract(doc, spec, ctx), doc_id=doc.id)
        if spec is None:
            add_findings(case, ctx, [limitation(
                "extract", UNSUPPORTED,
                "This document matched no supported type. Only dates, amounts and 'label: value' pairs were read from it, "
                "and no checks written for a specific type ran on it.", [doc_evidence(doc.id, "unsupported document type")])])
            if reader is not None:
                reader.read(doc)
