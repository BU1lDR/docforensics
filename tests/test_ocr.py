"""OCR reader tests. Pages are rendered from known text, so recall is measured against what was drawn."""
import io
import statistics

import numpy as np
import pymupdf
import pytest
from PIL import Image

from docforensics.config import Thresholds
from docforensics.ingest import create_case
from docforensics.pipeline import run_case
from docforensics.read.ocr import Ocr, load_image_page, split_line_box
from docforensics.read.pdf import read_pdf_page
from tests.helpers import SLIP_LINES, STATEMENT_LINES, iou, lines_pdf, pdf_bytes, png_bytes, recall, render_lines, within_only

TH = Thresholds()
ocr = pytest.mark.ocr


def as_array(img):
    return np.asarray(img.convert("RGB"))


def scan_pdf(pages=1):
    buf = io.BytesIO()
    render_lines(STATEMENT_LINES).save(buf, "PNG")
    doc = pymupdf.open()
    for _ in range(pages):
        doc.new_page().insert_image(pymupdf.Rect(0, 0, 595, 842), stream=buf.getvalue())
    return doc.tobytes(deflate=True)  # without it the image is stored raw and the file passes the 10 MB limit


def test_split_line_box_by_characters():
    words = split_line_box("ab cdef", (0, 10, 70, 30), "D1", 2, 0.9)
    assert [w.id for w in words] == ["D1-p2-w1", "D1-p2-w2"]
    assert [w.text for w in words] == ["ab", "cdef"]
    assert words[0].box == pytest.approx((0, 10, 20, 30)) and words[1].box == pytest.approx((30, 10, 70, 30))
    assert {w.conf for w in words} == {0.9}
    assert split_line_box("  ", (0, 0, 10, 10), "D1", 1, 1.0) == []


def test_the_count_of_turned_lines_is_the_engines_own_and_a_changed_engine_costs_the_count_not_the_reading():
    """The count reaches into the engine's angle test. A result in another shape than the pinned version's must leave the reading as it
    is and the count at (0, 0), which says nothing about the page."""
    from types import SimpleNamespace
    ocr = object.__new__(Ocr)
    ocr._engine = SimpleNamespace(text_cls=SimpleNamespace(cls_thresh=0.9))
    known = ("imgs", SimpleNamespace(cls_res=[("180", 0.95), ("180", 0.5), ("0", 0.99)]))
    assert ocr._count_turned(known) is known and ocr.turned == (1, 3)  # only a half turn the engine was sure of
    for odd in ("not a tuple", ("imgs", object()), ("imgs", SimpleNamespace(cls_res=[("180",)]))):
        assert ocr._count_turned(odd) is odd and ocr.turned == (0, 0)


@ocr
def test_ocr_reads_clean_render():
    words = Ocr.shared().read(as_array(render_lines(STATEMENT_LINES)), "D1", 1)
    print("recall", round(recall(words, STATEMENT_LINES), 3), "of", len(words), "words")
    assert recall(words, STATEMENT_LINES) >= 0.98
    assert words[0].id == "D1-p1-w1" and [w.id for w in words] == [f"D1-p1-w{k}" for k in range(1, len(words) + 1)]
    assert all(w.text and w.text == w.text.strip() for w in words)
    assert all(0 <= w.box[0] < w.box[2] and 0 <= w.box[1] < w.box[3] and 0 < w.conf <= 1 for w in words)


@ocr
def test_ocr_boxes_match_the_text_layer_boxes(tmp_path):
    """Evidence mapping needs OCR boxes and text-layer boxes in the same pixel frame."""
    pdf = tmp_path / "s.pdf"
    pdf.write_bytes(lines_pdf(STATEMENT_LINES))
    truth = read_pdf_page(pdf, 0, "D1", tmp_path / "p.png").words
    once = {w.text: w for w in truth if sum(t.text == w.text for t in truth) == 1}
    got = Ocr.shared().read(as_array(Image.open(tmp_path / "p.png")), "D1", 1)
    scores = [iou(w.box, once[w.text].box) for w in got if w.text in once]
    print("IoU over", len(scores), "words: median", round(statistics.median(scores), 3), "min", round(min(scores), 3))
    assert len(scores) >= 25 and statistics.median(scores) >= 0.6 and min(scores) >= 0.4


