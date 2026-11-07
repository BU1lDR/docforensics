"""Header values found by their label in layouts the drawn documents do not use: a label with its value under it, a value that wraps
over several lines, a label that goes on past the words the type knows. Pages are plain text at fixed places, so every case is exact.
These came out of probing the tool with statements, payslips and applications set in other house styles (docs/probe.md): the
reader had taken the next label for a value, or the first line of an address for the whole address, at full confidence."""
import pymupdf
import pytest

from docforensics.config import Thresholds
from docforensics.ingest import create_case
from docforensics.pipeline import run_case
from docforensics.understand.classify import classify
from docforensics.understand.extract import extract_document
from docforensics.understand.specs import FieldSpec, TypeSpec, load_specs
from tests.helpers import lines_pdf

TH = Thresholds()
SPECS = load_specs()
ADDRESS = "Flat 32, Maple Terrace, Garden Lane, Kochi 682001"
# labels in a row, the value of each right under it
STACKED = [(40, 100, "Account Holder", 9), (260, 100, "Account Number", 9), (420, 100, "Statement Period", 9),
           (40, 114, "Meera K. Varghese", 11), (260, 114, "000123456789", 11), (420, 114, "01/05/2026 to 31/05/2026", 11)]
# the address over four lines, then the next field
WRAPPED = [(40, 100, "Address", 9), (200, 100, "Flat 32,", 11), (200, 113, "Maple Terrace,", 11), (200, 126, "Garden Lane,", 11),
           (200, 139, "Kochi 682001", 11), (40, 160, "Account Number", 9), (200, 160, "000123456789", 11)]
# a table whose last heading is the label of a field, and under it a summary block with the labels and their values
HEADINGS = [(40, 100, "Date", 9), (110, 100, "Details", 9), (300, 100, "Debit", 9), (380, 100, "Credit", 9), (460, 100, "Closing Balance", 9),
            (40, 114, "01/05/2026", 10), (110, 114, "Salary", 10), (380, 114, "52,000.00", 10), (460, 114, "1,72,500.00", 10),
            (40, 128, "02/05/2026", 10), (110, 128, "Rent", 10), (300, 128, "18,000.00", 10), (460, 128, "1,54,500.00", 10)]
SUMMARY = [(40, 400, "Opening Balance", 9), (260, 400, "Closing Balance", 9), (40, 414, "1,20,500.00", 11), (260, 414, "1,54,500.00", 11)]


def spec_of(**kw) -> TypeSpec:
    return TypeSpec(type="t", min_score=1, keywords={"address": 1},
                    fields=[FieldSpec(name="address", kind="text", labels=["address"], **kw),
                            FieldSpec(name="account", kind="id", labels=["account number"])])


def header(tmp_path, lines, spec="bank_statement") -> dict:
    _, cd, _ = create_case(tmp_path / "data", [("d1.pdf", lines_pdf(lines))], TH)
    doc = run_case(cd, TH).documents[0]
    chosen = SPECS[spec] if isinstance(spec, str) else spec
    return {f.name: f for f in extract_document(doc, chosen, TH) if f.row is None}


def read(tmp_path, lines, spec="bank_statement") -> tuple[str, dict]:
    """(the type the page was given, every field by (name, row))."""
    _, cd, _ = create_case(tmp_path / "data", [("d1.pdf", lines_pdf(lines))], TH)
    doc = run_case(cd, TH).documents[0]
    return doc.doc_type, {(f.name, f.row): f for f in extract_document(doc, SPECS[spec], TH)}


def test_labels_in_a_row_with_their_values_under_them(tmp_path):
    """The cell to the right of 'Account Holder' is the next label, not its value: the value is the cell under the label."""
    got = header(tmp_path, STACKED)
    assert (got["account_holder"].value, got["account_no"].value) == ("Meera K. Varghese", "000123456789")
    assert (got["period_start"].value, got["period_end"].value) == ("2026-05-01", "2026-05-31")  # the last label has nothing to its right
    for name in ("account_holder", "account_no", "period_start"):
        assert "under the label" in got[name].note and got[name].conf >= TH.low_conf, name


def test_a_label_among_labels_is_never_a_value(tmp_path):
    got = header(tmp_path, [(40, 100, "Address", 9), (260, 100, "Account Number", 9),
                            (40, 114, "Statement Period", 9), (260, 114, "000123456789", 11)])
    assert got["address"].value is None and got["address"].note == "value not found next to the label"  # a label on each side, no value
    assert got["address"].conf == 0.0 and got["account_no"].value == "000123456789"


def test_a_cell_that_ends_in_a_colon_is_a_label_even_if_the_type_does_not_know_it(tmp_path):
    got = header(tmp_path, [(40, 100, "Address", 9), (260, 100, "Branch:", 9), (40, 114, "Cost centre:", 9), (260, 114, "Andheri", 11)])
    assert got["address"].value is None


def test_words_that_finish_a_label_are_not_its_value(tmp_path):
    got = header(tmp_path, [(40, 100, "Account Holder Name", 9), (200, 100, "Meera K. Varghese", 11),
                            (40, 120, "Account Number (INR)", 9), (200, 120, "000123456789", 11)])
    assert got["account_holder"].value == "Meera K. Varghese"  # 'Name' is the rest of the label, not the holder
    assert got["account_no"].value == "000123456789"  # so is '(INR)'
    assert "under the label" not in got["account_holder"].note


def test_a_value_that_starts_with_a_label_word_keeps_it(tmp_path):
    """Only what follows the label inside its own cell can finish it: 'Number 12' in a cell of its own is an address."""
    got = header(tmp_path, [(40, 100, "Address", 9), (200, 100, "Number 12, Garden Lane", 11)])
    assert got["address"].value == "Number 12, Garden Lane"


def test_a_value_that_wraps_is_read_whole_where_the_type_allows_it(tmp_path):
    assert header(tmp_path, WRAPPED, spec_of(lines=4))["address"].value == ADDRESS
    assert header(tmp_path, WRAPPED, spec_of())["address"].value == "Flat 32,"  # a type that does not say so reads one line
    got = header(tmp_path, WRAPPED)
    assert got["address"].value == ADDRESS and got["account_no"].value == "000123456789"  # the next field is not swallowed
    assert header(tmp_path, WRAPPED, "loan_application")["address"].value == ADDRESS


