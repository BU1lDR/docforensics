"""The slice on the command line (design 7.8): run a case, trace a finding to its place in the source file, verify the audit trail."""
import hashlib
import os
import stat

import pytest

from docforensics.cli import main
from docforensics.store import CaseDir, load_case
from tests.helpers import d1_edited_statement, pdf_bytes

NEW = "9,99,999.00"


@pytest.fixture
def edited():
    return d1_edited_statement(NEW)


def cli(tmp_path, capsys, *args):
    code = main([*args, "--data", str(tmp_path / "data")])
    return code, capsys.readouterr()


def run_files(tmp_path, capsys, **files):
    paths = []
    for name, data in files.items():
        (tmp_path / "in").mkdir(exist_ok=True)
        (tmp_path / "in" / name).write_bytes(data)
        paths.append(str(tmp_path / "in" / name))
    code, cap = cli(tmp_path, capsys, "run", *paths)
    cases = sorted((tmp_path / "data" / "cases").glob("C-*"))
    return code, cap, (CaseDir(cases[-1]) if cases else None)


def test_run_prints_summary_and_writes_case(tmp_path, capsys, edited):
    code, cap, cd = run_files(tmp_path, capsys, **{"statement.pdf": edited})
    case = load_case(cd)
    assert code == 0 and case.id in cap.out and "statement.pdf" in cap.out
    assert {"pdf_revisions", "statement_balance"} <= {f.detector for f in case.findings}  # the edit, seen by two kinds of check
    for f in case.findings:
        assert f.id in cap.out and f.fclass in cap.out and f.title in cap.out
    assert cd.case_json.is_file() and cd.audit_path.is_file() and list(cd.crops.glob("F-*.png"))


def test_run_leaves_explained_findings_and_crops_in_the_case(tmp_path, capsys, edited):
    _, _, cd = run_files(tmp_path, capsys, **{"statement.pdf": edited})
    case = load_case(cd)
    assert all(f.explanation and f.next_steps and f.explanation_source == "template" for f in case.findings)
    located = [e for f in case.findings for e in f.evidence if e.page > 0]
    assert located and any(e.crop_path for e in located)
    assert all((cd.root / e.crop_path).is_file() for f in case.findings for e in f.evidence if e.crop_path)


def test_run_takes_a_folder_but_not_its_subfolders(tmp_path, capsys):
    (tmp_path / "in" / "deeper").mkdir(parents=True)
    (tmp_path / "in" / "a.pdf").write_bytes(pdf_bytes(text="A"))
    (tmp_path / "in" / "deeper" / "b.pdf").write_bytes(pdf_bytes(text="B"))
    code, cap = cli(tmp_path, capsys, "run", str(tmp_path / "in"))
    (cd,) = (tmp_path / "data" / "cases").iterdir()
    assert code == 0 and [d.filename for d in load_case(CaseDir(cd)).documents] == ["a.pdf"]


def test_run_with_a_path_that_does_not_exist_makes_no_case(tmp_path, capsys):
    code, cap = cli(tmp_path, capsys, "run", str(tmp_path / "nope.pdf"))
    assert code == 2 and "nope.pdf" in cap.err and not (tmp_path / "data" / "cases").exists()


def test_run_with_nothing_readable_says_so_and_fails(tmp_path, capsys):
    code, cap, cd = run_files(tmp_path, capsys, **{"notes.txt": b"just words"})
    assert code == 1 and "File not ingested" in cap.out and load_case(cd).documents == []


def test_names_with_bidi_or_control_characters_are_printed_clean(tmp_path, capsys):
    bad = "stmt" + chr(0x202E) + "fdp.pdf"
    code, cap, _ = run_files(tmp_path, capsys, **{bad: pdf_bytes()})
    assert code == 0 and chr(0x202E) not in cap.out and "stmt" in cap.out


