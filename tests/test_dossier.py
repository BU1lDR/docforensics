"""The dossier (design 7.9): PS-2 sections in order, every row traceable to a place in a file, the classes kept apart, text from
documents escaped, one self-contained file that carries its own hash."""
import copy
import hashlib
import html
import json
import re

import pytest

from docforensics.audit import AuditLog
from docforensics.config import Thresholds
from docforensics.dossier import READING_LABEL, build_dossier, dossier_dict
from docforensics.findings import add_findings
from docforensics.ingest import create_case
from docforensics.model import Evidence, Field, Finding, Reasoning, Relation
from docforensics.pipeline import Ctx, run_case
from tests.helpers import d1_edited_statement, pdf_bytes, png_bytes

SECTIONS = ["overview", "extracted_information", "contextual_analysis", "visual_forensic_findings",
            "evidence_and_traceability", "investigation_summary"]
APPENDICES = ["appendix_audit_trail", "appendix_capabilities", "appendix_limitations"]
VERDICT = re.compile(r"fraud|forg|fake|counterfeit", re.I)
XSS = "<script>alert(1)</script>"
BOX = (10.0, 10.0, 50.0, 20.0)


@pytest.fixture(scope="module")
def ran(tmp_path_factory):
    """One real run, shared by the tests that only read it: a statement whose first credit was re-typed in an incremental save."""
    th = Thresholds()
    _, cd, _ = create_case(tmp_path_factory.mktemp("data"), [("statement.pdf", d1_edited_statement())], th)
    case = run_case(cd, th)
    return case, Ctx(cd, AuditLog(cd.audit_path), th)


def fresh(tmp_path, files=None, th=None):
    th = th or Thresholds()
    case, cd, audit = create_case(tmp_path / "data", files or [("a.pdf", pdf_bytes())], th)
    return case, Ctx(cd, audit, th)


def rows_of(d):
    """Every full finding row in the dossier."""
    return (d["contextual_analysis"]["inconsistencies"] + d["contextual_analysis"]["potential_manipulation"]
            + d["visual_forensic_findings"]["observations"] + d["investigation_summary"]["limitations"])


def test_sections_follow_ps2_order(ran):
    case, ctx = ran
    d = dossier_dict(case, ctx)
    assert list(d) == SECTIONS + ["appendices", "integrity"]
    assert list(d["appendices"]) == ["audit_trail", "capabilities", "limitations"]
    assert list(d["investigation_summary"]) == ["anomalies", "evidence", "explanations", "further_verification", "limitations", "ai_reading"]
    page = ctx.cd.dossier_html.read_text(encoding="utf-8")
    assert re.findall(r'<section id="([a-z_]+)"', page) == SECTIONS + APPENDICES


def test_every_finding_row_has_file_sha_page_box(ran):
    case, ctx = ran
    d = dossier_dict(case, ctx)
    docs = {x.id: x for x in case.documents}
    assert any(f.evidence for f in case.findings)
    assert sorted(r["id"] for r in rows_of(d)) == sorted(f.id for f in case.findings)  # each finding listed once
    for r in rows_of(d):
        f = next(f for f in case.findings if f.id == r["id"])
        assert len(r["evidence"]) == len(f.evidence)
        for e, item in zip(f.evidence, r["evidence"]):
            assert (item["file"], item["sha256"], item["page"], item["box"]) == (
                docs[e.doc].filename, docs[e.doc].sha256, e.page, [round(v, 1) for v in e.box])
            if e.page:  # page 0 is the document as a whole: no box to convert
                dpi = docs[e.doc].pages[e.page - 1].dpi
                assert item["dpi"] == dpi and item["box_pt"] == [round(v * 72 / dpi, 1) for v in e.box]
    trace = d["evidence_and_traceability"]["trace"]
    assert len(trace) == sum(len(f.evidence) for f in case.findings)
    for t in trace:
        doc = docs[t["document"]]
        assert (t["file"], t["sha256"]) == (doc.filename, doc.sha256)
        assert {"finding", "n", "page", "box", "box_pt", "dpi", "note", "value", "crop"} <= set(t)


