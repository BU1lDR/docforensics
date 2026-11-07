"""OCR boxes run wider than their text. When the box of a date stands so near the narration beside it that the gap is under the cell gap, the
two read as one cell, the row has no date in its first column, and the whole row, amounts and all, was left out without a word: the balance
chain then broke by exactly that row's amount. Found on a 150 dpi scan of a statement printed by another program (docs/probe.md)."""
import pytest

from datagen.fictional import identity
from datagen.layouts.statement import draw_statement
from docforensics.config import Thresholds
from docforensics.ingest import create_case
from docforensics.pipeline import _stage_fns, run_case
from docforensics.understand.extract import extract_document
from docforensics.understand.layout import CELL_GAP
from docforensics.understand.specs import load_specs

TH = Thresholds()
SPEC = load_specs()["bank_statement"]


def read(tmp_path):
    case, cd, _ = create_case(tmp_path / "data", [("d.pdf", draw_statement(identity(4), rows=12, seed=4).pdf)], TH)
    fns = _stage_fns()
    return run_case(cd, TH, stages={k: fns[k] for k in ("read", "classify")}).documents[0]


def values(fields):
    return {(f.name, f.row): f.value for f in fields}


def with_date_box_widened(doc, row, gap):
    """The document with the box of one row's date stretched to the right, to `gap` line heights from the first word of its narration."""
    fields = {(f.name, f.row): f for f in extract_document(doc, SPEC, TH)}
    date, narration = fields[("txn.date", row)], fields[("txn.description", row)]
    words = {w.id: w for p in doc.pages for w in p.words}
    first, last = words[narration.word_ids[0]], words[date.word_ids[-1]]
    height = last.box[3] - last.box[1]
    wide = last.model_copy(update={"box": (last.box[0], last.box[1], first.box[0] - gap * height, last.box[3]), "pt_box": None})
    pages = [p.model_copy(update={"words": [wide if w.id == wide.id else w for w in p.words]}) for p in doc.pages]
    return doc.model_copy(update={"pages": pages})


@pytest.mark.parametrize("row", [1, 3, 7])
def test_a_date_box_that_runs_into_the_narration_does_not_drop_the_row(tmp_path, row):
    doc = read(tmp_path)
    want = values(extract_document(doc, SPEC, TH))
    near = with_date_box_widened(doc, row, CELL_GAP / 2)
    assert values(extract_document(near, SPEC, TH)) == want


def test_a_date_box_with_room_beside_it_reads_as_before(tmp_path):
    doc = read(tmp_path)
    want = values(extract_document(doc, SPEC, TH))
    apart = with_date_box_widened(doc, 3, CELL_GAP * 1.5)
    assert values(extract_document(apart, SPEC, TH)) == want