@ocr
def test_two_consecutive_reads_both_work():
    engine = Ocr.shared()
    first = engine.read(as_array(render_lines(STATEMENT_LINES)), "D1", 1)
    # a recogniser-only call, like the spike's re-read, leaves its flags in the engine unless every read sets its own
    engine._engine(np.full((40, 120, 3), 255, np.uint8), use_det=False, use_cls=False, use_rec=True)
    second = engine.read(as_array(render_lines(SLIP_LINES)), "D2", 1)
    assert recall(first, STATEMENT_LINES) >= 0.9 and recall(second, SLIP_LINES) >= 0.9
    assert second[0].id == "D2-p1-w1"


@ocr
def test_exif_rotated_photo_is_read_upright(tmp_path):
    exif = Image.Exif()
    exif[0x0112] = 6  # Orientation: rotate 90 clockwise to display
    src = tmp_path / "photo.jpg"
    render_lines(STATEMENT_LINES).transpose(Image.Transpose.ROTATE_90).save(src, "JPEG", exif=exif, quality=95)
    page = load_image_page(src, "D1", tmp_path / "p.png", TH)
    assert recall(page.words, STATEMENT_LINES) >= 0.9
    assert page.width < page.height and (page.width, page.height) == Image.open(tmp_path / "p.png").size
    assert (page.n, page.read_mode) == (1, "ocr") and page.sharpness is not None and page.image_path == (tmp_path / "p.png").as_posix()


@ocr
def test_long_side_is_capped_and_a_blank_page_reads_nothing(tmp_path):
    src = tmp_path / "big.png"
    Image.new("RGB", (3600, 1800), "white").save(src)
    page = load_image_page(src, "D1", tmp_path / "p.png", TH)
    assert (page.width, page.height) == (2400, 1200) == Image.open(tmp_path / "p.png").size
    assert page.words == [] and page.quality_class == "poor"


@ocr
def test_transparent_png_keeps_its_text(tmp_path):
    src = tmp_path / "t.png"
    clear = Image.new("RGBA", (50, 50), (0, 0, 0, 0))
    clear.putpixel((10, 10), (0, 0, 0, 255))
    clear.save(src)
    load_image_page(src, "D1", tmp_path / "p.png", TH)
    saved = np.asarray(Image.open(tmp_path / "p.png").convert("L"))
    assert saved[0, 0] == 255 and saved[10, 10] == 0, "transparent pixels become white, not black"


@pytest.mark.filterwarnings("ignore::PIL.Image.DecompressionBombWarning")  # Pillow's own warning between one and two times the limit
@pytest.mark.parametrize("limit", [100, 300])  # 20x20 = 400 px: over twice the limit, then between one and two times
def test_image_bomb_gives_limitation_not_crash(tmp_path, monkeypatch, limit):
    case, cd, audit = create_case(tmp_path / "data", [("scan.png", png_bytes())], TH)
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", limit)
    out = within_only(run_case(cd, TH))  # the notice that one document cannot be compared with another is not what this is about
    lims = [f for f in out.findings if f.fclass == "processing_limitation"]
    assert out.documents[0].pages == [] and len(lims) == 1 and lims[0].evidence[0].doc == "D1"
    assert "DecompressionBombError" in lims[0].detail


@ocr
def test_scanned_pdf_pages_get_ocr_and_class(tmp_path):
    case, cd, audit = create_case(tmp_path / "data", [("d.pdf", pdf_bytes(text="TST")), ("scan.pdf", scan_pdf(2))], TH)
    out = run_case(cd, TH)
    digital, scan = out.documents
    assert digital.pages[0].quality_class == "text-layer" and digital.pages[0].sharpness is None
    assert scan.kind == "pdf-scanned" and len(scan.pages) == 2
    for p in scan.pages:
        print("scanned page", p.n, "sharpness", round(p.sharpness, 3), "recall", round(recall(p.words, STATEMENT_LINES), 3))
        assert p.read_mode == "ocr" and p.quality_class == "good" and p.sharpness is not None
        assert recall(p.words, STATEMENT_LINES) >= 0.9 and p.image_path == f"pages/D2-p{p.n}.png"
    assert scan.pages[1].words[0].id == "D2-p2-w1"
    events = audit.events()
    names = [e.event for e in events]
    assert names.count("ocr_models") == 1 and names.index("ocr_models") < names.index("doc_read", names.index("doc_read") + 1)
    models = events[names.index("ocr_models")].data["models"]
    assert len(models) == 3 and all(len(v) == 64 for v in models.values())
    assert not [f for f in out.findings if f.fclass == "processing_limitation" and f.detector == "read"]


def test_digital_only_case_never_starts_the_engine(tmp_path):
    case, cd, audit = create_case(tmp_path / "data", [("d.pdf", pdf_bytes())], TH)
    run_case(cd, TH)
    assert "ocr_models" not in [e.event for e in audit.events()]
