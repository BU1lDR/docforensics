"""The report of evaluation/run_e.py lists the false regions and the misses, keeps the cases the check cannot see apart and uses no verdict word."""
import re

from evaluation.run_e import HOSTS, format_dev, format_report

RUN = {"date": "d", "commit": "abc", "dirty": False, "seeds": (1, 2), "knobs": {"Z": 6.0}, "machine": "m", "hosts": ""}


def row(case, expect, regions=0, located=False, stray=0, kind="pasted-field", final=95):
    return {"case": case, "kind": kind, "level": "mild", "expect": expect, "host": 85, "last_save": 95, "final": final, "earlier": 85,
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


def test_the_report_counts_the_unchanged_scans_it_cannot_examine_so_that_no_region_is_not_read_as_a_pass():
    rows = [row("c0", "none", kind="genuine", final=35), row("c1", "none", kind="genuine", final=39), row("c2", "none", kind="genuine", final=40),
            row("c3", "none", kind="resaved", final=95), row("c4", "none", kind="genuine", final=None), row("c5", "seen", regions=1, located=True)]
    text = format_report("ext-dev", "pixels", rows, RUN)
    assert "Scans without an edit (5): a region on 0, which is a false flag. 3 of them cannot be examined (last save under quality 40, or none found)." in text
    assert "cannot be examined" not in format_report("ext-dev", "whole tool", [dict(r, final=None) for r in rows], RUN)  # that mode does not record the saves


def test_the_guard_counts_the_scans_it_cannot_examine_among_those_nobody_changed():
    def scan(case, key, final):
        return {"case": case, "file": f"{case}.jpg", "key": key, "level": "120dpi", "final": final, "earlier": None, "regions": 0, "box": None, "boxes": [],
                "touch": False, "located": False}
    rows = [scan("d0", "genuine", 35), scan("d1", "genuine", 85), scan("d2", "other", 35), scan("d3", "S1", 85)]
    text = format_dev(rows, 4, {"date": "d", "commit": "abc", "dirty": False, "machine": "m", "knobs": {"Z": 6.0}})
    assert "Scans of genuine cases (nothing changed): 2 scans, a region on 0; 1 of the 2 cannot be examined (last save under quality 40, or none found)" in text
    assert "not themselves changed as a picture: 1 scans, a region on 0; 1 of the 1 cannot be examined" in text
    assert "S1 (part of another scan pasted in): 1 scans, a region on 0, touching the edit on 0, at the edit (IoU above 0.3) on 0." in text