def test_a_wrapped_value_has_one_box_around_all_its_lines(tmp_path):
    f = header(tmp_path, WRAPPED)["address"]
    assert f.raw == ADDRESS and len(f.word_ids) == 8
    px = 200 / 72  # boxes are in pixels of a 200-DPI render of the page
    assert f.box[1] < 105 * px and f.box[3] > 142 * px and f.box[0] > 190 * px  # from the top of the first line to the foot of the last


@pytest.mark.parametrize("name, lines", [
    ("next label", [(40, 100, "Address", 9), (200, 100, "Flat 32, Maple Terrace", 11), (40, 114, "Employer", 9), (200, 114, "Northwind Test Pvt Ltd", 11)]),
    ("far below", [(40, 100, "Address", 9), (200, 100, "Flat 32, Maple Terrace", 11), (200, 170, "Page 1 of 2", 9)]),
    ("not aligned", [(40, 100, "Address", 9), (200, 100, "Flat 32, Maple Terrace", 11), (120, 113, "Kochi 682001", 11)]),
    ("label in the column", [(40, 100, "Address", 9), (200, 100, "Flat 32, Maple Terrace", 11), (200, 113, "Account Number", 9)]),
])
def test_a_wrapped_value_stops_where_the_next_thing_begins(tmp_path, name, lines):
    assert header(tmp_path, lines, spec_of(lines=4))["address"].value == "Flat 32, Maple Terrace", name


# a value of 2, 3 and 4 lines with its label centred against it, as a table cell is unless it says otherwise: the label stands
# between the two middle lines, or on the middle one
CENTRED2 = [(200, 100, "Flat 32, Maple Terrace,", 11), (40, 106, "Address", 9), (200, 113, "Kochi 682001", 11),
            (40, 150, "Account Number", 9), (200, 150, "000123456789", 11)]
CENTRED3 = [(200, 100, "Flat 32,", 11), (40, 113, "Address", 9), (200, 113, "Maple Terrace, Garden Lane,", 11), (200, 126, "Kochi 682001", 11),
            (40, 170, "Account Number", 9), (200, 170, "000123456789", 11)]
CENTRED4 = [(200, 100, "Flat 32,", 11), (200, 113, "Maple Terrace,", 11), (40, 119, "Address", 9), (200, 126, "Garden Lane,", 11),
            (200, 139, "Kochi 682001", 11), (40, 180, "Account Number", 9), (200, 180, "000123456789", 11)]


@pytest.mark.parametrize("name, lines, want", [
    ("two lines", CENTRED2, "Flat 32, Maple Terrace, Kochi 682001"),
    ("three lines, the label on the middle one", CENTRED3, "Flat 32, Maple Terrace, Garden Lane, Kochi 682001"),
    ("four lines", CENTRED4, ADDRESS),
])
def test_a_label_centred_against_a_value_of_several_lines_reads_the_whole_value(tmp_path, name, lines, want):
    got = header(tmp_path, lines)
    assert got["address"].value == want, name
    assert got["account_no"].value == "000123456789"  # and the next field is not swallowed
    assert got["address"].conf >= TH.low_conf


def test_a_value_centred_on_its_label_says_how_it_was_read_and_has_one_box(tmp_path):
    f = header(tmp_path, CENTRED4)["address"]
    px = 200 / 72
    assert "beside the label" in f.note and f.box[1] < 95 * px and f.box[3] > 141 * px and f.box[0] > 190 * px


def test_the_tail_of_the_field_before_is_not_part_of_the_value(tmp_path):
    """The tail of the field before, with a gap of a row, is not part of a two-line address whose label is on its first line."""
    lines = [(40, 100, "Account Number", 9), (200, 100, "000123456789", 11), (200, 113, "(savings)", 11),
             (40, 140, "Address", 9), (200, 140, "Flat 32, Maple Terrace,", 11), (200, 153, "Kochi 682001", 11)]
    assert header(tmp_path, lines)["address"].value == "Flat 32, Maple Terrace, Kochi 682001"


@pytest.mark.parametrize("name, lines", [
    ("a line on one side only", [(200, 100, "Flat 32, Maple Terrace,", 11), (40, 106, "Address", 9)]),
    ("labels beside it", [(200, 100, "Branch:", 9), (40, 106, "Address", 9), (200, 113, "Cost centre:", 9)]),
    ("not in a column", [(120, 100, "Flat 32, Maple Terrace,", 11), (40, 106, "Address", 9), (300, 113, "Kochi 682001", 11)]),
    ("left of the label", [(10, 100, "Flat 32,", 11), (250, 106, "Address", 9), (10, 113, "Kochi 682001", 11)]),
    ("far apart", [(200, 100, "Flat 32,", 11), (40, 125, "Address", 9), (200, 150, "Kochi 682001", 11)]),
])
def test_a_label_with_nothing_centred_on_it_has_no_value(tmp_path, name, lines):
    got = header(tmp_path, lines)["address"]
    assert got.value is None and got.note == "value not found next to the label", name


def test_a_wrapped_value_under_its_label_is_read_whole(tmp_path):
    lines = [(40, 100, "Address", 9), (40, 114, "Flat 32, Maple Terrace,", 11), (40, 127, "Garden Lane, Kochi 682001", 11),
             (40, 158, "Account Number", 9), (40, 172, "000123456789", 11)]
    got = header(tmp_path, lines)
    assert got["address"].value == ADDRESS and "under the label" in got["address"].note
    assert got["account_no"].value == "000123456789"


def test_a_heading_of_the_table_is_not_the_label_of_a_field(tmp_path):
    """'Closing Balance' above a column of balances: the first balance under it is not the statement's closing balance."""
    assert header(tmp_path, HEADINGS)["closing_balance"].note == "label not found"
    got = header(tmp_path, HEADINGS + SUMMARY)  # the summary block's own labels are found instead, past the heading
    assert (got["opening_balance"].value, got["closing_balance"].value) == ("120500.00", "154500.00")
    assert got["closing_balance"].box[1] > 400  # and that is where the field points


def test_a_cell_that_is_not_an_amount_is_not_the_amount(tmp_path):
    got = header(tmp_path, [(40, 100, "Opening Balance", 9), (200, 100, "Total Debits", 9), (40, 114, "1,20,500.00", 11), (200, 114, "70,000.00", 11)])
    assert got["opening_balance"].value == "120500.00" and "under the label" in got["opening_balance"].note
    got = header(tmp_path, [(40, 100, "Opening Balance", 9), (200, 100, "n/a", 11)])  # nothing else to read: the cell is kept, as unreadable
    assert got["opening_balance"].value is None and got["opening_balance"].raw == "n/a" and got["opening_balance"].note == "not a readable amount"


