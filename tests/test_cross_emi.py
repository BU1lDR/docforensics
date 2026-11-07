"""The existing EMI declared on an application against the instalments a bank statement shows being paid (cross_emi). The documents
are built by hand: rows, cells and confidences are chosen here, so each rule of the check has a case that would break it. The
last tests pin what the check must never do to the scored splits: the base generator writes no instalment word, so a run over
those splits cannot change."""
from decimal import Decimal

import pytest

from datagen.fictional import identity
from datagen.layouts.statement import CREDITS, DEBITS
from docforensics.checks.cross import is_instalment
from docforensics.checks.within import SHOWN
from docforensics.model import Field
from tests.test_cross import TH, by, built, check, document, fld

UNREAD = "?"  # a cell the reader could not make anything of


def cell(doc, n, column, value, kind, page=1):
    """One table cell: a value, None for an empty cell that was found, UNREAD for one that was not."""
    if value == UNREAD:
        value, conf, words = None, 0.0, []
    else:
        conf, words = 0.95, ([] if value is None else [f"{doc}-w{n}{column}"])
    return Field(id=f"{doc}-r{n}-{column}", doc=doc, name=f"table.{column}", raw=value or "", value=value, kind=kind, conf=conf,
                 word_ids=words, page=page, box=(10.0, 100.0 + 20 * n, 100.0, 118.0 + 20 * n), row=n)


def statement(*rows, doc="D1", quality="text-layer", read_mode="text-layer"):
    """rows are (date 'YYYY-MM-DD', description, debit, credit); row numbers count from 1."""
    cells = []
    for n, (day, text, debit, credit) in enumerate(rows, 1):
        cells += [cell(doc, n, "date", day, "date"), cell(doc, n, "description", text, "text"),
                  cell(doc, n, "debit", debit, "amount"), cell(doc, n, "credit", credit, "amount")]
    return document(doc, "bank_statement", *cells, quality=quality, read_mode=read_mode)


def application(declared, doc="D2", conf=0.95, **kw):
    if declared is UNREAD:
        return document(doc, "loan_application", fld(doc, "existing_emi", None, conf=0.0, kind="amount", words=0), **kw)
    return document(doc, "loan_application", fld(doc, "existing_emi", declared, conf=conf, kind="amount"), **kw)


OTHER = [("2026-03-03", "UPI/Grocery Orchid Stores", "850.00", None), ("2026-03-05", "NEFT/Salary Harborview", None, "52000.00"),
         ("2026-03-18", "POS/Fuel Station", "1500.00", None)]
EMI_ROW = ("2026-03-07", "ECS/EMI Home Loan 4412", "12000.00", None)  # row 4 after OTHER


def run(tmp_path, declared, *rows, **kw):
    return check(tmp_path, built(statement(*rows, **kw), application(declared)))


def gaps(case):
    """The text of the one folded limitation of the comparisons that could not be made."""
    return " ".join(f.detail for f in by(case, "cross_checks"))


# --- what is a finding

@pytest.mark.parametrize("declared", ["0.00", "5000.00", "10000.00"])
def test_a_declared_emi_below_the_instalment_debit_is_an_inconsistency_that_cites_both_documents(tmp_path, declared):
    (f,) = by(run(tmp_path, declared, *OTHER, EMI_ROW), "cross_emi")
    assert (f.fclass, f.family) == ("inconsistency", "cross_document") and f.conf >= TH.low_conf
    assert [e.field_id for e in f.evidence] == ["D2-existing_emi", "D1-r4-debit", "D1-r4-description"]  # the declared figure first
    assert f"INR {Decimal(declared):.2f}" in f.detail and "INR 12000.00" in f.detail
    assert "March 2026" in f.detail and "row 4" in f.detail
    assert "Tolerance" in f.detail and f"{TH.emi_rel:.0%}" in f.detail  # the limit is printed


@pytest.mark.parametrize("declared", ["12000.00", "11000.00", "13000.00", "20000.00"])
def test_a_declared_emi_that_matches_or_exceeds_the_instalments_gives_nothing_at_all(tmp_path, declared):
    case = run(tmp_path, declared, *OTHER, EMI_ROW)
    assert not by(case, "cross_emi") and "instalment" not in gaps(case)


