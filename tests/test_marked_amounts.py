"""A statement that prints one column of amounts and, beside it, a column that marks each amount Dr or Cr, in place of a debit column
and a credit column. The amount goes to the debit or to the credit as the mark says; a mark that is not Dr or Cr, or is missing, leaves
both unread, and the dossier says so. Added after a probe of statements printed by a browser in eight invented layouts, two of which
print their amounts like this (docs/probe.md): their credits were never read. Pages are plain text at fixed places, so every case is exact."""
import pymupdf
import pytest

from docforensics.config import Thresholds
from docforensics.ingest import create_case
from docforensics.pipeline import run_case
from docforensics.understand.extract import extract_document
from docforensics.understand.specs import load_specs
from tests.helpers import lines_pdf

TH = Thresholds()
SPEC = load_specs()["bank_statement"]


def right(x1, y, text, fs):
    return (x1 - pymupdf.get_text_length(text, fontname="helv", fontsize=fs), y, text, fs)


TOP = [(40, 60, "Meridian Test Bank", 16), (40, 80, "Statement of Account", 10),
       (40, 100, "Opening Balance", 9), (40, 114, "10,000.00 Cr", 11), (260, 100, "Closing Balance", 9), (260, 114, "42,000.00 Cr", 11),
       (40, 127, "Statement Period", 9), (160, 127, "01/05/2026 to 31/05/2026", 9)]  # a period, so that no gap is left but the one a test provokes
HEAD = [(40, 140, "Date", 9), (110, 140, "Particulars", 9), right(400, 140, "Amount", 9), (420, 140, "Dr/Cr", 9), right(560, 140, "Balance", 9)]
SALARY = ("01/05/2026", "NEFT/Salary Ironwood", "52,000.00", "Cr", "62,000.00 Cr")
RENT = ("02/05/2026", "Rent", "18,000.00", "Dr", "44,000.00 Cr")
FUEL = ("03/05/2026", "Fuel", "2,000.00", "Dr", "42,000.00 Cr")


def rows_of(*rows, y=154, pitch=14):
    """Table rows, each (date, narration, amount, mark, balance); an amount or a mark that is None is not printed."""
    out = []
    for date, narration, amount, mark, balance in rows:
        out += [(40, y, date, 10), (110, y, narration, 10), right(560, y, balance, 10)]
        out += [right(400, y, amount, 10)] if amount else []
        out += [(420, y, mark, 10)] if mark else []
        y += pitch
    return out


def read(tmp_path, lines) -> dict:
    """Every field of the statement by (name, row)."""
    _, cd, _ = create_case(tmp_path / "data", [("d1.pdf", lines_pdf(lines))], TH)
    doc = run_case(cd, TH).documents[0]
    assert doc.doc_type == "bank_statement"
    return {(f.name, f.row): f for f in extract_document(doc, SPEC, TH)}


def case_of(tmp_path, lines):
    _, cd, _ = create_case(tmp_path / "data", [("d1.pdf", lines_pdf(lines))], TH)
    return run_case(cd, TH)


def test_an_amount_marked_cr_is_a_credit_and_one_marked_dr_a_debit(tmp_path):
    got = read(tmp_path, TOP + HEAD + rows_of(SALARY, RENT, FUEL))
    assert [got[("txn.credit", 1)].value, got[("txn.debit", 2)].value, got[("txn.debit", 3)].value] == ["52000.00", "18000.00", "2000.00"]
    for key in (("txn.debit", 1), ("txn.credit", 2), ("txn.credit", 3)):  # the other side of the row is found empty: nothing moved there
        f = got[key]
        assert f.value is None and not f.word_ids and f.conf >= TH.low_conf, key
    assert [got[("txn.balance", r)].value for r in (1, 2, 3)] == ["62000.00", "44000.00", "42000.00"]


def test_the_debit_or_credit_is_located_at_the_amount_and_says_what_decided_it(tmp_path):
    got = read(tmp_path, TOP + HEAD + rows_of(SALARY, RENT))
    f = got[("txn.credit", 1)]
    assert f.raw == "52,000.00" and len(f.word_ids) == 1 and f.conf >= TH.low_conf  # the words of the amount, not those of the mark
    assert "Dr/Cr" in f.note and "'Cr'" in f.note and "credit" in f.note
    assert "'Dr'" in got[("txn.debit", 2)].note
    px = 200 / 72
    assert 400 * px - 60 * px < f.box[2] < 405 * px and f.box[1] > 154 * px - 14 * px  # at the amount on its line, not at the mark


def test_the_mark_is_a_field_of_its_own_with_its_own_place(tmp_path):
    got = read(tmp_path, TOP + HEAD + rows_of(SALARY, RENT))
    m = got[("txn.marker", 1)]
    assert (m.value, m.raw, m.kind) == ("Cr", "Cr", "text") and len(m.word_ids) == 1 and m.box[0] > 415 * 200 / 72