def test_a_label_with_a_stop_and_a_colon_after_it_is_still_that_label(tmp_path):
    """'A/c No.:' is 'a/c no' with a stop and a colon: the characters that end a label do not count against it."""
    got = header(tmp_path, [(40, 100, "Customer Name:", 9), (200, 100, "Meera K. Varghese", 11),
                            (40, 120, "A/c No.:", 9), (200, 120, "000123456789", 11)])
    assert (got["account_holder"].value, got["account_no"].value) == ("Meera K. Varghese", "000123456789")


def test_a_bare_date_is_the_application_date_only_with_its_colon(tmp_path):
    assert read(tmp_path, [(300, 100, "Date: 20/08/2026", 11)], "loan_application")[1][("application_date", None)].value == "2026-08-20"
    other = read(tmp_path, [(40, 100, "Date of Birth: 01/01/1990", 11), (300, 130, "Date", 11), (360, 130, "20/08/2026", 11)], "loan_application")[1]
    assert other[("application_date", None)].value is None  # 'Date' with no colon, and a date of birth, are not the application's date


def test_the_wordings_of_a_payslip_that_calls_itself_a_salary_slip(tmp_path):
    lines = [(40, 60, "Northwind Test Pvt Ltd", 18), (40, 90, "Salary Slip for the month of May 2026", 12),
             (40, 120, "Employee Name", 9), (200, 120, "Meera K. Varghese", 11), (40, 140, "Employee No", 9), (200, 140, "E-10442", 11),
             (40, 160, "Bank Account No", 9), (200, 160, "000123456789", 11), (40, 180, "Payment Date", 9), (200, 180, "31/05/2026", 11),
             (40, 200, "Gross Salary", 9), (200, 200, "52,000.00", 11), (40, 220, "Total Deductions", 9), (200, 220, "6,900.00", 11),
             (40, 240, "Net Salary", 9), (200, 240, "45,100.00", 11)]
    kind, got = read(tmp_path, lines, "payslip")
    assert kind == "payslip"
    assert (got[("employee_id", None)].value, got[("bank_account", None)].value) == ("E-10442", "000123456789")
    assert (got[("pay_date", None)].value, got[("net_pay", None)].value) == ("2026-05-31", "45100.00")


def test_a_statement_whose_columns_are_called_particulars_and_withdrawal_amt(tmp_path):
    lines = [(40, 100, "Date", 9), (110, 100, "Particulars", 9), (300, 100, "Withdrawal Amt.", 9), (380, 100, "Deposit Amt.", 9), (460, 100, "Closing Balance", 9),
             (40, 114, "01/05/2026", 10), (110, 114, "Salary", 10), (380, 114, "52,000.00", 10), (460, 114, "1,72,500.00", 10),
             (40, 128, "02/05/2026", 10), (110, 128, "Rent", 10), (300, 128, "18,000.00", 10), (460, 128, "1,54,500.00", 10)]
    got = read(tmp_path, lines)[1]
    assert (got[("txn.description", 1)].value, got[("txn.credit", 1)].value, got[("txn.balance", 1)].value) == ("Salary", "52000.00", "172500.00")
    assert (got[("txn.debit", 2)].value, got[("txn.balance", 2)].value) == ("18000.00", "154500.00")


def test_a_statement_period_given_as_from_and_to(tmp_path):
    got = header(tmp_path, [(40, 100, "Statement From : 01/05/2026 To : 31/05/2026", 10)])
    assert (got["period_start"].value, got["period_end"].value) == ("2026-05-01", "2026-05-31")


def test_the_monthly_gross_income_of_an_application(tmp_path):
    got = header(tmp_path, [(40, 100, "Monthly Gross Income (Rs.)", 9), (260, 100, ": 1,07,000.00", 11)], "loan_application")
    assert got["declared_monthly_income"].value == "107000.00"


def test_a_unit_after_a_heading_is_not_part_of_its_name(tmp_path):
    """'Withdrawal Amount (INR)' and 'Balance (INR)' are the headings 'withdrawal amount' and 'balance'."""
    lines = [(40, 100, "Date", 9), (110, 100, "Transaction Remarks", 9), (230, 100, "Withdrawal Amount (INR)", 9),
             (350, 100, "Deposit Amount (INR)", 9), (470, 100, "Balance (INR)", 9),
             (40, 114, "01/05/2026", 10), (110, 114, "Salary", 10), (350, 114, "52,000.00", 10), (470, 114, "1,72,500.00", 10),
             (40, 128, "02/05/2026", 10), (110, 128, "Rent", 10), (230, 128, "18,000.00", 10), (470, 128, "1,54,500.00", 10)]
    got = read(tmp_path, lines)[1]
    assert (got[("txn.credit", 1)].value, got[("txn.balance", 1)].value) == ("52000.00", "172500.00")
    assert (got[("txn.debit", 2)].value, got[("txn.description", 2)].value) == ("18000.00", "Rent")


def test_a_row_of_labels_above_the_table_is_not_its_heading(tmp_path):
    """A summary row (Opening Balance, Total Debits, ...) has the column words in it, but only the real heading has the date column."""
    lines = [(40, 80, "Opening Balance", 9), (200, 80, "Total Debits", 9), (360, 80, "Total Credits", 9), (480, 80, "Closing Balance", 9),
             (40, 94, "1,20,500.00", 10), (200, 94, "18,000.00", 10), (360, 94, "52,000.00", 10), (480, 94, "1,54,500.00", 10)] + HEADINGS
    got = read(tmp_path, lines)[1]
    assert [got[("txn.date", r)].value for r in (1, 2)] == ["2026-05-01", "2026-05-02"]
    assert (got[("txn.credit", 1)].value, got[("txn.debit", 2)].value) == ("52000.00", "18000.00")


