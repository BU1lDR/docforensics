"""Scan simulation (Task 17) and the manipulations and detectors for scans. These tests are about mechanisms: that a simulated
scan lands in the quality class the ladder says, that a manipulation changes what it says it changes, that a detector fires on
a change it is built to see and stays quiet on a genuine scan. How often a detector finds a manipulation is measured by the
evaluation, not here."""
import io
import math
import re

import numpy as np
import pytest
from PIL import Image

from datagen.fictional import identity
from datagen.layouts.statement import draw_statement
from datagen.manipulate import Manipulation, s1_splice, s2_erase_retype
from datagen.scan import LEVELS, simulate_scan, turn
from docforensics.audit import AuditLog
from docforensics.config import Thresholds
from docforensics.forensics import run_forensics
from docforensics.forensics.scan_layout import layout_consistency, page_turn
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


@ocr
def test_splice_from_a_scan_turned_otherwise_fires_layout(tmp_path):
    donor_turn = 2  # turn(2) is -0.9 degrees, turn(1) +1.3: the donor's text lies at another slant than the host's
    assert abs(turn(donor_turn) - turn(1)) >= 1.5
    host, donor = scan_of(1), scan_of(2, angle_seed=donor_turn)  # the same level: the grain does not give the splice away
    (tmp_path / "a").mkdir()
    boxes, (w, _) = amount_boxes(tmp_path / "a", host)
    box = [60, int(boxes[3][1]) - 4, w - 60, int(boxes[5][3]) + 4]
    edited, _ = s1_splice(host, donor, box)
    found = [f for f in run(tmp_path / "b", edited).findings if f.detector == "scan_layout" and f.fclass == "observation"]
    print([(e.value, e.note) for f in found for e in f.evidence])
    assert found and any(box[1] <= e.box[1] and e.box[3] <= box[3] for f in found for e in f.evidence if e.page == 1)


@ocr
def test_retyped_larger_figure_fires_layout(tmp_path):
    host = scan_of(1)
    (tmp_path / "a").mkdir()
    boxes, _ = amount_boxes(tmp_path / "a", host)
    x0, y0, x1, y1 = (int(round(v)) for v in boxes[4])
    box = [x0 - 8, y0 - 8, x1 + 8, y1 + 8]  # the generator sets the new figure by the height of the box: larger than its neighbours
    edited, _ = s2_erase_retype(host, box, "8,88,888.00")
    found = [f for f in run(tmp_path / "b", edited).findings if f.detector == "scan_layout" and f.fclass == "observation"]
    print([(e.value, e.note) for f in found for e in f.evidence])
    assert any(box[0] - 4 <= e.box[0] and e.box[2] <= box[2] + 4 and box[1] - 4 <= e.box[1] and e.box[3] <= box[3] + 4
               for f in found for e in f.evidence if e.page == 1)


@ocr
@pytest.mark.parametrize("angle_seed", [1, 5])  # one turn each way
def test_page_turn_is_the_turn_the_simulation_applied(tmp_path, angle_seed):
    src = tmp_path / "scan.jpg"
    src.write_bytes(scan_of(1, angle_seed=angle_seed))
    page = load_image_page(src, "D1", tmp_path / "p.png", TH)
    assert page_turn(page.words, page.width, page.height) == pytest.approx(turn(angle_seed), abs=0.15)


# --- the layout detector on words placed by hand

def case_of(tmp_path, words, quality="good"):
    """A one-page scan case built from `words`. The image file does not exist: a detector that opened it would fail."""
    cd = CaseDir.create(tmp_path)
    page = Page(n=1, width=1600, height=2200, read_mode="ocr", quality_class=quality, image_path="never-opened.png", words=words)
    doc = Document(id="D1", sha256="0", filename="s.jpg", stored_path="s.jpg", pages=[page])
    return Case(id="C", created="2026-11-04T00:00:00+00:00", documents=[doc]), doc, Ctx(cd, AuditLog(cd.audit_path), TH)


def turned(box, deg, centre=(800.0, 1100.0)):
    """The box around `box` once the page is turned by `deg` degrees anticlockwise: what the reader gives for a word on a turned page."""
    a = math.radians(deg)
    pts = [(x - centre[0], y - centre[1]) for x in (box[0], box[2]) for y in (box[1], box[3])]
    xs = [centre[0] + dx * math.cos(a) + dy * math.sin(a) for dx, dy in pts]
    ys = [centre[1] - dx * math.sin(a) + dy * math.cos(a) for dx, dy in pts]
    return min(xs), min(ys), max(xs), max(ys)