def test_the_tolerance_is_a_share_of_the_instalments_paid(tmp_path):
    assert not by(run(tmp_path, "10900.00", *OTHER, EMI_ROW), "cross_emi")  # 1,100 short, under 10 % of 12,000
    assert by(run(tmp_path / "b", "10700.00", *OTHER, EMI_ROW), "cross_emi")  # 1,300 short


def test_a_small_instalment_is_held_to_the_absolute_floor(tmp_path):
    small = ("2026-03-07", "ECS/EMI Home Loan 4412", "5.00", None)  # 10 % of 5 is under the floor of INR 1.00 ...
    assert not by(run(tmp_path, "4.20", *OTHER, small), "cross_emi")  # 0.80 short is over 10 % but within the floor
    assert by(run(tmp_path / "b", "3.50", *OTHER, small), "cross_emi")  # ... and 1.50 short is not


def test_two_instalments_in_one_month_are_added_up(tmp_path):
    second = ("2026-03-21", "NACH/Instalment Car Loan 7731", "7000.00", None)
    assert not by(run(tmp_path, "19000.00", *OTHER, EMI_ROW, second), "cross_emi")
    (f,) = by(run(tmp_path / "b", "12000.00", *OTHER, EMI_ROW, second), "cross_emi")  # one loan declared, two paid
    assert "INR 19000.00" in f.detail and "rows 4, 5" in f.detail
    assert [e.field_id for e in f.evidence] == ["D2-existing_emi", "D1-r4-debit", "D1-r4-description", "D1-r5-debit", "D1-r5-description"]


def test_months_are_compared_one_at_a_time_and_the_largest_is_named(tmp_path):
    feb = ("2026-02-07", "ECS/EMI Home Loan 4412", "12000.00", None)
    assert not by(run(tmp_path, "12000.00", feb, *OTHER, EMI_ROW), "cross_emi")  # the same instalment twice is not 24,000
    smaller = ("2026-02-07", "ECS/EMI Home Loan 4412", "9000.00", None)
    (f,) = by(run(tmp_path / "b", "5000.00", smaller, *OTHER, EMI_ROW), "cross_emi")
    assert "March 2026" in f.detail and "February" not in f.detail and "INR 12000.00" in f.detail


def test_a_credit_beside_the_instalments_is_neither_listed_nor_cited(tmp_path):
    credit = ("2026-03-09", "NEFT/Loan A/C 4412", None, "500000.00")
    (f,) = by(run(tmp_path, "0.00", *OTHER, EMI_ROW, credit), "cross_emi")
    assert "row 4" in f.detail and "row 5" not in f.detail and "INR 12000.00" in f.detail
    assert len(f.evidence) == 3  # the declared figure, and the one debit with its narration


def test_a_long_run_of_instalments_is_all_added_and_listed_to_the_cap(tmp_path):
    rows = [(f"2026-03-{d:02d}", "ECS/EMI Loan 1", "1000.00", None) for d in range(1, 9)]  # eight debits of INR 1,000
    (f,) = by(run(tmp_path, "0.00", *rows), "cross_emi")
    assert "INR 8000.00" in f.detail and "and 2 more" in f.detail
    assert len(f.evidence) == 1 + 2 * SHOWN


def test_each_statement_is_compared_on_its_own_and_the_finding_cites_the_one_that_shows_the_instalment(tmp_path):
    case = built(statement(*OTHER, doc="D1"), statement(*OTHER, EMI_ROW, doc="D2"), application("0.00", doc="D3"))
    check(tmp_path, case)
    (f,) = by(case, "cross_emi")
    assert {e.doc for e in f.evidence} == {"D3", "D2"}


def test_instalments_split_over_two_statements_are_not_added_together(tmp_path):
    half = ("2026-03-07", "ECS/EMI Home Loan 4412", "6000.00", None)
    case = built(statement(*OTHER, half, doc="D1"), statement(*OTHER, half, doc="D2"), application("6000.00", doc="D3"))
    check(tmp_path, case)
    assert not by(case, "cross_emi")  # each statement shows 6,000 and 6,000 was declared


