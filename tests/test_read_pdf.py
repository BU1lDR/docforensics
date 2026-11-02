import numpy as np
import pymupdf
import pytest
from PIL import Image

from docforensics.config import Thresholds
from docforensics.ingest import create_case
from docforensics.model import Word
from docforensics.pipeline import run_case
from docforensics.read.pdf import layer_is_usable, pdf_meta, read_pdf_page
from tests.helpers import png_bytes

TH = Thresholds()
LINES = [
    (72, 100, "Account Statement TST-0001", 14),
    (72, 130, "01/04/2026 Salary credit 52,000.00 1,20,500.00", 10),
    (72, 150, "03/04/2026 Rent debit 18,000.00 1,02,500.00", 10),
    (300, 400, "Closing balance 1,02,500.00", 12),
]


def make_pdf(path, rotate=0, crop=None, size=(595, 842)):
    doc = pymupdf.open()
    page = doc.new_page(width=size[0], height=size[1])
    for x, y, text, fs in LINES:
        page.insert_text((x, y), text, fontname="helv", fontsize=fs)
    if crop:
        page.set_cropbox(pymupdf.Rect(*crop))
    if rotate:
        page.set_rotation(rotate)
    doc.save(path)
    doc.close()
    return path


def ink_outside_boxes(page, pad=3):
    """Share of dark pixels that no word box (padded) covers."""
    dark = np.array(Image.open(page.image_path).convert("L")) < 128
    covered = np.zeros_like(dark)
    for w in page.words:
        x0, y0, x1, y1 = w.box
        covered[max(0, int(y0) - pad):int(y1) + pad + 1, max(0, int(x0) - pad):int(x1) + pad + 1] = True
    return (dark & ~covered).sum() / max(dark.sum(), 1)


def test_word_boxes_match_render(tmp_path):
    page = read_pdf_page(make_pdf(tmp_path / "a.pdf"), 0, "D1", tmp_path / "p.png")
    assert (page.read_mode, page.quality_class, page.dpi) == ("text-layer", "text-layer", 200)
    assert {"Salary", "52,000.00", "TST-0001"} <= {w.text for w in page.words}
    assert (page.width, page.height) == Image.open(page.image_path).size
    assert page.words[0].id == "D1-p1-w1" and page.words[0].pt_box is not None
    assert ink_outside_boxes(page) <= 0.02


@pytest.mark.parametrize("rotate, crop", [(90, None), (180, None), (270, None), (90, (50, 50, 500, 500)), (0, (50, 50, 500, 500))])
def test_rotated_page_boxes_land_on_ink(tmp_path, rotate, crop):
    page = read_pdf_page(make_pdf(tmp_path / "a.pdf", rotate, crop), 0, "D1", tmp_path / "p.png")
    assert len(page.words) >= 15
    assert ink_outside_boxes(page) <= 0.02
    covered_ink = 1 - ink_outside_boxes(page, pad=0)
    assert covered_ink > 0.5  # boxes sit on the ink, not merely around it


def test_unusable_text_layer_falls_back_to_ocr(tmp_path):
    def w(text):
        return Word(id="w", text=text, box=(0, 0, 1, 1))

    bad = chr(0xFFFD)
    assert layer_is_usable([w("Salary"), w("52,000.00")])
    assert not layer_is_usable([])
    assert not layer_is_usable([w(bad * 3)])
    assert not layer_is_usable([w(chr(0xE001) * 5)])  # private-use area
    assert not layer_is_usable([w("(cid:12)(cid:7)")])
    assert layer_is_usable([w("abcdefg"), w(bad * 3)])      # 3 of 10 characters: not over 30%
    assert not layer_is_usable([w("abcdef"), w(bad * 4)])   # 4 of 10
    doc = pymupdf.open()
    doc.new_page().insert_image(pymupdf.Rect(50, 50, 300, 300), stream=png_bytes())
    doc.save(tmp_path / "img.pdf")
    page = read_pdf_page(tmp_path / "img.pdf", 0, "D1", tmp_path / "p.png")
    assert page.read_mode == "ocr" and page.words == [] and page.quality_class == "poor"


def test_invisible_text_over_an_image_counts_as_a_scan(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_image(pymupdf.Rect(50, 50, 500, 700), stream=png_bytes())
    page.insert_text((72, 100), "Searchable layer from some OCR", render_mode=3)
    doc.save(tmp_path / "scan.pdf")
    read = read_pdf_page(tmp_path / "scan.pdf", 0, "D1", tmp_path / "p.png")
    assert read.read_mode == "ocr" and read.words == []


def test_font_size_color_per_word(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Total", fontname="hebo", fontsize=14, color=(1, 0, 0))
    page.insert_text((200, 100), "plain", fontname="helv", fontsize=10)
    doc.save(tmp_path / "f.pdf")
    words = {w.text: w for w in read_pdf_page(tmp_path / "f.pdf", 0, "D1", tmp_path / "p.png").words}
    assert "Bold" in words["Total"].font and words["Total"].size == pytest.approx(14) and words["Total"].color == "#ff0000"
    assert "Bold" not in words["plain"].font and words["plain"].size == pytest.approx(10) and words["plain"].color == "#000000"


def test_huge_page_is_capped(tmp_path):
    doc = pymupdf.open()
    doc.new_page(width=3000, height=1500).insert_text((100, 200), "TST-0001 Closing balance 1,02,500.00", fontsize=40)
    doc.save(tmp_path / "huge.pdf")
    page = read_pdf_page(tmp_path / "huge.pdf", 0, "D1", tmp_path / "p.png")
    assert max(page.width, page.height) <= 6000 and page.dpi < 200
    assert (page.width, page.height) == Image.open(page.image_path).size
    assert ink_outside_boxes(page) <= 0.02


def test_pdf_meta_keys(tmp_path):
    doc = pymupdf.open()
    doc.new_page()
    doc.set_metadata({"producer": "TST Maker 1.0", "creator": "TST Writer"})
    doc.save(tmp_path / "m.pdf")
    meta = pdf_meta(tmp_path / "m.pdf")
    assert {"producer", "creator", "creationDate", "modDate", "format", "pages"} <= set(meta)
    assert meta["producer"] == "TST Maker 1.0" and meta["creator"] == "TST Writer" and meta["pages"] == "1"
    assert all(isinstance(v, str) for v in meta.values())


@pytest.mark.ocr
def test_read_stage_via_run_case(tmp_path):
    digital = make_pdf(tmp_path / "d.pdf").read_bytes()
    scan = pymupdf.open()
    scan.new_page().insert_image(pymupdf.Rect(50, 50, 300, 300), stream=png_bytes())
    case, cd, audit = create_case(tmp_path / "data", [("d.pdf", digital), ("s.pdf", scan.tobytes())], TH)
    out = run_case(cd, TH)
    d1, d2 = out.documents
    assert (d1.kind, d2.kind) == ("pdf-digital", "pdf-scanned")
    assert d1.meta["pages"] == "1" and len(d1.pages) == 1 and len(d1.pages[0].words) > 10
    assert d1.pages[0].image_path == "pages/D1-p1.png" and (cd.root / d1.pages[0].image_path).is_file()
    assert [e.data["doc"] for e in audit.events() if e.event == "doc_read"] == ["D1", "D2"]
    assert not [f for f in out.findings if f.fclass == "processing_limitation" and f.detector == "read"]
