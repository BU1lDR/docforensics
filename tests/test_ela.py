"""Compression history of a scan (scope D, package E). A JPEG that was saved at one quality and later saved again at a higher one keeps
a trace of the first save wherever the picture was not changed: saving it again at that first quality alters it far less than at its
neighbours. A piece pasted in from elsewhere does not share the trace. These tests are about that mechanism, on the scans of
datagen/ela_pack.py (payslips, three scan levels): that a pasted piece is found where it was put, that a page saved once, a page saved
again without an edit and an edit made at the page's own grid and quality are not flagged, and that a page the check cannot read is a
limitation and not a pass. How often it finds an edit is measured by the evaluation (docs/spike-e-ela.md), not here."""
import io
import re

import numpy as np
import pytest
from PIL import Image

from datagen.ela_pack import build_case, plan_cases
from docforensics.config import Thresholds
from docforensics.explain.templates import TEMPLATES
from docforensics.forensics.ela import DETECTOR, ela_regions, jpeg_history
from docforensics.ingest import create_case
from docforensics.model import Page
from docforensics.pipeline import Ctx
from tests.helpers import iou

TH = Thresholds()
PLAN = {(p["kind"], p["level"]): p for p in plan_cases("ext-dev", 36)}
VERDICT = re.compile(r"fraud|forg|fake|counterfeit", re.I)


def made(kind, level="150dpi"):
    return build_case(PLAN[kind, level])


def gray(jpeg):
    return np.asarray(Image.open(io.BytesIO(jpeg)).convert("L"))


def page_of(tmp_path, data, name):
    """A case of one picture, with the page the reader would have made of it (a PNG of its pixels), and no OCR."""
    case, cd, audit = create_case(tmp_path / "data", [(name, data)], TH)
    doc = case.documents[0]
    im = Image.open(io.BytesIO(data)).convert("RGB")
    out = cd.pages / f"{doc.id}-p1.png"
    im.save(out)
    doc.pages = [Page(n=1, width=im.width, height=im.height, image_path=out.relative_to(cd.root).as_posix(), read_mode="ocr", quality_class="good")]
    return case, doc, Ctx(cd, audit, TH)


# --- the mechanism, on pixels

@pytest.mark.parametrize("kind, level", [("pasted-field", "150dpi"), ("pasted-field", "120dpi"), ("pasted-block", "150dpi")])
def test_a_piece_pasted_off_the_grid_after_an_earlier_save_is_found_where_it_was_put(kind, level):
    scan, e = made(kind, level)
    r = ela_regions(gray(scan))
    assert (r.final, r.earlier) == (e["final_quality"], e["host_quality"])
    assert r.regions and max(iou(g.box, e["box"]) for g in r.regions) > 0.3
    assert all(iou(g.box, e["box"]) > 0 for g in r.regions)  # nothing is marked elsewhere on the page


@pytest.mark.parametrize("level", ["mild", "150dpi", "120dpi"])
def test_a_page_saved_once_has_no_earlier_save_to_compare_with_and_gives_nothing(level):
    scan, _ = made("genuine", level)
    r = ela_regions(gray(scan))
    assert r.earlier is None and r.regions == []


@pytest.mark.parametrize("level", ["mild", "150dpi", "120dpi"])
def test_a_page_saved_again_without_an_edit_gives_nothing(level):
    scan, _ = made("resaved", level)
    assert ela_regions(gray(scan)).regions == []


def test_an_edit_made_at_the_pages_own_grid_and_quality_has_the_pages_own_history_and_is_not_seen():
    scan, e = made("aligned")
    assert e["expect"] == "blind" and ela_regions(gray(scan)).regions == []


# --- the detector

def test_a_pasted_piece_is_an_observation_with_its_box_the_two_qualities_and_no_verdict(tmp_path):
    scan, e = made("pasted-field")
    case, doc, ctx = page_of(tmp_path, scan, "s.jpg")
    (f,) = jpeg_history(case, doc, ctx)
    assert (f.fclass, f.detector, f.family) == ("observation", DETECTOR, "visual")
    assert f.evidence and all(ev.doc == doc.id and ev.page == 1 for ev in f.evidence)
    assert max(iou(ev.box, e["box"]) for ev in f.evidence) > 0.3
    assert "95" in f.detail and "50" in f.detail and not VERDICT.search(f.title + f.detail)


def test_a_page_with_nothing_to_report_gives_no_finding_at_all(tmp_path):
    for kind in ("genuine", "resaved"):
        scan, _ = made(kind)
        assert jpeg_history(*page_of(tmp_path / kind, scan, "s.jpg")) == []


