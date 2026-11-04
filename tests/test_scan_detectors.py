"""Scan simulation (Task 17) and the manipulations and detectors for scans. These tests are about mechanisms: that a simulated
scan lands in the quality class the ladder says, that a manipulation changes what it says it changes, that a detector fires on
a change it is built to see and stays quiet on a genuine scan. How often a detector finds a manipulation is measured by the
evaluation, not here."""
import io
import re

import numpy as np
import pytest
from PIL import Image

from datagen.fictional import identity
from datagen.layouts.statement import draw_statement
from datagen.manipulate import Manipulation, s1_splice, s2_erase_retype
from datagen.scan import LEVELS, simulate_scan
from docforensics.audit import AuditLog
from docforensics.config import Thresholds
from docforensics.forensics import run_forensics
from docforensics.forensics.scan_noise import noise_residual
from docforensics.ingest import create_case
from docforensics.model import Case, Document, Page, Word
from docforensics.pipeline import Ctx, run_case
from docforensics.read import read_stage
from docforensics.read.ocr import load_image_page
from docforensics.store import CaseDir
from tests.helpers import iou

TH = Thresholds()
ocr = pytest.mark.ocr
AMOUNT = re.compile(r"^(\d{1,3}(,\d\d)*,\d{3}|\d{1,3})\.\d\d$")
DETECTORS = ("scan_noise", "scan_layout")


def statement_pdf(seed=1):
    return draw_statement(identity(seed), rows=12, seed=seed).pdf


def scan_of(seed=1, level="mild", angle_seed=1):
    return simulate_scan(statement_pdf(seed), level, seed=angle_seed)


def amount_boxes(tmp_path, jpeg):
    """The boxes of the amounts on a scan, as the reader finds them, from the top of the page down."""
    src = tmp_path / "find.jpg"
    src.write_bytes(jpeg)
    page = load_image_page(src, "D1", tmp_path / "find.png", TH)
    return [list(w.box) for w in page.words if AMOUNT.match(w.text)], (page.width, page.height)


def run(tmp_path, *scans):
    """Read the scans and run the forensic detectors, nothing else."""
    _, cd, _ = create_case(tmp_path / "data", [(f"s{i}.jpg", s) for i, s in enumerate(scans, 1)], TH)
    return run_case(cd, TH, stages={"read": read_stage, "forensics": run_forensics})


def gray(jpeg):
    return np.asarray(Image.open(io.BytesIO(jpeg)).convert("L"), dtype=np.float32)


def seen(case):
    return [f for f in case.findings if f.detector in DETECTORS and f.fclass == "observation"]


# --- the simulation

@ocr
@pytest.mark.parametrize("level, classes", [("mild", {"good"}), ("150dpi", {"good", "degraded"}), ("120dpi", {"degraded", "poor"})])
def test_simulated_scan_gets_expected_quality_class(tmp_path, level, classes):
    src = tmp_path / "scan.jpg"
    src.write_bytes(simulate_scan(statement_pdf(), level, seed=1))
    page = load_image_page(src, "D1", tmp_path / "p.png", TH)
    print(level, page.quality_class, round(page.sharpness, 3))
    assert page.quality_class in classes and page.read_mode == "ocr"


def test_simulated_scan_is_a_jpeg_that_the_seed_decides():
    pdf = statement_pdf()
    a, b, c = (simulate_scan(pdf, "mild", s) for s in (1, 1, 2))
    assert a[:3] == b"\xff\xd8\xff" and a == b and a != c
    assert set(LEVELS) == {"mild", "150dpi", "120dpi"}


# --- the manipulations

@ocr
def test_s1_and_s2_change_the_box_and_little_else(tmp_path):
    host, donor = scan_of(1), scan_of(2, angle_seed=1)
    boxes, _ = amount_boxes(tmp_path, host)
    x0, y0, x1, y1 = (int(round(v)) for v in boxes[3])
    box = [x0 - 3, y0 - 3, x1 + 3, y1 + 3]
    for name, (out, m) in {"S1": s1_splice(host, donor, box), "S2": s2_erase_retype(host, box, "9,99,999.00")}.items():
        assert isinstance(m, Manipulation) and (m.method, m.page) == (name, 1) and m.box == [float(v) for v in box]
        diff = np.abs(gray(out) - gray(host))
        inside = diff[box[1]:box[3], box[0]:box[2]].mean()
        diff[box[1]:box[3], box[0]:box[2]] = 0
        assert inside > 8 and diff.mean() < 2  # the box is changed; the rest is only the second JPEG save


# --- the detectors

@ocr
def test_flat_erased_patch_fires_noise_residual(tmp_path):
    host = scan_of(1, level="150dpi")  # at the mild level the second JPEG save puts back grain about as large as the scan's own
    (tmp_path / "a").mkdir()
    boxes, _ = amount_boxes(tmp_path / "a", host)
    x0, y0, x1, y1 = (int(round(v)) for v in boxes[4])
    box = [x0 - 8, y0 - 8, x1 + 8, y1 + 8]  # a generous patch: the new figure lies well inside it
    edited, _ = s2_erase_retype(host, box, "8,88,888.00")
    found = [f for f in run(tmp_path / "b", edited).findings if f.detector == "scan_noise" and f.fclass == "observation"]
    print([e.note for f in found for e in f.evidence])
    assert len(found) == 1 and "less" in found[0].detail
    assert any(e.page == 1 and e.box[0] >= box[0] and e.box[2] <= box[2] + 4 and e.box[1] >= box[1] and e.box[3] <= box[3] + 4
               for e in found[0].evidence)  # a word lying in the patch is named


@ocr
def test_strong_splice_fires_noise_or_layout(tmp_path):
    host, donor = scan_of(1), scan_of(2, level="150dpi", angle_seed=1)  # the donor was scanned worse: more noise, more blur
    (tmp_path / "a").mkdir()
    boxes, (w, _) = amount_boxes(tmp_path / "a", host)
    box = [60, int(boxes[3][1]) - 4, w - 60, int(boxes[5][3]) + 4]  # three rows of the table
    edited, _ = s1_splice(host, donor, box)
    found = seen(run(tmp_path / "b", edited))
    assert found and any(iou(e.box, box) >= 0.2 or (e.box[1] >= box[1] and e.box[3] <= box[3]) for f in found for e in f.evidence if e.page == 1)


@ocr
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_genuine_scans_fire_at_most_one_observation_each(tmp_path, seed):
    case = run(tmp_path, scan_of(seed, angle_seed=seed))
    print(seed, [(f.detector, f.title) for f in case.findings])
    assert len(seen(case)) <= 1


def poor_case(tmp_path):
    cd = CaseDir.create(tmp_path)
    page = Page(n=1, width=100, height=100, read_mode="ocr", quality_class="poor", image_path="never-opened.png",
                words=[Word(id="D1-p1-w1", text="1,00.00", box=(10.0, 10.0, 50.0, 30.0), conf=0.9)])
    doc = Document(id="D1", sha256="0", filename="s.jpg", stored_path="s.jpg", pages=[page])
    return Case(id="C", created="2026-11-04T00:00:00+00:00", documents=[doc]), doc, Ctx(cd, AuditLog(cd.audit_path), TH)


def test_poor_page_is_not_analysed_and_says_so(tmp_path):
    case, doc, ctx = poor_case(tmp_path)  # the image file does not exist: a detector that opened it would fail
    for det in (noise_residual,):
        (f,) = det(case, doc, ctx)
        assert f.fclass == "processing_limitation" and f.family == "limitation" and "page 1" in f.detail and "poor" in f.detail
