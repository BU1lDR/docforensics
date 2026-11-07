"""A credit and the balance after it, set 20 px apart on a scan, are two amounts in neighbouring columns that OCR boxes (wider than their
text) read as ONE cell. Left alone, that cell is unreadable in the credit column (a named gap, as it should be) but it also widens the
Credit heading over the Balance column; the balance words of the other rows then went to Credit at full confidence, and the balance
chain broke by exactly that amount: a false inconsistency on a genuine statement. Found on scans of a statement style that prints credit
and balance side by side (docs/probe.md, second probe); tests/fixtures/stored_statement_sbi_words.json is page 1 of one of them as stored:
242 OCR words with their boxes, fictional people and amounts, no image."""
import json
from decimal import Decimal
from pathlib import Path

import pytest

from docforensics.config import Thresholds
from docforensics.model import Document, Page, Word
from docforensics.understand.extract import extract_document
from docforensics.understand.specs import load_specs
from tests.helpers import lines_pdf
from tests.test_extraction_layouts import read

TH = Thresholds()
SPEC = load_specs()["bank_statement"]


def stored_statement() -> Document:
    got = json.loads(Path(__file__).with_name("fixtures").joinpath("stored_statement_sbi_words.json").read_text(encoding="utf-8"))
    words = [Word(id=f"w{i}", text=t, box=(x0, y0, x1, y1), conf=c) for i, (t, x0, y0, x1, y1, c) in enumerate(got["words"])]
    page = Page(n=1, width=got["width"], height=got["height"], dpi=got["dpi"], read_mode="ocr", quality_class="good", words=words)
    return Document(id="d1", sha256="0", filename="statement.pdf", stored_path="", kind="pdf-scanned", doc_type="bank_statement", pages=[page])


def cells(fields) -> dict[tuple[str, int | None], object]:
    return {(f.name, f.row): f for f in fields}


def test_the_balance_of_each_row_of_the_stored_statement_is_the_balance_and_the_chain_holds():
    got = cells(extract_document(stored_statement(), SPEC, TH))
    rows = sorted({row for _, row in got if row is not None})
    assert rows == list(range(1, 15))
    previous = None
    for r in rows:
        debit, credit, balance = (got[(f"txn.{n}", r)] for n in ("debit", "credit", "balance"))
        assert balance.value is not None, f"row {r}: balance {balance.raw!r} ({balance.note}); credit read as {credit.raw!r}"
        if previous is not None:
            moved = Decimal(credit.value or 0) - Decimal(debit.value or 0)
            assert Decimal(balance.value) == previous + moved, f"row {r}: {previous} + {moved} is not {balance.value}"
        previous = Decimal(balance.value)


def test_a_credit_and_a_balance_read_as_one_cell_are_two_cells():
    """Row 2 is a credit of 65,600.00 that takes the balance from 2,47,905.00 to 3,13,505.00; row 12 is a debit with no credit."""
    got = cells(extract_document(stored_statement(), SPEC, TH))
    assert (got[("txn.credit", 2)].value, got[("txn.balance", 2)].value) == ("65600.00", "313505.00")
    assert (got[("txn.credit", 12)].value, got[("txn.credit", 12)].raw, got[("txn.balance", 12)].value) == (None, "", "238706.50")


def test_the_credit_heading_does_not_take_in_the_balance_column():
    got = cells(extract_document(stored_statement(), SPEC, TH))
    credit, balance = got[("txn.credit", 12)], got[("txn.balance", 12)]
    assert credit.box[2] <= balance.box[0], (credit.box, balance.box)  # the empty credit cell ends before the balance cell begins


# the statements of these tests: Date | Details | Debit | Credit | Balance, the credit right-aligned to x 425 and the balance to x 500
# (20 pt apart: two cells), or to x 480 with the heading moved to match (2 pt apart: one cell, the cell gap is 0.8 line heights)
HEAD = [(40, 60, "Opening Balance", 9), (40, 74, "1,20,500.00", 11), (260, 60, "Closing Balance", 9), (260, 74, "1,48,000.00", 11),
        (40, 100, "Date", 9), (110, 100, "Details", 9), (300, 100, "Debit", 9), (380, 100, "Credit", 9), (470, 100, "Balance", 9)]
HEAD_NEAR = HEAD[:-1] + [(450, 100, "Balance", 9)]


