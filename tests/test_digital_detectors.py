"""Digital detectors for D2 to D5 (design 7.5, 8) and the manipulations they are measured against. Each manipulated file is
made from a drawn one, goes through the reader and the forensic stage, and the finding must point at the place the
manipulation record says. Genuine files must raise none of them."""
import re

import pymupdf
import pytest

from datagen.fictional import identity
from datagen.layouts import money
from datagen.layouts.application import draw_application
from datagen.layouts.payslip import draw_payslip
from datagen.layouts.statement import draw_statement
from datagen.manipulate import ARIAL, Manipulation, d1_incremental_edit, d2_cover_retype, d3_near_font_retype, d4_metadata_edit, d5_paste_image
from docforensics.config import Thresholds
from docforensics.forensics import run_forensics
from docforensics.ingest import create_case
from docforensics.pipeline import run_case
from docforensics.read import read_stage
from tests.helpers import STATEMENT_LINES, iou, lines_pdf

TH = Thresholds()
SALARY = lines_pdf(STATEMENT_LINES)
DRAWERS = {"statement": lambda i, s: draw_statement(i, rows=12, seed=s), "long statement": lambda i, s: draw_statement(i, rows=40, seed=s),
           "payslip": lambda i, s: draw_payslip(i, seed=s), "application": lambda i, s: draw_application(i, seed=s)}
NEEDS_ARIAL = pytest.mark.skipif(not all(p.is_file() for p in ARIAL.values()), reason="D3 is written in Arial from the Windows fonts folder")
INTENT = ("tamper", "manipulat", "forg", "fraud", "fake", "malicious", "intent", "suspici")


def run(tmp_path, *pdfs, th=TH):
    """Read the documents and run the forensic detectors, nothing else."""
    _, cd, _ = create_case(tmp_path / "data", [(f"d{i}.pdf", p) for i, p in enumerate(pdfs, 1)], th)
    return run_case(cd, th, stages={"read": read_stage, "forensics": run_forensics})


def statement():
    """A drawn statement, and the display text of one balance on it (it stands once on the page)."""
    drawn = draw_statement(identity(1), rows=12, seed=1)
    return drawn.pdf, money(drawn.truth["rows"][2]["balance"])


def by(case, detector):
    return [f for f in case.findings if f.detector == detector]


# --- D2: covered and retyped in the same font

def test_d2_cover_and_retype_found(tmp_path):
    edited, m = d2_cover_retype(SALARY, "52,000.00", "82,000.00")
    assert isinstance(m, Manipulation) and (m.method, m.page) == ("D2", 1) and len(m.box) == 4
    case = run(tmp_path, edited)
    (f,) = case.findings  # the file is one revision, in one font: the covering shape is all there is to see
    assert (f.fclass, f.detector, f.family, f.status) == ("observation", "pdf_overlay", "visual", "open")
    assert "52,000.00" in f.detail and "82,000.00" in f.detail
    assert f.evidence[0].page == m.page and iou(f.evidence[0].box, m.box) >= 0.5 and f.evidence[0].value == "82,000.00"
    assert any(e.value == "52,000.00" for e in f.evidence[1:]), "the text that is covered is cited too"


def test_d2_covers_the_old_text_without_removing_it():
    edited, _ = d2_cover_retype(SALARY, "52,000.00", "82,000.00")
    text = pymupdf.open(stream=edited, filetype="pdf")[0].get_text()
    assert "52,000.00" in text and "82,000.00" in text


def test_d1_edit_is_not_reported_as_covered_text(tmp_path):
    edited, _ = d1_incremental_edit(SALARY, "52,000.00", "82,000.00")  # the old text is taken out: nothing lies under the white fill
    assert {f.detector for f in run(tmp_path, edited).findings} == {"pdf_revisions"}


# --- D3: covered and retyped in a font that looks alike

@NEEDS_ARIAL
def test_d3_near_font_found_by_font_name(tmp_path):
    pdf, old = statement()
    edited, m = d3_near_font_retype(pdf, old, "9,99,999.99")
    assert (m.method, m.page) == ("D3", 1)
    case = run(tmp_path, edited)
    (f,) = by(case, "pdf_fonts")
    assert (f.fclass, f.family) == ("observation", "visual")
    assert "Arial" in f.detail and "Helvetica" in f.detail, "both font names are given as the file spells them"
    assert f.evidence[0].page == m.page and iou(f.evidence[0].box, m.box) >= 0.5 and f.evidence[0].value == "9,99,999.99"
    assert by(case, "pdf_overlay"), "the white rectangle over the old figure is seen as well"


# --- D4: metadata

def test_d4_metadata_found(tmp_path):
    pdf, _ = statement()
    edited, m = d4_metadata_edit(pdf, "Adobe Acrobat Pro 24.1", "D:20260301103000+05'30'")
    assert (m.method, m.page, m.box) == ("D4", 0, None)
    found = by(run(tmp_path, edited), "pdf_meta")
    assert len(found) == 2 and all((f.fclass, f.family) == ("observation", "metadata") for f in found)
    tool, late = sorted(found, key=lambda f: "Acrobat" not in f.detail)
    assert "Adobe Acrobat Pro 24.1" in tool.detail
    assert "2026-02-01" in late.detail and "2026-03-01" in late.detail, "the creation and modification times are both printed"
    assert all(f.evidence[0].page == 0 and f.evidence[0].note == "file metadata" for f in found)


