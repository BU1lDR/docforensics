"""Cross-document checks and context rules (Task 15). Real runs: three drawn documents of one identity go through the whole
pipeline, and a manipulated one must be found where the manipulation is. Hand-built cases cover what a drawing cannot show:
a doubtful reading, an unreadable field, a masked account number."""
import dataclasses
import re
from datetime import date

import pymupdf
import pytest

from datagen.fictional import identity
from datagen.layouts.application import draw_application
from datagen.layouts.payslip import draw_payslip
from datagen.layouts.statement import draw_statement
from datagen.manipulate import c1_consistent_change, c2_cross_document, c3_duplicate
from docforensics.audit import AuditLog
from docforensics.config import Thresholds
from docforensics.ingest import create_case
from docforensics.model import Case, Document, Field, Page
from docforensics.pipeline import Ctx, run_case
from docforensics.store import CaseDir
from docforensics.understand.normalise import name_similarity
from tests.helpers import iou

TH = Thresholds()
SEEDS = (1, 2, 4)  # identities whose EMI ratio is well under emi_ratio_max


def run(tmp_path, *pdfs):
    case, cd, _ = create_case(tmp_path / "data", [(f"d{i}.pdf", p) for i, p in enumerate(pdfs, 1)], TH)
    return run_case(cd, TH)


def trio(ident, seed=1, stmt=None, slip=None, app=None):
    """(statement, payslip, application) drawn for one identity; any of them can be drawn from a changed identity instead.
    Uploaded in this order they become D1, D2 and D3."""
    return (draw_statement(stmt or ident, seed=seed), draw_payslip(slip or ident, seed=seed),
            draw_application(app or ident, seed=seed))


def by(case, detector):
    return [f for f in case.findings if f.detector == detector]


def hit(e, doc, drawn, key):
    """Evidence `e` sits on box `key` of the drawn document that was uploaded as `doc`."""
    page, *box = drawn.truth["boxes"][key]
    return e.doc == doc and e.page == page and iou(e.box, box) >= 0.9


def cites(f, doc, drawn, key):
    return any(hit(e, doc, drawn, key) for e in f.evidence)


# --- hand-built cases

def fld(doc, name, value, role="", conf=0.95, kind="text", words=1):
    return Field(id=f"{doc}-{name}", doc=doc, name=name, raw=value or "", value=value, kind=kind, conf=conf,
                 word_ids=[f"{doc}-w{i}" for i in range(words)], page=1, box=(10.0, 10.0, 100.0, 30.0), role=role)


def document(id, doc_type, *fields, meta=None, quality="text-layer", read_mode="text-layer"):
    return Document(id=id, sha256=id, filename=f"{id}.pdf", stored_path="", doc_type=doc_type, type_conf=1.0,
                    pages=[Page(n=1, width=1654, height=2339, quality_class=quality, read_mode=read_mode)], fields=list(fields),
                    meta=meta or {})


def built(*docs):
    return Case(id="C-test", created="2026-11-04T00:00:00Z", documents=list(docs))


def check(tmp_path, case):
    from docforensics.checks.cross import run_cross_checks
    cd = CaseDir.create(tmp_path)
    run_cross_checks(case, Ctx(cd, AuditLog(cd.audit_path), TH))
    return case


def pair(a, b, role="name", names=("employee_name", "applicant_name"), **kw):
    """A payslip and an application that carry one value each for a role."""
    return built(document("D1", "payslip", fld("D1", names[0], a, role, **kw)),
                 document("D2", "loan_application", fld("D2", names[1], b, role)))


# --- the genuine case, and each manipulation of design 8

@pytest.mark.parametrize("seed", SEEDS)
def test_genuine_documents_of_one_person_have_no_findings(tmp_path, seed):
    ident = identity(seed)
    assert (ident.existing_emi + ident.loan_amount / ident.tenure_months) / ident.monthly_gross <= TH.emi_ratio_max
    case = run(tmp_path, *(d.pdf for d in trio(ident, seed)))
    assert [(f.detector, f.title) for f in case.findings] == []