def test_classes_live_in_separate_sections(ran):
    case, ctx = ran
    d = dossier_dict(case, ctx)
    by = lambda c: [f.id for f in case.findings if f.fclass == c]
    ids = lambda rows: [r["id"] for r in rows]
    assert by("observation") and by("inconsistency") and by("potential_manipulation")  # the run produced all three (the linker made the last)
    assert ids(d["visual_forensic_findings"]["observations"]) == by("observation")
    assert ids(d["contextual_analysis"]["inconsistencies"]) == by("inconsistency")
    assert ids(d["contextual_analysis"]["potential_manipulation"]) == by("potential_manipulation")
    assert ids(d["investigation_summary"]["limitations"]) == by("processing_limitation")
    assert ids(d["investigation_summary"]["anomalies"]) == by("potential_manipulation") + by("inconsistency")  # an observation is not an anomaly


def test_potential_manipulation_is_kept_apart_from_inconsistencies(ran):
    case, ctx = ran
    case = copy.deepcopy(case)
    case.findings.append(Finding(id="F-900", fclass="potential_manipulation", detector="cluster", family="cluster",
                                 title="Candidate for review", evidence=[Evidence(doc="D1", page=1, box=BOX)]))
    d = dossier_dict(case, ctx)
    inc = [f.id for f in case.findings if f.fclass == "inconsistency"]
    pm = [f.id for f in case.findings if f.fclass == "potential_manipulation"]
    assert len(pm) == 2 and pm[-1] == "F-900"  # the headline the linker made for the real run, then the one added here
    assert [r["id"] for r in d["contextual_analysis"]["potential_manipulation"]] == pm
    assert [r["id"] for r in d["contextual_analysis"]["inconsistencies"]] == inc
    assert [(a["id"], a["class"]) for a in d["investigation_summary"]["anomalies"]] == \
        [(i, "potential_manipulation") for i in pm] + [(i, "inconsistency") for i in inc]


def test_summary_carries_evidence_explanations_and_steps(ran):
    case, ctx = ran
    s = dossier_dict(case, ctx)["investigation_summary"]
    anomalies = [a["id"] for a in s["anomalies"]]
    assert anomalies
    assert [e["finding"] for e in s["evidence"]] == anomalies and all(e["places"] for e in s["evidence"])
    assert [e["finding"] for e in s["explanations"]] == anomalies
    assert all(e["explanation"] and e["source"] == "template" for e in s["explanations"])
    steps = [v["step"] for v in s["further_verification"]]
    assert steps and len(steps) == len(set(steps))  # one entry per step, however many findings share it
    assert all(v["findings"] for v in s["further_verification"])


def test_extracted_fields_carry_confidence_and_location(ran):
    case, ctx = ran
    docs = dossier_dict(case, ctx)["extracted_information"]["documents"]
    assert [d["id"] for d in docs] == ["D1"] and docs[0]["fields"] and docs[0]["pages"][0]["read_mode"] == "text-layer"
    for f in docs[0]["fields"]:
        assert {"id", "name", "raw", "value", "kind", "confidence", "page", "box"} <= set(f)
        assert 0 <= f["confidence"] <= 1 and f["page"] >= 1 and len(f["box"]) == 4


def test_dossier_escapes_untrusted_text(tmp_path):
    case, ctx = fresh(tmp_path)
    doc = case.documents[0]
    doc.filename = "<b>x</b>.pdf"
    doc.fields.append(Field(id="D1-X1", doc="D1", name="net_pay", raw=XSS, value=XSS, kind="text", conf=0.9, page=1, box=BOX))
    add_findings(case, ctx, [Finding(
        fclass="inconsistency", detector="statement_balance", family="arithmetic", title=XSS, detail='" onmouseover="alert(1)',
        evidence=[Evidence(doc="D1", page=1, box=BOX, note=XSS, field_id="D1-X1", value=XSS)])])
    build_dossier(case, ctx)
    page = ctx.cd.dossier_html.read_text(encoding="utf-8")
    assert XSS not in page and "<b>x</b>" not in page and 'onmouseover="alert' not in page
    assert html.escape(XSS) in page and html.escape("<b>x</b>.pdf") in page
    assert "<script" not in page.lower()