# --- what is an instalment

@pytest.mark.parametrize("text", ["ECS/EMI Home Loan 4412", "NACH DR EMI-LN-5521", "emi 12345", "LOAN INSTALMENT 7/12", "Instalment: Car",
                                  "Installments paid", "INSTL 8841", "Loan repayment", "NEFT/LOAN A/C 99", "ACH D- EMI"])
def test_a_narration_with_the_word_emi_instalment_or_loan_is_an_instalment(text):
    assert is_instalment(text)


@pytest.mark.parametrize("text", ["EMIRATES AIRLINES BOOKING", "REMITTANCE TO FAMILY", "SEMINAR REGISTRATION", "DEMI GLACE RESTAURANT",
                                  "NEFT/Salary Harborview", "UPI/Rent Payment", "ECS/Electricity Board", "",
                                  "LOAN PROCESSING FEE", "EMI BOUNCE CHARGES", "GST ON LOAN FEE", "EMI REVERSAL", "EMI REFUND",
                                  "LOAN A/C CLOSURE", "LOAN FORECLOSURE", "LOAN PREPAYMENT", "PENALTY ON EMI", "RETURNED EMI",
                                  "LOAN INSURANCE PREMIUM", "TAX ON LOAN"])
def test_a_fee_a_reversal_or_a_word_that_only_contains_emi_is_not_an_instalment(text):
    assert not is_instalment(text)


def test_the_base_generator_never_writes_an_instalment_word():
    """The scored splits are drawn from this vocabulary. While it holds, the check finds nothing in them and cannot change a score."""
    assert not [t for t in DEBITS + CREDITS if is_instalment(t)]
    for seed in range(40):
        assert not is_instalment(f"NEFT/Salary {identity(seed).employer.split()[0]}")


def test_a_credit_whose_narration_names_a_loan_is_not_an_instalment_paid(tmp_path):
    credit = ("2026-03-09", "NEFT/Loan A/C 4412", None, "500000.00")
    assert is_instalment(credit[1])  # the words alone would make it one: the column decides
    case = run(tmp_path, "0.00", *OTHER, credit)
    assert not by(case, "cross_emi") and "instalment" not in gaps(case)


# --- what is not there, or not trustworthy: never a silent pass

def test_a_statement_with_no_instalment_debit_leaves_the_declared_emi_alone(tmp_path):
    case = check(tmp_path, built(statement(*OTHER), application(UNREAD)))
    assert not by(case, "cross_emi") and "instalment" not in gaps(case)  # nothing was there to compare


def test_an_unreadable_declared_emi_is_a_gap_when_the_statement_shows_an_instalment(tmp_path):
    case = check(tmp_path, built(statement(*OTHER, EMI_ROW), application(UNREAD)))
    assert not by(case, "cross_emi")
    (gap,) = by(case, "cross_checks")
    assert "existing EMI" in gap.detail and "instalment" in gap.detail and {"D1", "D2"} <= {e.doc for e in gap.evidence}


def test_an_application_without_the_field_is_the_same_gap(tmp_path):
    app = document("D2", "loan_application", fld("D2", "loan_amount", "300000.00", kind="amount"))
    case = check(tmp_path, built(statement(*OTHER, EMI_ROW), app))
    assert not by(case, "cross_emi") and "existing EMI" in gaps(case)


def test_an_instalment_row_whose_debit_cannot_be_read_is_a_gap_not_a_pass(tmp_path):
    case = run(tmp_path, "0.00", *OTHER, ("2026-03-07", "ECS/EMI Home Loan 4412", UNREAD, None))
    assert not by(case, "cross_emi")
    assert "instalment" in gaps(case) and "could not be read" in gaps(case)


def test_an_instalment_debit_with_no_readable_date_cannot_be_placed_in_a_month(tmp_path):
    case = run(tmp_path, "0.00", *OTHER, (UNREAD, "ECS/EMI Home Loan 4412", "12000.00", None))
    assert not by(case, "cross_emi") and "instalment" in gaps(case)