def test_c1_a_self_consistent_payslip_is_caught_only_against_the_other_documents(tmp_path):
    ident = identity(2)
    richer = c1_consistent_change(ident, monthly_gross=ident.monthly_gross + 20_000)
    stmt, slip, app = trio(ident, 2, slip=richer)
    case = run(tmp_path, stmt.pdf, slip.pdf, app.pdf)
    assert sorted(f.detector for f in case.findings) == ["cross_income", "cross_net_pay"]  # the payslip adds up by itself
    (net,) = by(case, "cross_net_pay")
    assert (net.fclass, net.family, net.status) == ("inconsistency", "cross_document", "open") and net.conf >= TH.low_conf
    assert hit(net.evidence[0], "D2", slip, "net_pay") and cites(net, "D1", stmt, "credit@2")
    assert "Tolerance: INR" in net.detail
    (inc,) = by(case, "cross_income")
    assert hit(inc.evidence[0], "D3", app, "declared_monthly_income") and cites(inc, "D2", slip, "gross_earnings")
    assert "Tolerance" in inc.detail


def test_c2_a_changed_name_is_pinned_on_the_document_that_differs(tmp_path):
    ident = identity(1)
    new = "Kavya R. Menon"
    assert name_similarity(ident.name, new) < TH.name_sim
    stmt, slip, app = trio(ident, 1, slip=c2_cross_document(ident, "name", new))
    case = run(tmp_path, stmt.pdf, slip.pdf, app.pdf)
    (f,) = case.findings
    assert (f.detector, f.fclass, f.family) == ("cross_name", "inconsistency", "cross_document") and len(f.evidence) == 3
    assert f.title.startswith("Mismatch:")  # far apart, not a near miss
    assert hit(f.evidence[0], "D2", slip, "employee_name")  # it disagrees with both others, so it comes first
    assert cites(f, "D1", stmt, "account_holder") and cites(f, "D3", app, "applicant_name")
    assert "0.85" in f.detail  # the limit is printed


def test_c2_a_changed_employer_is_caught_by_the_name_and_by_the_salary_credit(tmp_path):
    ident = identity(1)  # Harborview
    stmt, slip, app = trio(ident, 1, slip=c2_cross_document(ident, "employer", "Ironwood Test Pvt Ltd"))
    case = run(tmp_path, stmt.pdf, slip.pdf, app.pdf)
    assert sorted(f.detector for f in case.findings) == ["cross_employer", "cross_payer"]
    (emp,), (pay,) = by(case, "cross_employer"), by(case, "cross_payer")
    assert cites(emp, "D2", slip, "employer") and cites(emp, "D3", app, "employer")
    assert hit(pay.evidence[0], "D2", slip, "employer") and cites(pay, "D1", stmt, "description@2")
    assert (pay.fclass, pay.family) == ("inconsistency", "cross_document")


@pytest.mark.parametrize("new", ["Flat 9, Rose Court, Mill Road, Bhopal 462001", None])
def test_c2_a_changed_address_is_caught_even_when_only_a_number_changes(tmp_path, new):
    ident = identity(1)
    if new is None:  # same words, another flat number: the text alone is 98 % alike
        new = re.sub(r"Flat (\d+)", lambda m: f"Flat {int(m[1]) % 39 + 1}", ident.address)
    assert new != ident.address
    stmt, slip, app = trio(ident, 1, app=c2_cross_document(ident, "address", new))
    case = run(tmp_path, stmt.pdf, slip.pdf, app.pdf)
    (f,) = case.findings
    assert f.detector == "cross_address" and f.fclass == "inconsistency"
    assert cites(f, "D1", stmt, "address") and cites(f, "D3", app, "address")


