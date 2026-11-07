"""A row whose date a scan cut short ('03-M-26' for '03-Mar-26') is still a row: its date is unreadable and says so, its other cells are
read, the balance chain holds and the dossier names the date. The shape is a day of digits, a few letters, a year, the same separator on
both sides, and it counts in the cell of the date column alone. The digit-for-letter variant ('O3/05/2026') is in test_extraction_layouts."""
import pytest

from docforensics.config import Thresholds
from docforensics.ingest import create_case
from docforensics.pipeline import run_case
from tests.helpers import lines_pdf
from tests.test_extraction_layouts import read

TH = Thresholds()


def statement(third: str, extra=()):
    """Four rows in the style that prints 01-Mar-26; the date of the third is `third`; `extra` lines follow the fourth row."""
    return [(40, 60, "Opening Balance", 9), (40, 74, "1,20,500.00", 11), (260, 60, "Closing Balance", 9), (260, 74, "1,48,000.00", 11),
            (40, 100, "Date", 9), (110, 100, "Details", 9), (300, 100, "Debit", 9), (380, 100, "Credit", 9), (460, 100, "Balance", 9),
            (40, 114, "01-Mar-26", 10), (110, 114, "Salary", 10), (380, 114, "52,000.00", 10), (460, 114, "1,72,500.00", 10),
            (40, 128, "02-Mar-26", 10), (110, 128, "Rent", 10), (300, 128, "18,000.00", 10), (460, 128, "1,54,500.00", 10),
            (40, 142, third, 10), (110, 142, "Groceries", 10), (300, 142, "4,500.00", 10), (460, 142, "1,50,000.00", 10),
            (40, 156, "04-Mar-26", 10), (110, 156, "Fuel", 10), (300, 156, "2,000.00", 10), (460, 156, "1,48,000.00", 10), *extra]


def rows_of(got) -> list[int]:
    return sorted({row for _, row in got if row is not None})


def test_a_date_with_its_month_cut_short_is_still_a_row_with_no_readable_date(tmp_path):
    got = read(tmp_path, statement("03-M-26"))[1]
    assert rows_of(got) == [1, 2, 3, 4]
    assert got[("txn.date", 3)].value is None and got[("txn.date", 3)].conf == 0 and got[("txn.date", 3)].note == "not a readable date"
    assert [got[("txn.description", 3)].value, got[("txn.debit", 3)].value, got[("txn.balance", 3)].value] == ["Groceries", "4500.00", "150000.00"]
    assert got[("txn.date", 4)].value == "2026-03-04"


def test_a_statement_with_a_cut_short_month_keeps_its_balance_chain_and_says_which_date(tmp_path):
    """Without that row the balance after row 2 (1,54,500.00) and after the row after it (1,48,000.00) differ by 6,500.00 where one row
    moves 2,000.00: an inconsistency that is not there. The chain holds, and the dossier says which date could not be read."""
    _, cd, _ = create_case(tmp_path / "data", [("d1.pdf", lines_pdf(statement("03-M-26")))], TH)
    case = run_case(cd, TH)
    assert case.documents[0].doc_type == "bank_statement"
    assert not [f for f in case.findings if f.fclass == "inconsistency"], [f.title for f in case.findings]
    gaps = [f for f in case.findings if f.title == "Cannot fully verify this statement"]
    assert gaps and "date in row 3" in gaps[0].detail, [f.detail for f in gaps]


@pytest.mark.parametrize("third", ["03-Mar-26", "03-March-26", "03-MAR-26", "03/03/2026"])
def test_a_date_that_reads_is_read_as_before(tmp_path, third):
    got = read(tmp_path, statement(third))[1]
    assert rows_of(got) == [1, 2, 3, 4]
    assert got[("txn.date", 3)].value == "2026-03-03" and got[("txn.date", 3)].conf > 0, third


@pytest.mark.parametrize("text", ["ref-no-2026", "A/B/2026", "26-Q1-12", "Page 1 of 3", "03-M/26", "03-Mar-6", "103-Mar-26", "03-M-26 Fuel", "03-1M-26"])
def test_a_cell_of_the_date_column_that_is_not_that_shape_is_not_a_row(tmp_path, text):
    """Separators that differ, a digit among the letters, a one-digit year, a day of three digits, other words in the cell: not a date
    that was damaged, and not a row."""
    note = [(40, 170, text, 10), (300, 170, "9,999.00", 10)]
    assert rows_of(read(tmp_path, statement("03-Mar-26", note))[1]) == [1, 2, 3, 4], text


def test_that_shape_outside_the_date_column_is_not_a_row(tmp_path):
    """A narration that reads '03-M-26' stands under the heading of the narration, and its line has nothing in the first column."""
    note = [(110, 170, "03-M-26", 10), (300, 170, "9,999.00", 10)]
    assert rows_of(read(tmp_path, statement("03-Mar-26", note))[1]) == [1, 2, 3, 4]