def test_readable_instalments_that_already_exceed_the_declared_figure_are_found_even_if_another_row_is_unreadable(tmp_path):
    unread = ("2026-03-09", "NACH/EMI Car Loan 7731", UNREAD, None)
    (f,) = by(run(tmp_path, "5000.00", *OTHER, EMI_ROW, unread), "cross_emi")
    assert "INR 12000.00" in f.detail and "could not be read" in f.detail and "minimum" in f.detail  # the total is a floor, and says so


def test_an_unreadable_row_of_another_month_does_not_qualify_the_month_found(tmp_path):
    feb = ("2026-02-09", "NACH/EMI Car Loan 7731", UNREAD, None)
    (f,) = by(run(tmp_path, "5000.00", feb, *OTHER, EMI_ROW), "cross_emi")
    assert "INR 12000.00" in f.detail and "could not be read" not in f.detail


def test_an_instalment_with_no_readable_date_may_belong_to_the_month_found(tmp_path):
    undated = (UNREAD, "NACH/EMI Car Loan 7731", "4000.00", None)
    (f,) = by(run(tmp_path, "5000.00", *OTHER, EMI_ROW, undated), "cross_emi")
    assert "INR 12000.00" in f.detail and "row 5 could not be read" in f.detail.lower() and "minimum" in f.detail


def test_a_negative_debit_is_not_added_to_the_instalments(tmp_path):
    case = run(tmp_path, "0.00", *OTHER, ("2026-03-07", "ECS/EMI Home Loan 4412", "-12000.00", None))
    assert not by(case, "cross_emi") and "instalment" in gaps(case)  # not used, and said so


def test_unreadable_rows_beside_a_matching_figure_are_still_reported(tmp_path):
    unread = ("2026-03-09", "NACH/EMI Car Loan 7731", UNREAD, None)
    case = run(tmp_path, "12000.00", *OTHER, EMI_ROW, unread)
    assert not by(case, "cross_emi") and "instalment" in gaps(case)  # a match on the rows that were read is not a match on all


def test_a_declared_emi_on_a_poor_page_is_not_used(tmp_path):
    case = check(tmp_path, built(statement(*OTHER, EMI_ROW), application("0.00", quality="poor", read_mode="ocr")))
    assert not by(case, "cross_emi") and "existing EMI" in gaps(case)


def test_a_doubtful_declared_figure_is_shown_as_a_possible_misreading(tmp_path):
    case = check(tmp_path, built(statement(*OTHER, EMI_ROW), application("0.00", conf=0.4)))
    (f,) = by(case, "cross_emi")
    assert f.fclass == "processing_limitation" and f.title.startswith("Possible extraction error, verify:")


def test_a_difference_read_by_ocr_from_a_degraded_statement_is_a_possible_misreading(tmp_path):
    case = check(tmp_path, built(statement(*OTHER, EMI_ROW, quality="degraded", read_mode="ocr"), application("0.00")))
    (f,) = by(case, "cross_emi")
    assert f.fclass == "processing_limitation" and f.title.startswith("Possible extraction error, verify:")


def test_a_good_scan_is_trusted_like_a_text_layer(tmp_path):
    case = check(tmp_path, built(statement(*OTHER, EMI_ROW, quality="good", read_mode="ocr"), application("0.00")))
    assert [f.fclass for f in by(case, "cross_emi")] == ["inconsistency"]


def test_a_poor_page_is_not_used_and_the_comparison_says_it_could_not_look_there(tmp_path):
    case = check(tmp_path, built(statement(*OTHER, EMI_ROW, quality="poor", read_mode="ocr"), application("0.00")))
    assert not by(case, "cross_emi")  # no description on the page can be trusted
    assert "instalment" in gaps(case) and "poor" in gaps(case)


def test_an_application_with_no_statement_is_told_the_emi_was_not_compared(tmp_path):
    slip = document("D1", "payslip", fld("D1", "employee_name", "Meera K. Varghese", "name"))
    case = check(tmp_path, built(slip, application("0.00")))
    assert "instalment" in gaps(case)