def test_a_keyword_may_name_several_wordings_of_one_thing(tmp_path):
    spec = TypeSpec(type="slip", min_score=5, keywords={"payslip|pay slip|salary slip": 3, "net pay|net salary": 2}, fields=[])

    def kind(title, net):
        _, cd, _ = create_case(tmp_path / f"{title}{net}".replace(" ", ""), [("d1.pdf", lines_pdf([(40, 60, title, 14), (40, 90, net, 10)]))], TH)
        return classify(run_case(cd, TH).documents[0].pages, {"slip": spec})[0]

    assert [kind(t, n) for t, n in (("Payslip", "Net Pay"), ("Salary Slip", "Net Salary"), ("Pay Slip", "Net Pay"))] == ["slip"] * 3
    assert kind("Salary Slip", "Payslip") == "unknown"  # three wordings of one thing weigh 3 once, short of the 5 needed


# a table whose long narrations wrap inside their cell: the rest of the narration is a line of its own, with no date or amount
TOP = [(40, 100, "Date", 9), (110, 100, "Particulars", 9), (300, 100, "Withdrawal Amt.", 9), (380, 100, "Deposit Amt.", 9), (460, 100, "Closing Balance", 9)]


def rows_of(*rows, pitch=26):
    """Table rows, each (date, narration lines, debit, credit, balance): the first narration line on the row of the numbers, the
    others under it. `pitch` is the distance from the first line of a row to the first line of the next."""
    out, y = [], 114
    for date, narration, debit, credit, balance in rows:
        out += [(40, y, date, 10), (110, y, narration[0], 10), (460, y, balance, 10)]
        out += [(300, y, debit, 10)] if debit else [(380, y, credit, 10)]
        out += [(110, y + 12 * k, line, 10) for k, line in enumerate(narration[1:], 1)]
        y += pitch + 12 * (len(narration) - 1)
    return out


SALARY = ("01/05/2026", ["NEFT/Salary Ironwood-0838-PAYMENT", "FROM PHONE"], None, "52,000.00", "1,72,500.00")
RENT = ("02/05/2026", ["Rent"], "18,000.00", None, "1,54,500.00")


def test_a_closing_balance_labelled_closing_bal_is_found_under_its_label(tmp_path):
    """A summary row of labels with the values under them, as retail statements print it; the table's own 'Closing Balance' heading
    above it is not the label."""
    summary = [(40, 400, "Opening Balance", 9), (140, 400, "Dr Count", 9), (230, 400, "Closing Bal", 9),
               (40, 414, "1,20,500.00", 11), (140, 414, "2", 11), (230, 414, "1,54,500.00", 11)]
    got = header(tmp_path, HEADINGS + summary)
    assert (got["opening_balance"].value, got["closing_balance"].value) == ("120500.00", "154500.00")


def test_a_narration_that_wraps_is_read_whole(tmp_path):
    got = read(tmp_path, TOP + rows_of(SALARY, RENT))[1]
    assert got[("txn.description", 1)].value == "NEFT/Salary Ironwood-0838-PAYMENT FROM PHONE"
    assert got[("txn.description", 2)].value == "Rent"  # the next row does not take the line
    assert (got[("txn.credit", 1)].value, got[("txn.balance", 2)].value) == ("52000.00", "154500.00")
    f = got[("txn.description", 1)]
    assert f.conf >= TH.low_conf and "2 lines" in f.note and f.box[3] > 126 * 200 / 72  # one box around both lines


def test_a_narration_broken_after_a_hyphen_is_joined_without_a_space(tmp_path):
    """A browser breaks a long reference after a hyphen, and the reference has no space there. A hyphen that stands apart ('Rent -')
    is not the end of one, and the words on one line keep their spaces."""
    cut = ("01/05/2026", ["NEFT/Salary Ironwood-0838-", "PAYMENT FROM PHONE"], None, "52,000.00", "1,72,500.00")
    apart = ("02/05/2026", ["Rent -", "May"], "18,000.00", None, "1,54,500.00")
    got = read(tmp_path, TOP + rows_of(cut, apart))[1]
    assert got[("txn.description", 1)].value == "NEFT/Salary Ironwood-0838-PAYMENT FROM PHONE"
    assert got[("txn.description", 2)].value == "Rent - May"


def test_a_narration_of_three_lines_and_the_row_after_it(tmp_path):
    three = ("01/05/2026", ["UPI/Online Shopping-0283", "PAYMENT FROM", "PHONE ORCHID STORES"], "9,000.00", None, "1,11,500.00")
    got = read(tmp_path, TOP + rows_of(three, RENT))[1]
    assert got[("txn.description", 1)].value == "UPI/Online Shopping-0283 PAYMENT FROM PHONE ORCHID STORES"
    assert got[("txn.description", 2)].value == "Rent"


def test_a_narration_split_above_and_below_the_numbers_is_read_whole(tmp_path):
    """A table cell is centred on its row unless it says otherwise: the numbers stand on the middle line of the narration."""
    lines = TOP + [(110, 106, "NEFT/Salary Ironwood-0838", 10), (40, 114, "01/05/2026", 10), (380, 114, "52,000.00", 10), (460, 114, "1,72,500.00", 10),
                   (110, 122, "PAYMENT FROM PHONE", 10),
                   (110, 160, "UPI/Rent", 10), (40, 168, "02/05/2026", 10), (300, 168, "18,000.00", 10), (460, 168, "1,54,500.00", 10), (110, 176, "Payment", 10)]
    got = read(tmp_path, lines)[1]
    assert got[("txn.description", 1)].value == "NEFT/Salary Ironwood-0838 PAYMENT FROM PHONE"
    assert got[("txn.description", 2)].value == "UPI/Rent Payment"
    assert got[("txn.debit", 2)].value == "18000.00"


def test_a_line_that_could_belong_to_either_row_is_not_given_to_one(tmp_path):
    """Rows packed with no space between them: the line between two rows is as near to one as to the other."""
    lines = TOP + [(40, 114, "01/05/2026", 10), (110, 114, "NEFT/Salary", 10), (380, 114, "52,000.00", 10), (460, 114, "1,72,500.00", 10),
                   (110, 126, "FROM PHONE", 10),
                   (40, 138, "02/05/2026", 10), (110, 138, "Rent", 10), (300, 138, "18,000.00", 10), (460, 138, "1,54,500.00", 10)]
    got = read(tmp_path, lines)[1]
    for row, first in ((1, "NEFT/Salary"), (2, "Rent")):
        f = got[("txn.description", row)]
        assert f.value == first and f.conf < TH.low_conf and "between this row and a neighbour" in f.note, row
    assert got[("txn.credit", 1)].conf >= TH.low_conf  # the numbers are not in doubt