def edited_case(tmp_path, capsys, edited):
    _, _, cd = run_files(tmp_path, capsys, **{"statement.pdf": edited})
    case = load_case(cd)
    return cd, case, next(f for f in case.findings if f.detector == "pdf_revisions")


def test_trace_prints_file_sha_page_box_value(tmp_path, capsys, edited):
    cd, case, f = edited_case(tmp_path, capsys, edited)
    code, cap = cli(tmp_path, capsys, "trace", case.id, f.id)
    e, doc = f.evidence[0], case.documents[0]
    sha = hashlib.sha256(edited).hexdigest()
    assert code == 0 and f.id in cap.out
    assert f"files/{sha}.pdf" in cap.out and sha in cap.out and "stored file matches" in cap.out
    assert f"page {e.page}" in cap.out and " ".join(f"{v:.1f}" for v in e.box) in cap.out
    assert e.value == NEW and NEW in cap.out and e.crop_path in cap.out
    x0, dpi = e.box[0], doc.pages[0].dpi
    assert f"{x0 * 72 / dpi:.1f}" in cap.out  # the same box in PDF points


def test_trace_reports_a_stored_file_that_no_longer_matches(tmp_path, capsys, edited):
    cd, case, f = edited_case(tmp_path, capsys, edited)
    stored = cd.root / case.documents[0].stored_path
    os.chmod(stored, stat.S_IWRITE)
    stored.write_bytes(edited + b"\n% altered after intake")
    code, cap = cli(tmp_path, capsys, "trace", case.id, f.id)
    assert code == 0 and "STORED FILE DIFFERS" in cap.out and "stored file matches" not in cap.out


def test_trace_prints_a_finding_with_hostile_text_clean(tmp_path, capsys, edited):
    cd, case, f = edited_case(tmp_path, capsys, edited)
    bad = "\x1b[31mred\x1b[0m" + chr(0x202E) + "evil"
    case.findings[case.findings.index(f)] = f.model_copy(update={"title": bad, "detail": bad, "evidence": [
        f.evidence[0].model_copy(update={"note": bad, "value": bad})]})
    (cd.root / "case.json").write_text(case.model_dump_json(), encoding="utf-8")
    code, cap = cli(tmp_path, capsys, "trace", case.id, f.id)
    assert code == 0 and "red" in cap.out and "\x1b" not in cap.out and chr(0x202E) not in cap.out


@pytest.mark.parametrize("case_id, finding", [("C-20260101-000000-abcd", "F-001"), ("../../etc", "F-001"), ("REAL", "F-999")])
def test_trace_of_something_that_does_not_exist_is_a_usage_error(tmp_path, capsys, edited, case_id, finding):
    _, case, _ = edited_case(tmp_path, capsys, edited)
    code, cap = cli(tmp_path, capsys, "trace", case.id if case_id == "REAL" else case_id, finding)
    assert code == 2 and cap.err.strip() and cap.out == ""


def test_verify_audit_ok_then_tampered(tmp_path, capsys, edited):
    cd, case, _ = edited_case(tmp_path, capsys, edited)
    code, cap = cli(tmp_path, capsys, "verify-audit", case.id)
    assert code == 0 and cap.out.startswith("OK: ") and " events, head " in cap.out
    lines = cd.audit_path.read_text(encoding="utf-8").splitlines()
    assert '"actor":"system"' in lines[2]
    lines[2] = lines[2].replace('"actor":"system"', '"actor":"reviewer"', 1)
    cd.audit_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    code, cap = cli(tmp_path, capsys, "verify-audit", case.id)
    assert code == 1 and "BROKEN at event 3" in cap.out


def test_verify_audit_does_not_call_a_missing_trail_ok(tmp_path, capsys, edited):
    cd, case, _ = edited_case(tmp_path, capsys, edited)
    cd.audit_path.unlink()
    code, cap = cli(tmp_path, capsys, "verify-audit", case.id)
    assert code == 1 and "OK" not in cap.out and "no audit trail" in cap.out.lower()
