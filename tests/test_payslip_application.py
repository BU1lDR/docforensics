"""Payslips and loan applications (Task 14): drawn truth in, fields out, then the checks inside each document. A tampered
document is drawn with one text changed and nothing recomputed, so the truth says which box the finding must cite."""
from decimal import Decimal

import pytest

from datagen.fictional import identity
from datagen.layouts import money, words
from datagen.layouts.application import draw_application
from datagen.layouts.payslip import draw_payslip
from datagen.layouts.statement import draw_statement
from docforensics.config import Thresholds
from docforensics.ingest import create_case
from docforensics.pipeline import run_case
from docforensics.understand.classify import classify
from docforensics.understand.specs import load_specs
from tests.helpers import iou, within_only

TH = Thresholds()
SPECS = load_specs()
SLIP_COLS = ("earning_name", "earning_amount", "deduction_name", "deduction_amount")


def run(tmp_path, *pdfs):
    case, cd, _ = create_case(tmp_path / "data", [(f"d{i}.pdf", p) for i, p in enumerate(pdfs, 1)], TH)
    return within_only(run_case(cd, TH))


def header(doc):
    return {f.name: f for f in doc.fields if f.row is None}


def cells(doc):
    return {(f.row, f.name.partition(".")[2]): f for f in doc.fields if f.row is not None}


def on(e, drawn, key):
    page, *box = drawn.truth["boxes"][key]
    return e.page == page and iou(e.box, box) >= 0.9


def cites(f, drawn, key):
    return any(on(e, drawn, key) for e in f.evidence)


def slip_rows(seed):
    return draw_payslip(identity(seed), seed=seed).truth["rows"]


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_extraction_matches_truth(tmp_path, seed):
    slip, app = draw_payslip(identity(seed), seed=seed), draw_application(identity(seed), seed=seed)
    got = run(tmp_path, slip.pdf, app.pdf).documents
    assert [d.doc_type for d in got] == ["payslip", "loan_application"]
    for doc, drawn, n in zip(got, (slip, app), (11, 9)):
        head = header(doc)
        assert set(head) == set(drawn.truth["fields"]) and len(head) == n, doc.doc_type
        for name, want in drawn.truth["fields"].items():
            page, *box = drawn.truth["boxes"][name]
            assert head[name].value == want, (doc.doc_type, name)
            assert head[name].page == page and iou(head[name].box, box) >= 0.9, (doc.doc_type, name)
            assert head[name].conf >= TH.low_conf, (doc.doc_type, name)
    rows = cells(got[0])
    assert len(slip.truth["rows"]) == 4 and len(rows) == 16 and not cells(got[1])
    for r, row in enumerate(slip.truth["rows"], 1):
        for col in SLIP_COLS:
            f = rows[(r, col)]
            assert f.value == row[col], (r, col)
            if row[col] is None:  # a blank cell is found empty: nothing read, no words behind it, but not unreadable
                assert not f.word_ids and f.conf > 0, (r, col)
            else:
                page, *box = slip.truth["boxes"][f"{col}@{r}"]
                assert f.page == page and iou(f.box, box) >= 0.9 and f.conf >= TH.low_conf, (r, col)


def test_three_types_are_told_apart(tmp_path):
    ident = identity(2)
    case = run(tmp_path, draw_statement(ident, seed=2).pdf, draw_payslip(ident, seed=2).pdf, draw_application(ident, seed=2).pdf)
    assert [(d.doc_type, d.type_conf >= 0.5) for d in case.documents] == [
        ("bank_statement", True), ("payslip", True), ("loan_application", True)]
    for doc in case.documents:  # take the winner away and nothing else reaches its own threshold on this page
        assert classify(doc.pages, {t: s for t, s in SPECS.items() if t != doc.doc_type})[0] == "unknown", doc.doc_type


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5, 6])
def test_genuine_documents_have_no_findings(tmp_path, seed):
    ident = identity(seed)
    case = run(tmp_path, draw_payslip(ident, seed=seed).pdf, draw_application(ident, seed=seed).pdf)
    assert [f.title for f in case.findings] == []


def test_changed_net_pay_is_flagged_by_the_sum_and_by_the_words(tmp_path):
    ident = identity(5)
    drawn = draw_payslip(ident, seed=5, overrides={"net_pay": money(ident.net_pay + 5000)})
    found = {f.detector: f for f in run(tmp_path, drawn.pdf).findings}
    assert set(found) == {"payslip_sums", "payslip_words"}
    for f in found.values():
        assert (f.fclass, f.family, f.status) == ("inconsistency", "arithmetic", "open") and f.conf >= TH.low_conf
        assert on(f.evidence[0], drawn, "net_pay") and "Tolerance: INR 1.00" in f.detail
    assert cites(found["payslip_sums"], drawn, "gross_earnings") and cites(found["payslip_sums"], drawn, "total_deductions")
    assert cites(found["payslip_words"], drawn, "net_pay_words")


def test_words_that_do_not_match_the_figure_are_flagged_alone_and_not_repeated(tmp_path):
    ident = identity(5)
    wrong = words(ident.net_pay + 4000)
    drawn = draw_payslip(ident, seed=5, overrides={"net_pay_words": wrong})
    (f,) = run(tmp_path, drawn.pdf).findings
    assert (f.fclass, f.detector, f.family) == ("inconsistency", "payslip_words", "arithmetic")
    assert on(f.evidence[0], drawn, "net_pay") and cites(f, drawn, "net_pay_words")
    assert str(ident.net_pay + 4000) in f.detail.replace(",", "") and wrong not in f.detail + f.title  # the document's words stay out of the finding