def test_c2_an_application_dated_before_its_supporting_documents_is_flagged(tmp_path):
    ident = identity(1)  # statement for January 2026, payslip paid 01 Jan 2026
    early = c2_cross_document(ident, "month", date(2025, 10, 1).isoformat())  # application dated in November 2025
    stmt, slip, app = trio(ident, 1, app=early)
    case = run(tmp_path, stmt.pdf, slip.pdf, app.pdf)
    (f,) = case.findings
    assert (f.detector, f.fclass, f.family) == ("cross_dates", "inconsistency", "cross_document")
    assert hit(f.evidence[0], "D3", app, "application_date")
    assert cites(f, "D1", stmt, "period_end") and cites(f, "D2", slip, "pay_date")


def test_c2_a_payslip_outside_every_statement_period_is_reported_as_unchecked_not_as_a_conflict(tmp_path):
    ident = identity(1)
    old = c2_cross_document(ident, "month", date(2025, 6, 1).isoformat())  # paid a year and a half before the statement
    stmt, slip, app = trio(ident, 1, slip=old)
    case = run(tmp_path, stmt.pdf, slip.pdf, app.pdf)
    assert sorted(f.detector for f in case.findings) == ["context_age", "cross_checks"]
    (gap,), (age,) = by(case, "cross_checks"), by(case, "context_age")
    assert gap.fclass == "processing_limitation" and "pay date" in gap.detail and "D2" in gap.detail
    assert (age.fclass, age.family) == ("observation", "cross_document") and age.title.startswith("Context rule:")
    assert cites(age, "D2", slip, "pay_date") and "90" in age.detail and "synthetic" in age.detail


def test_c3_the_same_file_submitted_twice_is_an_observation(tmp_path):
    files = c3_duplicate([d.pdf for d in trio(identity(1), 1)])
    assert len(files) == 4 and files[3] == files[0]
    case = run(tmp_path, *files)
    (f,) = case.findings
    assert (f.detector, f.fclass, f.family) == ("cross_duplicate", "observation", "metadata")
    assert sorted(e.doc for e in f.evidence) == ["D1", "D4"] and all(e.page == 0 for e in f.evidence)


def test_the_manipulators_refuse_what_they_cannot_change():
    ident = identity(1)
    for bad in (lambda: c1_consistent_change(ident), lambda: c1_consistent_change(ident, name="X"),
                lambda: c2_cross_document(ident, "bank", "X"), lambda: c2_cross_document(ident, "month", "2025-06-15"),
                lambda: c3_duplicate([])):
        with pytest.raises(ValueError):
            bad()
    assert c2_cross_document(ident, "name", "A B") == dataclasses.replace(ident, name="A B", hand=ident.name)  # the signature stays the person's own


# --- what is not there, or not trustworthy: never a silent pass

def test_one_document_gets_one_notice(tmp_path):
    (f,) = run(tmp_path, draw_payslip(identity(1), seed=1).pdf).findings
    assert (f.detector, f.fclass) == ("cross_checks", "processing_limitation") and "one document" in f.title


def test_a_missing_document_type_is_reported_once_for_everything_that_depends_on_it(tmp_path):
    stmt, slip, _ = trio(identity(1), 1)
    (f,) = run(tmp_path, stmt.pdf, slip.pdf).findings
    assert (f.detector, f.fclass) == ("cross_checks", "processing_limitation") and "loan application" in f.detail
    assert {e.doc for e in f.evidence} == {"D1", "D2"} and all(e.page == 0 for e in f.evidence)


def test_a_low_confidence_reading_is_shown_as_a_possible_misreading(tmp_path):
    case = check(tmp_path, pair("Meera K. Varghese", "Rohan T. Kulkarni", conf=0.4))
    (f,) = by(case, "cross_name")
    assert f.fclass == "processing_limitation" and f.title.startswith("Possible extraction error, verify:")


