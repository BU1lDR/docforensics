"""The report of evaluation/run_structure.py names the false flags and the misses, and uses no verdict word; ext-test is not read without the flag."""
import re

import pytest

from datagen import structure_pack as pack
from docforensics.config import Thresholds
from evaluation import run_structure

RUN = {"date": "d", "commit": "abc", "dirty": False, "seeds": (1, 2), "machine": "m"}


def row(case, kind, expect=(), shown=(), limitations=()):
    expect, shown = sorted(expect), sorted(shown)
    return {"case": case, "kind": kind, "file": "document.pdf", "bytes": 10, "expect": expect, "shown": shown, "limitations": list(limitations),
            "missed": [t for t in expect if t not in shown], "stray": [t for t in shown if t not in expect], "seconds": 1.0}


def test_the_report_names_false_flags_misses_and_strays_and_uses_no_verdict_word():
    rows = [row("c0", "statement", shown=["Bytes follow the last end-of-file marker"]), row("c1", "payslip"),
            row("c2", "tail", expect=pack.TITLES["tail"], shown=pack.TITLES["tail"]), row("c3", "records", expect=pack.TITLES["records"]),
            row("c4", "attached", expect=pack.TITLES["attached"], shown=pack.TITLES["attached"][:1]),
            row("c5", "signed-then-added", expect=pack.TITLES["signed-then-added"], shown=pack.TITLES["signed-then-added"],
                limitations=["Signature present, not verified"]), row("c6", "signed-then-added", expect=pack.TITLES["signed-then-added"],
                                                                        shown=pack.TITLES["signed-then-added"], limitations=["Signature present, not verified"])]
    text = run_structure.format_report("ext-dev", rows, RUN)
    assert "Files without a planted change (2): an observation on 1, which is a false flag (c0)." in text
    assert "every expected observation shown on 3; 4 of 6 expected observations shown. Missed: c3, c4." in text
    assert "Observations that were not expected: 1 (on c0)." in text
    assert "Limitations the check raised: 2: signed-then-added: Signature present, not verified (2)." in text  # grouped, not one entry a case
    assert "nothing about files made by other programs" in text
    assert not re.search(r"fraud|forg|fake|counterfeit|tamper", text, re.I)


def test_ext_test_is_not_read_without_the_once_flag(monkeypatch, tmp_path):
    monkeypatch.setattr(run_structure, "run_pack", lambda *a, **k: pytest.fail("this must not be reached"))
    with pytest.raises(SystemExit) as stop:
        run_structure.main(["ext-test", "--out", str(tmp_path / "s")])
    assert "--once-at-freeze" in str(stop.value.code)  # sys.exit(message): the message is the code
    assert not (tmp_path / "s").exists()


def test_the_whole_tool_shows_what_was_planted_in_one_file(tmp_path):
    p = next(c for c in pack.plan_cases("ext-dev", len(pack.KINDS)) if c["kind"] == "tail")
    data, entry = pack.build_case(p)
    r = run_structure.look(entry, data, tmp_path, Thresholds())
    assert r["shown"] == r["expect"] == pack.TITLES["tail"] and r["missed"] == r["stray"] == []