def test_a_line_far_under_the_last_row_is_not_part_of_it(tmp_path):
    got = read(tmp_path, TOP + rows_of(RENT) + [(110, 160, "Page 1 of 2", 10)])[1]
    assert got[("txn.description", 1)].value == "Rent" and "lines" not in got[("txn.description", 1)].note


def test_a_line_with_an_amount_is_not_a_continuation(tmp_path):
    """Only text is carried over: a line of numbers with no date is something else, and the rows stay as they were."""
    lines = TOP + rows_of(RENT) + [(300, 126, "5.00", 10)]
    got = read(tmp_path, lines)[1]
    assert got[("txn.description", 1)].value == "Rent" and got[("txn.debit", 1)].value == "18000.00"


def test_a_narration_is_not_joined_to_text_that_starts_elsewhere(tmp_path):
    """A line under a narration, in its column, that starts well to the right of it and is not centred on it is not the narration
    going on."""
    got = read(tmp_path, TOP + rows_of(RENT) + [(185, 126, "carried fwd", 10)])[1]
    assert got[("txn.description", 1)].value == "Rent"


def test_a_narration_centred_in_its_cell_is_read_whole(tmp_path):
    """A cell set centred puts the lines of a narration at different left edges, on one centre."""
    first, second = "NEFT/Salary Ironwood-0838", "from phone"
    x = 110 + (pymupdf.get_text_length(first, "helv", 10) - pymupdf.get_text_length(second, "helv", 10)) / 2
    lines = TOP + [(40, 114, "01/05/2026", 10), (110, 114, first, 10), (380, 114, "52,000.00", 10), (460, 114, "1,72,500.00", 10), (x, 126, second, 10)]
    assert read(tmp_path, lines)[1][("txn.description", 1)].value == f"{first} {second}"


# a heading set over three lines in narrow columns, as a bank prints a table of eight: a serial number in the first column, the date twice
WRAPPED_HEAD = [(40, 100, "S No.", 8), (70, 100, "Value", 8), (125, 100, "Transaction", 8), (190, 100, "Cheque", 8), (240, 100, "Transaction", 8),
                (390, 100, "Withdrawal", 8), (450, 100, "Deposit", 8), (510, 100, "Balance", 8),
                (70, 109, "Date", 8), (125, 109, "Date", 8), (190, 109, "Number", 8), (240, 109, "Remarks", 8),
                (390, 109, "Amount", 8), (450, 109, "Amount", 8), (510, 109, "(INR)", 8),
                (390, 118, "(INR)", 8), (450, 118, "(INR)", 8)]
SERIAL_ROWS = [(45, 140, "1", 8), (70, 140, "13/05/2026", 8), (125, 140, "13/05/2026", 8), (240, 140, "NEFT/Salary", 8),
               (392, 140, "0.00", 8), (452, 140, "52,000.00", 8), (512, 140, "1,72,500.00", 8),
               (45, 152, "2", 8), (70, 152, "14/05/2026", 8), (125, 152, "14/05/2026", 8), (240, 152, "Rent", 8),
               (392, 152, "18,000.00", 8), (452, 152, "0.00", 8), (512, 152, "1,54,500.00", 8)]


def test_a_heading_set_over_several_lines_is_read_as_one(tmp_path):
    """'Value' over 'Date', 'Withdrawal' over 'Amount' over '(INR)': the second line alone says 'Date', 'Amount', '(INR)'."""
    got = read(tmp_path, WRAPPED_HEAD + SERIAL_ROWS)[1]
    assert [got[("txn.date", r)].value for r in (1, 2)] == ["2026-05-13", "2026-05-14"]
    assert [got[("txn.description", r)].value for r in (1, 2)] == ["NEFT/Salary", "Rent"]
    assert [(got[("txn.debit", r)].value, got[("txn.credit", r)].value, got[("txn.balance", r)].value) for r in (1, 2)] == [
        ("0.00", "52000.00", "172500.00"), ("18000.00", "0.00", "154500.00")]
    assert all(f.conf >= TH.low_conf for f in got.values() if f.value)


# the same table as a browser prints it: headings of two lines stand at the top and the bottom of the row, those of one line between
# them (half a line off), the third line of two columns runs together, and the two dates stand side by side with nothing between them
MIXED_HEAD = [(40, 100, "S", 8), (116, 100, "Transaction", 8), (190, 100, "Cheque", 8), (390, 100, "Withdrawal", 8), (450, 100, "Deposit", 8),
              (70, 105, "Value Date", 8), (240, 105, "Transaction Remarks", 8), (510, 105, "Balance (INR)", 8),
              (40, 110, "No.", 8), (116, 110, "Date", 8), (190, 110, "Number", 8), (388, 110, "Amount (INR)", 8), (442, 110, "Amount (INR)", 8)]
MIXED_ROWS = [(45, 140, "1", 8), (70, 140, "13/05/2026", 8), (116, 140, "13/05/2026", 8), (240, 140, "NEFT/Salary", 8),
              (392, 140, "0.00", 8), (452, 140, "52,000.00", 8), (512, 140, "1,72,500.00", 8),
              (45, 152, "2", 8), (70, 152, "14/05/2026", 8), (116, 152, "15/05/2026", 8), (240, 152, "Rent", 8),
              (392, 152, "18,000.00", 8), (452, 152, "0.00", 8), (512, 152, "1,54,500.00", 8)]


def test_a_heading_whose_lines_stand_over_different_columns_is_read_whole(tmp_path):
    """A heading of one line is centred between the lines of those that need two: nothing above it, and it is a heading of its own."""
    got = read(tmp_path, MIXED_HEAD + MIXED_ROWS)[1]
    assert [got[("txn.description", r)].value for r in (1, 2)] == ["NEFT/Salary", "Rent"]
    assert [(got[("txn.debit", r)].value, got[("txn.credit", r)].value, got[("txn.balance", r)].value) for r in (1, 2)] == [
        ("0.00", "52000.00", "172500.00"), ("18000.00", "0.00", "154500.00")]


def test_two_dates_side_by_side_are_one_cell_and_the_first_is_read(tmp_path):
    """Value date and transaction date, set together: the cell holds both, and the field says which one it took."""
    got = read(tmp_path, MIXED_HEAD + MIXED_ROWS)[1]
    assert [got[("txn.date", r)].value for r in (1, 2)] == ["2026-05-13", "2026-05-14"]
    f = got[("txn.date", 2)]
    assert f.raw == "14/05/2026" and "2 dates" in f.note and f.conf >= TH.low_conf


