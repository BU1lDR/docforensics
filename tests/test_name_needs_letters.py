"""A name or an employer holds a letter. In a form that stacks its fields in two staggered columns, the value of a label in the left column
can stand on the same line as the label of the right column ('Employer' beside the 48 that belongs to 'Tenure in Months' above it), and the
reader took that number for the employer, at full confidence, and raised a false conflict with the payslip (the second probe, docs/probe.md).
A bare number is not a name: it is passed over like the next label, the value is read from under the label if one stands there, and left
unread, with the gap stated, if none does. Pages are plain text at fixed places, so every case is exact."""
import pytest

from docforensics.config import Thresholds
from docforensics.ingest import create_case
from docforensics.pipeline import run_case
from docforensics.understand.extract import extract_document
from docforensics.understand.specs import load_specs
from tests.helpers import lines_pdf

TH = Thresholds()
SPEC = load_specs()["loan_application"]
# the tenure of the right column stands under its label, on the line of the left column's employer label; the employer is under its label
STAGGERED = [(307, 183, "Tenure in Months", 9), (40, 194, "Employer", 9), (307, 192, "48", 11), (40, 203, "NORTHWIND TEST PVT. LTD.", 11)]


def header(tmp_path, lines) -> dict:
    _, cd, _ = create_case(tmp_path / "data", [("d1.pdf", lines_pdf(lines))], TH)
    doc = run_case(cd, TH).documents[0]
    return {f.name: f for f in extract_document(doc, SPEC, TH) if f.row is None}


def test_a_number_beside_the_employer_label_is_not_the_employer(tmp_path):
    got = header(tmp_path, STAGGERED)
    assert got["employer"].value == "NORTHWIND TEST PVT. LTD." and "under the label" in got["employer"].note
    assert got["tenure_months"].value == "48.00"  # the number is read where it belongs


def test_with_nothing_under_the_label_the_employer_is_left_unread_and_says_so(tmp_path):
    f = header(tmp_path, STAGGERED[:3])["employer"]
    assert f.value is None and f.conf == 0.0 and f.note == "value not found next to the label"


def test_the_same_goes_for_a_name(tmp_path):
    f = header(tmp_path, [(40, 100, "Applicant Name", 9), (200, 100, "12345", 11)])["applicant_name"]
    assert f.value is None and f.note == "value not found next to the label"


@pytest.mark.parametrize("employer", ["3M India Ltd", "7-Eleven Stores", "Ironwood 24x7 Services", "A1 Traders"])
def test_a_name_with_digits_in_it_is_still_a_name(tmp_path, employer):
    assert header(tmp_path, [(40, 100, "Employer", 9), (200, 100, employer, 11)])["employer"].value == employer
