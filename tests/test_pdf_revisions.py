"""Revision-diff detector (design 7.5) and the D1 edit it is measured against. A PDF saved incrementally keeps its earlier
revisions inside the file; comparing the words of consecutive revisions shows what a later save changed."""
import pymupdf
import pytest

from datagen.fictional import identity
from datagen.layouts import PX
from datagen.layouts.statement import draw_statement
from datagen.manipulate import Manipulation, d1_incremental_edit, incremental, retype
from docforensics import forensics
from docforensics.audit import AuditLog
from docforensics.config import Thresholds
from docforensics.forensics import run_forensics
from docforensics.forensics.pdf_revisions import quote
from docforensics.ingest import create_case
from docforensics.model import Case, Document, Finding, Page
from docforensics.pipeline import Ctx, run_case
from docforensics.read import read_stage
from docforensics.store import CaseDir
from tests.helpers import STATEMENT_LINES, iou, lines_pdf

TH = Thresholds()
SALARY = lines_pdf(STATEMENT_LINES)  # "03/04/2026 Salary credit 52,000.00   1,72,500.00" and the rest of a small statement


def run(tmp_path, *pdfs, th=TH):
    """Read the documents and run the forensic detectors, nothing else. The raw file-structure detector (tests/test_structure.py)
    also reports on the bytes these tests append after the last marker or break on purpose; its findings are left out here."""
    _, cd, _ = create_case(tmp_path / "data", [(f"d{i}.pdf", p) for i, p in enumerate(pdfs, 1)], th)
    case = run_case(cd, th, stages={"read": read_stage, "forensics": run_forensics})
    case.findings = [f for f in case.findings if f.detector != "file_structure"]
    return case


def add_line(pdf, text, y=400):
    return incremental(pdf, lambda pg: pg.insert_text((72, y), text, fontname="helv", fontsize=10))


# --- the D1 edit

def test_d1_edit_found_with_old_and_new_text(tmp_path):
    edited, m = d1_incremental_edit(SALARY, "52,000.00", "82,000.00")
    assert isinstance(m, Manipulation) and (m.method, m.page, m.field) == ("D1", 1, None) and len(m.box) == 4
    (f,) = run(tmp_path, edited).findings  # the new number is written last in the file, but it replaces the old one in place
    assert (f.fclass, f.detector, f.family, f.status) == ("observation", "pdf_revisions", "metadata", "open")
    assert "52,000.00" in f.detail and "82,000.00" in f.detail and "revision 1" in f.detail and "revision 2" in f.detail
    e = f.evidence[0]
    assert e.page == m.page and iou(e.box, m.box) >= 0.9 and e.value == "82,000.00"


def words_of(pdf):
    return sorted((round(w[0], 1), round(w[1], 1), w[4]) for w in pymupdf.open(stream=pdf, filetype="pdf")[0].get_text("words"))


def test_d1_edit_changes_nothing_else():
    edited, _ = d1_incremental_edit(SALARY, "52,000.00", "82,000.00")
    put_back = [(x, y, "52,000.00" if w == "82,000.00" else w) for x, y, w in words_of(edited)]
    assert sorted(put_back) == words_of(SALARY)  # the same words in the same places, but for the one that was edited


def test_d1_matches_whole_words_only():
    pdf = lines_pdf([(72, 100, "Total 1,52,000.00", 10), (72, 120, "Paid 52,000.00", 10)])
    edited, _ = d1_incremental_edit(pdf, "52,000.00", "82,000.00")
    text = pymupdf.open(stream=edited, filetype="pdf")[0].get_text()
    assert "Total 1,52,000.00" in text and "Paid 82,000.00" in text


@pytest.mark.parametrize("old", ["99,999.00", "debit"])  # not there; there more than once
def test_d1_needs_exactly_one_target(old):
    pdf = lines_pdf([(72, 100, "Rent debit 18,000.00", 10), (72, 120, "Grocery debit 4,125.50", 10)])
    with pytest.raises(ValueError, match="exactly once"):
        d1_incremental_edit(pdf, old, "1.00")


# --- the detector

@pytest.mark.parametrize("seed", [1, 2, 3])
def test_genuine_pdf_has_no_revision_findings(tmp_path, seed):
    assert run(tmp_path, draw_statement(identity(seed), rows=12, seed=seed).pdf).findings == []


