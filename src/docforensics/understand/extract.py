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
from .layout import Line, find_phrase, issuer_line, lines_of, similar, straightened, text_of, unturned, union
from .normalise import fmt_amount, parse_amount, parse_date
from .specs import ColumnSpec, FieldSpec, TableSpec, TypeSpec, load_specs

TITLE_SCORE = 0.9     # the biggest line on page 1 is the institution, until a label says otherwise
GENERIC_SCORE = 0.8   # a "label: value" pair on a page of an unsupported type: the label is not one we know
DATE_AMBIGUOUS = 0.5  # validator for 04/05/2026: 4 May or 5 April
DATE_INFERRED = 0.9   # ... in a document whose other dates are day-first
BELOW_REACH = 2.5     # line heights: how far under its label a value may sit
GENERIC_NOTE = "unsupported type: generic extraction"
UNSUPPORTED = "Unsupported document type: generic extraction only, no document-specific checks"
_SEPARATORS = {":", "-", chr(0x2013), "="}
_NUM_DATE = re.compile(r"(\d{1,2})([/.-])(\d{1,2})\2(\d{2}|\d{4})", re.A)
_CENTS = re.compile(r"\d\.\d\d(?!\d)", re.A)
_CURRENCY = re.compile(rf"{chr(0x20B9)}|\brs\b|\binr\b|/-", re.I)


@dataclass
class _Head:
    x0: float
    x1: float
    col: str | None  # the column this heading names, None if no known wording matched
    score: float


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


def _reads(kind: str, text: str) -> bool:
    if kind == "date":
        return parse_date(text)[0] is not None
    if kind == "amount":
        return parse_amount(text) is not None
    return bool(text.strip())


def _amount_like(text: str) -> bool:
    """An amount with cents or a currency mark: a bare 5 or 411001 is not one."""
    return parse_amount(text) is not None and bool(_CENTS.search(text) or _CURRENCY.search(text))