# value date set far from the date, with the narration close after it: nearer to the narration than to the date column
DATES_APART = [(40, 100, "Date", 9), (200, 100, "Value Date", 9), (270, 100, "Details", 9), (390, 100, "Debit", 9), (450, 100, "Credit", 9),
               (510, 100, "Balance", 9),
               (40, 114, "13/05/2026", 10), (200, 114, "14/05/2026", 10), (270, 114, "Salary", 10), (452, 114, "52,000.00", 10),
               (512, 114, "1,72,500.00", 10),
               (40, 128, "14/05/2026", 10), (200, 128, "16/05/2026", 10), (270, 128, "Rent", 10), (392, 128, "18,000.00", 10),
               (512, 128, "1,54,500.00", 10)]


def test_a_second_date_column_far_from_the_first_does_not_fall_to_the_next_column(tmp_path):
    """The column of the value date is the column of the date: its cells are read with the first, not with the narration beside."""
    got = read(tmp_path, DATES_APART)[1]
    assert [got[("txn.date", r)].value for r in (1, 2)] == ["2026-05-13", "2026-05-14"]
    assert [got[("txn.description", r)].value for r in (1, 2)] == ["Salary", "Rent"]
    assert "2 dates" in got[("txn.date", 1)].note


# the value date set after the narration and the reference number, as some banks do: two date headings with others between them
VALUE_LATE = [(40, 100, "Date", 9), (110, 100, "Particulars", 9), (250, 100, "Chq./Ref.No.", 9), (320, 100, "Value Date", 9), (390, 100, "Debit", 9),
              (450, 100, "Credit", 9), (510, 100, "Balance", 9),
              (40, 114, "13/05/2026", 10), (110, 114, "Salary", 10), (250, 114, "REF4471", 10), (320, 114, "14/05/2026", 10),
              (452, 114, "52,000.00", 10), (512, 114, "1,72,500.00", 10),
              (40, 128, "14/05/2026", 10), (110, 128, "Rent", 10), (250, 128, "REF4472", 10), (320, 128, "16/05/2026", 10),
              (392, 128, "18,000.00", 10), (512, 128, "1,54,500.00", 10)]


def test_a_second_date_heading_with_other_columns_between_is_not_made_part_of_the_first(tmp_path):
    """Only a heading beside the first is the same column: here the narration stands between, and it keeps its own cells."""
    got = read(tmp_path, VALUE_LATE)[1]
    assert [got[("txn.date", r)].value for r in (1, 2)] == ["2026-05-13", "2026-05-14"]
    assert [got[("txn.description", r)].value for r in (1, 2)] == ["Salary", "Rent"]
    assert "dates" not in got[("txn.date", 1)].note


# the heading of the narration set centred over a column whose text starts well to the left of it, and a narration of two lines
# set above and below the row, the second a single short word: it stands nearer the heading of the column on its left than its own
CENTRED = [(40, 100, "Date", 8), (130, 100, "Cheque Number", 8), (290, 100, "Transaction Remarks", 8), (420, 100, "Debit", 8),
           (470, 100, "Credit", 8), (520, 100, "Balance", 8),
           (40, 130, "13/05/2026", 8), (205, 130, "NEFT/Salary Silverleaf-004650482664-ONLINE", 8), (472, 130, "52,000.00", 8),
           (522, 130, "1,72,500.00", 8),
           (205, 154, "UPI/Online Shopping-832732409964-BILL", 8), (40, 160, "14/05/2026", 8), (422, 160, "18,000.00", 8),
           (522, 160, "1,54,500.00", 8), (205, 166, "PAYMENT", 8),
           (40, 200, "15/05/2026", 8), (205, 200, "UPI/Rent Payment-928163279188-MONTHLY", 8), (422, 200, "9,000.00", 8),
           (522, 200, "1,45,500.00", 8)]


def test_a_short_line_of_a_narration_goes_with_the_column_whose_text_it_starts_with(tmp_path):
    """The place of a column is where its cells stand, not where its heading's words do."""
    got = read(tmp_path, CENTRED)[1]
    assert [got[("txn.description", r)].value for r in (1, 2, 3)] == [
        "NEFT/Salary Silverleaf-004650482664-ONLINE", "UPI/Online Shopping-832732409964-BILL PAYMENT", "UPI/Rent Payment-928163279188-MONTHLY"]
    assert [got[("txn.balance", r)].value for r in (1, 2, 3)] == ["172500.00", "154500.00", "145500.00"]
    assert (got[("txn.credit", 1)].value, got[("txn.debit", 2)].value, got[("txn.debit", 3)].value) == ("52000.00", "18000.00", "9000.00")


# a payslip as payroll software prints it: the same heading, 'Amount', over the earnings and over the deductions; names set to the
# left under headings centred over them, amounts to the right; a row with an earning and no deduction; the totals as the last row
def right(x1, y, text, fs):
    return (x1 - pymupdf.get_text_length(text, fontname="helv", fontsize=fs), y, text, fs)


SLIP_TOP = [(40, 60, "Ironwood Test Pvt Ltd", 18), (40, 90, "Salary Slip for the month of July 2026", 11),
            (40, 120, "Employee Name", 9), (200, 120, "Kavya L. Pillai", 11), (40, 140, "Employee No", 9), (200, 140, "EMP-6971", 11),
            (40, 160, "Pay Date", 9), (200, 160, "01 Aug 2026", 11)]
SLIP_HEAD = [(115, 220, "Earnings", 9), right(316, 220, "Amount", 9), (372, 220, "Deductions", 9), right(550, 220, "Amount", 9)]
SLIP_ROWS = [(45, 240, "Basic Salary", 10), right(316, 240, "35,000.00", 10), (330, 240, "Provident Fund", 10), right(550, 240, "4,200.00", 10),
             (45, 260, "House Rent Allowance", 10), right(316, 260, "14,000.00", 10), (330, 260, "Professional Tax", 10),
             right(550, 260, "200.00", 10),
             (45, 280, "Special Allowance", 10), right(316, 280, "21,000.00", 10)]
SLIP_TOTALS = [(100, 300, "Gross Salary", 10), right(316, 300, "70,000.00", 10), (360, 300, "Total Deductions", 10), right(550, 300, "4,400.00", 10),
               (45, 340, "Net Salary: 65,600.00", 10)]