def test_a_crop_that_cannot_be_embedded_is_said_so(tmp_path):
    case, ctx = fresh(tmp_path)
    (tmp_path / "secret.png").write_bytes(png_bytes())  # three folders above the case folder
    (ctx.cd.crops / "notpng.png").write_bytes(b"not an image")
    (ctx.cd.crops / "big.png").write_bytes(png_bytes() + bytes(2_000_001))  # a PNG header, but too big to be a crop of ours
    add_findings(case, ctx, [Finding(fclass="observation", detector="pdf_revisions", family="metadata", title="t", evidence=[
        Evidence(doc="D1", page=1, box=BOX, crop_path="../../../secret.png"),
        Evidence(doc="D1", page=1, box=BOX, crop_path="crops/missing.png"),
        Evidence(doc="D1", page=1, box=BOX, crop_path="crops/notpng.png"),
        Evidence(doc="D1", page=1, box=BOX, crop_path="crops/big.png")])])
    build_dossier(case, ctx)
    page = ctx.cd.dossier_html.read_text(encoding="utf-8")
    assert "data:image" not in page and page.count("crop not available") == 4


def test_html_is_self_contained(ran):
    _, ctx = ran
    page = ctx.cd.dossier_html.read_text(encoding="utf-8")
    assert "data:image/png;base64," in page  # the crops are inside the file
    assert "<script" not in page.lower() and not re.search(r"<(link|iframe|object|embed|form|base)\b", page, re.I)
    assert not re.search(r"https?://", page)
    for value in re.findall(r'\b(?:src|href|action|data)\s*=\s*"([^"]*)"', page):
        assert value.startswith(("data:image/png;base64,", "#")), value


def test_json_hash_matches(ran):
    case, ctx = ran
    d = json.loads(ctx.cd.dossier_json.read_bytes())
    body = {k: v for k, v in d.items() if k != "integrity"}
    canon = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("ascii")
    assert d["integrity"]["json_sha256"] == hashlib.sha256(canon).hexdigest()
    body["overview"]["case"] = "C-changed"
    changed = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("ascii")
    assert hashlib.sha256(changed).hexdigest() != d["integrity"]["json_sha256"]


def test_building_the_dossier_is_audited(ran):
    _, ctx = ran
    events = ctx.audit.events()
    made = [e for e in events if e.event == "dossier_generated"]
    assert len(made) == 1
    assert made[0].data["html_sha256"] == hashlib.sha256(ctx.cd.dossier_html.read_bytes()).hexdigest()
    assert made[0].data["json_sha256"] == hashlib.sha256(ctx.cd.dossier_json.read_bytes()).hexdigest()
    trail = json.loads(ctx.cd.dossier_json.read_bytes())["appendices"]["audit_trail"]  # the trail as it stood when the dossier was made
    assert trail["chain_ok"] is True and trail["anchor"]["events"] == made[0].seq - 1 == len(trail["events"])
    assert events[trail["anchor"]["events"] - 1].hash == trail["anchor"]["head"]


def test_audit_appendix_flags_a_broken_missing_or_garbled_trail(tmp_path):
    case, ctx = fresh(tmp_path)
    good = dossier_dict(case, ctx)["appendices"]["audit_trail"]
    assert good["chain_ok"] is True and good["problem"] is None and len(good["events"]) >= 2
    lines = ctx.cd.audit_path.read_bytes().splitlines()
    lines[1] = lines[1].replace(b"file_ingested", b"file_ingestes")
    ctx.cd.audit_path.write_bytes(b"\n".join(lines) + b"\n")
    bad = dossier_dict(case, ctx)["appendices"]["audit_trail"]
    assert bad["chain_ok"] is False and "event 2" in bad["problem"]
    build_dossier(case, ctx)  # a broken trail is reported in the dossier, not a reason to refuse to make one
    assert html.escape(bad["problem"]) in ctx.cd.dossier_html.read_text(encoding="utf-8")
    for content in (b"", b"not json at all\n"):
        ctx.cd.audit_path.write_bytes(content)
        t = dossier_dict(case, ctx)["appendices"]["audit_trail"]
        assert t["chain_ok"] is False and t["events"] == [] and t["problem"]


def test_case_with_no_accepted_documents_still_has_dossier(tmp_path):
    th = Thresholds()
    _, cd, _ = create_case(tmp_path / "data", [("notes.txt", b"just text"), ("empty.pdf", b"")], th)
    case = run_case(cd, th)  # the registered dossier stage makes it
    assert case.documents == [] and cd.dossier_html.is_file() and cd.dossier_json.is_file()
    d = json.loads(cd.dossier_json.read_bytes())
    assert d["overview"]["documents"] == [] and d["extracted_information"]["documents"] == []
    lim = d["investigation_summary"]["limitations"]
    assert len(lim) == 2 and all(r["title"].startswith("File not ingested") for r in lim)
    assert d["appendices"]["audit_trail"]["chain_ok"] is True