def grid(tmp_path, tilt=0.0, move=None, grow=None, quality="good"):
    """Ten rows of six words, the sixth a figure whose right edges line up, boxed as the reader boxes a page turned by `tilt` degrees.
    move[(row, column)] = (dx, dy) shifts a word, grow[(row, column)] adds height about its centre. Returns case, document, context, boxes."""
    move, grow, boxes, words = move or {}, grow or {}, {}, []
    for r in range(10):
        for c in range(6):
            (dx, dy), extra = move.get((r, c), (0, 0)), grow.get((r, c), 0)
            width, x1 = (100.0, 1500.0) if c == 5 else (90.0 + 12 * c, 190.0 + 262 * c)
            box = (x1 - width + dx, 400.0 + 37 * r - extra / 2 + dy, x1 + dx, 434.0 + 37 * r + extra / 2 + dy)
            boxes[r, c] = turned(box, tilt)
            words.append(Word(id=f"D1-p1-w{len(words) + 1}", text="1,234.56" if c == 5 else f"item{r}{c}", box=boxes[r, c], conf=0.95))
    return (*case_of(tmp_path, words, quality), boxes)


@pytest.mark.parametrize("tilt", [0.0, 1.5, -2.5])
def test_page_turn_is_found_from_the_words(tmp_path, tilt):
    _, doc, _, _ = grid(tmp_path, tilt)
    assert page_turn(doc.pages[0].words, 1600, 2200) == pytest.approx(tilt, abs=0.1)


@pytest.mark.parametrize("tilt", [0.0, 1.5, -2.5])
def test_words_in_line_on_a_turned_page_give_no_finding(tmp_path, tilt):
    case, doc, ctx, _ = grid(tmp_path, tilt)
    assert layout_consistency(case, doc, ctx) == []


def test_a_word_off_its_row_is_named(tmp_path):
    case, doc, ctx, boxes = grid(tmp_path, tilt=1.2, move={(4, 2): (0, 12)})
    (f,) = layout_consistency(case, doc, ctx)
    (e,) = f.evidence
    assert (f.fclass, f.detector, f.family) == ("observation", "scan_layout", "visual")
    assert e.box == pytest.approx(boxes[4, 2]) and "centre" in e.note and "lower" in e.note


def test_a_figure_off_its_column_is_named(tmp_path):
    case, doc, ctx, boxes = grid(tmp_path, tilt=-1.0, move={(6, 5): (14, 0)})
    (f,) = layout_consistency(case, doc, ctx)
    (e,) = f.evidence
    assert e.box == pytest.approx(boxes[6, 5]) and "right edge" in e.note


def test_a_taller_word_is_named(tmp_path):
    case, doc, ctx, boxes = grid(tmp_path, grow={(3, 5): 14})
    (f,) = layout_consistency(case, doc, ctx)
    (e,) = f.evidence
    assert e.box == pytest.approx(boxes[3, 5]) and "height" in e.note


def test_a_degraded_page_needs_a_larger_difference(tmp_path):
    move = {(4, 2): (0, 8)}  # 8 px is above what a good page tolerates and below what a degraded one does
    assert len(layout_consistency(*grid(tmp_path / "good", move=move)[:3])) == 1
    assert layout_consistency(*grid(tmp_path / "degraded", move=move, quality="degraded")[:3]) == []


def test_a_page_with_few_words_is_not_compared_and_says_so(tmp_path):
    words = [Word(id=f"D1-p1-w{i}", text="x", box=(10.0 * i, 10.0, 10.0 * i + 8, 30.0), conf=0.9) for i in range(1, 6)]
    (f,) = layout_consistency(*case_of(tmp_path, words))
    assert f.fclass == "processing_limitation" and f.family == "limitation" and "5 words" in f.detail


def poor_case(tmp_path):
    return case_of(tmp_path, [Word(id="D1-p1-w1", text="1,00.00", box=(10.0, 10.0, 50.0, 30.0), conf=0.9)], quality="poor")


def test_poor_page_is_not_analysed_and_says_so(tmp_path):
    case, doc, ctx = poor_case(tmp_path)  # the image file does not exist: a detector that opened it would fail
    for det in (noise_residual, layout_consistency):
        (f,) = det(case, doc, ctx)
        assert f.fclass == "processing_limitation" and f.family == "limitation" and "page 1" in f.detail and "poor" in f.detail
