"""Reviewer decisions (Task 28): what a person decided about each finding, read from the verified audit trail, and a count per detector.
Nothing is learned from them; the export and the counts are for a person who edits a threshold file."""
import json

import pytest

from docforensics.audit import AuditLog
from docforensics.cli import main
from docforensics.config import Thresholds
from docforensics.decisions import KEYS, case_dirs, decisions, jsonl, tally
from docforensics.findings import add_findings
from docforensics.ingest import create_case
from docforensics.model import Evidence, Finding
from docforensics.pipeline import Ctx
from docforensics.review import apply_review
from docforensics.signing import checkpoint
from docforensics.store import save_case
from tests.helpers import pdf_bytes

BOX = (10.0, 10.0, 50.0, 20.0)
STATUS_KEYS = ["open", "needs_verification", "confirmed_by_reviewer", "dismissed"]


def make_case(data, findings=True):
    """A saved case with three findings and nothing reviewed: F-001 pdf_cover potential_manipulation, F-002 and F-003 pdf_fonts (an
    observation and a potential manipulation, to show that the class stays part of the count's key)."""
    th = Thresholds()
    case, cd, audit = create_case(data, [("a.pdf", pdf_bytes())], th)
    ctx = Ctx(cd, audit, th)
    ev = [Evidence(doc="D1", page=1, box=BOX)]
    add_findings(case, ctx, [
        Finding(fclass="potential_manipulation", detector="pdf_cover", family="visual", title="A shape covers text", evidence=ev),
        Finding(fclass="observation", detector="pdf_fonts", family="visual", title="Font differs", evidence=ev),
        Finding(fclass="potential_manipulation", detector="pdf_fonts", family="visual", title="Font differs a lot", evidence=ev)] if findings else [])
    save_case(case, cd)
    return case, ctx


@pytest.fixture
def made(tmp_path):
    return make_case(tmp_path / "data")


def row(rows, fid):
    return next(r for r in rows if r["finding"] == fid)


def test_a_case_nobody_reviewed_has_every_finding_open(made):
    _, ctx = made
    rows = decisions(ctx.cd)
    assert [r["finding"] for r in rows] == ["F-001", "F-002", "F-003"]
    assert list(rows[0]) == list(KEYS) == ["case", "finding", "detector", "class", "status", "note", "actions", "last_action"]
    assert rows[0] == {"case": ctx.cd.id, "finding": "F-001", "detector": "pdf_cover", "class": "potential_manipulation",
                       "status": "open", "note": "", "actions": 0, "last_action": None}
    assert {r["status"] for r in rows} == {"open"}


def test_the_decision_is_what_the_trail_says_in_order(made):
    case, ctx = made
    apply_review(case, ctx, "F-001", "needs_verification", "Ask the branch for the original")
    apply_review(case, ctx, "F-001", "confirmed_by_reviewer")  # a status alone keeps the note
    apply_review(case, ctx, "F-002", None, "Looks like the template's own font")  # a note alone keeps the status
    apply_review(case, ctx, "F-002", "dismissed", "")  # an empty note clears the earlier one
    apply_review(case, ctx, "F-002", None, "")
    rows = decisions(ctx.cd)
    stamps = {e.data["finding"]: e.ts for e in ctx.audit.events() if e.event == "reviewer_action"}  # the last action of each finding wins
    one, two, three = row(rows, "F-001"), row(rows, "F-002"), row(rows, "F-003")
    assert (one["status"], one["note"], one["actions"], one["last_action"]) == ("confirmed_by_reviewer", "Ask the branch for the original", 2, stamps["F-001"])
    assert (two["status"], two["note"], two["actions"], two["last_action"]) == ("dismissed", "", 3, stamps["F-002"])
    assert (three["status"], three["actions"], three["last_action"]) == ("open", 0, None)


def test_the_counts_are_per_detector_and_class_sorted_and_only_counts(made):
    case, ctx = made
    apply_review(case, ctx, "F-001", "confirmed_by_reviewer")
    apply_review(case, ctx, "F-002", "dismissed")
    apply_review(case, ctx, "F-003", "needs_verification")
    t = tally(decisions(ctx.cd))
    assert t == [
        {"detector": "pdf_cover", "class": "potential_manipulation", "raised": 1, "open": 0, "needs_verification": 0, "confirmed_by_reviewer": 1, "dismissed": 0},
        {"detector": "pdf_fonts", "class": "observation", "raised": 1, "open": 0, "needs_verification": 0, "confirmed_by_reviewer": 0, "dismissed": 1},
        {"detector": "pdf_fonts", "class": "potential_manipulation", "raised": 1, "open": 0, "needs_verification": 1, "confirmed_by_reviewer": 0, "dismissed": 0}]
    assert all(set(x) == {"detector", "class", "raised", *STATUS_KEYS} for x in t) and all(isinstance(v, (int, str)) for x in t for v in x.values())  # no rate, no score
    assert tally([]) == []