@pytest.mark.parametrize("quality, value", [("text-layer", None), ("poor", "Rohan T. Kulkarni")])
def test_an_unreadable_value_is_a_gap_and_not_a_pass_or_a_conflict(tmp_path, quality, value):
    case = built(document("D1", "payslip", fld("D1", "employee_name", "Meera K. Varghese", "name")),
                 document("D2", "loan_application", fld("D2", "applicant_name", value, "name", conf=0.0 if value is None else 0.9,
                                                        words=0 if value is None else 1), quality=quality))
    check(tmp_path, case)
    assert not by(case, "cross_name")
    (gap,) = by(case, "cross_checks")
    assert gap.fclass == "processing_limitation" and "name" in gap.detail and "D2" in gap.detail


# --- near misses are graded (design 7.4): pass, written differently (observation), Minor mismatch, Mismatch

def graded(case, detector):
    """[(fclass, title)] of the findings of one detector."""
    return [(f.fclass, f.title) for f in by(case, detector)]


@pytest.mark.parametrize("other", ["MEERA K. VARGHESE", "Meera K Varghese", "meera  k.  varghese", "Meera K. Varghese"])
def test_names_that_differ_only_in_case_spacing_or_punctuation_pass(tmp_path, other):
    assert not by(check(tmp_path, pair("Meera K. Varghese", other)), "cross_name")


@pytest.mark.parametrize("other", ["Meera K. Varghes", "Meera K. Varghse", "Mera K. Varghese", "Meera K. Varghesee"])
def test_one_character_name_difference_is_flagged_minor(tmp_path, other):
    (f,) = by(check(tmp_path, pair("Meera K. Varghese", other)), "cross_name")
    assert (f.fclass, f.family) == ("inconsistency", "cross_document") and f.title.startswith("Minor mismatch:")
    assert "similarity 0.9" in f.detail and "0.85" in f.detail  # the measure and the limit are printed
    assert [e.doc for e in f.evidence] == ["D1", "D2"] and {e.field_id for e in f.evidence} == {"D1-employee_name", "D2-applicant_name"}


@pytest.mark.parametrize("other", ["M. K. Varghese", "Varghese, Meera K.", "Dr. Meera K. Varghese", "Meera Varghese K"])
def test_initials_only_difference_is_an_observation(tmp_path, other):
    (f,) = by(check(tmp_path, pair("Meera K. Varghese", other)), "cross_name")
    assert (f.fclass, f.family) == ("observation", "cross_document") and "written differently" in f.title
    assert "mismatch" not in f.title.lower()  # nothing is called a mismatch here


@pytest.mark.parametrize("other", ["M. Varghese", "Meera Varghese"])
def test_a_name_with_a_word_left_out_is_a_minor_mismatch_and_not_a_form_difference(tmp_path, other):
    assert graded(check(tmp_path, pair("Meera K. Varghese", other)), "cross_name") == [
        ("inconsistency", "Minor mismatch: name differs between documents")]


@pytest.mark.parametrize("a, b", [("Rahul Kumar Sharma", "Rahul Sharma"), ("Rahul Sharma", "Rahul Kumar Sharma"), ("Asha Verma", "Asha Verma Singh")])
def test_a_name_with_a_whole_part_left_out_is_a_minor_mismatch_and_says_so(tmp_path, a, b):
    """A middle name is dropped from one document and not from another (similarity 0.80 and 0.77, under the limit): a minor mismatch,
    not a mismatch, and the finding says what differs."""
    (f,) = by(check(tmp_path, pair(a, b)), "cross_name")
    assert (f.fclass, f.title) == ("inconsistency", "Minor mismatch: name differs between documents")
    assert "one of them has a part the other lacks" in f.detail


def test_two_names_that_share_a_word_but_not_every_word_of_the_shorter_one_stay_a_mismatch(tmp_path):
    assert graded(check(tmp_path, pair("Rahul Kumar Sharma", "Rahul Verma")), "cross_name") == [
        ("inconsistency", "Mismatch: name differs between documents")]


@pytest.mark.parametrize("other", ["Meera K. Kulkarni", "Rohan T. Kulkarni"])
def test_names_further_apart_than_the_limit_are_a_plain_mismatch(tmp_path, other):
    assert graded(check(tmp_path, pair("Meera K. Varghese", other)), "cross_name") == [
        ("inconsistency", "Mismatch: name differs between documents")]


