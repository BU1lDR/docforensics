"""The measurements and the detector of the learned patch detector (Task 29). These tests are about mechanisms: that each measurement sees what it is
named for on a picture built to show it, and that the features of a page are the same twice. How often the trained detector finds an
edit is measured by evaluation/train_patches.py and written to eval/patches/, not here."""
import io

import numpy as np
import pytest
from PIL import Image

from docforensics.forensics import learned_patches as lp


def jpeg_grid_picture(size=(96, 160), seed=0, quality=30):
    """A smooth, slightly noisy picture saved as a JPEG and read back: its 8 x 8 blocks lie on the picture's own grid."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:size[0], 0:size[1]]
    base = 200 + 20 * np.sin(xx / 17.0) + 15 * np.cos(yy / 11.0) + rng.normal(0, 4, size)
    out = io.BytesIO()
    Image.fromarray(np.clip(base, 0, 255).astype(np.uint8)).save(out, "JPEG", quality=quality)
    return np.asarray(Image.open(io.BytesIO(out.getvalue())).convert("L"), dtype=np.float32)


def test_grid_excess_is_on_the_global_grid_for_a_picture_saved_once_and_elsewhere_for_a_shifted_one():
    img = jpeg_grid_picture()
    paper = np.ones(img.shape, bool)
    on, other = lp._grid_excess(img, paper, (8, 8, 152, 88))
    assert on > 0.15 and on > 2 * other  # the blocks stand where the picture's grid says
    shifted = jpeg_grid_picture()[5:, 3:]  # the same blocks, 3 px left and 5 px up of the grid that a crop's coordinates have
    on_s, other_s = lp._grid_excess(shifted, np.ones(shifted.shape, bool), (8, 8, 145, 83))
    assert other_s > 0.15 and other_s > 2 * on_s


def test_shear_slope_finds_the_slope_of_a_line_of_bars():
    h, w, slope = 40, 120, 0.03
    ink = np.zeros((h, w), np.float32)
    for x in range(w):
        for top in (8, 26):
            y = int(round(top + slope * (x - w / 2)))
            ink[y:y + 4, x] = 1.0
    assert abs(lp._shear_slope(ink) - slope) < 0.005
    assert abs(lp._shear_slope(ink[:, ::-1].copy()) + slope) < 0.005  # mirrored, the slope changes its sign
    assert abs(lp._shear_slope(np.zeros((h, w), np.float32))) < 1e-9  # no ink: no slope, not an arbitrary one


def page_of(rows):
    """A scanned-looking page of words; each row is (text, x0, y0, x1, y1)."""
    from docforensics.model import Page, Word
    words = [Word(id=f"w{i}", text=t, box=(x0, y0, x1, y1)) for i, (t, x0, y0, x1, y1) in enumerate(rows)]
    return Page(n=1, width=1654, height=2339, read_mode="ocr", quality_class="good", words=words)


def label_value_page(lines=8, off_line=None, drop=0.0, descender=None):
    """`lines` rows, each a label and a value of the same height on one line; the value of row `off_line` sits `drop` px lower, and the label
    of row `descender` has a box 6 px taller at the bottom (a letter that hangs below the line) with the same top."""
    rows = []
    for r in range(lines):
        y = 300 + 60 * r
        rows.append(("Label", 100, y, 260, y + 30 + (6 if r == descender else 0)))
        rows.append(("1,000.00", 400, y + (drop if r == off_line else 0), 560, y + 30 + (drop if r == off_line else 0)))
    return page_of(rows)


def test_a_word_that_sits_off_the_line_of_its_neighbour_is_named_by_it_and_a_hanging_letter_is_not():
    page = label_value_page(off_line=4, drop=8.0, descender=2)
    pair, mates = lp._line_offsets(page)
    value4, label4 = 2 * 4 + 1, 2 * 4
    assert abs(pair[value4] - 8.0) < 0.5 and abs(pair[label4] - 8.0) < 0.5  # a pair is off by the same amount from both sides
    assert np.nanmax(np.delete(pair, [label4, value4])) < 0.5               # the other rows are straight, the hanging letter included
    assert np.isnan(mates).all()                                            # two words on a line: no median of the others to compare with


def test_with_three_words_on_a_line_the_odd_one_out_is_the_one_far_from_the_median_of_the_others():
    rows = [(t, x, 300 + 60 * r + (6 if (r, t) == (3, "b") else 0), x + 100, 330 + 60 * r + (6 if (r, t) == (3, "b") else 0))
            for r in range(6) for t, x in (("a", 100), ("b", 300), ("c", 500))]
    pair, mates = lp._line_offsets(page_of(rows))
    b3 = 3 * 3 + 1
    assert abs(mates[b3] - 6.0) < 0.5 and np.delete(mates, [b3 - 1, b3, b3 + 1]).max() < 0.5
    assert abs(mates[b3 - 1] - 3.0) < 0.5 and abs(mates[b3 + 1] - 3.0) < 0.5  # its mates are half-way off the median of {themselves-and-the-other, b}


def test_a_page_turned_by_a_degree_is_straightened_before_the_lines_are_compared():
    import math
    t = math.radians(1.2)
    rows = []
    for r in range(8):
        for x in (100, 400):
            y = 300 + 60 * r + math.sin(t) * (x - 827)  # every row slopes the same, as on a turned scan
            rows.append(("w", x, y, x + 150, y + 30))
    pair, _ = lp._line_offsets(page_of(rows))
    assert np.nanmax(pair) < 1.0


# --- the detector, with weights made up for the test (the learned ones are tested by the evaluation, not here)

def made_up_weights(threshold=4.0, **beta):
    """Weights that look at the named measures only: standardisation does nothing, each named measure counts `beta` times."""
    n = len(lp.FEATURES)
    return {"features": list(lp.FEATURES), "mean": [0.0] * n, "scale": [1.0] * n, "clip": 8.0, "threshold": threshold, "listed": 8,
            "beta": [beta.get(f, 0.0) for f in lp.FEATURES] + [0.0]}


def scanned(tmp_path, rows, quality="good", mode="ocr"):
    """(case, doc, ctx) for a document of one page: a grey picture with a little grain, and the words of `rows` (text, box)."""
    from types import SimpleNamespace
    from PIL import Image
    from docforensics.config import Thresholds
    from docforensics.model import Case, Document, Page, Word
    from docforensics.pipeline import Ctx
    rng = np.random.default_rng(1)
    Image.fromarray(np.clip(rng.normal(200, 3, (2339, 1654)), 0, 255).astype(np.uint8)).save(tmp_path / "p1.png")
    page = Page(n=1, width=1654, height=2339, image_path="p1.png", read_mode=mode, quality_class=quality,
                words=[Word(id=f"w{i}", text=t, box=b) for i, (t, b) in enumerate(rows)])
    doc = Document(id="D1", sha256="0" * 64, filename="s.jpg", stored_path="s.jpg", kind="image", pages=[page])
    return Case(id="C", created="2026-11-07T00:00:00Z", documents=[doc]), doc, Ctx(SimpleNamespace(root=tmp_path), None, Thresholds())


def three_a_line(off=0.0):
    """Six lines of three words; the middle word of the fourth line sits `off` px lower than the others on its line."""
    return [("abc", (x, 300.0 + 60 * r + (off if (r, x) == (3, 400) else 0.0), x + 150.0, 330.0 + 60 * r + (off if (r, x) == (3, 400) else 0.0)))
            for r in range(6) for x in (100.0, 400.0, 700.0)]


def test_a_word_far_off_its_line_is_named_when_its_score_reaches_the_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(lp, "_weights", lambda: made_up_weights(line_mates=20.0))
    case, doc, ctx = scanned(tmp_path, three_a_line(off=8.0))
    found = lp.learned_patches(case, doc, ctx)
    assert [(f.fclass, f.detector, f.family) for f in found] == [("observation", "learned_patches", "visual")]
    ev = found[0].evidence
    assert [e.box for e in ev] == [doc.pages[0].words[3 * 3 + 1].box] and ev[0].page == 1 and ev[0].doc == "D1"
    assert "4" in found[0].detail and "limit" in found[0].detail  # the limit that was reached is in the text


def test_a_straight_page_gets_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(lp, "_weights", lambda: made_up_weights(line_mates=20.0))
    assert lp.learned_patches(*scanned(tmp_path, three_a_line(off=0.0))) == []


def test_the_text_of_a_finding_names_no_verdict_and_shows_no_percentage(tmp_path, monkeypatch):
    monkeypatch.setattr(lp, "_weights", lambda: made_up_weights(line_mates=20.0))
    f = lp.learned_patches(*scanned(tmp_path, three_a_line(off=8.0)))[0]
    text = " ".join([f.title, f.detail, *(e.note for e in f.evidence)]).lower()
    assert not any(w in text for w in ("forg", "fake", "tamper", "counterfeit", "fraud", "%"))


def test_a_poor_page_is_not_measured_and_says_so_and_a_text_layer_page_is_left_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(lp, "_weights", lambda: made_up_weights(line_mates=20.0))
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    poor = lp.learned_patches(*scanned(tmp_path / "a", three_a_line(off=8.0), quality="poor"))
    assert [f.fclass for f in poor] == ["processing_limitation"] and "poor" in poor[0].detail
    assert lp.learned_patches(*scanned(tmp_path / "b", three_a_line(off=8.0), quality="text-layer", mode="text-layer")) == []


def test_weights_made_for_another_feature_list_are_refused(tmp_path, monkeypatch):
    w = made_up_weights(line_mates=20.0)
    w["features"] = w["features"][:-1]
    monkeypatch.setattr(lp, "_weights", lambda: w)
    with pytest.raises(ValueError, match="feature"):
        lp.learned_patches(*scanned(tmp_path, three_a_line(off=8.0)))


# --- registered, with the weights that the evaluation made (eval/patches/acceptance.md); the rate of finding is measured there, not here

def test_the_detector_is_one_of_the_scan_checks_and_has_wording_for_what_it_reports():
    from docforensics.explain.templates import TEMPLATES
    from docforensics.forensics import SCAN_DETECTORS
    assert lp.learned_patches in SCAN_DETECTORS
    assert ("learned_patches", "observation") in TEMPLATES and ("learned_patches", "processing_limitation") in TEMPLATES


def test_the_shipped_weights_are_for_this_feature_list_and_were_trained_on_development_data_only():
    import json
    w = json.loads(lp.WEIGHTS.read_text(encoding="utf-8"))
    assert w["features"] == list(lp.FEATURES) and len(w["beta"]) == len(lp.FEATURES) + 1
    assert len(w["mean"]) == len(w["scale"]) == len(lp.FEATURES) and np.isfinite(w["threshold"]) and w["listed"] >= 1
    assert w["training"]["slices"] == ["dev-design", "xdev-design"] and len(w["training"]["edit_labels_sha256"]) == 64


def a_splice_from_a_scan_turned_otherwise(tmp_path):
    """The statement of seed 1 with three rows of its table taken from the scan of seed 2, which was turned the other way."""
    from datagen.manipulate import s1_splice
    from tests.test_scan_detectors import amount_boxes, scan_of
    host, donor = scan_of(1), scan_of(2, angle_seed=2)
    (tmp_path / "a").mkdir()
    boxes, (w, _) = amount_boxes(tmp_path / "a", host)
    box = [60, int(boxes[3][1]) - 4, w - 60, int(boxes[5][3]) + 4]
    return s1_splice(host, donor, box)[0], box


@pytest.mark.ocr
def test_a_splice_from_a_scan_turned_otherwise_is_named_through_the_stage(tmp_path):
    from tests.test_scan_detectors import run
    edited, box = a_splice_from_a_scan_turned_otherwise(tmp_path)
    found = [f for f in run(tmp_path / "b", edited).findings if f.detector == "learned_patches" and f.fclass == "observation"]
    print([(e.value, e.note) for f in found for e in f.evidence])
    assert found and all(f.id and f.family == "visual" for f in found)
    assert any(box[1] <= e.box[1] and e.box[3] <= box[3] for f in found for e in f.evidence if e.page == 1)


@pytest.mark.ocr
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_genuine_scans_get_no_observation_from_it(tmp_path, seed):
    from tests.test_scan_detectors import run, scan_of
    case = run(tmp_path, scan_of(seed, angle_seed=seed))
    assert [(f.detector, f.title) for f in case.findings if f.detector == "learned_patches" and f.fclass == "observation"] == []
