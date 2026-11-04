"""Explanation templates (design 7.6): measured wording per detector, fixed next steps, never a verdict, never the document's own text."""
import re

import pytest

from docforensics.audit import AuditLog
from docforensics.config import Thresholds
from docforensics.explain import run_explain
from docforensics.explain.templates import TEMPLATES, explain_finding
from docforensics.model import Case, Document, Evidence, Finding
from docforensics.pipeline import Ctx
from docforensics.store import CaseDir

VERDICT = re.compile(r"fraud|forg|fake|counterfeit", re.I)
CLASSES = ("observation", "inconsistency", "potential_manipulation", "processing_limitation")
FAMILY = {"observation": "visual", "inconsistency": "arithmetic", "potential_manipulation": "cluster", "processing_limitation": "limitation"}
DETECTORS = sorted({d for d, _ in TEMPLATES} | {"a_detector_nobody_registered"})
HOSTILE = "FORGED fraud <script>alert(1)</script> counterfeit \x1b[31m fake"


def case_of(*docs):
    return Case(id="C", created="2026-11-02T00:00:00+00:00", documents=list(docs))


def doc(id="D1", **kw):
    return Document(id=id, sha256="0", filename=kw.pop("filename", "a.pdf"), stored_path="files/a.pdf", **kw)


def sample(detector, fclass, **kw):
    kw.setdefault("evidence", [Evidence(doc="D1", page=1, box=(1, 2, 30, 40), note="a cell", value="52,000.00")])
    return Finding(id="F-001", fclass=fclass, detector=detector, family=FAMILY[fclass], title="t", detail="d", **kw)


@pytest.mark.parametrize("fclass", CLASSES)
@pytest.mark.parametrize("detector", DETECTORS)
def test_every_finding_is_explained_with_next_steps_and_no_verdict(detector, fclass):
    text, steps = explain_finding(sample(detector, fclass), case_of(doc()))
    assert text.strip() and steps and all(s.strip() for s in steps)
    assert not VERDICT.search(text) and not any(VERDICT.search(s) for s in steps)


@pytest.mark.parametrize("detector", ["cross_name", "cross_address", "cross_employer"])
def test_a_difference_in_form_only_has_its_own_explanation_that_calls_it_ordinary(detector):
    text, steps = TEMPLATES[(detector, "observation")]
    assert text != TEMPLATES[("*", "observation")][0] and "ordinary" in text and steps and not VERDICT.search(text)


def test_no_verdict_words_in_any_template():
    for (detector, fclass), (text, steps) in TEMPLATES.items():
        assert not VERDICT.search(text) and not any(VERDICT.search(s) for s in steps), (detector, fclass)


@pytest.mark.parametrize("fclass", CLASSES)
def test_explanation_never_repeats_text_taken_from_the_document(fclass):
    f = sample("pdf_revisions", fclass, evidence=[Evidence(doc="D1", page=1, box=(1, 2, 3, 4), note=HOSTILE, value=HOSTILE)])
    f = f.model_copy(update={"title": HOSTILE, "detail": HOSTILE})
    text, steps = explain_finding(f, case_of(doc(filename=HOSTILE)))
    assert not VERDICT.search(text) and "<script>" not in text and "\x1b" not in text and HOSTILE not in " ".join(steps)


def test_evidence_is_summarised_by_document_page_and_count_only():
    ev = [Evidence(doc="D1", page=1, box=(1, 2, 3, 4)), Evidence(doc="D1", page=2, box=(1, 2, 3, 4)),
          Evidence(doc="D2", page=0, box=(0, 0, 0, 0)), Evidence(doc="D7", page=1, box=(1, 2, 3, 4))]  # D7 is not in the case
    text, _ = explain_finding(sample("statement_balance", "inconsistency", evidence=ev), case_of(doc(), doc("D2")))
    assert "4 places" in text and "D1" in text and "pages 1, 2" in text and "D2" in text and "whole document" in text and "D7" in text


def test_a_finding_without_evidence_is_still_explained():
    text, steps = explain_finding(sample("statement_balance", "inconsistency", evidence=[]), case_of(doc()))
    assert text.strip() and steps


def test_a_limitation_is_a_limit_of_the_analysis_not_a_finding_about_the_document():
    for detector in DETECTORS:
        text, _ = explain_finding(sample(detector, "processing_limitation"), case_of(doc()))
        assert "not a finding about the document" in text, detector


def test_a_cluster_is_a_priority_for_the_reviewer_not_a_probability():
    text, _ = explain_finding(sample("cluster", "potential_manipulation", conf=0.8), case_of(doc()))
    assert "not a probability" in text and "%" not in text


@pytest.mark.parametrize("conf, said", [(0.73, True), (1.0, False)])
def test_the_weakest_reading_is_named_when_it_is_in_doubt(conf, said):
    text, _ = explain_finding(sample("statement_balance", "inconsistency", conf=conf), case_of(doc()))
    assert ("0.73" in text) is said and ("weakest" in text) is said


def test_run_explain_fills_every_finding_and_logs_it(tmp_path):
    cd = CaseDir.create(tmp_path)
    ctx = Ctx(cd, AuditLog(cd.audit_path), Thresholds())
    case = case_of(doc())
    case.findings = [sample("statement_balance", "inconsistency"), sample("x", "processing_limitation")]
    case.findings[1] = case.findings[1].model_copy(update={"id": "F-002", "explanation_source": "llm", "explanation": "old words"})
    run_explain(case, ctx)
    for f in case.findings:
        assert f.explanation.strip() and f.next_steps and f.explanation_source == "template"
    assert "old words" not in case.findings[1].explanation
    (done,) = [e for e in ctx.audit.events() if e.event == "findings_explained"]
    assert done.data == {"findings": 2, "source": "template"}
