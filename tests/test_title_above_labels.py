"""The title of a page (the employer on a payslip, the bank on a statement) stands above the first line that holds a label of the type. A
scan's boxes make the rows of a form about as tall as the title, or taller (the second probe, docs/probe.md): at 150 dpi 'Employee Name
Kurian, Nikhil B. Employee Code EMP-9384' was the tallest line of two of the 24 genuine payslips, was read as the employer at 0.90, and
gave a false employer conflict with the application. Pages here are plain text at fixed places, so every case is exact: the title is set
smaller than the rows below it, as a scan's boxes make it."""
from docforensics.config import Thresholds
from docforensics.ingest import create_case
from docforensics.pipeline import run_case
from docforensics.understand.extract import extract_document
from docforensics.understand.specs import load_specs
from tests.helpers import lines_pdf

TH = Thresholds()


def slip(title_size: int) -> list:
    return [(60, 80, "HARBORVIEW TEST PVT LTD", title_size), (60, 96, "Pay Slip for the month of March 2026", 9),
            (60, 130, "Employee Name Kurian, Nikhil B.", 11), (330, 130, "Employee Code EMP-9384", 11),
            (60, 150, "Designation Technician", 11), (330, 150, "Date of Payment 01/04/2026", 11)]


def read(tmp_path, kind, lines, field) -> str | None:
    _, cd, _ = create_case(tmp_path / "data", [("d1.pdf", lines_pdf(lines))], TH)
    doc = run_case(cd, TH).documents[0]
    return {f.name: f for f in extract_document(doc, load_specs()[kind], TH) if f.row is None}[field].value


def test_a_row_of_the_form_taller_than_the_title_is_not_the_employer(tmp_path):
    assert read(tmp_path, "payslip", slip(9), "employer") == "HARBORVIEW TEST PVT LTD"


def test_a_customer_name_taller_than_the_bank_is_not_the_bank(tmp_path):
    lines = [(60, 60, "Halcyon Test Bank", 12), (60, 90, "Statement of Account", 10), (60, 120, "Account Holder Ms. Divya T. Pillai", 16)]
    assert read(tmp_path, "bank_statement", lines, "bank") == "Halcyon Test Bank"


def test_a_title_taller_than_the_rows_below_it_is_read_as_before(tmp_path):
    assert read(tmp_path, "payslip", slip(14), "employer") == "HARBORVIEW TEST PVT LTD"


def test_a_page_with_a_label_on_its_first_line_is_read_as_before(tmp_path):
    """Nothing stands above that line, so the tallest line of the page is the title, as it was."""
    lines = [(60, 60, "Employee Name Kurian, Nikhil B.", 9), (60, 100, "HARBORVIEW TEST PVT LTD", 14)]
    assert read(tmp_path, "payslip", lines, "employer") == "HARBORVIEW TEST PVT LTD"


def test_a_name_that_opens_with_the_word_of_a_heading_is_still_the_title(tmp_path):
    """'Credit' heads a column of a statement, and a bank may be called 'Credit Union Test Bank'."""
    lines = [(60, 60, "Credit Union Test Bank", 14), (60, 90, "Statement of Account", 10), (60, 110, "Account No TST-5221167323", 10)]
    assert read(tmp_path, "bank_statement", lines, "bank") == "Credit Union Test Bank"


def test_a_tallest_line_that_holds_no_label_is_the_title_wherever_it_stands(tmp_path):
    """The rows of a page turned half a turn come in the opposite order: its footer stands where the title would, the title at the foot.
    The reader finds such a page only when most of its lines are turned (tests/test_upside_down.py); a scan of a bank statement turned
    half a turn was not found, and its bank was read right by the tallest line, so that line is not given up for the one at the top."""
    lines = [(60, 60, "Page 1 of 1", 9), (60, 100, "Account Holder Ms. Divya T. Pillai", 11), (60, 140, "Statement of Account", 10),
             (60, 700, "Halcyon Test Bank", 14)]
    assert read(tmp_path, "bank_statement", lines, "bank") == "Halcyon Test Bank"
