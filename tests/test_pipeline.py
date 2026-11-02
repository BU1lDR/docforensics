import time

import pytest

from docforensics.audit import AuditLog
from docforensics.config import Thresholds
from docforensics.findings import add_findings, demote, doc_evidence, limitation
from docforensics.ingest import create_case
from docforensics.model import Evidence, Finding
from docforensics.pipeline import STAGE_ORDER, Ctx, guarded, run_case
from docforensics.store import load_case
from tests.helpers import pdf_bytes

TH = Thresholds()


def two_docs(tmp_path, th=TH):
    return create_case(tmp_path, [("a.pdf", pdf_bytes(text="A")), ("b.pdf", pdf_bytes(text="B"))], th)


def test_add_findings_assigns_ids_and_audits(tmp_path):
    case, cd, audit = two_docs(tmp_path)
    a, b = add_findings(case, Ctx(cd, audit, TH), [limitation("x", "t1", "d"), limitation("x", "t2", "d", [doc_evidence("D1")])])
    assert (a.id, b.id) == ("F-001", "F-002") and case.findings == [a, b]
    assert a.fclass == "processing_limitation" and a.family == "limitation" and a.conf == 1.0
    assert b.evidence[0].doc == "D1" and b.evidence[0].page == 0
    assert [e.event for e in audit.events()].count("finding_created") == 2


def test_demote_turns_an_inconsistency_into_a_limitation():
    ev = [Evidence(doc="D1", page=1, box=(1, 2, 3, 4), field_id="D1-f1")]
    f = Finding(fclass="inconsistency", detector="arithmetic", family="arithmetic", title="Total differs", detail="1 vs 2", conf=0.4, evidence=ev)
    d = demote(f, "page is degraded")
    assert (d.fclass, d.family, d.detector) == ("processing_limitation", "limitation", "arithmetic")
    assert d.title == "Possible extraction error, verify: Total differs"
    assert "page is degraded" in d.detail and "1 vs 2" in d.detail and d.evidence == ev and d.conf == 0.4
    assert f.fclass == "inconsistency" and f.title == "Total differs"
    with pytest.raises(ValueError):
        demote(d, "again")


def test_failing_stage_is_isolated(tmp_path):
    case, cd, audit = two_docs(tmp_path)

    def read(case, ctx):
        for d in case.documents:
            def work(d=d):
                if d.id == "D2":
                    raise RuntimeError("boom")
                d.meta["read"] = "ok"
            guarded(ctx, case, "read", work, doc_id=d.id)

    out = run_case(cd, TH, stages={"read": read})
    assert out.documents[0].meta == {"read": "ok"} and out.documents[1].meta == {}
    lims = [f for f in out.findings if f.fclass == "processing_limitation"]
    assert len(lims) == 1 and lims[0].evidence[0].doc == "D2" and "boom" in lims[0].detail and "failed" in lims[0].title
    failed = [e for e in audit.events() if e.event == "stage_failed"]
    assert len(failed) == 1 and failed[0].data["doc"] == "D2" and failed[0].data["stage"] == "read"
    names = [e.event for e in audit.events()]
    assert "stage_start" in names and "stage_end" in names and audit.verify() == (True, None)
    assert load_case(cd).findings == out.findings


def test_guarded_timeout_returns_false_and_records(tmp_path):
    th = Thresholds(stage_timeout_s=0.2)
    case, cd, audit = two_docs(tmp_path, th)
    ctx = Ctx(cd, audit, th)
    assert guarded(ctx, case, "read", lambda: time.sleep(3), doc_id="D1") is False
    assert "timed out" in case.findings[-1].title and case.findings[-1].evidence[0].doc == "D1"
    assert guarded(ctx, case, "read", lambda: None, doc_id="D1") is True


def test_stage_timeout(tmp_path):
    th = Thresholds(stage_timeout_s=0.2)
    case, cd, audit = two_docs(tmp_path, th)
    ran = []
    t0 = time.monotonic()
    out = run_case(cd, th, stages={"read": lambda c, x: time.sleep(5), "classify": lambda c, x: ran.append("classify")})
    assert time.monotonic() - t0 < 4 and ran == ["classify"]
    lims = [f for f in out.findings if f.fclass == "processing_limitation"]
    assert len(lims) == 1 and "timed out" in lims[0].title and lims[0].evidence == []
    ends = {e.data["stage"]: e.data for e in audit.events() if e.event == "stage_end"}
    assert ends["read"]["ok"] is False and ends["classify"]["ok"] is True and "version" in ends["read"]


def test_stages_run_in_the_fixed_order(tmp_path):
    case, cd, _ = two_docs(tmp_path)
    seen = []
    stages = {name: (lambda c, x, n=name: seen.append(n)) for name in reversed(STAGE_ORDER)}
    run_case(cd, TH, stages=stages)
    assert seen == list(STAGE_ORDER)