def row(y, date, what, debit="", credit="", balance="", edge=500):
    right = lambda text, to: (to - 5.56 * sum(c.isdigit() for c in text) - 2.78 * sum(not c.isdigit() for c in text), y, text, 10)
    cells_ = [(40, y, date, 10), (110, y, what, 10)]
    if debit:
        cells_.append(right(debit, 340))
    if credit:
        cells_.append(right(credit, 425))
    if balance:
        cells_.append(right(balance, edge))
    return cells_


def test_a_credit_and_a_balance_set_close_together_on_a_digital_page_are_two_cells(tmp_path):
    lines = [*HEAD_NEAR, *row(114, "01-Mar-26", "Salary", credit="52,000.00", balance="1,72,500.00", edge=480),
             *row(128, "02-Mar-26", "Rent", debit="18,000.00", balance="1,54,500.00", edge=480),
             *row(142, "03-Mar-26", "Bonus", credit="3,500.00", balance="1,58,000.00", edge=480)]
    got = read(tmp_path, lines)[1]
    assert [(got[("txn.credit", r)].value, got[("txn.balance", r)].value) for r in (1, 2, 3)] == [
        ("52000.00", "172500.00"), (None, "154500.00"), ("3500.00", "158000.00")]


def test_two_amounts_under_one_heading_stay_one_cell_and_unread(tmp_path):
    lines = [*HEAD, *row(114, "01-Mar-26", "Salary", credit="52,000.00", balance="1,72,500.00"),
             *row(128, "02-Mar-26", "Rent", debit="18,000.00", balance="1,54,500.00")]
    lines += [(300, 142, "10.00 20.00", 10), (40, 142, "03-Mar-26", 10), (110, 142, "Two in one", 10)]
    got = read(tmp_path, lines)[1]
    assert got[("txn.debit", 3)].value is None and got[("txn.debit", 3)].note == "not a readable amount", got[("txn.debit", 3)]
    assert (got[("txn.credit", 1)].value, got[("txn.balance", 1)].value) == ("52000.00", "172500.00")


def test_a_cell_of_a_narration_and_an_amount_that_runs_under_the_next_heading_is_not_cut(tmp_path):
    """Only a cell that is amounts and nothing else is cut where its headings change; a narration is one cell wherever it ends."""
    lines = [*HEAD, *row(114, "01-Mar-26", "Salary credit 52,000.00 Mar", credit="52,000.00", balance="1,72,500.00")]
    got = read(tmp_path, lines)[1]
    assert got[("txn.description", 1)].value == "Salary credit 52,000.00 Mar", got[("txn.description", 1)]
    assert (got[("txn.credit", 1)].value, got[("txn.balance", 1)].value) == ("52000.00", "172500.00")


def test_an_amount_wider_than_its_heading_stays_in_its_own_column(tmp_path):
    """Right-aligned amounts run to the left of a heading that is only as wide as its word."""
    lines = [*HEAD, *row(114, "01-Mar-26", "Big", debit="12,34,567.89", balance="1,20,500.00"),
             *row(128, "02-Mar-26", "Small", debit="2.00", balance="1,20,498.00")]
    got = read(tmp_path, lines)[1]
    assert [got[("txn.debit", r)].value for r in (1, 2)] == ["1234567.89", "2.00"]
    assert [got[("txn.balance", r)].value for r in (1, 2)] == ["120500.00", "120498.00"]


def test_a_heading_centred_over_left_aligned_text_still_takes_in_the_lines_of_its_column(tmp_path):
    """A heading says only where its own word stands: the narration column is where the narrations are (see stretch). Without
    that, 'Mumbai' under a narration, at the left edge of the column, would go with the date column beside it (it is nearer to
    that heading's word than to the heading of the narrations)."""
    lines = [(40, 100, "Date", 9), (200, 100, "Description", 9), (480, 100, "Debit", 9), (540, 100, "Balance", 9),
             (40, 114, "01-Mar-26", 10), (110, 114, "UPI payment to the grocer", 10), (480, 114, "100.00", 10), (540, 114, "1,000.00", 10),
             (110, 125, "Mumbai", 10),
             (40, 142, "02-Mar-26", 10), (110, 142, "Cash withdrawal at the branch", 10), (480, 142, "200.00", 10), (540, 142, "800.00", 10)]
    got = read(tmp_path, lines)[1]
    assert got[("txn.description", 1)].value == "UPI payment to the grocer Mumbai", got[("txn.description", 1)]