def test_two_amount_columns_with_the_same_heading_are_told_apart_by_the_heading_before_each(tmp_path):
    """'Amount' over the earnings and 'Amount' over the deductions: the first goes with Earnings, the second with Deductions."""
    got = read(tmp_path, SLIP_TOP + SLIP_HEAD + SLIP_ROWS, "payslip")[1]
    assert [got[("line.earning_name", r)].value for r in (1, 2, 3)] == ["Basic Salary", "House Rent Allowance", "Special Allowance"]
    assert [got[("line.earning_amount", r)].value for r in (1, 2, 3)] == ["35000.00", "14000.00", "21000.00"]
    assert [got[("line.deduction_name", r)].value for r in (1, 2)] == ["Provident Fund", "Professional Tax"]
    assert [got[("line.deduction_amount", r)].value for r in (1, 2, 3)] == ["4200.00", "200.00", None]
    assert got[("line.deduction_amount", 3)].conf >= TH.low_conf  # found empty, not lost


def test_a_plain_amount_heading_with_another_heading_before_it_is_not_the_earnings_amount(tmp_path):
    """'Amount' names the earnings' amount only as the heading right after 'Earnings'. With 'Remarks' between them it is not
    guessed at: the table is not read, which is a gap the dossier shows, not a column of wrong numbers."""
    head = [(115, 220, "Earnings", 9), (200, 220, "Remarks", 9), right(316, 220, "Amount", 9), (372, 220, "Deductions", 9),
            right(550, 220, "Amount", 9)]
    got = read(tmp_path, SLIP_TOP + head + SLIP_ROWS, "payslip")[1]
    assert not [key for key in got if key[1] is not None]


def test_a_totals_row_in_the_table_is_not_a_line_of_it(tmp_path):
    """'Gross Salary 70,000.00 Total Deductions 4,400.00' as the last row would be counted as an earning and a deduction."""
    got = read(tmp_path, SLIP_TOP + SLIP_HEAD + SLIP_ROWS + SLIP_TOTALS, "payslip")[1]
    assert sorted({row for _, row in got if row is not None}) == [1, 2, 3]
    assert (got[("gross_earnings", None)].value, got[("total_deductions", None)].value) == ("70000.00", "4400.00")


def test_a_total_printed_as_one_text_with_its_amount_still_ends_the_table(tmp_path):
    """'Total Deductions: 4,400.00' as one run of text is the label of a total, and a line under it is not a row."""
    below = [(330, 300, "Total Deductions: 4,400.00", 10), (330, 320, "Loan Recovery", 10), right(550, 320, "1,000.00", 10)]
    got = read(tmp_path, SLIP_TOP + SLIP_HEAD + SLIP_ROWS + below, "payslip")[1]
    assert sorted({row for _, row in got if row is not None}) == [1, 2, 3]


def slip_case(tmp_path, lines):
    _, cd, _ = create_case(tmp_path / "data", [("d1.pdf", lines_pdf(lines))], TH)
    case = run_case(cd, TH)
    assert case.documents[0].doc_type == "payslip"
    return case


def test_a_consistent_payslip_of_this_layout_raises_no_inconsistency_and_its_table_is_checked(tmp_path):
    found = slip_case(tmp_path, SLIP_TOP + SLIP_HEAD + SLIP_ROWS + SLIP_TOTALS).findings
    assert not [f for f in found if f.fclass == "inconsistency"], [f.title for f in found]
    assert not [f for f in found if "earnings and deductions table" in f.detail]  # the table was read, so it is not a gap


def test_an_earning_that_does_not_add_up_to_the_gross_is_flagged_in_this_layout(tmp_path):
    rows = SLIP_ROWS[:-1] + [right(316, 280, "22,000.00", 10)]  # the last earning is typed 22,000.00; the gross still says 70,000.00
    found = slip_case(tmp_path, SLIP_TOP + SLIP_HEAD + rows + SLIP_TOTALS).findings
    assert [f.title for f in found if f.fclass == "inconsistency"] == ["Gross earnings do not equal the earnings listed"]


def test_a_deduction_listed_on_a_row_with_no_earning_is_still_counted(tmp_path):
    rows = SLIP_ROWS + [(330, 300, "Loan Recovery", 10), right(550, 300, "1,000.00", 10)]
    totals = [(100, 320, "Gross Salary", 10), right(316, 320, "70,000.00", 10), (360, 320, "Total Deductions", 10), right(550, 320, "5,400.00", 10),
              (45, 360, "Net Salary: 64,600.00", 10)]
    case = slip_case(tmp_path, SLIP_TOP + SLIP_HEAD + rows + totals)
    assert not [f for f in case.findings if f.fclass == "inconsistency"], [f.title for f in case.findings]
    got = {(f.name, f.row): f for f in case.documents[0].fields}
    assert got[("line.deduction_amount", 4)].value == "1000.00" and got[("line.earning_amount", 4)].value is None


# low-resolution OCR reads the comma of '35,000.00' as a point: '35.000.00' is no amount and is not guessed at
MISREAD = [(45, 240, "Basic Salary", 10), right(316, 240, "35.000.00", 10), (330, 240, "Provident Fund", 10), right(550, 240, "4.200.00", 10)]     + SLIP_ROWS[4:8] + [(45, 280, "Special Allowance", 10), right(316, 280, "21.000.00", 10)]


def test_a_row_whose_amounts_have_a_misread_separator_is_still_a_row_with_no_readable_amount(tmp_path):
    """A row of which every amount is unreadable is not dropped as if it were not there: its names are read, its amounts are
    missing (confidence 0), and a cell found empty next to them stays empty."""
    got = read(tmp_path, SLIP_TOP + SLIP_HEAD + MISREAD, "payslip")[1]
    assert sorted({row for _, row in got if row is not None}) == [1, 2, 3]
    assert [got[("line.earning_name", r)].value for r in (1, 2, 3)] == ["Basic Salary", "House Rent Allowance", "Special Allowance"]
    assert [got[("line.deduction_name", r)].value for r in (1, 2)] == ["Provident Fund", "Professional Tax"]
    for key in (("line.earning_amount", 1), ("line.deduction_amount", 1), ("line.earning_amount", 3)):
        assert got[key].value is None and got[key].conf == 0, key
    assert [got[("line.earning_amount", 2)].value, got[("line.deduction_amount", 2)].value] == ["14000.00", "200.00"]
    assert got[("line.deduction_amount", 3)].value is None and got[("line.deduction_amount", 3)].conf >= TH.low_conf  # found empty, not lost