def test_two_edits_two_findings(tmp_path):
    once, _ = d1_incremental_edit(SALARY, "52,000.00", "82,000.00")
    twice, _ = d1_incremental_edit(once, "18,000.00", "8,000.00")  # a third revision
    first, second = run(tmp_path, twice).findings
    assert "revision 2" in first.title and "52,000.00" in first.detail and "82,000.00" in first.detail
    assert "revision 3" in second.title and "18,000.00" in second.detail and "8,000.00" in second.detail


def test_two_edits_in_one_revision_are_two_findings(tmp_path):
    both = incremental(SALARY, lambda pg: [retype(pg, "52,000.00", "82,000.00"), retype(pg, "18,000.00", "8,000.00")])
    found = run(tmp_path, both).findings
    assert len(found) == 2 and all("revision 2" in f.title for f in found)


def test_text_added_and_text_removed(tmp_path):
    (added,) = run(tmp_path / "a", add_line(SALARY, "Approved by branch manager")).findings
    assert added.title == "Text added in revision 2 (page 1)" and "Approved by branch manager" in added.detail
    e = added.evidence[0]
    assert abs(e.box[0] - 72 * PX) < 2 and e.box[1] < 400 * PX < e.box[3]  # the baseline lies inside the box

    where = pymupdf.open(stream=SALARY, filetype="pdf")[0].search_for("Grocery")[0]
    gone = incremental(SALARY, lambda pg: (pg.add_redact_annot(pg.search_for("Grocery")[0]), pg.apply_redactions()))
    (removed,) = run(tmp_path / "b", gone).findings
    assert removed.title == "Text removed in revision 2 (page 1)" and '"Grocery"' in removed.detail
    assert iou(removed.evidence[0].box, [v * PX for v in where]) >= 0.8  # where it was, in the revision that still had it


def test_nothing_in_the_text_changed_nothing_reported(tmp_path):
    saved = incremental(SALARY, lambda pg: pg.add_text_annot((300, 300), "a reviewer's note"))  # a second revision, same words
    assert run(tmp_path, saved).findings == []


def test_a_rewritten_page_is_one_finding_not_a_list(tmp_path):
    n = TH.max_revision_runs + 8
    pdf = lines_pdf([(72, 40 + 20 * i, f"item {i} amount {1000 + i}.00", 10) for i in range(n)])
    rewritten = incremental(pdf, lambda pg: [retype(pg, f"{1000 + i}.00", f"{2000 + i}.00") for i in range(n)])
    (f,) = run(tmp_path, rewritten).findings
    assert f.fclass == "observation" and f"{n} " in f.detail and f"{TH.max_revision_runs}" in f.detail
    assert "revision 1" in f.detail and "revision 2" in f.detail


def test_quote_is_one_clean_short_line():
    assert quote("a" + chr(0x202E) + "b\nc\x07d\t e") == "a b c d e"  # bidi override, newline, bell, tab: all become one space
    assert quote("x" * 300) == "x" * 117 + "..." and quote("y" * 120) == "y" * 120


# --- what cannot be compared

def test_garbage_after_last_eof_gives_limitation(tmp_path):
    edited, _ = d1_incremental_edit(SALARY, "52,000.00", "82,000.00")
    found = run(tmp_path / "a", edited + b"\n<<not a revision>>\x00\x01 appended later").findings
    assert sorted(f.fclass for f in found) == ["observation", "processing_limitation"]  # the edit is still reported
    (lim,) = [f for f in found if f.fclass == "processing_limitation"]
    assert lim.detector == "pdf_revisions" and lim.family == "limitation" and "follow the last end-of-file marker" in lim.detail
    (only,) = run(tmp_path / "b", SALARY + b"\njunk after the end").findings
    assert only.fclass == "processing_limitation"


def test_eof_text_inside_a_page_is_not_a_revision(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "x", fontname="helv", fontsize=10)  # gives the page its font and a content stream
    doc.update_stream(page.get_contents()[0], b"BT /helv 10 Tf 72 700 Td (startxref 12 %%EOF) Tj ET", compress=False)
    pdf = doc.tobytes()
    assert b"startxref 12 %%EOF" in pdf  # in the clear (insert_text hides its text in hex strings): a split at any %%EOF cuts the page
    assert run(tmp_path, pdf).findings == []