def test_no_verdict_words_anywhere(ran):
    _, ctx = ran
    for path in (ctx.cd.dossier_json, ctx.cd.dossier_html):
        text = re.sub(r"data:image/png;base64,[A-Za-z0-9+/=]+", "", path.read_text(encoding="utf-8"))  # image bytes are not words
        assert not VERDICT.search(text), path.name


def test_anomalies_are_ordered_by_class_then_review_priority(ran):
    case, ctx = ran
    case = copy.deepcopy(case)
    for fid, fclass, priority in (("F-901", "inconsistency", 2), ("F-902", "inconsistency", 5), ("F-903", "potential_manipulation", 1)):
        case.findings.append(Finding(id=fid, fclass=fclass, detector="x", family="cluster", title="t", review_priority=priority,
                                     evidence=[Evidence(doc="D1", page=1, box=BOX)]))
    order = [a["id"] for a in dossier_dict(case, ctx)["investigation_summary"]["anomalies"]]
    added = [i for i in order if i in ("F-901", "F-902", "F-903")]  # the real run has its own candidate and conflicts, with priorities of their own
    assert added == ["F-903", "F-902", "F-901"]  # candidates first, then the higher review priority
    real_head = next(f for f in case.findings if f.detector == "link")
    assert order.index(real_head.id) < order.index("F-903")  # a candidate of priority 2 comes before one of priority 1


def test_llm_wording_is_labelled_as_inference(tmp_path):
    case, ctx = fresh(tmp_path)
    add_findings(case, ctx, [Finding(fclass="inconsistency", detector="statement_balance", family="arithmetic", title="t",
                                     explanation="Reworded by a model.", explanation_source="llm",
                                     evidence=[Evidence(doc="D1", page=1, box=BOX)])])
    build_dossier(case, ctx)
    page = ctx.cd.dossier_html.read_text(encoding="utf-8")
    assert page.count("AI-generated wording (inference)") == 2 and "Template wording" not in page  # on its card and in the summary
    assert json.loads(ctx.cd.dossier_json.read_bytes())["investigation_summary"]["explanations"][0]["source"] == "llm"


def test_internal_links_resolve(ran):
    case, ctx = ran
    page = ctx.cd.dossier_html.read_text(encoding="utf-8")
    ids = set(re.findall(r'\bid="([^"]+)"', page))
    assert [x for x in re.findall(r'\bhref="#([^"]*)"', page) if x not in ids] == []
    for section, fids in (("evidence_and_traceability", {f.id for f in case.findings if f.evidence}),
                          ("investigation_summary", {f.id for f in case.findings if f.fclass == "inconsistency"})):
        body = re.search(rf'<section id="{section}">(.*?)</section>', page, re.S).group(1)
        assert fids and all(f'href="#{i}"' in body for i in fids), section  # each finding there is a working link, not escaped text


def test_overview_states_the_notice_and_counts_add_up(ran):
    case, ctx = ran
    o = dossier_dict(case, ctx)["overview"]
    assert html.escape(o["notice"]) in ctx.cd.dossier_html.read_text(encoding="utf-8")
    c = o["counts"]
    assert c["findings"] == len(case.findings) == c["observations"] + c["inconsistencies"] + c["potential_manipulation"] + c["limitations"]
    assert c["documents"] == len(case.documents) == len(o["documents"])


def test_a_finding_in_a_cluster_points_at_its_headline(ran):
    case, ctx = ran
    page = ctx.cd.dossier_html.read_text(encoding="utf-8")
    heads = {f.id for f in case.findings if f.detector == "link"}
    members = [f for f in case.findings if f.cluster]
    assert heads and members and {f.cluster for f in members} <= heads
    for f in members:
        card = re.search(rf'<article class="[a-z_]+" id="{f.id}">(.*?)</article>', page, re.S).group(1)
        assert f'href="#{f.cluster}"' in card, f.id