def test_a_payslip_with_rows_it_could_not_read_is_not_summed_without_them(tmp_path):
    """Without the two unreadable rows the earnings listed come to 14,000.00 against a gross of 70,000.00, on a page read at full
    confidence: an inconsistency that is not there. They are rows, so the sum cannot be made, and the dossier says which amounts."""
    case = slip_case(tmp_path, SLIP_TOP + SLIP_HEAD + MISREAD + SLIP_TOTALS)
    assert not [f for f in case.findings if f.fclass == "inconsistency"], [f.title for f in case.findings]
    gaps = [f for f in case.findings if f.title == "Cannot fully verify this payslip"]
    assert gaps and "earning amount in lines 1, 3" in gaps[0].detail and "deduction amount in line 1" in gaps[0].detail, [f.detail for f in gaps]


# a statement of four rows: the third row's date is read 'O3/05/2026' (the letter O for the digit 0), as a scan at low resolution may
STATEMENT = [(40, 60, "Opening Balance", 9), (40, 74, "1,20,500.00", 11), (260, 60, "Closing Balance", 9), (260, 74, "1,48,000.00", 11),
             (40, 100, "Date", 9), (110, 100, "Details", 9), (300, 100, "Debit", 9), (380, 100, "Credit", 9), (460, 100, "Balance", 9),
             (40, 114, "01/05/2026", 10), (110, 114, "Salary", 10), (380, 114, "52,000.00", 10), (460, 114, "1,72,500.00", 10),
             (40, 128, "02/05/2026", 10), (110, 128, "Rent", 10), (300, 128, "18,000.00", 10), (460, 128, "1,54,500.00", 10),
             (40, 142, "O3/05/2026", 10), (110, 142, "Groceries", 10), (300, 142, "4,500.00", 10), (460, 142, "1,50,000.00", 10),
             (40, 156, "04/05/2026", 10), (110, 156, "Fuel", 10), (300, 156, "2,000.00", 10), (460, 156, "1,48,000.00", 10)]


def test_a_row_whose_date_is_misread_is_still_a_row_with_no_readable_date(tmp_path):
    """The row is not dropped as if it were not there: its date is missing (confidence 0) and its other cells are read."""
    got = read(tmp_path, STATEMENT)[1]
    assert sorted({row for _, row in got if row is not None}) == [1, 2, 3, 4]
    assert got[("txn.date", 3)].value is None and got[("txn.date", 3)].conf == 0 and got[("txn.date", 3)].note == "not a readable date"
    assert [got[("txn.description", 3)].value, got[("txn.debit", 3)].value, got[("txn.balance", 3)].value] == ["Groceries", "4500.00", "150000.00"]
    assert got[("txn.date", 4)].value == "2026-05-04"


def test_a_statement_with_a_misread_date_keeps_its_balance_chain_and_says_which_date(tmp_path):
    """Without that row the balance after row 2 (1,54,500.00) and after the row after it (1,48,000.00) differ by 6,500.00 where one row
    moves 2,000.00: an inconsistency that is not there. The chain holds, and the dossier says which date could not be read."""
    _, cd, _ = create_case(tmp_path / "data", [("d1.pdf", lines_pdf(STATEMENT))], TH)
    case = run_case(cd, TH)
    assert case.documents[0].doc_type == "bank_statement"
    assert not [f for f in case.findings if f.fclass == "inconsistency"], [f.title for f in case.findings]
    gaps = [f for f in case.findings if f.title == "Cannot fully verify this statement"]
    assert gaps and "date in row 3" in gaps[0].detail, [f.detail for f in gaps]


def test_a_cell_of_the_date_column_that_is_no_date_in_shape_is_not_a_row(tmp_path):
    """Only a cell shaped like a date (digits or what they are misread as, two separators alike) stands for a row."""
    note = [(40, 170, "Page 1 of 2", 10), (110, 170, "Continued overleaf", 10), (300, 170, "9,999.00", 10)]
    got = read(tmp_path, STATEMENT + note)[1]
    assert sorted({row for _, row in got if row is not None}) == [1, 2, 3, 4]


# an account that goes into overdraft: the balance after row 1 is printed '5,000.00 Dr' (5,000.00 owed), the others 'Cr'
OVERDRAWN = [(40, 60, "Opening Balance", 9), (40, 74, "10,000.00 Cr", 11), (260, 60, "Closing Balance", 9), (260, 74, "3,000.00 Cr", 11),
             (40, 100, "Date", 9), (110, 100, "Details", 9), (300, 100, "Debit", 9), (380, 100, "Credit", 9), (460, 100, "Balance", 9),
             (40, 114, "01/05/2026", 10), (110, 114, "Cheque", 10), (300, 114, "15,000.00", 10), (460, 114, "5,000.00 Dr", 10),
             (40, 128, "02/05/2026", 10), (110, 128, "Deposit", 10), (380, 128, "8,000.00", 10), (460, 128, "3,000.00 Cr", 10)]


def test_a_balance_marked_dr_is_read_as_money_owed_and_one_marked_cr_as_money_held(tmp_path):
    """'5,000.00 Dr' is minus 5,000.00. The marker on the amount of a debit column says which column it is, not a sign."""
    got = read(tmp_path, OVERDRAWN)[1]
    assert [got[("txn.balance", r)].value for r in (1, 2)] == ["-5000.00", "3000.00"]
    assert [got[("opening_balance", None)].value, got[("closing_balance", None)].value] == ["10000.00", "3000.00"]
    marked = [(x, y, "15,000.00 Dr" if t == "15,000.00" else t, z) for x, y, t, z in OVERDRAWN]
    assert read(tmp_path / "again", marked)[1][("txn.debit", 1)].value == "15000.00"


def test_a_statement_that_goes_into_overdraft_keeps_its_balance_chain(tmp_path):
    """Read as +5,000.00 the balance after a debit of 15,000.00 from 10,000.00 is a break in the chain of 10,000.00 that is not there."""
    _, cd, _ = create_case(tmp_path / "data", [("d1.pdf", lines_pdf(OVERDRAWN))], TH)
    case = run_case(cd, TH)
    assert case.documents[0].doc_type == "bank_statement"
    assert not [f for f in case.findings if f.fclass == "inconsistency"], [f.title for f in case.findings]