def test_d4_an_unchanged_producer_and_date_raise_nothing(tmp_path):
    pdf, _ = statement()
    edited, _ = d4_metadata_edit(pdf, "Halcyon Test Bank Statement Service 4.2", "D:20260201092900+05'30'")
    assert run(tmp_path, edited).findings == []


# --- D5: a picture over the figure

def test_d5_pasted_image_found(tmp_path):
    pdf, old = statement()
    edited, m = d5_paste_image(pdf, old, "9,99,999.99")
    assert (m.method, m.page) == ("D5", 1)
    (f,) = run(tmp_path, edited).findings
    assert (f.fclass, f.detector, f.family) == ("observation", "pdf_overlay", "visual")
    assert f.evidence[0].page == m.page and iou(f.evidence[0].box, m.box) >= 0.8
    assert old in f.detail, "the text that lies under the picture is named"


# --- hidden text

def hidden_pdf(kind):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Visible line of text", fontname="helv", fontsize=11)
    where, size, extra = {"invisible": ((72, 140), 11, {"render_mode": 3}), "tiny": ((72, 140), 1, {}), "off the page": ((700, 140), 11, {})}[kind]
    page.insert_text(where, "Approved by manager", fontname="helv", fontsize=size, **extra)
    return doc.tobytes()


@pytest.mark.parametrize("kind", ["invisible", "tiny", "off the page"])
def test_hidden_text_is_reported_with_its_words(tmp_path, kind):
    (f,) = run(tmp_path, hidden_pdf(kind)).findings
    assert (f.fclass, f.detector, f.family) == ("observation", "pdf_overlay", "visual") and kind in f.title.lower()
    assert "Approved by manager" in f.detail and f.evidence[0].value == "Approved by manager"


# --- the other way round

@pytest.mark.parametrize("seed", [1, 2, 3])
@pytest.mark.parametrize("kind", DRAWERS)
def test_genuine_documents_trigger_no_digital_detector(tmp_path, kind, seed):
    assert run(tmp_path, DRAWERS[kind](identity(seed), seed).pdf).findings == []


def test_more_objects_than_the_limit_is_a_limitation_not_a_pass(tmp_path):
    pdf, _ = statement()
    case = run(tmp_path, pdf, th=Thresholds(max_page_objects=10))
    assert {f.fclass for f in case.findings} == {"processing_limitation"}
    assert {"pdf_overlay", "pdf_fonts"} <= {f.detector for f in case.findings}
    assert all("10" in f.detail for f in case.findings)


@NEEDS_ARIAL
def test_observations_state_measurements_not_intent(tmp_path):
    pdf, old = statement()
    files = [d2_cover_retype(pdf, old, "9,99,999.99")[0], d3_near_font_retype(pdf, old, "9,99,999.99")[0],
             d4_metadata_edit(pdf, "Adobe Acrobat Pro 24.1", "D:20260301103000+05'30'")[0], d5_paste_image(pdf, old, "9,99,999.99")[0]]
    found = [f for i, one in enumerate(files) for f in run(tmp_path / str(i), one).findings]
    assert len(found) >= 5
    for f in found:
        text = f"{f.title} {f.detail}".lower()
        assert f.fclass == "observation" and not any(w in text for w in INTENT), text
        assert re.search(r"\d", f.detail), "a measurement is given"


# --- a page with /Rotate: the detectors read the page as it was drawn, the reader and the viewer show it turned

def rotated(pdf: bytes, degrees: int) -> bytes:
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    doc[0].set_rotation(degrees)
    return doc.tobytes()


def word_box(case, text):
    return next(w.box for w in case.documents[0].pages[0].words if w.text == text)


@pytest.mark.parametrize("degrees", [90, 180, 270])
def test_overlay_evidence_on_a_rotated_page_lands_on_the_text_the_reader_found(tmp_path, degrees):
    edited, _ = d2_cover_retype(SALARY, "52,000.00", "82,000.00")
    case = run(tmp_path, rotated(edited, degrees))
    (f,) = case.findings
    assert iou(f.evidence[0].box, word_box(case, "82,000.00")) >= 0.5


@pytest.mark.parametrize("degrees", [90, 180, 270])
def test_font_evidence_on_a_rotated_page_lands_on_the_text_the_reader_found(tmp_path, degrees):
    column = [(400, 100 + 30 * i, "1,000.00", 10) for i in range(5)]
    column[2] = (400, 160, "9,999.00", 14)  # one value of five is set larger than the rest of its column
    case = run(tmp_path, rotated(lines_pdf(column), degrees))
    (f,) = by(case, "pdf_fonts")
    assert iou(f.evidence[0].box, word_box(case, "9,999.00")) >= 0.5


@pytest.mark.parametrize("degrees", [90, 270])
def test_text_low_on_a_rotated_page_is_not_reported_as_off_the_page(tmp_path, degrees):
    pdf = lines_pdf([(72, 100, "Visible line of text", 11), (72, 800, "Page footer text", 11)])  # 800 pt down a 842 pt page
    assert run(tmp_path, rotated(pdf, degrees)).findings == []
