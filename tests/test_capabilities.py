"""capabilities.json is the one list of what the tool does, partly does, plans and declines (design 9). The dossier and the README
print it, so it has to be well formed, and what it cites as evidence has to exist."""
import re
from pathlib import Path

from docforensics.capabilities import load_capabilities

ROOT = Path(__file__).resolve().parents[1]
STATUSES = {"Implemented", "Partial", "Planned", "Unsupported"}
VERDICT = re.compile(r"fraud|forg|fake|counterfeit", re.I)


def test_capabilities_valid():
    caps = load_capabilities()
    assert set(caps) == {"capabilities", "limitations", "assumptions"}
    rows = caps["capabilities"]
    assert rows and len({r["name"] for r in rows}) == len(rows)
    for r in rows:
        assert {"name", "status", "evidence"} <= set(r) <= {"name", "status", "evidence", "note"}, r
        assert r["status"] in STATUSES, r
        if r["status"] in ("Implemented", "Partial"):
            assert r["evidence"] and all(isinstance(e, str) and e for e in r["evidence"]), r  # no claim without evidence
    assert {r["status"] for r in rows} == STATUSES  # an honest matrix has every kind of row
    assert caps["limitations"] and caps["assumptions"]
    assert all(isinstance(s, str) and s for s in caps["limitations"] + caps["assumptions"])


def test_evidence_points_at_tests_that_exist():
    for r in load_capabilities()["capabilities"]:
        for ev in r["evidence"]:
            path, _, name = ev.partition("::")
            assert path.startswith(("tests/", "eval/")), ev
            f = ROOT / path
            assert f.is_file(), ev
            if name:
                assert re.search(rf"^\s*def {re.escape(name)}\(", f.read_text(encoding="utf-8"), re.M), ev


def test_capability_text_makes_no_verdicts():
    assert not VERDICT.search(str(load_capabilities()))
