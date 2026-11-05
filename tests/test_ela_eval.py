"""The report of evaluation/run_e.py lists the false regions and the misses, keeps the cases the check cannot see apart and uses no verdict word."""
import re

from evaluation.run_e import HOSTS, format_report

RUN = {"date": "d", "commit": "abc", "dirty": False, "seeds": (1, 2), "knobs": {"Z": 6.0}, "machine": "m", "hosts": ""}


def row(case, expect, regions=0, located=False, stray=0, kind="pasted-field"):
    return {"case": case, "kind": kind, "level": "mild", "expect": expect, "host": 85, "last_save": 95, "final": 95, "earlier": 85,
            "regions": regions, "limited": False, "located": located, "stray": stray, "seconds": 1.0}


def test_the_report_names_false_regions_and_misses_and_keeps_blind_cases_apart():
    rows = [row("c0", "none", regions=1, stray=1, kind="genuine"), row("c1", "seen", regions=1, located=True), row("c2", "seen"),
            row("c3", "blind", regions=1, kind="aligned")]
    text = format_report("ext-dev", "pixels", rows, RUN)
    assert "a region on 1, which is a false flag (c0)." in text
    assert "Missed among those it is meant to see: c2." in text
    assert "Edits it cannot see (1, listed apart, not claimed): a region anyway on 1, touching the edit on 1" in text
    assert not re.search(r"fraud|forg|fake|counterfeit", text, re.I)


def test_the_off_grid_hosts_lie_between_the_steps_of_five_the_check_tries():
    assert all(q % 5 for q in HOSTS["off-grid"].values())