def test_the_counts_add_up_across_cases(tmp_path):
    a, ca = make_case(tmp_path / "data")
    b, cb = make_case(tmp_path / "data")
    apply_review(a, ca, "F-001", "dismissed")
    apply_review(b, cb, "F-001", "dismissed")
    t = tally(decisions(ca.cd) + decisions(cb.cd))
    assert (t[0]["detector"], t[0]["raised"], t[0]["dismissed"], t[0]["open"]) == ("pdf_cover", 2, 2, 0)
    assert (t[1]["detector"], t[1]["raised"], t[1]["open"]) == ("pdf_fonts", 2, 2)


def test_the_export_is_ascii_and_a_hostile_note_stays_inert(made):
    case, ctx = made
    hostile = "<script>alert(1)</script>\nnext line \u202e reversed \u2028 separator \x1b[31m red \x7f del \u009b csi \u00e9"
    apply_review(case, ctx, "F-001", "dismissed", hostile)
    out = jsonl(decisions(ctx.cd))
    lines = out.splitlines()
    assert len(lines) == 3 and out.endswith("\n") and out.isascii()
    assert not any(c in out.replace("\n", "") for c in "\x1b\x7f\u202e\u2028\u009b")  # nothing a terminal could act on, all escaped
    assert "\\u202e" in lines[0] and "\\u007f" in lines[0]
    assert json.loads(lines[0])["note"] == hostile and [list(json.loads(x)) for x in lines] == [list(KEYS)] * 3  # nothing lost, nothing added
    assert jsonl([]) == ""


def test_a_trail_that_does_not_verify_is_refused_and_says_where(made):
    case, ctx = made
    apply_review(case, ctx, "F-001", "dismissed")
    lines = ctx.cd.audit_path.read_bytes().splitlines()
    i = next(n for n, x in enumerate(lines) if b"reviewer_action" in x)
    lines[i] = lines[i].replace(b"dismissed", b"confirmed_by_reviewer", 1)  # one decision changed after it was written
    ctx.cd.audit_path.write_bytes(b"\n".join(lines) + b"\n")
    with pytest.raises(ValueError, match=rf"audit trail of {ctx.cd.id} does not verify .*event {i + 1}"):
        decisions(ctx.cd)


def test_a_trail_cut_short_of_its_signed_checkpoint_is_refused(made):
    case, ctx = made
    assert checkpoint(ctx.cd, start=True)  # a run begins the chain of signed checkpoints; a review then adds one for itself
    apply_review(case, ctx, "F-001", "confirmed_by_reviewer")
    lines = ctx.cd.audit_path.read_bytes().splitlines()
    ctx.cd.audit_path.write_bytes(b"\n".join(lines[:-1]) + b"\n")  # the decision is cut off the end: the chain alone still verifies
    assert AuditLog(ctx.cd.audit_path).verify() == (True, None)
    with pytest.raises(ValueError, match=rf"audit trail of {ctx.cd.id} does not agree with its signed checkpoints"):
        decisions(ctx.cd)


@pytest.mark.parametrize("content", [b"", None], ids=["emptied", "missing"])
def test_a_missing_or_emptied_trail_is_refused_not_read_as_no_decisions(made, content):
    _, ctx = made
    if content is None:
        ctx.cd.audit_path.unlink()
    else:
        ctx.cd.audit_path.write_bytes(content)
    with pytest.raises(ValueError, match="missing or empty"):
        decisions(ctx.cd)


def test_only_folders_that_look_like_cases_are_listed(tmp_path):
    data = tmp_path / "data"
    assert case_dirs(data) == []  # no data folder at all
    _, ctx = make_case(data)
    (data / "cases" / "notes").mkdir()
    (data / "cases" / "C-20260101-000000-abcd").mkdir()  # the right name but no case.json
    (data / "cases" / "C-20260101-000000-abce").write_text("a file, not a case folder")
    assert [c.id for c in case_dirs(data)] == [ctx.cd.id]


def cli(tmp_path, capsys, *args):
    code = main([*args, "--data", str(tmp_path / "data")])
    return code, capsys.readouterr()


