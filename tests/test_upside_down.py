"""A page that stands upside down (a scan or a PDF page turned half a turn). The reader does not turn pages back, and the words of such a
page come in the wrong order along each row, so a value pairs with the wrong label or none: a statement stored turned half a turn gave a
false account-number conflict with the other documents (limitation 36). The OCR engine's own angle test finds a scan that stands
upside down, the text layer's writing direction finds a PDF page, and the page is then read as poor and says why, as a page on its
side is (tests/test_sideways.py)."""
import io

import numpy as np
import pymupdf
import pytest
from PIL import Image

from datagen.fictional import identity
from datagen.scan import simulate_scan
from docforensics.config import Thresholds
from docforensics.ingest import create_case
from docforensics.pipeline import run_case
from docforensics.read.ocr import Ocr
from docforensics.understand.layout import upside_down
from tests.helpers import SLIP_LINES, lines_pdf
from tests.test_cross import run, trio
from tests.test_digital_detectors import rotated
from tests.test_sideways import judged, reasons

TH = Thresholds()
ocr = pytest.mark.ocr
TITLE = "Page 1 stands upside down"


def test_most_items_upside_down_mean_the_page_stands_upside_down():
    assert upside_down(20, 24) == (20, 24)


@pytest.mark.parametrize("turned, counted", [(2, 24), (12, 24), (11, 11), (0, 0)],
                         ids=["a few short lines", "half is not most", "too few to tell", "nothing read"])
def test_other_pages_do_not(turned, counted):
    assert upside_down(turned, counted) is None


def test_a_pdf_page_stored_upside_down_is_read_as_poor_and_says_why(tmp_path):
    case = run(tmp_path, rotated(lines_pdf(SLIP_LINES * 4), 180))
    page = case.documents[0].pages[0]
    assert (page.read_mode, page.quality_class) == ("text-layer", "poor")
    assert reasons(case) == [("D1", 1, TITLE)]
    assert "run right to left" in case.findings[[f.detector for f in case.findings].index("read")].detail
    assert judged(case) == []


def test_an_upright_pdf_page_is_not(tmp_path):
    case = run(tmp_path, lines_pdf(SLIP_LINES * 4))
    assert case.documents[0].pages[0].upside_down is None
    assert reasons(case) == []


def test_a_pdf_page_drawn_upside_down_is_found_without_a_page_rotation(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    for x, y, text, fs in SLIP_LINES * 4:  # each line drawn from its right end, turned half a turn, at the mirrored place
        page.insert_text((595 - x, 842 - y), text, fontname="helv", fontsize=fs, rotate=180)
    case = run(tmp_path, doc.tobytes())
    assert reasons(case) == [("D1", 1, TITLE)]


@pytest.mark.parametrize("which", [0, 1, 2])
def test_a_genuine_document_stored_upside_down_gives_no_conflict_with_the_others(tmp_path, which):
    pdfs = [d.pdf for d in trio(identity(1))]
    pdfs[which] = rotated(pdfs[which], 180)
    case = run(tmp_path, *pdfs)
    assert judged(case) == []
    assert reasons(case) == [(f"D{which + 1}", 1, TITLE)]


@ocr
def test_a_scan_turned_half_a_turn_is_read_as_poor_and_a_genuine_case_gives_no_conflict(tmp_path):
    scans = [simulate_scan(d.pdf, "mild", 5) for d in trio(identity(1))]
    turned = io.BytesIO()
    Image.open(io.BytesIO(scans[0])).convert("RGB").rotate(180, fillcolor=(255, 255, 255)).save(turned, "JPEG", quality=85)
    _, cd, _ = create_case(tmp_path / "data", [("d1.jpg", turned.getvalue()), ("d2.jpg", scans[1]), ("d3.jpg", scans[2])], TH)
    case = run_case(cd, TH)
    assert case.documents[0].pages[0].quality_class == "poor"
    assert case.documents[0].pages[0].upside_down is not None
    assert [d.pages[0].upside_down for d in case.documents[1:]] == [None, None]
    assert reasons(case) == [("D1", 1, TITLE)]
    assert judged(case) == []


@ocr
def test_the_engine_reports_how_many_of_its_lines_it_turned():
    pdf = pymupdf.open(stream=lines_pdf(SLIP_LINES * 4), filetype="pdf")
    pix = pdf[0].get_pixmap(dpi=200, alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    engine = Ocr.shared()
    engine.read(np.asarray(img), "d", 1)
    upright = engine.turned
    engine.read(np.asarray(img.rotate(180, fillcolor=(255, 255, 255))), "d", 1)
    assert upright[0] == 0 and upright[1] > 0
    assert engine.turned[0] > engine.turned[1] // 2
    assert all(type(n) is int for n in (*upright, *engine.turned))  # plain numbers: they go into a log line and a JSON file
