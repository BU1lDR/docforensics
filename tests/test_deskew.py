"""A scan is a little turned (0.5 to 2 degrees in the simulation). The reader finds rows, cells and columns as the page would stand
upright, and still reports every box where the word is on the page as given."""
import math

import pytest

from datagen.fictional import identity
from datagen.layouts.payslip import draw_payslip
from datagen.layouts.statement import draw_statement
from docforensics.config import Thresholds
from docforensics.ingest import create_case
from docforensics.model import Page, Word
from docforensics.pipeline import _stage_fns, run_case
from docforensics.understand.extract import extract_document
from docforensics.understand.layout import lines_of, straightened, union
from docforensics.understand.specs import load_specs

TH = Thresholds()
CENTRE = (800.0, 1100.0)


def turned(box, deg):
    """The box around `box` once the page is turned by `deg` degrees anticlockwise, as the reader boxes a word on a turned page."""
    a = math.radians(deg)
    pts = [(x - CENTRE[0], y - CENTRE[1]) for x in (box[0], box[2]) for y in (box[1], box[3])]
    xs = [CENTRE[0] + dx * math.cos(a) + dy * math.sin(a) for dx, dy in pts]
    ys = [CENTRE[1] - dx * math.sin(a) + dy * math.cos(a) for dx, dy in pts]
    return min(xs), min(ys), max(xs), max(ys)


def scan_of(page: Page, deg: float) -> Page:
    words = [w.model_copy(update={"box": turned(w.box, deg), "pt_box": None}) for w in page.words]
    return page.model_copy(update={"words": words, "read_mode": "ocr", "quality_class": "good", "width": 1600, "height": 2200})


def read_straight(tmp_path, pdf):
    case, cd, _ = create_case(tmp_path / "data", [("d.pdf", pdf)], TH)
    fns = _stage_fns()
    case = run_case(cd, TH, stages={k: fns[k] for k in ("read", "classify")})
    return case.documents[0]


@pytest.mark.parametrize("deg", [1.5, -1.5, 2.0])
def test_rows_of_a_turned_page_stay_apart(deg):
    words = [Word(id=f"w{r}-{c}", text=f"item{r}{c}", box=turned((100.0 + 250 * c, 400.0 + 37 * r, 300.0 + 250 * c, 434.0 + 37 * r), deg))
             for r in range(10) for c in range(6)]
    page = Page(n=1, width=1600, height=2200, read_mode="ocr", words=words)
    assert [len(ln.words) for ln in lines_of(page)] != [6] * 10  # as given, the rows run into each other
    got = [[w.id for w in ln.words] for ln in lines_of(straightened(page)[0])]
    assert got == [[f"w{r}-{c}" for c in range(6)] for r in range(10)]


@pytest.mark.parametrize("make,doc_type", [(lambda: draw_statement(identity(4), rows=12, seed=4), "bank_statement"),
                                           (lambda: draw_payslip(identity(7), seed=7), "payslip")])
@pytest.mark.parametrize("deg", [1.2, -1.8])
def test_a_turned_scan_is_read_like_the_straight_page(tmp_path, make, doc_type, deg):
    doc = read_straight(tmp_path, make().pdf)
    assert doc.doc_type == doc_type
    spec = load_specs()[doc_type]
    want = {(f.name, f.row): f.value for f in extract_document(doc, spec, TH)}
    scan = doc.model_copy(update={"pages": [scan_of(p, deg) for p in doc.pages]})
    got = extract_document(scan, spec, TH)
    assert {(f.name, f.row): f.value for f in got} == want
    words = {w.id: w for p in scan.pages for w in p.words}
    for f in got:
        if f.word_ids:  # a box is where the words are on the page as given, not on the straightened page
            assert f.box == union(words[i].box for i in f.word_ids), f.name