@pytest.mark.parametrize("printed, side", [("DR", "debit"), ("Dr.", "debit"), ("(Dr)", "debit"), ("Debit", "debit"),
                                           ("CR", "credit"), ("Cr.", "credit"), ("(Cr)", "credit"), ("CREDIT", "credit")])
def test_the_mark_is_read_in_its_usual_spellings(tmp_path, printed, side):
    got = read(tmp_path, TOP + HEAD + rows_of(("01/05/2026", "Transfer", "5,000.00", printed, "15,000.00 Cr")))
    other = "credit" if side == "debit" else "debit"
    assert got[(f"txn.{side}", 1)].value == "5000.00" and got[(f"txn.{other}", 1)].value is None


@pytest.mark.parametrize("heading", ["Dr/Cr", "DR/CR", "Cr/Dr", "Dr / Cr"])
def test_the_column_of_marks_is_known_by_its_usual_headings(tmp_path, heading):
    head = [h if h[2] != "Dr/Cr" else (h[0], h[1], heading, h[3]) for h in HEAD]
    assert read(tmp_path, TOP + head + rows_of(SALARY))[("txn.credit", 1)].value == "52000.00"


def test_a_side_is_no_surer_than_the_mark_that_chose_it(tmp_path):
    """The mark decides which side the amount goes to: a mark the reader is unsure of makes the side unsure, and only that row's."""
    _, cd, _ = create_case(tmp_path / "data", [("d1.pdf", lines_pdf(TOP + HEAD + rows_of(SALARY, RENT)))], TH)
    doc = run_case(cd, TH).documents[0]
    smudged = [w for w in doc.pages[0].words if w.text == "Cr" and abs(w.pt_box[0] - 420) < 1]  # the mark of row 1, not a 'Cr' after a balance
    assert len(smudged) == 1
    smudged[0].conf = 0.55
    got = {(f.name, f.row): f for f in extract_document(doc, SPEC, TH)}
    assert got[("txn.credit", 1)].conf == pytest.approx(0.55) and got[("txn.debit", 2)].conf > 0.9


def test_a_mark_that_is_neither_dr_nor_cr_leaves_both_sides_of_the_row_unread(tmp_path):
    odd = ("02/05/2026", "Rent", "18,000.00", "TRF", "44,000.00 Cr")
    got = read(tmp_path, TOP + HEAD + rows_of(SALARY, odd, FUEL))
    for side in ("debit", "credit"):
        f = got[(f"txn.{side}", 2)]
        assert f.value is None and f.conf == 0 and "Dr/Cr" in f.note and "TRF" in f.note, f.note
    assert got[("txn.credit", 1)].value == "52000.00" and got[("txn.debit", 3)].value == "2000.00"  # the rows around it are read


@pytest.mark.parametrize("printed", ["Drawn", "Crossed", "Cr/Dr", "Dr Cr"])
def test_a_mark_is_read_on_its_letters_and_not_on_how_it_starts(tmp_path, printed):
    got = read(tmp_path, TOP + HEAD + rows_of(("01/05/2026", "Transfer", "5,000.00", printed, "15,000.00 Cr")))
    for side in ("debit", "credit"):
        f = got[(f"txn.{side}", 1)]
        assert f.value is None and f.conf == 0 and "neither Dr nor Cr" in f.note, (printed, f.note)


def test_an_amount_with_no_mark_beside_it_is_neither_a_debit_nor_a_credit(tmp_path):
    got = read(tmp_path, TOP + HEAD + rows_of(SALARY, ("02/05/2026", "Rent", "18,000.00", None, "44,000.00 Cr")))
    for side in ("debit", "credit"):
        f = got[(f"txn.{side}", 2)]
        assert f.value is None and f.conf == 0 and "empty" in f.note, f.note


def test_a_row_with_neither_an_amount_nor_a_mark_moved_nothing(tmp_path):
    got = read(tmp_path, TOP + HEAD + rows_of(("01/05/2026", "Balance brought forward", None, None, "10,000.00 Cr"), SALARY))
    for side in ("debit", "credit"):
        f = got[(f"txn.{side}", 1)]
        assert f.value is None and not f.word_ids and f.conf >= TH.low_conf, side


def test_an_amount_that_cannot_be_read_leaves_the_row_unread(tmp_path):
    got = read(tmp_path, TOP + HEAD + rows_of(SALARY, ("02/05/2026", "Rent", "18.000.00", "Dr", "44,000.00 Cr")))
    for side in ("debit", "credit"):
        f = got[(f"txn.{side}", 2)]
        assert f.value is None and f.conf == 0 and "amount" in f.note, f.note