@pytest.mark.parametrize("a, b", [("Meera K. Varghese", "Meera K. Varg hese"), ("Anil Kumar Rao", "Anilkumar Rao"), ("Mohd Ali Khan", "Mohdali Khan")])
def test_a_name_with_a_space_more_or_less_inside_a_word_is_only_written_differently(tmp_path, a, b):
    """A scan puts a space into a word, and two writers join or split a name: the same letters in the same order, an observation."""
    assert graded(check(tmp_path, pair(a, b)), "cross_name") == [("observation", "Name is written differently in the documents")]


def test_a_letter_changed_in_a_name_is_still_not_a_space(tmp_path):
    assert graded(check(tmp_path, pair("Meera K. Varghese", "Meera K. Varg hese e")), "cross_name") != [
        ("observation", "Name is written differently in the documents")]


@pytest.mark.parametrize("employer, payer, flagged", [("IRONW OOD TEST PVT LTD", "NEFT SALARY IRONWOOD TEST PVT LTD", False),
                                                      ("IRONWOOD TEST PVT LTD", "NEFT SALARY IRONWOOD TEST PVT LTD", False),
                                                      ("IRONW OOD TEST PVT LTD", "NEFT SALARY HARBORVIEW TEST PVT LTD", True)])
def test_an_employer_the_scan_split_in_two_is_still_the_payer_of_the_salary(tmp_path, employer, payer, flagged):
    credit = fld("D1", "txn.description", payer).model_copy(update={"row": 2})
    case = built(document("D1", "bank_statement", credit), document("D2", "payslip", fld("D2", "employer", employer, "employer")))
    check(tmp_path, case)
    assert [f.title for f in by(case, "cross_payer")] == (["Employer is not the payer of the salary credits"] if flagged else [])


def test_each_grade_is_its_own_finding_and_the_one_that_differs_most_comes_first(tmp_path):
    case = built(document("D1", "bank_statement", fld("D1", "account_holder", "Meera K. Varghese", "name")),
                 document("D2", "payslip", fld("D2", "employee_name", "Rohan T. Kulkarni", "name")),
                 document("D3", "loan_application", fld("D3", "applicant_name", "Meera K. Varghes", "name")))
    check(tmp_path, case)
    major, minor = by(case, "cross_name")
    assert major.title.startswith("Mismatch:") and minor.title.startswith("Minor mismatch:")
    assert [e.doc for e in major.evidence] == ["D2", "D1", "D3"]  # D2 differs from both others
    assert [e.doc for e in minor.evidence] == ["D1", "D3"] and "D2" not in minor.detail


@pytest.mark.parametrize("other, expected", [
    ("FLAT 12 ROSE COURT MILL ROAD BHOPAL 462001", []),
    ("Bhopal 462001, Flat 12, Rose Court, Mill Road", [("observation", "Address is written differently in the documents")]),
    ("Flat 12, Rose Court, Mill Rd, Bhopal 462001", [("inconsistency", "Minor mismatch: address differs between documents")]),
    ("Flat 12, Rose Cort, Mill Road, Bhopal 462001", [("inconsistency", "Minor mismatch: address differs between documents")]),
    ("Flat 12, Rose Cou rt, Mill Road, Bhopal 462001", [("observation", "Address is written differently in the documents")]),  # a space in a word
    ("Flat 12, RoseCourt, Mill Road, Bhopal 462001", [("observation", "Address is written differently in the documents")]),
    ("Flat 21, Rose Court, Mill Road, Bhopal 462001", [("inconsistency", "Mismatch: address differs between documents")]),  # a number changed
    ("Flat 12, Lotus Heights, Hill Street, Pune 411001", [("inconsistency", "Mismatch: address differs between documents")])])
def test_addresses_are_graded(tmp_path, other, expected):
    case = check(tmp_path, pair("Flat 12, Rose Court, Mill Road, Bhopal 462001", other, "address", ("address", "address")))
    assert graded(case, "cross_address") == expected