def test_a_difference_inside_the_tolerance_passes_and_one_outside_does_not(tmp_path):
    ident = identity(1)
    inside = draw_payslip(ident, seed=1, overrides={"net_pay": f"{ident.net_pay}.50"})
    assert [f.title for f in run(tmp_path, inside.pdf).findings] == []
    outside = draw_payslip(ident, seed=1, overrides={"net_pay": f"{ident.net_pay + 2}.00"})
    assert {f.detector for f in run(tmp_path, outside.pdf).findings} == {"payslip_sums", "payslip_words"}


def test_a_changed_earning_breaks_the_gross_total_alone(tmp_path):
    ident = identity(4)
    old = Decimal(slip_rows(4)[1]["earning_amount"])
    drawn = draw_payslip(ident, seed=4, overrides={"earning_amount@2": money(old + 3000)})
    (f,) = run(tmp_path, drawn.pdf).findings
    assert (f.fclass, f.detector) == ("inconsistency", "payslip_sums") and on(f.evidence[0], drawn, "gross_earnings")
    assert all(cites(f, drawn, f"earning_amount@{n}") for n in range(1, 5))


def test_a_changed_deduction_breaks_the_deduction_total_alone(tmp_path):
    ident = identity(4)
    old = Decimal(slip_rows(4)[2]["deduction_amount"])
    drawn = draw_payslip(ident, seed=4, overrides={"deduction_amount@3": money(old + 700)})
    (f,) = run(tmp_path, drawn.pdf).findings
    assert (f.fclass, f.detector) == ("inconsistency", "payslip_sums") and on(f.evidence[0], drawn, "total_deductions")
    assert all(cites(f, drawn, f"deduction_amount@{n}") for n in range(1, 4))  # the blank fourth cell is zero, and is not cited


@pytest.mark.parametrize("pay_date, flagged", [("30/04/2026", False), ("31/05/2026", False), ("13/06/2026", True), ("28/03/2026", True)])
def test_the_pay_date_is_in_the_pay_month_or_the_month_after(tmp_path, pay_date, flagged):
    drawn = draw_payslip(identity(2), seed=2, overrides={"pay_month": "April 2026", "pay_date": pay_date})
    found = run(tmp_path, drawn.pdf).findings
    assert [f.detector for f in found] == (["payslip_dates"] if flagged else []), pay_date
    for f in found:
        assert (f.fclass, f.family) == ("inconsistency", "arithmetic") and on(f.evidence[0], drawn, "pay_date") and cites(f, drawn, "pay_month")
        assert "April 2026" not in f.detail and "04/2026" in f.detail  # months are given as numbers


def test_a_pay_month_years_from_the_pay_date_is_flagged(tmp_path):
    drawn = draw_payslip(identity(3), seed=3, overrides={"pay_month": "March 2024"})
    (f,) = run(tmp_path, drawn.pdf).findings
    assert f.detector == "payslip_dates" and f.conf >= TH.low_conf


@pytest.mark.parametrize("key, text, gap", [("net_pay", "N/A", "net pay"), ("pay_month", "Quarter Two", "pay month"), ("pay_date", "31/04/2026", "pay date")])
def test_an_unreadable_value_is_a_limitation_not_a_finding(tmp_path, key, text, gap):
    (f,) = run(tmp_path, draw_payslip(identity(2), seed=2, overrides={key: text}).pdf).findings
    assert (f.fclass, f.detector, f.family) == ("processing_limitation", "payslip_checks", "limitation")
    assert f.title.startswith("Cannot fully verify this payslip") and gap in f.detail and f.explanation_source == "template"


def test_a_weekday_that_does_not_match_the_date_is_flagged(tmp_path):
    drawn = draw_application(identity(3), seed=3, overrides={"application_date": "Tue 03 Nov 2025"})  # 3 Nov 2025 was a Monday
    (f,) = run(tmp_path, drawn.pdf).findings
    assert (f.fclass, f.detector, f.family, f.status) == ("inconsistency", "application_dates", "arithmetic", "open")
    assert on(f.evidence[0], drawn, "application_date") and f.conf >= TH.low_conf
    assert "Tuesday" in f.detail and "Monday" in f.detail and "03/11/2025" in f.detail


def test_no_weekday_printed_means_nothing_to_check(tmp_path):
    drawn = draw_application(identity(3), seed=3, overrides={"application_date": "03 Nov 2025"})
    assert [f.title for f in run(tmp_path, drawn.pdf).findings] == []


def test_an_unreadable_application_date_is_a_limitation_not_a_finding(tmp_path):
    drawn = draw_application(identity(3), seed=3, overrides={"application_date": "Mon 31 Nov 2025"})  # there is no 31 November
    (f,) = run(tmp_path, drawn.pdf).findings
    assert (f.fclass, f.detector, f.family) == ("processing_limitation", "application_checks", "limitation")
    assert f.title.startswith("Cannot fully verify this application") and "application date" in f.detail