def _label_value(line: Line) -> tuple[str, list[Word]] | None:
    """('quote date', value words) for 'Quote Date: 31/03/2026' and for 'Quoted Total 45,000.00' (a date or an amount at the
    end of the line); None for any other line. A label has no digits, so table rows never read as pairs."""
    words = line.words
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
    def __init__(self, doc: Document, th: Thresholds):
        self.doc, self.th = doc, th
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

    def read(self, kind: str, text: str) -> tuple[str | None, float, str]:
        """(stored value, validator, note). A value that does not read as its kind is None, at validator 0, and says so."""
        if kind == "amount":
            v = parse_amount(text)
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

    def title(self) -> tuple[Line, list[Word], list[Word], float] | None:
        lines = self.lines.get(self.doc.pages[0].n, []) if self.doc.pages else []
        line = issuer_line(lines)  # the topmost of the lines about as tall as the tallest that reads as a name
        return None if line is None else (line, [], line.words, TITLE_SCORE)

    def labelled(self, fs: FieldSpec) -> tuple[Line, list[Word], list[Word], float] | None:
        best = None  # (line, (start, count, similarity)); the closest wins, then the one that spans more words ('Employer Name' is
        for p in self.doc.pages:  # 'employer' with 'Name' left over for a value), then the earliest page and topmost line
            for line in self.lines[p.n]:
                for label in fs.labels:
                    hit = find_phrase(line.words, label, self.th.label_sim)
                    if hit and (best is None or (hit[2], hit[1]) > (best[1][2], best[1][1])):
                        best = (line, hit)
        if best is None:
            return None
        line, (i, n, score) = best
        label_words, rest = line.words[i:i + n], line.words[i + n:]
        while rest and rest[0].text in _SEPARATORS:
            rest = rest[1:]
        if fs.position == "below":
            return line, label_words, self.below(line, label_words), score
        cell_of = {w.id: k for k, cell in enumerate(line.cells) for w in cell}
        first = cell_of[rest[0].id] if rest else None
        # the value is the cell it starts in: what follows a label inside one cell, or else the next cell
        return line, label_words, [w for w in rest if cell_of[w.id] == first], score

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

    def header(self, fs: FieldSpec) -> Field:
        found = self.title() if fs.position == "title" else self.labelled(fs)
        if found is None:
            return self.missing(fs.name, fs.kind, "label not found", role=fs.role)
        line, label_words, value_words, score = found
        if not value_words:  # the label is there, its value is not: keep the label as the place to look
            where = "under" if fs.position == "below" else "next to"
            return self.missing(fs.name, fs.kind, f"value not found {where} the label", page=line.page,
                                box=union(w.box for w in label_words), role=fs.role)
        words = value_words
        if fs.kind == "date":
            runs = _date_runs(value_words)
            words = runs[fs.index] if fs.index < len(runs) else value_words  # a period holds two dates
        value, validator, note = self.read(fs.kind, text_of(words))
        return self.make(fs.name, fs.kind, words, line.page, union(w.box for w in words), value, validator, score,
                         role=fs.role, note=note)

    # --- table

    def head(self, cell: list[Word], tb: TableSpec) -> _Head:
        text = text_of(cell)
        score, col = max(((similar(text, h, self.th.label_sim), c.name) for c in tb.columns for h in c.headers),
                         default=(0.0, None))
        box = union(w.box for w in cell)
        return _Head(box[0], box[2], col if score else None, score)

    def find_header(self, lines: list[Line], tb: TableSpec) -> tuple[int, list[_Head]] | None:
        """The first line of three or more digit-free cells, at least one of which is a known column heading."""
        for idx, line in enumerate(lines):
            if sum(not any(c.isdigit() for c in text_of(cell)) for cell in line.cells) < 3:
                continue
            heads = [self.head(cell, tb) for cell in line.cells]
            best: dict[str, int] = {}  # a column that two headings claim goes to the closer wording
            for k, h in enumerate(heads):
                if h.col and (h.col not in best or h.score > heads[best[h.col]].score):
                    best[h.col] = k
            for k, h in enumerate(heads):
                if h.col and best[h.col] != k:
                    h.col = None
            if any(h.col for h in heads):
                return idx, heads
        return None

    @staticmethod
    def assign(line: Line, heads: list[_Head]) -> dict[int, list[Word]]:
        """Each cell of a row goes to the heading it overlaps most, or else the one nearest sideways. Under a heading that
        is not a known column the words are kept out of every column: missing, not misplaced."""
        out: dict[int, list[Word]] = {}
        for cell in line.cells:
            x0, x1 = min(w.box[0] for w in cell), max(w.box[2] for w in cell)
            gaps = [max(h.x0 - x1, x0 - h.x1) for h in heads]  # negative: the overlap
            out.setdefault(gaps.index(min(gaps)), []).extend(cell)
        for words in out.values():
            words.sort(key=lambda w: w.box[0])
        return out

    def cell(self, tb: TableSpec, col: ColumnSpec, page: int, line: Line, row: int, heads: list[_Head],
             cells: dict[int, list[Word]]) -> Field:
        name = f"{tb.prefix}.{col.name}"
        k = next((k for k, h in enumerate(heads) if h.col == col.name), None)
        if k is None:
            return self.missing(name, col.kind, "column not found in the table header", page=page, box=line.box, row=row)
        words = cells.get(k, [])
        if not words:  # found empty, at the place the cell would be
            box = (heads[k].x0, line.box[1], heads[k].x1, line.box[3])
            return self.make(name, col.kind, [], page, box, None, 1.0, heads[k].score, row=row)
        value, validator, note = self.read(col.kind, text_of(words))
        return self.make(name, col.kind, words, page, union(w.box for w in words), value, validator, heads[k].score,
                         row=row, note=note)

    def table(self, tb: TableSpec) -> list[Field]:
        """Rows are the lines that read as a value in the first column, under the last heading seen (a page without
        its own heading continues the previous page's columns). Row numbers count from 1 through the document."""
        out: list[Field] = []
        heads, row, first = None, 0, tb.columns[0]
        for p in self.doc.pages:
            lines, start = self.lines[p.n], 0
            if found := self.find_header(lines, tb):
                start, heads = found[0] + 1, found[1]
            if heads is None:
                continue
            anchor = next((k for k, h in enumerate(heads) if h.col == first.name), None)
            if anchor is None:  # no way to tell a row from any other line
                continue
            for line in lines[start:]:
                cells = self.assign(line, heads)
                if not _reads(first.kind, text_of(cells.get(anchor, []))):
                    continue
                row += 1
                out += [self.cell(tb, col, p.n, line, row, heads, cells) for col in tb.columns]
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
            for line in self.lines[p.n]:
                if not (hit := _label_value(line)):
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
    ex = _Extractor(doc, th)
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