def test_the_balance_chain_of_such_a_statement_is_checked_and_holds(tmp_path):
    case = case_of(tmp_path, TOP + HEAD + rows_of(SALARY, RENT, FUEL))
    assert not [f for f in case.findings if f.fclass == "inconsistency"], [f.title for f in case.findings]
    assert not [f for f in case.findings if f.title == "Cannot fully verify this statement"], [f.detail for f in case.findings]


def test_an_edited_balance_of_such_a_statement_is_an_inconsistency_that_names_the_balance(tmp_path):
    edited = ("02/05/2026", "Rent", "18,000.00", "Dr", "46,000.00 Cr")  # 62,000 - 18,000 is 44,000
    case = case_of(tmp_path, TOP + HEAD + rows_of(SALARY, edited, ("03/05/2026", "Fuel", "2,000.00", "Dr", "44,000.00 Cr")))
    hits = [f for f in case.findings if f.fclass == "inconsistency" and f.detector == "statement_balance"]
    assert hits and "row 2" in hits[0].detail, [(f.detector, f.title) for f in case.findings]


def test_a_mark_that_cannot_be_read_is_a_gap_the_dossier_names_and_not_a_pass(tmp_path):
    odd = ("02/05/2026", "Rent", "18,000.00", "TRF", "44,000.00 Cr")
    case = case_of(tmp_path, TOP + HEAD + rows_of(SALARY, odd, FUEL))
    gaps = [f for f in case.findings if f.title == "Cannot fully verify this statement"]
    assert gaps and "row 2" in gaps[0].detail, [(f.detector, f.title, f.detail) for f in case.findings]
    assert not [f for f in case.findings if f.fclass == "inconsistency"]


# --- what must stay as it was

SEPARATE = [(40, 140, "Date", 9), (110, 140, "Details", 9), (300, 140, "Debit", 9), (380, 140, "Credit", 9), (460, 140, "Balance", 9),
            (530, 140, "Dr/Cr", 9),
            (40, 154, "01/05/2026", 10), (110, 154, "Salary", 10), (380, 154, "52,000.00", 10), (460, 154, "62,000.00", 10), (530, 154, "Cr", 10),
            (40, 168, "02/05/2026", 10), (110, 168, "Rent", 10), (300, 168, "18,000.00", 10), (460, 168, "44,000.00", 10), (530, 168, "Cr", 10)]


def test_a_statement_with_a_debit_and_a_credit_column_is_read_as_before(tmp_path):
    """A 'Dr/Cr' column after the balance marks the balance, not an amount; the table has its own debit and credit."""
    got = read(tmp_path, TOP + SEPARATE)
    assert [got[("txn.credit", 1)].value, got[("txn.debit", 2)].value] == ["52000.00", "18000.00"]
    assert not [key for key in got if key[0] in ("txn.marker", "txn.amount")]


def test_a_heading_with_a_debit_and_a_credit_is_not_given_an_amount_and_a_mark_as_well(tmp_path):
    """The columns of amounts and of marks are looked for only where the heading names no debit and no credit."""
    both = [(40, 140, "Date", 9), (110, 140, "Details", 9), (230, 140, "Debit", 9), (290, 140, "Credit", 9), right(400, 140, "Amount", 9),
            (420, 140, "Dr/Cr", 9), right(560, 140, "Balance", 9),
            (40, 154, "01/05/2026", 10), (110, 154, "Salary", 10), (290, 154, "52,000.00", 10), right(560, 154, "62,000.00 Cr", 10),
            (40, 168, "02/05/2026", 10), (110, 168, "Rent", 10), (230, 168, "18,000.00", 10), right(560, 168, "44,000.00 Cr", 10)]
    got = read(tmp_path, TOP + both)
    assert [got[("txn.credit", 1)].value, got[("txn.debit", 2)].value] == ["52000.00", "18000.00"]
    assert not [key for key in got if key[0] in ("txn.marker", "txn.amount")]


def test_an_amount_column_with_no_column_of_marks_is_not_guessed_at(tmp_path):
    head = [h for h in HEAD if h[2] != "Dr/Cr"]
    got = read(tmp_path, TOP + head + [r for r in rows_of(SALARY, RENT) if r[2] not in ("Cr", "Dr")])
    assert not [key for key in got if key[0] in ("txn.marker", "txn.amount")]
    assert got[("txn.debit", 1)].value is None and got[("txn.debit", 1)].conf == 0 and "not found" in got[("txn.debit", 1)].note


def test_a_column_of_marks_with_no_column_of_amounts_is_not_guessed_at(tmp_path):
    head = [h for h in HEAD if h[2] != "Amount"]
    got = read(tmp_path, TOP + head + [r for r in rows_of(SALARY, RENT) if r[2] not in ("52,000.00", "18,000.00")])
    assert not [key for key in got if key[0] == "txn.marker"]
    assert got[("txn.credit", 1)].value is None and got[("txn.credit", 1)].conf == 0
