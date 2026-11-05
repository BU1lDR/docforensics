"""A page that stands on its side (plan review focus 1). The reader does not turn pages back, so its rows are the document's
columns and a value pairs with the wrong label: three genuine documents with one of them turned gave conflicts between them.
Such a page is read as poor and says why, whether it is a scan or a PDF page stored turned."""
import io

import pytest
from PIL import Image

from datagen.fictional import identity
from datagen.scan import simulate_scan
from docforensics.config import Thresholds
from docforensics.ingest import create_case
from docforensics.model import Word
from docforensics.pipeline import run_case
from docforensics.understand.layout import sideways
from tests.helpers import SLIP_LINES, lines_pdf
from tests.test_cross import run, trio
from tests.test_digital_detectors import rotated

TH = Thresholds()
ocr = pytest.mark.ocr


def words(n, w, h, text="abcd"):
    return [Word(id=f"w{i}", text=text, box=(0.0, 40.0 * i, float(w), 40.0 * i + h), conf=1.0) for i in range(n)]


def judged(case):
    """The findings that are not limitations of the analysis."""
    return [f"{f.detector}: {f.title}" for f in case.findings if f.fclass != "processing_limitation"]


def reasons(case):
    return [(f.evidence[0].doc, f.evidence[0].page, f.title) for f in case.findings if f.detector == "read"]


def test_a_page_of_tall_words_stands_on_its_side():
    assert sideways(words(20, 20, 60)) == (20, 20)


@pytest.mark.parametrize("page", [words(20, 60, 20), words(11, 20, 60), words(30, 20, 60, text="ab")],
                         ids=["upright", "too few words", "words too short"])
def test_other_pages_do_not(page):
    assert sideways(page) is None


@pytest.mark.parametrize("degrees", [90, 270])
def test_a_pdf_page_stored_turned_is_read_as_poor_and_says_why(tmp_path, degrees):
    case = run(tmp_path, rotated(lines_pdf(SLIP_LINES * 4), degrees))
    page = case.documents[0].pages[0]
    assert (page.read_mode, page.quality_class) == ("text-layer", "poor")
    assert reasons(case) == [("D1", 1, "Page 1 stands on its side")]
    assert "taller than wide" in case.findings[[f.detector for f in case.findings].index("read")].detail
    assert judged(case) == []


@pytest.mark.parametrize("which", [0, 1, 2])
@pytest.mark.parametrize("degrees", [90, 270])
def test_a_genuine_document_stored_turned_gives_no_conflict_with_the_others(tmp_path, which, degrees):
    pdfs = [d.pdf for d in trio(identity(1))]
    pdfs[which] = rotated(pdfs[which], degrees)
    case = run(tmp_path, *pdfs)
    assert judged(case) == []
    assert reasons(case) == [(f"D{which + 1}", 1, "Page 1 stands on its side")]


@ocr
def test_a_scan_turned_a_quarter_is_read_as_poor_and_a_genuine_case_gives_no_conflict(tmp_path):
    scans = [simulate_scan(d.pdf, "mild", 5) for d in trio(identity(1))]
    turned = io.BytesIO()
    Image.open(io.BytesIO(scans[0])).convert("RGB").rotate(-90, expand=True, fillcolor=(255, 255, 255)).save(turned, "JPEG", quality=85)
    _, cd, _ = create_case(tmp_path / "data", [("d1.jpg", turned.getvalue()), ("d2.jpg", scans[1]), ("d3.jpg", scans[2])], TH)
    case = run_case(cd, TH)
    assert [d.pages[0].quality_class for d in case.documents][0] == "poor"
    assert reasons(case) == [("D1", 1, "Page 1 stands on its side")]
    assert judged(case) == []
