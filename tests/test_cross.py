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


def document(id, doc_type, *fields, meta=None, quality="text-layer"):
    return Document(id=id, sha256=id, filename=f"{id}.pdf", stored_path="", doc_type=doc_type, type_conf=1.0,
                    pages=[Page(n=1, width=1654, height=2339, quality_class=quality)], fields=list(fields), meta=meta or {})


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
    assert c2_cross_document(ident, "name", "A B") == dataclasses.replace(ident, name="A B")


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


@pytest.mark.parametrize("other, flagged", [("Meera K. Varghes", False), ("Varghese, Meera K.", False),
                                            ("M. Varghese", False), ("Meera K. Kulkarni", True)])
def test_names_match_by_similarity_and_the_limit_is_known(tmp_path, other, flagged):
    case = check(tmp_path, pair("Meera K. Varghese", other))
    assert bool(by(case, "cross_name")) is flagged  # one wrong letter passes at 0.85: a stated limit, see the limitations


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