def test_file_without_a_revision_structure_gives_limitation(tmp_path):
    (lim,) = run(tmp_path, SALARY.replace(b"startxref", b"startxrex")).findings
    assert lim.fclass == "processing_limitation" and "no end-of-file marker" in lim.detail


def test_linearized_pdf_is_not_compared(tmp_path):
    edited, _ = d1_incremental_edit(SALARY, "52,000.00", "82,000.00")
    marked = edited.replace(b"\n", b"\n%/Linearized 1\n", 1)  # the marker a linearized file carries in its first 1024 bytes
    (lim,) = run(tmp_path, marked).findings
    assert lim.fclass == "processing_limitation" and "linearized" in lim.title.lower()


def test_too_many_revisions_are_not_opened(tmp_path):
    pdf = SALARY
    for i in range(TH.max_revisions + 3):
        pdf = add_line(pdf, f"w{i}", y=400 + 12 * i)
    (lim,) = run(tmp_path, pdf).findings
    assert lim.fclass == "processing_limitation" and f"{TH.max_revisions + 4}" in lim.detail and f"{TH.max_revisions}" in lim.detail


def test_a_page_too_large_to_compare_is_said_not_skipped(tmp_path):
    th = Thresholds(max_diff_words=200)
    crowded = lines_pdf([(10, 20 + 3 * i, "a " * 60, 1) for i in range(10)])  # 600 words on one page, set at 1 pt: the overlay detector notes that too
    (lim,) = [f for f in run(tmp_path, add_line(crowded, "added"), th=th).findings if f.detector == "pdf_revisions"]
    assert lim.fclass == "processing_limitation" and "page 1" in lim.detail and "200" in lim.detail


# --- the stage

def ctx_for(tmp_path):
    cd = CaseDir.create(tmp_path)
    return Ctx(cd, AuditLog(cd.audit_path), TH)


def case_with(*modes):
    pages = [Page(n=i, width=10, height=10, read_mode=m, quality_class="text-layer" if m == "text-layer" else "good")
             for i, m in enumerate(modes, 1)]
    doc = Document(id="D1", sha256="0", filename="a.pdf", stored_path="a.pdf", pages=pages)
    return Case(id="C", created="2026-11-02T00:00:00+00:00", documents=[doc])


def test_detectors_run_by_page_kind(monkeypatch, tmp_path):
    calls = []

    def digital(case, doc, ctx):
        calls.append("digital")
        return []

    def scan(case, doc, ctx):
        calls.append("scan")
        return []

    monkeypatch.setattr(forensics, "DIGITAL_DETECTORS", [digital])
    monkeypatch.setattr(forensics, "SCAN_DETECTORS", [scan])
    monkeypatch.setattr(forensics, "FILE_DETECTORS", [])  # its own run on every document is tested in tests/test_structure.py
    for modes, want in ((("text-layer",), ["digital"]), (("ocr",), ["scan"]), (("text-layer", "ocr"), ["digital", "scan"]), ((), [])):
        calls.clear()
        run_forensics(case_with(*modes), ctx_for(tmp_path))
        assert calls == want


def test_failing_detector_is_a_limitation_and_the_rest_still_run(monkeypatch, tmp_path):
    def boom(case, doc, ctx):
        raise RuntimeError("detector exploded")

    def fine(case, doc, ctx):
        return [Finding(fclass="observation", detector="fine", family="visual", title="Seen")]

    monkeypatch.setattr(forensics, "DIGITAL_DETECTORS", [boom, fine])
    monkeypatch.setattr(forensics, "FILE_DETECTORS", [])  # the document's file does not exist here: that detector would fail as well
    case, ctx = case_with("text-layer"), ctx_for(tmp_path)
    run_forensics(case, ctx)
    lim, seen = case.findings
    assert lim.fclass == "processing_limitation" and "forensics.boom" in lim.title and "detector exploded" in lim.detail
    assert (seen.id, seen.fclass) == ("F-002", "observation")
    done = [e.data for e in ctx.audit.events() if e.event == "doc_forensics"]
    assert done == [{"doc": "D1", "detector": "fine", "findings": 1}]
