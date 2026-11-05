"""H (reused marks), the pack: cases whose payslip and application carry the very same signature, or whose statement and application
carry the very same stamp pressing, and genuine controls drawn like the rest. It has seeds of its own and changes nothing in the dev
and test splits."""
import hashlib
import json
from collections import Counter

import pytest

from datagen import marks, reuse_pack, signatures
from datagen.build import SECOND, SPLIT_BASE, SPLIT_SPAN, build_case, plan_cases


def box_size(entry, doc_stem, region):
    (doc,) = [d for d in entry["docs"] if d["file"].startswith(doc_stem)]
    _, x0, y0, x1, y1 = doc["boxes"][region]
    return x1 - x0, y1 - y0


def same_size(a, b):
    """The boxes of two drawings of the same strokes agree to the rounding of their corners (a hundredth of a pixel); two signings do not."""
    return all(abs(u - v) < 0.05 for u, v in zip(a, b))


def test_the_pack_has_seeds_that_no_other_split_uses():
    """A case takes its seed and, for the second applicant some cases borrow from, a seed SECOND above it (a few hundred past that)."""
    def used(base, span):
        return [range(base, base + span), range(base + SECOND, base + SECOND + span + 1000)]
    taken = [r for b in SPLIT_BASE.values() for r in used(b, SPLIT_SPAN)]
    mine = {split: used(base, reuse_pack.SPAN) for split, base in reuse_pack.BASE.items()}
    for split, ranges in mine.items():
        assert not any(r.start < t.stop and t.start < r.stop for r in ranges for t in taken), split
    assert not any(r.start < s.stop and s.start < r.stop for r in mine["ext-dev"] for s in mine["ext-test"])
    assert reuse_pack.BASE == {"ext-dev": 3_200_000, "ext-test": 4_200_000}


def test_the_plan_takes_the_three_kinds_in_turn_and_each_kind_goes_through_the_media_in_turn():
    plan = reuse_pack.plan_pack("ext-dev", 24)
    assert [p["case"] for p in plan][:3] == ["ext-dev-h-0000", "ext-dev-h-0001", "ext-dev-h-0002"]
    assert Counter(p["kind"] for p in plan) == {"genuine": 8, "signature": 8, "stamp": 8}
    for kind in ("genuine", "signature", "stamp"):
        mine = [p for p in plan if p["kind"] == kind]
        assert [p["medium"] for p in mine] == list(reuse_pack.MEDIA)
        assert [p["k"] for p in mine] == list(range(8))
    assert [p["seed"] for p in plan] == [reuse_pack.BASE["ext-dev"] + i for i in range(24)]
    assert {p["layout"] for p in plan} == {"A"} and {p["layout"] for p in reuse_pack.plan_pack("ext-test", 24)} == {"A", "B"}
    assert reuse_pack.plan_pack("ext-dev", 5, start=3) == plan[3:8]


def test_a_plan_that_does_not_fit_is_refused():
    for args in (("dev", 3), ("ext-dev", -1), ("ext-dev", reuse_pack.SPAN + 1)):
        with pytest.raises(ValueError):
            reuse_pack.plan_pack(*args)


def test_two_signatures_of_one_pack_case_are_the_same_drawing_and_in_a_genuine_case_they_are_not():
    plan = {(p["kind"], p["medium"]): p for p in reuse_pack.plan_pack("ext-dev", 24)}
    _, copied = reuse_pack.build_pack_case(plan["signature", "digital"])
    assert copied["genuine"] is False and [r["kind"] for r in copied["reuse"]] == ["signature"]
    assert sorted(copied["reuse"][0]["docs"]) == ["02_payslip.pdf", "03_application.pdf"]
    assert same_size(box_size(copied, "02_payslip", "signature"), box_size(copied, "03_application", "signature"))
    _, genuine = reuse_pack.build_pack_case(plan["genuine", "digital"])
    assert genuine["genuine"] is True and genuine["reuse"] == []
    assert not same_size(box_size(genuine, "02_payslip", "signature"), box_size(genuine, "03_application", "signature"))


def test_two_stamps_of_one_pack_case_are_the_same_pressing_and_in_a_genuine_case_they_are_not():
    plan = {(p["kind"], p["medium"]): p for p in reuse_pack.plan_pack("ext-dev", 24)}
    _, copied = reuse_pack.build_pack_case(plan["stamp", "digital"])
    assert [r["kind"] for r in copied["reuse"]] == ["stamp"] and sorted(copied["reuse"][0]["docs"]) == ["01_statement.pdf", "03_application.pdf"]
    assert same_size(box_size(copied, "01_statement", "stamp"), box_size(copied, "03_application", "stamp"))
    # the signatures of a stamp case are still two signings
    assert not same_size(box_size(copied, "02_payslip", "signature"), box_size(copied, "03_application", "signature"))
    _, genuine = reuse_pack.build_pack_case(plan["genuine", "digital"])
    assert not same_size(box_size(genuine, "01_statement", "stamp"), box_size(genuine, "03_application", "stamp"))


def test_the_manifest_names_where_each_reused_mark_is_and_a_scan_has_its_boxes_in_the_scan():
    plan = {(p["kind"], p["medium"]): p for p in reuse_pack.plan_pack("ext-dev", 24)}
    files, entry = reuse_pack.build_pack_case(plan["signature", "mild"])
    assert entry["medium"] == "mild" and all(name.endswith(".jpg") for name in files)
    (r,) = entry["reuse"]
    for name in r["docs"]:
        assert len(r["boxes"][name]) == 5 and r["boxes"][name][0] == 1
        (doc,) = [d for d in entry["docs"] if d["file"] == name]
        assert r["boxes"][name] == doc["boxes"]["signature"]
        assert doc["sha256"] == hashlib.sha256(files[name]).hexdigest()


def test_building_the_same_pack_case_twice_gives_the_same_bytes():
    p = reuse_pack.plan_pack("ext-dev", 2)[1]
    (f1, e1), (f2, e2) = reuse_pack.build_pack_case(p), reuse_pack.build_pack_case(p)
    assert f1 == f2 and e1 == e2


def test_the_pack_leaves_the_drawers_and_the_dev_split_as_they_were():
    draw, press = signatures.draw, marks._draw
    before = build_case(plan_cases("dev", 1)[0])
    for p in reuse_pack.plan_pack("ext-dev", 3):
        reuse_pack.build_pack_case(p)
    assert signatures.draw is draw and marks._draw is press
    assert build_case(plan_cases("dev", 1)[0]) == before


def test_a_pack_is_written_with_a_manifest(tmp_path):
    path = reuse_pack.build_pack("ext-dev", tmp_path, 3)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["split"] == "ext-dev" and data["pack"] == "reuse" and [c["case"] for c in data["cases"]] == [f"ext-dev-h-000{i}" for i in range(3)]
    for c in data["cases"]:
        for d in c["docs"]:
            assert hashlib.sha256((tmp_path / c["case"] / d["file"]).read_bytes()).hexdigest() == d["sha256"]
