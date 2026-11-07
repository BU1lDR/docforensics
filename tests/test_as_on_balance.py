"""A balance dated in its own label: 'Opening Balance as on 1 Jun 2026 : 2,63,148.51'. The reader took everything after the label for the
value, found no amount in 'as on 1 Jun 2026 : 2,63,148.51' and left the balance unread; and where the year wrapped onto the next line of the
cell it took that line, '2026', for the balance: 2026.00 at 0.90, and a false break in the balance chain with it (the second probe,
docs/probe.md; two of the four statements set in that house style). The date is when the balance stands, not what it is: it is passed over,
and the value is what follows it. Pages are plain text at fixed places, so every case is exact."""
import pytest

from docforensics.config import Thresholds
from docforensics.ingest import create_case
from docforensics.pipeline import run_case
from docforensics.understand.extract import extract_document
from docforensics.understand.specs import load_specs
from tests.helpers import lines_pdf

TH = Thresholds()
SPEC = load_specs()["bank_statement"]
# the label and its date in one cell, the colon, and the value
SAME_LINE = [(43, 150, "Opening Balance as on 1 Jun 2026", 9), (190, 150, ":", 9), (195, 150, "2,63,148.51", 9)]
# the year goes onto a line of its own under the label
WRAPPED = [(43, 160, "Opening Balance as on 1 May", 9), (176, 160, ":", 9), (181, 160, "96,764.64", 9), (43, 170.5, "2026", 9)]


def header(tmp_path, lines) -> dict:
    _, cd, _ = create_case(tmp_path / "data", [("d1.pdf", lines_pdf(lines))], TH)
    doc = run_case(cd, TH).documents[0]
    return {f.name: f for f in extract_document(doc, SPEC, TH) if f.row is None}


def test_a_balance_dated_in_its_label_is_read_after_the_date(tmp_path):
    f = header(tmp_path, SAME_LINE)["opening_balance"]
    assert f.value == "263148.51" and f.raw == "2,63,148.51" and f.conf >= TH.low_conf and len(f.word_ids) == 1


def test_the_year_that_wrapped_under_the_label_is_not_the_balance(tmp_path):
    f = header(tmp_path, WRAPPED)["opening_balance"]
    assert f.value == "96764.64" and f.raw == "96,764.64"


def test_a_year_under_a_dated_label_is_not_a_balance_when_the_balance_itself_is_missing(tmp_path):
    f = header(tmp_path, WRAPPED[:2] + WRAPPED[3:])["opening_balance"]  # no amount on the page
    assert f.value is None and f.note == "value not found next to the label"


@pytest.mark.parametrize("date", ["01/06/2026", "1st June 2026", "Jun 1, 2026", "1 Jun", "01-06-26"])
def test_the_date_may_be_written_in_the_usual_ways(tmp_path, date):
    got = header(tmp_path, [(43, 150, f"Closing Balance as at {date}", 9), (300, 150, "-51,890.21", 9)])["closing_balance"]
    assert got.value == "-51890.21"


def test_a_balance_without_a_date_is_read_as_before(tmp_path):
    got = header(tmp_path, [(43, 150, "Opening Balance", 9), (195, 150, "2,63,148.51", 9), (43, 170, "Closing Balance as on demand", 9)])
    assert got["opening_balance"].value == "263148.51"
