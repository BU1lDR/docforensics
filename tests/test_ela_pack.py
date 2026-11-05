"""Scans for measuring the compression-history detector (scope D, package E): genuine pages, genuine pages saved again, and pages
edited in ways that leave a region with a compression history of its own, or none that differs. The manifest says, before any
detector runs, which cases the test can see and which it cannot by construction; only the scorer reads it."""
import io

import numpy as np
import pytest
from PIL import Image

from datagen import build
from datagen.ela_pack import BASE, KINDS, LEVELS, PACK, SPAN, build_case, build_split, plan_cases
from datagen.scan import LEVELS as QUALITY


def gray(b: bytes) -> np.ndarray:
    return np.asarray(Image.open(io.BytesIO(b)).convert("L")).astype(np.int16)


def test_the_plan_keeps_to_its_own_seeds_and_covers_every_kind_and_level():
    plan = plan_cases("ext-dev", 36)
    assert [p["case"] for p in plan][:2] == ["ext-dev-e-0000", "ext-dev-e-0001"]
    assert {p["seed"] for p in plan} == set(range(BASE["ext-dev"] + PACK, BASE["ext-dev"] + PACK + 36))
    assert {(p["kind"], p["level"]) for p in plan} == {(k, lv) for k in KINDS for lv in LEVELS}
    assert max(build.SPLIT_BASE.values()) + build.SPLIT_SPAN <= BASE["ext-dev"] < BASE["ext-test"] and SPAN > 1000
    assert PACK >= 100_000  # the pack of package X draws the seeds below it
    assert plan_cases("ext-dev", 2, 5)[0]["case"] == "ext-dev-e-0005"
    with pytest.raises(ValueError):
        plan_cases("dev", 1)
    with pytest.raises(ValueError):
        plan_cases("ext-dev", 1, SPAN)


def test_every_kind_makes_a_jpeg_page_with_a_manifest_entry_and_the_same_bytes_again():
    for p in plan_cases("ext-dev", len(KINDS)):
        scan, entry = build_case(p)
        img = Image.open(io.BytesIO(scan))
        assert img.format == "JPEG" and abs(img.size[0] - 1654) <= 1 and img.size[1] == 2339  # A4 at 200 dpi, as far as the pixmap rounds
        assert entry["case"] == p["case"] and entry["kind"] == p["kind"] and entry["level"] == p["level"] and len(entry["sha256"]) == 64
        assert build_case(p)[0] == scan


def test_what_each_kind_is_and_whether_the_test_can_see_it_is_written_before_the_detector_runs():
    plan = plan_cases("ext-dev", 36)
    by = {}
    for p in plan:
        _, e = build_case(p)
        by.setdefault(e["kind"], []).append(e)
    for e in by["genuine"] + by["resaved"]:
        assert e["expect"] == "none" and e["box"] is None
    for e in by["pasted-field"] + by["pasted-block"] + by["retyped"] + by["aligned"]:
        x0, y0, x1, y1 = e["box"]
        assert 0 <= x0 < x1 <= 1654 and 0 <= y0 < y1 <= 2339
    for e in by["pasted-field"] + by["pasted-block"] + by["retyped"]:
        # the last save is better than the host's own: the host keeps an earlier history of its own that the edit does not share, but only if
        # the last save is at least 10 above it (two steps of the grid the detector looks at)
        assert e["expect"] == ("seen" if e["final_quality"] >= QUALITY[e["level"]][4] + 10 else "blind"), e
    assert {e["expect"] for e in by["aligned"]} == {"blind"}  # the same level, the same place: the same history by construction
    assert {e["expect"] for e in by["pasted-field"]} == {"seen"} and {e["level"] for e in by["pasted-field"]} == set(LEVELS)
    assert {e["expect"] for e in by["retyped"]} == {"seen", "blind"}  # stock S2 saves at 85: a host saved at 85 has nothing earlier to show


def test_a_pasted_region_comes_off_the_grid_and_an_aligned_one_does_not():
    plan = {(p["kind"], p["level"]): p for p in plan_cases("ext-dev", 36)}
    _, e = build_case(plan["pasted-field", "150dpi"])
    assert e["shift"][0] % 8 and e["shift"][1] % 8  # the donor's JPEG blocks do not fall on the host's
    _, e = build_case(plan["aligned", "150dpi"])
    assert e["shift"] == [0, 0]


def test_the_edit_is_where_the_manifest_says_and_only_there():
    plan = {(p["kind"], p["level"]): p for p in plan_cases("ext-dev", 36)}
    for kind in ("pasted-field", "pasted-block", "retyped"):
        edited, e = build_case(plan[kind, "150dpi"])
        plain, _ = build_case({**plan[kind, "150dpi"], "kind": "genuine"})  # the page the edit was made on, before the edit
        d = np.abs(gray(edited) - gray(plain)).astype(np.float32)
        x0, y0, x1, y1 = (int(v) for v in e["box"])
        inside, outside = d[y0:y1, x0:x1].mean(), (d.sum() - d[y0:y1, x0:x1].sum()) / (d.size - d[y0:y1, x0:x1].size)
        assert inside > 4 * outside and inside > 5, (kind, inside, outside)


def test_a_split_is_written_with_its_manifest(tmp_path):
    import json
    path = build_split("ext-dev", tmp_path, 6)
    m = json.loads(path.read_text(encoding="utf-8"))
    assert m["pack"] == "e" and [c["kind"] for c in m["cases"]] == list(KINDS)
    assert all((tmp_path / c["case"] / c["file"]).exists() for c in m["cases"])