@pytest.mark.parametrize("other, expected", [
    ("HARBORVIEW TEST PVT LTD", []),
    ("Harborview Test Private Limited", [("observation", "Employer is written differently in the documents")]),
    ("Harborview Test", [("observation", "Employer is written differently in the documents")]),
    ("Harborview Test (P) Ltd.", [("observation", "Employer is written differently in the documents")]),  # (P) is Private
    ("Harborview P Test Pvt Ltd", [("inconsistency", "Minor mismatch: employer differs between documents")]),  # a bare P is a word
    ("Harborview Tst Pvt Ltd", [("inconsistency", "Minor mismatch: employer differs between documents")]),
    ("Harborview T est Pvt Ltd", [("observation", "Employer is written differently in the documents")]),  # a scan put a space in a word
    ("HarborviewTest Pvt Ltd", [("observation", "Employer is written differently in the documents")]),  # and a writer left one out
    ("Ironwood Test Pvt Ltd", [("inconsistency", "Mismatch: employer differs between documents")])])
def test_employers_are_graded_and_the_legal_form_is_only_a_form(tmp_path, other, expected):
    case = check(tmp_path, pair("Harborview Test Pvt Ltd", other, "employer", ("employer", "employer")))
    assert graded(case, "cross_employer") == expected


def test_an_account_number_is_the_same_or_a_mismatch_with_no_minor_grade(tmp_path):
    case = check(tmp_path, pair("TST-1234567890", "TST-1234567891", "account", ("bank_account", "account_no")))
    assert graded(case, "cross_account") == [("inconsistency", "Mismatch: account number differs between documents")]


@pytest.mark.parametrize("quality, read_mode, said", [("good", "ocr", True), ("text-layer", "text-layer", False)])
def test_a_minor_name_mismatch_on_a_scan_says_one_letter_may_be_a_misreading(tmp_path, quality, read_mode, said):
    case = built(document("D1", "payslip", fld("D1", "employee_name", "Meera K. Varghese", "name")),
                 document("D2", "loan_application", fld("D2", "applicant_name", "Meera K. Varghes", "name"),
                          quality=quality, read_mode=read_mode))
    check(tmp_path, case)
    (f,) = by(case, "cross_name")
    assert f.fclass == "inconsistency" and f.title.startswith("Minor mismatch:")  # a good scan is still trusted
    assert ("misreading" in f.detail) is said


def test_a_minor_mismatch_read_from_a_degraded_scan_is_a_possible_extraction_error(tmp_path):
    case = built(document("D1", "payslip", fld("D1", "employee_name", "Meera K. Varghese", "name")),
                 document("D2", "loan_application", fld("D2", "applicant_name", "Meera K. Varghes", "name"),
                          quality="degraded", read_mode="ocr"))
    check(tmp_path, case)
    (f,) = by(case, "cross_name")
    assert f.fclass == "processing_limitation" and f.title.startswith("Possible extraction error, verify: Minor mismatch:")


def test_c2_one_letter_dropped_from_a_name_is_a_minor_mismatch_pinned_on_the_slip(tmp_path):
    ident = identity(1)
    stmt, slip, app = trio(ident, 1, slip=c2_cross_document(ident, "name", ident.name[:-1]))
    case = run(tmp_path, stmt.pdf, slip.pdf, app.pdf)
    (f,) = case.findings
    assert (f.detector, f.fclass) == ("cross_name", "inconsistency") and f.title.startswith("Minor mismatch:")
    assert hit(f.evidence[0], "D2", slip, "employee_name") and cites(f, "D1", stmt, "account_holder") and cites(f, "D3", app, "applicant_name")