def two_findings(tmp_path):
    """A case with F-001 (priority 1) and F-002 (priority 2): the tool reads F-002 first."""
    case, ctx = fresh(tmp_path)
    add_findings(case, ctx, [
        Finding(fclass="inconsistency", detector="statement_balance", family="arithmetic", title="t1", review_priority=1,
                evidence=[Evidence(doc="D1", page=1, box=BOX)]),
        Finding(fclass="inconsistency", detector="payslip_sums", family="arithmetic", title="t2", review_priority=2,
                evidence=[Evidence(doc="D1", page=1, box=BOX)])])
    return case, ctx


def reading(**kw):
    return Reasoning(model="qwen3:4b", summary="F-001 and F-002 both cite 52000.00.", relations=[
        Relation(a="F-001", b="F-002", kind="same_value", reason="Both cite 52000.00.")], **kw)


def test_without_a_model_the_reading_says_so(ran):
    case, ctx = ran
    note = "No language model was used for this case."
    assert dossier_dict(case, ctx)["investigation_summary"]["ai_reading"] == {"status": "none", "note": note}
    page = ctx.cd.dossier_html.read_text(encoding="utf-8")
    assert page.count(READING_LABEL) == 1 and note in page


def test_the_models_reading_is_inference_and_changes_no_finding(tmp_path):
    case, ctx = two_findings(tmp_path)
    before = dossier_dict(case, ctx)
    case.reasoning = reading(order=["F-002", "F-001"], rejected=[("relation", "unknown id")])
    d = dossier_dict(case, ctx)
    a = d["investigation_summary"]["ai_reading"]
    assert (a["status"], a["source"], a["model"]) == ("kept", "llm", "qwen3:4b")
    assert a["summary"] == "F-001 and F-002 both cite 52000.00."
    assert a["relations"] == [{"a": "F-001", "b": "F-002", "kind": "same_value", "reason": "Both cite 52000.00."}]
    assert a["rejected"] == [{"part": "relation", "reason": "unknown id"}]
    for k in ("extracted_information", "contextual_analysis", "visual_forensic_findings", "evidence_and_traceability"):
        assert d[k] == before[k], k  # the reading adds a block of its own and touches nothing the checks found
    rest = lambda x: {k: v for k, v in x["investigation_summary"].items() if k != "ai_reading"}
    assert rest(d) == rest(before) and d["overview"]["counts"] == before["overview"]["counts"]
    build_dossier(case, ctx)
    page = ctx.cd.dossier_html.read_text(encoding="utf-8")
    assert page.count(READING_LABEL) == 1 and "qwen3:4b" in page and "Both cite 52000.00." in page and "relation: unknown id" in page
    assert not VERDICT.search(page)


def test_the_models_order_is_shown_only_when_it_differs_from_the_tools(tmp_path):
    case, ctx = two_findings(tmp_path)
    case.reasoning = reading(order=["F-002", "F-001"])  # the tool's own order
    assert dossier_dict(case, ctx)["investigation_summary"]["ai_reading"]["order"] == []
    case.reasoning = reading(order=["F-001", "F-002"])
    assert dossier_dict(case, ctx)["investigation_summary"]["ai_reading"]["order"] == ["F-001", "F-002"]
    build_dossier(case, ctx)
    assert "Reading order the model suggests" in ctx.cd.dossier_html.read_text(encoding="utf-8")


def test_a_reading_that_was_asked_for_and_not_kept_says_why(tmp_path):
    case, ctx = fresh(tmp_path)
    ctx.audit.append("system", "llm_reasoning", {"model": "qwen3:4b", "accepted": False, "reason": "unavailable: ConnectError"})
    a = dossier_dict(case, ctx)["investigation_summary"]["ai_reading"]
    assert a["status"] == "none" and "qwen3:4b" in a["note"] and "unavailable: ConnectError" in a["note"]
    build_dossier(case, ctx)
    assert html.escape(a["note"]) in ctx.cd.dossier_html.read_text(encoding="utf-8")


def test_text_in_the_models_reading_is_escaped(tmp_path):
    case, ctx = two_findings(tmp_path)
    case.reasoning = Reasoning(model=XSS, summary=XSS, relations=[Relation(a="F-001", b="F-002", kind="same_value", reason=XSS)],
                               order=["F-001", "F-002"], rejected=[(XSS, XSS)])
    build_dossier(case, ctx)
    page = ctx.cd.dossier_html.read_text(encoding="utf-8")
    assert XSS not in page and "<script" not in page.lower() and html.escape(XSS) in page
