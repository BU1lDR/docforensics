"""H (reused marks): the two measures, and the detector that raises an observation when two documents of one case carry the same
signature image. A stamp is not looked at (eval/h/reuse-ext-dev-stamps.md says why)."""
import re

import cv2
import numpy as np
import pytest

from datagen import reuse_pack
from datagen.fictional import identity
from datagen.layouts.application import draw_application
from datagen.layouts.payslip import draw_payslip
from docforensics.audit import AuditLog
from docforensics.config import Thresholds
from docforensics.forensics import run_forensics
from docforensics.forensics.reuse import bits, dhash, ink_gap
from docforensics.ingest import create_case
from docforensics.pipeline import run_case
from docforensics.read import read_stage
from docforensics.understand.classify import classify_stage
from tests.helpers import iou

TH = Thresholds()
STAGES = {"read": read_stage, "classify": classify_stage, "forensics": run_forensics}
VERDICT = re.compile(r"fraud|forg|fake|counterfeit", re.I)


def squiggle(seed=1, size=(192, 64), pad=4):
    """A made-up canvas of ink like the ones the detectors compare: one stroke through seven random points, padded so that it can slide."""
    r = np.random.default_rng(seed)
    pts = np.stack([np.sort(r.uniform(8, size[0] - 8, 7)), r.uniform(10, size[1] - 10, 7)], 1)
    img = np.zeros((size[1], size[0]), np.uint8)
    cv2.polylines(img, [pts.astype(np.int32)], False, 1, 2)
    return np.pad(img > 0, pad)


def test_the_same_canvas_has_no_gap_and_the_same_hash():
    a = squiggle(3)
    assert ink_gap(a, a.copy()) == 0.0 and bits(dhash(a, 4), dhash(a.copy(), 4)) == 0


def test_a_canvas_slid_by_one_pixel_is_still_the_same_image():
    a = squiggle(3)
    b = np.roll(a, (1, -1), (0, 1))
    assert ink_gap(a, b) == 0.0


def test_another_drawing_is_far_in_both_measures():
    a, b = squiggle(3), squiggle(4)
    assert ink_gap(a, b) > 40 and bits(dhash(a, 4), dhash(b, 4)) > 8


def test_a_few_stray_pixels_move_the_hash_a_little_and_not_the_gap_much():
    a = squiggle(3)
    b = a.copy()
    r = np.random.default_rng(0)
    for y, x in zip(r.integers(4, 60, 6), r.integers(4, 188, 6)):
        b[y, x] = not b[y, x]
    assert bits(dhash(a, 4), dhash(b, 4)) <= 6 and ink_gap(a, b) < 10


def test_the_hash_has_sixty_four_bits_and_ignores_the_padding():
    a = squiggle(3, pad=4)
    assert 0 <= dhash(a, 4) < 2 ** 64
    assert dhash(np.pad(a, 3), 7) == dhash(a, 4)


def test_bits_counts_the_bits_that_differ():
    assert bits(0b1011, 0b0010) == 2 and bits(0, 2 ** 64 - 1) == 64


# --- the detector

def run(tmp_path, *files):
    _, cd, _ = create_case(tmp_path / "data", list(files), TH)
    case = run_case(cd, TH, stages=STAGES)
    return case, AuditLog(cd.audit_path).events()


def reuse_findings(case):
    return [f for f in case.findings if f.detector == "reuse"]


def compared(events, kind=None):
    return [e.data for e in events if e.event == "reuse_compared" and kind in (None, e.data["kind"])]


def pack_files(tmp_path, kind, medium="digital"):
    (p,) = [p for p in reuse_pack.plan_pack("ext-dev", 24) if p["kind"] == kind and p["medium"] == medium][:1]
    files, entry = reuse_pack.build_pack_case(p)
    return sorted(files.items()), entry


def test_a_signature_drawn_twice_is_one_observation_that_points_at_both_and_names_ordinary_causes(tmp_path):
    files, entry = pack_files(tmp_path, "signature")
    case, events = run(tmp_path, *files)
    (f,) = reuse_findings(case)
    assert (f.fclass, f.family) == ("observation", "visual") and "signature" in f.title.lower()
    assert not VERDICT.search(f.title + f.detail) and "ordinary" in f.detail.lower() and "does not say" in f.detail.lower()
    assert f"{TH.repeat_ink:g}" in f.detail
    (done,) = compared(events, "signature")
    assert done["repeat"] is True and done["ink"] <= TH.repeat_ink and 0 <= done["hash_bits"] <= 64
    truth = {name: box[1:] for name, box in entry["reuse"][0]["boxes"].items()}
    by_doc = {c.id: c.filename for c in case.documents}
    assert len(f.evidence) == 2
    for e in f.evidence:
        assert iou(e.box, truth[by_doc[e.doc]]) > 0.8


def test_a_stamp_pressed_twice_is_not_looked_at_and_neither_is_a_logo(tmp_path):
    """Separate pressings of the generated stamp can match as closely as a copy (eval/h/reuse-ext-dev-stamps.md), so a stamp is left out."""
    files, _ = pack_files(tmp_path, "stamp")
    case, events = run(tmp_path, *files)
    assert reuse_findings(case) == []  # the stamps of this case are one pressing, and the signatures are two signings
    assert {d["kind"] for d in compared(events)} == {"signature"}  # one pair, of signatures; none of stamps or logos


def test_a_genuine_case_is_compared_and_raises_nothing(tmp_path):
    files, _ = pack_files(tmp_path, "genuine")
    case, events = run(tmp_path, *files)
    assert reuse_findings(case) == []
    (done,) = compared(events)
    assert done["kind"] == "signature" and done["repeat"] is False and done["limit_ink"] == TH.repeat_ink and done["ink"] > done["limit_ink"]


def test_a_document_submitted_twice_is_not_reported_again_for_its_marks(tmp_path):
    ident = identity(1)
    slip = draw_payslip(ident, seed=31).pdf
    case, events = run(tmp_path, ("a.pdf", draw_application(ident, seed=1).pdf), ("b.pdf", slip), ("c.pdf", slip))
    assert reuse_findings(case) == []
    assert [d["docs"] for d in compared(events)] == [["D1", "D2"], ["D1", "D3"]]  # the two copies of one file are not compared with each other