def test_the_command_prints_one_json_line_per_finding(tmp_path, capsys):
    case, ctx = make_case(tmp_path / "data")
    apply_review(case, ctx, "F-001", "needs_verification", "Ask the branch")
    code, cap = cli(tmp_path, capsys, "decisions")
    rows = [json.loads(x) for x in cap.out.splitlines()]
    assert code == 0 and cap.err == "" and rows == decisions(ctx.cd)
    assert rows[0]["status"] == "needs_verification" and rows[0]["note"] == "Ask the branch"
    code, cap = cli(tmp_path, capsys, "decisions", ctx.cd.id)  # naming the case gives the same rows
    assert code == 0 and [json.loads(x) for x in cap.out.splitlines()] == rows


def test_the_command_can_print_the_counts_as_a_table(tmp_path, capsys):
    case, ctx = make_case(tmp_path / "data")
    apply_review(case, ctx, "F-001", "confirmed_by_reviewer")
    apply_review(case, ctx, "F-002", "dismissed")
    code, cap = cli(tmp_path, capsys, "decisions", "--tally")
    lines = cap.out.splitlines()
    assert code == 0 and "not accuracy figures" in lines[0] and "1 case," in lines[0] and "3 findings" in lines[0]
    assert lines[1].split() == ["detector", "class", "raised", *STATUS_KEYS]
    assert [x.split() for x in lines[2:]] == [
        ["pdf_cover", "potential_manipulation", "1", "0", "0", "1", "0"],
        ["pdf_fonts", "observation", "1", "0", "0", "0", "1"],
        ["pdf_fonts", "potential_manipulation", "1", "1", "0", "0", "0"]]
    assert len({len(x) for x in lines[1:]}) == 1  # one aligned block


def test_the_command_covers_every_case_or_the_one_named(tmp_path, capsys):
    a, ca = make_case(tmp_path / "data")
    b, cb = make_case(tmp_path / "data")
    apply_review(b, cb, "F-002", "dismissed")
    _, cap = cli(tmp_path, capsys, "decisions")
    assert {json.loads(x)["case"] for x in cap.out.splitlines()} == {ca.cd.id, cb.cd.id}
    _, cap = cli(tmp_path, capsys, "decisions", cb.cd.id)
    assert {json.loads(x)["case"] for x in cap.out.splitlines()} == {cb.cd.id}


def test_a_case_with_no_findings_says_so_in_the_table_and_prints_no_rows(tmp_path, capsys):
    make_case(tmp_path / "data", findings=False)
    code, cap = cli(tmp_path, capsys, "decisions")
    assert (code, cap.out) == (0, "")
    code, cap = cli(tmp_path, capsys, "decisions", "--tally")
    assert code == 0 and cap.out.startswith("No findings") and len(cap.out.splitlines()) == 1


def test_an_unknown_case_or_an_empty_data_folder_is_a_usage_error(tmp_path, capsys):
    make_case(tmp_path / "data")
    code, cap = cli(tmp_path, capsys, "decisions", "C-20260101-000000-abcd")
    assert code == 2 and "no such case" in cap.err and cap.out == ""
    code, cap = cli(tmp_path, capsys, "decisions", "not-an-id")
    assert code == 2 and cap.out == ""
    code = main(["decisions", "--data", str(tmp_path / "nothing-here")])
    cap = capsys.readouterr()
    assert code == 2 and "no cases" in cap.err and cap.out == ""


def test_a_case_whose_trail_does_not_verify_is_reported_and_the_others_are_still_printed(tmp_path, capsys):
    a, ca = make_case(tmp_path / "data")
    b, cb = make_case(tmp_path / "data")
    lines = ca.cd.audit_path.read_bytes().splitlines()
    i = next(n for n, x in enumerate(lines) if b"finding_created" in x)
    lines[i] = lines[i].replace(b"finding_created", b"finding_createx")
    ca.cd.audit_path.write_bytes(b"\n".join(lines) + b"\n")
    assert AuditLog(ca.cd.audit_path).verify()[0] is False and AuditLog(cb.cd.audit_path).verify() == (True, None)
    code, cap = cli(tmp_path, capsys, "decisions")
    assert code == 1 and f"audit trail of {ca.cd.id} does not verify" in cap.err
    assert {json.loads(x)["case"] for x in cap.out.splitlines()} == {cb.cd.id}  # the case that verifies is still exported
    code, cap = cli(tmp_path, capsys, "decisions", ca.cd.id)  # named on its own it is refused: exit 1, nothing on stdout
    assert code == 1 and cap.out == "" and "does not verify" in cap.err
    code, cap = cli(tmp_path, capsys, "decisions", "--tally")  # the counts leave the refused case out and say so
    assert code == 1 and "does not verify" in cap.err and "1 case," in cap.out.splitlines()[0]
