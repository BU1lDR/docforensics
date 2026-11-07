"""The report of evaluation/run_emi.py names the false flags, the misses and the blind spot, and uses no verdict word; ext-test is not read without the flag."""
import re

import pytest

from datagen import emi_pack as pack
from docforensics.audit import AuditLog
from docforensics.config import Thresholds
from docforensics.pipeline import STAGE_ORDER
from evaluation import run_emi

RUN = {"date": "d", "commit": "abc", "dirty": False, "seeds": (1, 2), "machine": "m"}
T = pack.TITLE


def row(case, kind, shown=(), total_ok=None, limitations=(), gap=False, other=(), layout="A", medium="digital"):
    expect = [T] if kind in pack.PLANTED else []
    shown = sorted(shown)
    return {"case": case, "kind": kind, "layout": layout, "medium": medium, "declared": "0.00", "total": "100.00" if expect else None,
            "expect": expect, "shown": shown, "total_ok": total_ok, "limitations": list(limitations), "gap": gap, "other": list(other),
            "missed": [t for t in expect if t not in shown], "stray": [t for t in shown if t not in expect], "seconds": 1.0}


def test_the_report_names_false_flags_misses_the_blind_spot_and_uses_no_verdict_word():
    rows = [row("c0", "none", shown=[T]), row("c1", "match"), row("c2", "match", gap=True),
            row("c3", "under-zero", shown=[T], total_ok=True), row("c4", "under-part", shown=[T], total_ok=False),
            row("c5", "under-some", gap=True), row("c6", "under-zero", limitations=["Possible extraction error, verify: x"], medium="scan"),
            row("c7", "lender-only"), row("c8", "lender-only", shown=[T], total_ok=True),
            row("c9", "lookalike", other=["cross_name: Name differs"])]
    text = run_emi.format_report("ext-dev", rows, RUN)
    assert "Cases with nothing to find (4): a finding on 1, which is a false flag (c0)." in text
    assert "Cases with a gap the check reads (4): found on 2; missed: c5, c6." in text
    assert "named the instalments' total correctly on 1 of 2" in text
    assert "Cases with a gap the check cannot read (2, kind lender-only): found on 1 (c8)." in text
    assert "could not compare: 2 (c2, c5)" in text
    assert "Possible extraction error" in text and "c6" in text
    assert "Findings of other checks on these cases: 1 (cross_name: Name differs on c9)" in text
    assert "nothing about other layouts or other producers" in text
    assert not re.search(r"fraud|forg|fake|counterfeit|tamper", text, re.I)
    assert "| under-zero | yes | 2 |" in text and "| lender-only | yes, not readable | 2 |" in text  # one line a kind


def test_ext_test_is_not_read_without_the_once_flag(monkeypatch, tmp_path):
    monkeypatch.setattr(run_emi, "run_pack", lambda *a, **k: pytest.fail("this must not be reached"))
    with pytest.raises(SystemExit) as stop:
        run_emi.main(["ext-test", "--out", str(tmp_path / "s")])
    assert "--once-at-freeze" in str(stop.value.code)  # sys.exit(message): the message is the code
    assert not (tmp_path / "s").exists()


def test_the_whole_tool_shows_what_was_set_in_one_case(tmp_path):
    p = next(c for c in pack.plan_cases("ext-dev", len(pack.KINDS)) if c["kind"] == "under-part")
    files, entry = pack.build_case(p)
    r = run_emi.look(entry, files, tmp_path, Thresholds())
    assert r["shown"] == r["expect"] == [T] and r["missed"] == r["stray"] == [] and r["total_ok"] is True
    (audit,) = tmp_path.rglob("audit.jsonl")
    assert [e.data["stage"] for e in AuditLog(audit).events() if e.event == "stage_end"] == list(STAGE_ORDER)  # every registered stage


def test_a_case_without_a_finding_is_a_clean_row(tmp_path):
    p = next(c for c in pack.plan_cases("ext-dev", len(pack.KINDS)) if c["kind"] == "lookalike")
    files, entry = pack.build_case(p)
    r = run_emi.look(entry, files, tmp_path, Thresholds())
    assert r["shown"] == r["expect"] == [] and r["total_ok"] is None and r["gap"] is False
