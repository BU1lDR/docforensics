"""Reviewer actions (Task 20, design 7.8): a person sets a finding's status and note. The change is saved with the case, written to the
audit trail as the reviewer with the status before and after, and shown in the dossier. It never changes the finding's class."""
import pytest

from docforensics.config import Thresholds
from docforensics.dossier import build_dossier, dossier_dict
from docforensics.findings import add_findings
from docforensics.ingest import create_case
from docforensics.model import Evidence, Finding
from docforensics.pipeline import Ctx
from docforensics.review import MAX_NOTE, STATUSES, apply_review
from docforensics.store import load_case, save_case
from tests.helpers import pdf_bytes

BOX = (10.0, 10.0, 50.0, 20.0)


@pytest.fixture
def made(tmp_path):
    """A case with two findings and nothing reviewed yet, saved to disk."""
    th = Thresholds()
    case, cd, audit = create_case(tmp_path / "data", [("a.pdf", pdf_bytes())], th)
    ctx = Ctx(cd, audit, th)
    add_findings(case, ctx, [
        Finding(fclass="potential_manipulation", detector="pdf_cover", family="visual", title="A shape covers text", evidence=[Evidence(doc="D1", page=1, box=BOX)]),
        Finding(fclass="observation", detector="pdf_fonts", family="visual", title="Font differs", evidence=[Evidence(doc="D1", page=1, box=BOX)])])
    save_case(case, cd)
    return case, ctx


def actions(ctx):
    return [(e.actor, e.data) for e in ctx.audit.events() if e.event == "reviewer_action"]


def test_review_changes_status_and_audits(made):
    case, ctx = made
    f = apply_review(case, ctx, "F-001", "needs_verification", "Ask the branch for the original")
    assert f is case.findings[0] and (f.status, f.note) == ("needs_verification", "Ask the branch for the original")
    apply_review(case, ctx, "F-001", "confirmed_by_reviewer")  # a status alone leaves the note as it was
    assert f.note == "Ask the branch for the original"
    apply_review(case, ctx, "F-001", None, "")  # a note alone leaves the status; an empty note clears the old one
    assert (f.status, f.note) == ("confirmed_by_reviewer", "")
    assert actions(ctx) == [
        ("reviewer", {"finding": "F-001", "from": "open", "to": "needs_verification", "note": "Ask the branch for the original"}),
        ("reviewer", {"finding": "F-001", "from": "needs_verification", "to": "confirmed_by_reviewer", "note": None}),
        ("reviewer", {"finding": "F-001", "from": "confirmed_by_reviewer", "to": "confirmed_by_reviewer", "note": ""})]
    assert ctx.audit.verify() == (True, None)
    assert (case.findings[1].status, case.findings[1].note) == ("open", "")  # the other finding is untouched


def test_unknown_status_rejected(made):
    case, ctx = made
    assert STATUSES == ("open", "needs_verification", "confirmed_by_reviewer", "dismissed")
    before = case.model_dump()
    for bad in ("fraud", "confirmed", "OPEN", "", " dismissed"):
        with pytest.raises(ValueError, match="unknown status .*use one of open, needs_verification, confirmed_by_reviewer, dismissed"):
            apply_review(case, ctx, "F-001", bad, "a note that must not be kept")
    assert case.model_dump() == before and load_case(ctx.cd) == case and actions(ctx) == []


@pytest.mark.parametrize("status, note", [(None, None), ("dismissed", "x" * (MAX_NOTE + 1)), (None, "x" * (MAX_NOTE + 1))])
def test_a_request_that_asks_for_nothing_or_too_much_changes_nothing(made, status, note):
    case, ctx = made
    before = case.model_dump()
    with pytest.raises(ValueError):
        apply_review(case, ctx, "F-001", status, note)
    assert case.model_dump() == before and load_case(ctx.cd) == case and actions(ctx) == []
    assert apply_review(case, ctx, "F-001", "dismissed", "x" * MAX_NOTE).note == "x" * MAX_NOTE  # the limit itself is allowed


@pytest.mark.parametrize("status, note", [("dismissed", None), (None, "a note"), ("dismissed", "a note")])
def test_an_unknown_finding_changes_nothing(made, status, note):
    case, ctx = made
    before = case.model_dump()
    with pytest.raises(KeyError):
        apply_review(case, ctx, "F-099", status, note)
    assert case.model_dump() == before and load_case(ctx.cd) == case and actions(ctx) == []


def test_review_survives_reload(made):
    case, ctx = made
    apply_review(case, ctx, "F-002", "dismissed", "Ordinary: the branch re-issued it")
    again = load_case(ctx.cd)  # as the review app does on its next request
    assert (again.findings[1].status, again.findings[1].note) == ("dismissed", "Ordinary: the branch re-issued it")
    apply_review(again, ctx, "F-001", "needs_verification")  # a second action works on what was loaded
    last = load_case(ctx.cd)
    assert [(f.id, f.status) for f in last.findings] == [("F-001", "needs_verification"), ("F-002", "dismissed")]
    assert last.findings[1].note == "Ordinary: the branch re-issued it" and len(actions(ctx)) == 2


def test_dossier_shows_reviewer_status(made):
    case, ctx = made
    html, _ = build_dossier(case, ctx)
    page = html.read_text(encoding="utf-8")
    assert "status open" in page and "Reviewer note" not in page and "status confirmed_by_reviewer" not in page
    apply_review(case, ctx, "F-001", "confirmed_by_reviewer", "Original seen; <b>differs</b>")
    html, js = build_dossier(case, ctx)
    page = html.read_text(encoding="utf-8")
    assert "status confirmed_by_reviewer" in page and "Reviewer note: Original seen; &lt;b&gt;differs&lt;/b&gt;" in page
    d = dossier_dict(case, ctx)
    (row,) = d["contextual_analysis"]["potential_manipulation"]  # confirming does not move a finding out of its class
    assert (row["id"], row["status"], row["reviewer_note"]) == ("F-001", "confirmed_by_reviewer", "Original seen; <b>differs</b>")
    assert case.findings[0].fclass == "potential_manipulation"
    assert ("F-001", "potential_manipulation", "confirmed_by_reviewer") in [(a["id"], a["class"], a["status"]) for a in d["investigation_summary"]["anomalies"]]
    assert [e["actor"] for e in d["appendices"]["audit_trail"]["events"] if e["event"] == "reviewer_action"] == ["reviewer"]