def test_c2_the_same_name_written_surname_first_is_an_observation_only(tmp_path):
    ident = identity(1)
    first, initial, last = ident.name.split()
    stmt, slip, app = trio(ident, 1, slip=c2_cross_document(ident, "name", f"{last.rstrip('.')}, {first} {initial}"))
    case = run(tmp_path, stmt.pdf, slip.pdf, app.pdf)
    (f,) = case.findings
    assert (f.detector, f.fclass) == ("cross_name", "observation") and hit(f.evidence[0], "D2", slip, "employee_name")


@pytest.mark.parametrize("other, flagged", [("XXXXXX7890", False), ("tst-1234567890", False), ("XXXX XXXX 7890", False),
                                            ("XXXXXX7891", True), ("TST-1234567899", True)])
def test_account_numbers_match_exactly_or_by_the_visible_tail_of_a_mask(tmp_path, other, flagged):
    case = check(tmp_path, pair("TST-1234567890", other, "account", ("bank_account", "account_no")))
    assert bool(by(case, "cross_account")) is flagged


@pytest.mark.parametrize("declared, flagged", [("62400.00", False), ("64200.00", True)])  # +4 % and +7 % of gross 60,000
def test_declared_income_is_compared_with_gross_within_the_tolerance(tmp_path, declared, flagged):
    case = built(document("D1", "payslip", fld("D1", "gross_earnings", "60000.00", kind="amount")),
                 document("D2", "loan_application", fld("D2", "declared_monthly_income", declared, kind="amount")))
    check(tmp_path, case)
    assert bool(by(case, "cross_income")) is flagged
    if flagged:
        assert "5%" in by(case, "cross_income")[0].detail  # the tolerance used is printed


@pytest.mark.parametrize("second, expected", [("D:20260201093500+05'30'", True), ("D:20260201123500+05'30'", False),
                                              ("D:20260201093500Z", False)])  # 6 minutes, 3 hours, 5 and a half hours
def test_the_same_software_within_minutes_across_document_types_is_noted(tmp_path, second, expected):
    def with_meta(pdf, created):
        with pymupdf.open(stream=pdf, filetype="pdf") as doc:
            doc.set_metadata({"producer": "Generic PDF Writer 1.0", "creator": "Generic PDF Writer 1.0",
                              "creationDate": created, "modDate": created})
            return doc.tobytes()

    stmt, slip, app = trio(identity(1), 1)
    case = run(tmp_path, with_meta(stmt.pdf, "D:20260201092900+05'30'"), with_meta(slip.pdf, second), app.pdf)
    assert [f.detector for f in case.findings] == (["cross_producer"] if expected else [])
    if expected:
        (f,) = case.findings
        assert (f.fclass, f.family) == ("observation", "metadata") and sorted(e.doc for e in f.evidence) == ["D1", "D2"]


def test_context_rules_are_observations_and_say_their_reference_is_synthetic(tmp_path):
    ident = dataclasses.replace(identity(1), loan_amount=1_000_000, tenure_months=24)
    assert (ident.existing_emi + ident.loan_amount / ident.tenure_months) / ident.monthly_gross > TH.emi_ratio_max
    stmt, slip, app = trio(ident, 1)
    (f,) = run(tmp_path, stmt.pdf, slip.pdf, app.pdf).findings
    assert (f.detector, f.fclass, f.family) == ("context_emi", "observation", "cross_document")
    assert f.title.startswith("Context rule:") and "synthetic" in f.detail and "0.5" in f.detail
    assert cites(f, "D3", app, "declared_monthly_income") and cites(f, "D3", app, "loan_amount")


def test_a_failing_check_becomes_a_limitation_and_the_others_still_run(tmp_path, monkeypatch):
    from docforensics.checks import cross

    def boom(case, th):
        raise RuntimeError("boom")

    monkeypatch.setattr(cross, "CROSS_CHECKS", [boom, *cross.CROSS_CHECKS])
    case = check(tmp_path, pair("Meera K. Varghese", "Rohan T. Kulkarni"))
    (failed,) = by(case, "boom")
    assert failed.title == "Step 'boom' failed" and failed.fclass == "processing_limitation"
    assert by(case, "cross_name")
