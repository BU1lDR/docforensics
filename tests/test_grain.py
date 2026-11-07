"""The no-grain gate. Three scan checks compare a word with the rest of its page (scan_noise, scan_layout, learned_patches); they were
built and measured on scans that carry scanner grain. A page without any, such as a render or a screenshot saved as an image, is not
given to them, and its document says so instead of passing. The limit comes from the project's simulated scans against noise-free
renders; no real scanner was measured (docs/limitations.md). How often an edit is found is measured by the evaluation, not here."""
import re
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from docforensics.config import Thresholds
from docforensics.explain.templates import TEMPLATES
from docforensics.forensics import SCAN_DETECTORS
from docforensics.forensics import learned_patches as lp
from docforensics.forensics.grain import grain_gate, lacks_grain
from docforensics.forensics.scan_layout import layout_consistency
from docforensics.forensics.scan_noise import noise_residual
from docforensics.model import Case, Document, Page
from tests.test_learned_patches import made_up_weights, scanned, three_a_line
from tests.test_scan_detectors import grid

SMOOTH, SCANNED = 0.0, 3.5  # the spread of the grain on the paper: a render has none, the project's simulated scans about this much
VERDICT = re.compile(r"fraud|forg|fake|counterfeit", re.I)


def save(path, sigma, size=(2200, 1600), flat=()):
    """A page picture: paper at 245 with grain of spread `sigma`; the boxes of `flat` get hardly any."""
    rng = np.random.default_rng(1)
    pix = np.full(size, 245.0) + (rng.normal(0, sigma, size) if sigma else 0)
    for x0, y0, x1, y1 in flat:
        pix[int(y0):int(y1), int(x0):int(x1)] = 245.0 + rng.normal(0, 0.8, (int(y1) - int(y0), int(x1) - int(x0)))
    Image.fromarray(np.clip(pix, 0, 255).astype(np.uint8)).save(path)


def given(made, sigma, flat=()):
    """(case, document, context) of `made` (the first three of what the builders return), with a picture of that grain written for its page."""
    case, doc, ctx = made[:3]
    save(ctx.cd.root / doc.pages[0].image_path, sigma, flat=flat)
    return case, doc, ctx


def pages_of(tmp_path, *kinds):
    """A document whose pages are (grain, read mode, quality class); the context has what the gate needs."""
    pages = []
    for n, (sigma, mode, quality) in enumerate(kinds, 1):
        save(tmp_path / f"p{n}.png", sigma, (1100, 800))
        pages.append(Page(n=n, width=800, height=1100, image_path=f"p{n}.png", read_mode=mode, quality_class=quality))
    doc = Document(id="D1", sha256="0" * 64, filename="s.png", stored_path="s.png", kind="image", pages=pages)
    return Case(id="C", created="2026-11-07T00:00:00Z", documents=[doc]), doc, SimpleNamespace(cd=SimpleNamespace(root=tmp_path), th=Thresholds())


# --- the measure

@pytest.mark.parametrize("sigma, size, gated", [(SMOOTH, (2200, 1600), True), (SCANNED, (2200, 1600), False), (SMOOTH, (100, 100), False)])
def test_a_page_without_scanner_grain_is_told_from_one_with_it_and_a_page_with_little_paper_is_not_judged(tmp_path, sigma, size, gated):
    case, doc, ctx = pages_of(tmp_path, (sigma, "ocr", "good"))
    save(tmp_path / "p1.png", sigma, size)
    assert lacks_grain(ctx, doc.pages[0]) is gated


def test_a_picture_that_cannot_be_opened_is_not_judged(tmp_path):
    page = Page(n=1, width=10, height=10, image_path="missing.png", read_mode="ocr", quality_class="good")
    assert lacks_grain(SimpleNamespace(cd=SimpleNamespace(root=tmp_path)), page) is False


# --- the limitation

def test_the_gate_names_the_pages_it_left_out_in_one_limitation_per_document(tmp_path):
    case, doc, ctx = pages_of(tmp_path, (SMOOTH, "ocr", "good"), (SCANNED, "ocr", "good"), (SMOOTH, "ocr", "good"),
                              (SMOOTH, "ocr", "poor"), (SMOOTH, "text-layer", "text-layer"))
    (f,) = grain_gate(case, doc, ctx)
    assert (f.fclass, f.family, f.detector) == ("processing_limitation", "limitation", "scan_grain")
    assert "page 1" in f.detail and "page 3" in f.detail and "no scanner grain" in f.detail
    assert "grain share" in f.detail and "below 0.5" in f.detail  # the figure comes with what it is and where the line lies
    assert not any(f"page {n}" in f.detail for n in (2, 4, 5)) and not VERDICT.search(f.title + f.detail)  # the poor page has its own limitation


def test_a_document_whose_pages_all_carry_grain_gets_no_limitation(tmp_path):
    assert grain_gate(*pages_of(tmp_path, (SCANNED, "ocr", "good"), (SCANNED, "ocr", "degraded"))) == []


# --- the three checks

def test_layout_leaves_a_page_without_grain_alone_and_still_reads_one_with_it(tmp_path):
    move = {(4, 2): (0, 12)}  # a word 12 px off its row: what test_scan_detectors names on a page of any picture
    assert layout_consistency(*given(grid(tmp_path / "smooth", move=move), SMOOTH)) == []
    assert [f.fclass for f in layout_consistency(*given(grid(tmp_path / "scanned", move=move), SCANNED))] == ["observation"]


def test_noise_leaves_a_page_without_grain_alone_and_still_reads_one_with_it(tmp_path):
    made = grid(tmp_path / "scanned")
    x0, y0, x1, y1 = made[3][4, 2]
    patch = [(x0 - 8, y0 - 8, x1 + 8, y1 + 8)]  # one word lies in paper that has no grain: the others carry it
    (f,) = noise_residual(*given(made, SCANNED, flat=patch))
    assert (f.fclass, f.detector) == ("observation", "scan_noise") and "less" in f.detail
    assert noise_residual(*given(grid(tmp_path / "smooth"), SMOOTH)) == []  # without the gate: "no measurable grain", a limitation of its own


def test_learned_patches_leaves_a_page_without_grain_alone_and_still_reads_one_with_it(tmp_path, monkeypatch):
    monkeypatch.setattr(lp, "_weights", lambda: made_up_weights(line_mates=20.0))
    for name in ("scanned", "smooth"):
        (tmp_path / name).mkdir()
    case, doc, ctx = scanned(tmp_path / "scanned", three_a_line(off=8.0))
    assert [f.fclass for f in lp.learned_patches(case, doc, ctx)] == ["observation"]
    case, doc, ctx = scanned(tmp_path / "smooth", three_a_line(off=8.0))
    save(tmp_path / "smooth" / "p1.png", SMOOTH, (2339, 1654))
    assert lp.learned_patches(case, doc, ctx) == []


# --- registered, with wording

def test_the_gate_is_one_of_the_scan_checks_and_has_wording_for_what_it_reports():
    assert grain_gate in SCAN_DETECTORS and ("scan_grain", "processing_limitation") in TEMPLATES