def test_a_lossless_picture_is_a_limitation_and_never_a_pass(tmp_path):
    scan, _ = made("pasted-field")
    png = io.BytesIO()
    Image.open(io.BytesIO(scan)).save(png, "PNG")
    (f,) = jpeg_history(*page_of(tmp_path, png.getvalue(), "s.png"))
    assert (f.fclass, f.detector) == ("processing_limitation", DETECTOR) and "JPEG" in f.detail and f.evidence[0].page == 0


def test_a_multi_picture_jpeg_is_named_as_such_and_not_called_lossless(tmp_path):
    scan, _ = made("pasted-field")
    im, mpo = Image.open(io.BytesIO(scan)), io.BytesIO()
    im.save(mpo, "MPO", save_all=True, append_images=[im.copy()])  # a camera's two-picture file: typed as a JPEG, read by Pillow as an MPO
    (f,) = jpeg_history(*page_of(tmp_path, mpo.getvalue(), "s.jpg"))
    assert f.fclass == "processing_limitation" and "MPO" in f.detail and "not a plain JPEG" in f.detail and "lossless" not in f.detail


def test_pages_that_cannot_be_examined_for_one_reason_are_one_clause_with_a_count(tmp_path):
    scan, _ = made("pasted-field")
    png = io.BytesIO()
    Image.open(io.BytesIO(scan)).save(png, "PNG")
    case, doc, ctx = page_of(tmp_path, png.getvalue(), "s.png")
    doc.pages = [doc.pages[0].model_copy(update={"n": n}) for n in range(1, 15)]  # a long scanned file of 14 pages
    (f,) = jpeg_history(case, doc, ctx)
    assert f.detail.count("PNG picture") == 1 and "page 1 is a PNG picture" in f.detail and "and 13 more pages for the same reason" in f.detail
    assert len(f.detail) < 250


def test_pages_that_cannot_be_examined_for_two_reasons_are_two_clauses(tmp_path):
    scan, _ = made("pasted-field")
    exif = Image.Exif()
    exif[274] = 3
    out = io.BytesIO()
    Image.open(io.BytesIO(scan)).save(out, "JPEG", quality=95, exif=exif)
    case, doc, ctx = page_of(tmp_path, out.getvalue(), "s.jpg")
    first = doc.pages[0]
    doc.pages = [first, first.model_copy(update={"n": 2, "width": first.width - 100}), first.model_copy(update={"n": 3})]
    (f,) = jpeg_history(case, doc, ctx)
    assert "page 1 was turned upright" in f.detail and "(and 1 more page for the same reason)" in f.detail and "page 2 was scaled" in f.detail
    assert f.detail.count("; ") == 1


def test_a_page_that_is_not_the_saved_picture_is_a_limitation(tmp_path):
    scan, _ = made("pasted-field")
    case, doc, ctx = page_of(tmp_path, scan, "s.jpg")
    doc.pages[0] = doc.pages[0].model_copy(update={"width": doc.pages[0].width - 100})  # the reader scaled it
    (f,) = jpeg_history(case, doc, ctx)
    assert f.fclass == "processing_limitation" and "scaled" in f.detail


def test_a_page_the_reader_turned_upright_by_the_pictures_own_note_is_a_limitation(tmp_path):
    scan, _ = made("pasted-field")
    exif = Image.Exif()
    exif[274] = 3  # upside down: the same size, so only the note tells
    out = io.BytesIO()
    Image.open(io.BytesIO(scan)).save(out, "JPEG", quality=95, exif=exif)
    (f,) = jpeg_history(*page_of(tmp_path, out.getvalue(), "s.jpg"))
    assert f.fclass == "processing_limitation" and "turned upright" in f.detail


def test_the_findings_have_their_own_explanation_which_names_the_ordinary_causes():
    for fclass in ("observation", "processing_limitation"):
        text, steps = TEMPLATES[DETECTOR, fclass]
        assert text != TEMPLATES["*", fclass][0] and steps and not VERDICT.search(text + " ".join(steps))
    assert "ordinary causes" in TEMPLATES[DETECTOR, "observation"][0]


def test_pages_that_were_read_from_the_text_layer_are_left_alone(tmp_path):
    scan, _ = made("pasted-field")
    case, doc, ctx = page_of(tmp_path, scan, "s.jpg")
    doc.pages[0] = doc.pages[0].model_copy(update={"read_mode": "text-layer"})
    assert jpeg_history(case, doc, ctx) == []
