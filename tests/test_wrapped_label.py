"""A label that wraps over two lines in a form whose cells are centred up and down: 'Salary Account' over 'Number' with the value between
the two lines, and beside it 'Declared Monthly' over 'Income' (a browser-printed table; the second probe, docs/probe.md). The reader
tolerates a short last word missing from a label ('salary account' for 'salary account no'), so it took the first line of the wrapped
label for the whole label, and the first line of the label beside it for the value: 'DeclaredMonthly', at 0.90, in six of the twenty-four
applications, and a false account conflict with the statement. The first line of a wrapped label is now never a value, and neither is the
line that finishes the label: the value is left unread and the dossier says so. Pages are plain text at fixed places, so every case is exact."""
import pytest

from docforensics.config import Thresholds
from docforensics.ingest import create_case
from docforensics.pipeline import run_case
from docforensics.understand.extract import extract_document
from docforensics.understand.specs import load_specs
from tests.helpers import lines_pdf

TH = Thresholds()
SPEC = load_specs()["loan_application"]
# two columns of label and value; each value stands between the two lines of its label
GRID = [(45, 160, "Salary Account", 9), (346, 160, "Declared Monthly", 9),
        (143, 166, "XXXX-7323", 11), (444, 166, "72,000.00", 11),
        (45, 171, "Number", 9), (346, 171, "Income", 9)]


def header(tmp_path, lines) -> dict:
    _, cd, _ = create_case(tmp_path / "data", [("d1.pdf", lines_pdf(lines))], TH)
    doc = run_case(cd, TH).documents[0]
    return {f.name: f for f in extract_document(doc, SPEC, TH) if f.row is None}


def test_the_first_line_of_the_label_beside_a_wrapped_label_is_not_its_value(tmp_path):
    f = header(tmp_path, GRID)["account_no"]
    assert f.value is None and f.conf == 0.0 and f.note == "value not found next to the label"  # the gap is stated, not filled with 'Declared Monthly'


def test_the_line_that_finishes_a_label_is_not_its_value_either(tmp_path):
    """With nothing but the wrapped label's second line to go by: 'Number' under 'Salary Account' finishes the label."""
    f = header(tmp_path, [(45, 160, "Salary Account", 9), (45, 171, "Number", 9)])["account_no"]
    assert f.value is None and f.note == "value not found next to the label"


@pytest.mark.parametrize("lines", [
    [(45, 160, "Salary Account Number", 9), (200, 160, "XXXX-7323", 11)],  # the label on one line
    [(45, 160, "Salary Account", 9), (200, 160, "XXXX-7323", 11), (45, 171, "Number", 9)],  # a wrapped label, its value level with the first line
    [(45, 160, "Salary Account Number", 9), (45, 174, "XXXX-7323", 11)],  # the value under the label
])
def test_a_value_that_stands_where_a_value_stands_is_read_as_before(tmp_path, lines):
    f = header(tmp_path, lines)["account_no"]
    assert f.value == "XXXX-7323" and f.conf >= TH.low_conf


def test_a_value_that_only_starts_like_a_label_is_still_a_value(tmp_path):
    f = header(tmp_path, [(45, 160, "Employer", 9), (200, 160, "Declared Monthly Traders Pvt Ltd", 11)])["employer"]
    assert f.value == "Declared Monthly Traders Pvt Ltd"


def test_a_cell_under_a_label_that_is_already_whole_is_its_value(tmp_path):
    """'Tenure in Months 48' is close to the label 'Tenure in Months', yet the 48 is not part of the label: the label is whole, and wraps no further."""
    f = header(tmp_path, [(307, 183, "Tenure in Months", 9), (307, 192, "48", 11)])["tenure_months"]
    assert f.value == "48.00" and "under the label" in f.note
