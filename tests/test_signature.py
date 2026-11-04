"""Signatures (Task 25): the hands the generator draws, the signature blocks of the two layouts, and the comparison across documents."""
import dataclasses
import io
import random
import re

import pymupdf
import pytest
from PIL import Image

from datagen import signatures
from datagen.fictional import identity
from datagen.layouts import PX
from datagen.layouts.application import draw_application
from datagen.layouts.payslip import draw_payslip
from datagen.manipulate import c4_other_hand
from datagen.scan import simulate_scan, to_scan_frame
from docforensics.audit import AuditLog
from docforensics.config import Thresholds
from docforensics.findings import add_findings
from docforensics.forensics import run_forensics
from docforensics.forensics.signature import compare_signatures
from docforensics.ingest import create_case
from docforensics.pipeline import Ctx, run_case
from docforensics.read import read_stage
from docforensics.understand.classify import classify_stage
from docforensics.understand.specs import load_specs
from tests.helpers import iou

TH = Thresholds()
ocr = pytest.mark.ocr
STAGES = {"read": read_stage, "classify": classify_stage, "forensics": run_forensics}
VERDICT = re.compile(r"fraud|forg|fake|counterfeit", re.I)


def test_a_hand_belongs_to_one_person_and_a_new_signing_moves_it_only_a_little():
    base = signatures.strokes("Meera K. Varghese")
    assert base == signatures.strokes("Meera K. Varghese") != signatures.strokes("Anil R. Rao")
    a = signatures.strokes("Meera K. Varghese", random.Random(1))
    b = signatures.strokes("Meera K. Varghese", random.Random(2))
    assert a != b and a != base and [len(s) for s in a] == [len(s) for s in b] == [len(s) for s in base]
    for s, t in zip(a, base):
        for (x, y), (u, v) in zip(s, t):
            assert abs(x - u) < 0.12 and abs(y - v) < 0.12
    assert all(-0.1 <= c <= 1.1 for s in a for p in s for c in p)  # stays in its box


def test_both_layouts_sign_just_above_a_caption_and_the_hand_follows_the_identity():
    ident = identity(1)
    for drawn, caption in ((draw_application(ident, seed=1), "Applicant Signature"), (draw_payslip(ident, seed=1), "Employee Signature")):
        with pymupdf.open(stream=drawn.pdf, filetype="pdf") as pdf:
            (cap,) = pdf[0].search_for(caption)
            assert len(pdf[0].get_drawings()) >= 2  # strokes, not text
        page, x0, y0, x1, y1 = drawn.truth["boxes"]["signature"]
        assert page == 1 and 0 < cap.y0 * PX - y1 < 60 and abs(x0 - cap.x0 * PX) < 40 and x1 - x0 > 250 and y1 - y0 > 60, caption
    other = dataclasses.replace(ident, hand=identity(2).name)
    assert draw_application(other, seed=1).pdf != draw_application(ident, seed=1).pdf
    assert draw_payslip(other, seed=1).pdf != draw_payslip(ident, seed=1).pdf


def test_c4_draws_a_document_in_another_persons_hand_and_changes_nothing_else():
    ident, other = identity(1), identity(2)
    changed = c4_other_hand(ident, other)
    assert changed.hand == other.name and dataclasses.replace(changed, hand="") == ident


def test_the_specs_of_the_two_signed_types_say_where_the_caption_is():
    specs = load_specs()
    assert "applicant signature" in specs["loan_application"].signature and "employee signature" in specs["payslip"].signature
    assert specs["bank_statement"].signature == []  # no signature is drawn on a statement: nothing is looked for


# --- the comparison

def drawn_pair(seed=1, sa=1, sb=31, hand=None):
    """An application and a payslip of one person; with `hand`, the payslip is signed in that other person's hand (C4)."""
    ident = identity(seed)
    return draw_application(ident, seed=sa), draw_payslip(c4_other_hand(ident, identity(hand)) if hand else ident, seed=sb)


def run(tmp_path, *files):
    """Read, classify and run the forensic detectors on the files, nothing else. (case, audit events)."""
    _, cd, _ = create_case(tmp_path / "data", list(files), TH)
    case = run_case(cd, TH, stages=STAGES)
    return case, AuditLog(cd.audit_path).events()


def signature_findings(case):
    return [f for f in case.findings if f.detector == "signature"]


def compared(events):
    return [e.data for e in events if e.event == "signature_compared"]


def pdfs(app, slip):
    return [("a.pdf", app.pdf), ("b.pdf", slip.pdf)]


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_one_hand_on_two_documents_is_compared_and_passes_without_a_finding(tmp_path, seed):
    case, events = run(tmp_path, *pdfs(*drawn_pair(seed, sa=seed, sb=seed + 30)))
    assert signature_findings(case) == []
    (done,) = compared(events)
    assert sorted(done["docs"]) == ["D1", "D2"] and done["differs"] is False and done["distance"] < TH.signature_dist


def test_another_hand_on_one_document_is_an_inconsistency_that_points_at_both_signatures(tmp_path):
    app, slip = drawn_pair(1, hand=2)
    case, events = run(tmp_path, *pdfs(app, slip))
    (f,) = signature_findings(case)
    assert (f.fclass, f.family) == ("inconsistency", "cross_document") and "D1" in f.title and "D2" in f.title
    assert f"{TH.signature_dist:g}" in f.detail and not VERDICT.search(f.title + f.detail)
    (done,) = compared(events)
    assert done["differs"] is True and done["distance"] > TH.signature_dist and done["limit"] == TH.signature_dist
    boxes = {e.doc: e for e in f.evidence}
    assert sorted(boxes) == ["D1", "D2"] and {e.page for e in f.evidence} == {1}
    for doc, drawn in (("D1", app), ("D2", slip)):
        assert iou(boxes[doc].box, drawn.truth["boxes"]["signature"][1:]) > 0.8, doc


def test_with_three_documents_every_pair_is_compared_and_the_odd_one_is_in_each_finding(tmp_path):
    ident = identity(1)
    files = [("a.pdf", draw_application(ident, seed=1).pdf), ("b.pdf", draw_payslip(ident, seed=31).pdf),
             ("c.pdf", draw_payslip(c4_other_hand(ident, identity(2)), seed=61).pdf)]
    case, events = run(tmp_path, *files)
    found = signature_findings(case)
    assert len(found) == 2 and all("D3" in f.title for f in found) and not any("D1" in f.title and "D2" in f.title for f in found)
    assert len(compared(events)) == 3


def whiteout(pdf, box):
    with pymupdf.open(stream=pdf, filetype="pdf") as d:
        _, x0, y0, x1, y1 = box
        d[0].draw_rect(pymupdf.Rect(x0 / PX - 2, y0 / PX - 2, x1 / PX + 2, y1 / PX + 2), color=None, fill=(1, 1, 1))
        return d.tobytes()


def test_a_blank_signature_area_is_a_limitation_and_not_a_pass(tmp_path):
    app, slip = drawn_pair(1)
    case, events = run(tmp_path, ("a.pdf", whiteout(app.pdf, app.truth["boxes"]["signature"])), ("b.pdf", slip.pdf))
    (f,) = signature_findings(case)
    assert (f.fclass, f.family) == ("processing_limitation", "limitation") and f.title == "Signatures only partly compared"
    assert "D1" in f.detail and "no ink" in f.detail and compared(events) == []


def test_a_caption_that_is_not_found_is_a_limitation_and_not_a_pass(tmp_path):
    app, slip = drawn_pair(1)
    with pymupdf.open(stream=slip.pdf, filetype="pdf") as d:
        for r in d[0].search_for("Employee Signature"):
            d[0].add_redact_annot(r)
        d[0].apply_redactions()
        assert not d[0].search_for("Employee Signature")
        gone = d.tobytes()
    case, events = run(tmp_path, ("a.pdf", app.pdf), ("b.pdf", gone))
    (f,) = signature_findings(case)
    assert f.fclass == "processing_limitation" and "D2" in f.detail and "caption" in f.detail and compared(events) == []


def blacken(pdf, *boxes):
    """The PDF with black bars over these boxes (pixels of the 200-dpi page)."""
    with pymupdf.open(stream=pdf, filetype="pdf") as d:
        for x0, y0, x1, y1 in boxes:
            d[0].draw_rect(pymupdf.Rect(x0 / PX, y0 / PX, x1 / PX, y1 / PX), color=None, fill=(0, 0, 0))
        return d.tobytes()


@pytest.mark.parametrize("side", [4, 8])
def test_a_speck_beside_a_signature_does_not_make_one_hand_differ(tmp_path, side):
    app, slip = drawn_pair(1)
    _, x0, y0, x1, y1 = app.truth["boxes"]["signature"]
    mid = (y0 + y1) / 2
    marked = blacken(app.pdf, (x1 + 60, mid - side / 2, x1 + 60 + side, mid + side / 2))  # clear of the signature, inside the area searched
    case, events = run(tmp_path, ("a.pdf", marked), ("b.pdf", slip.pdf))
    assert signature_findings(case) == []
    (done,) = compared(events)
    assert done["differs"] is False and done["distance"] < 3, done


def only_limitation(case, events, doc, phrase):
    (f,) = signature_findings(case)
    assert (f.fclass, f.title) == ("processing_limitation", "Signatures only partly compared"), f.title
    assert doc in f.detail and phrase in f.detail and compared(events) == [], f.detail


def test_an_area_full_of_printed_matter_is_a_limitation_and_not_a_comparison(tmp_path):
    app, slip = drawn_pair(1)
    _, x0, y0, x1, y1 = app.truth["boxes"]["signature"]
    hatched = blacken(app.pdf, *[(x0 + 10, y0 - 40 + 16 * k, x1 - 10, y0 - 32 + 16 * k) for k in range(9)])
    case, events = run(tmp_path, ("a.pdf", hatched), ("b.pdf", slip.pdf))
    only_limitation(case, events, "D1", "mostly ink")


def test_a_line_across_the_area_is_a_limitation_and_not_a_comparison(tmp_path):
    app, slip = drawn_pair(1)
    _, x0, y0, x1, y1 = app.truth["boxes"]["signature"]
    ruled = blacken(app.pdf, (0, y0 + 20, 1653, y0 + 28))
    case, events = run(tmp_path, ("a.pdf", ruled), ("b.pdf", slip.pdf))
    only_limitation(case, events, "D1", "reaches the edge")


def test_a_caption_with_too_little_page_above_it_is_a_limitation(tmp_path):
    app, slip = drawn_pair(1)
    with pymupdf.open(stream=app.pdf, filetype="pdf") as d:
        for r in d[0].search_for("Applicant Signature"):
            d[0].add_redact_annot(r)
        d[0].apply_redactions()
        d[0].insert_text((40, 30), "Applicant Signature", fontsize=8)
        moved = d.tobytes()
    case, events = run(tmp_path, ("a.pdf", moved), ("b.pdf", slip.pdf))
    only_limitation(case, events, "D1", "too little of page 1")


def test_one_signed_document_has_nothing_to_compare_and_says_nothing(tmp_path):
    case, events = run(tmp_path, ("a.pdf", drawn_pair(1)[1].pdf))
    assert signature_findings(case) == [] and compared(events) == []


# --- scans, read by the real reader

def scan_pair(la, lb, hand):
    """The pair as files: a level of None leaves that document digital; angle seeds 1 and 2 turn the scans differently."""
    app, slip = drawn_pair(3, hand=hand)
    files = [("a.jpg", simulate_scan(app.pdf, la, seed=1)) if la else ("a.pdf", app.pdf),
             ("b.jpg", simulate_scan(slip.pdf, lb, seed=2)) if lb else ("b.pdf", slip.pdf)]
    return app, slip, files


@ocr
@pytest.mark.parametrize("la, lb", [("mild", "150dpi"), (None, "150dpi"), ("150dpi", None)])
def test_scans_are_straightened_and_compared_like_digital_pages(tmp_path, la, lb):
    *_, files = scan_pair(la, lb, None)
    case, events = run(tmp_path / "same", *files)
    print([(f.title, f.detail) for f in signature_findings(case)], compared(events))
    assert signature_findings(case) == [] and len(compared(events)) == 1 and compared(events)[0]["differs"] is False

    app, slip, files = scan_pair(la, lb, 2)
    case, events = run(tmp_path / "other", *files)
    print([(f.title, f.detail) for f in signature_findings(case)], compared(events))
    (f,) = signature_findings(case)
    assert f.fclass == "inconsistency"
    for e, drawn, level, angle in zip(sorted(f.evidence, key=lambda e: e.doc), (app, slip), (la, lb), (1, 2)):
        want = drawn.truth["boxes"]["signature"][1:]
        if level:
            with Image.open(io.BytesIO(files[angle - 1][1])) as im:
                want = to_scan_frame(want, im.size, angle)
        assert iou(e.box, want) > 0.6, (e.doc, e.box, want)


def read_only(tmp_path, files):
    """The case after reading and classifying the files, and its context; no detector has run."""
    case, cd, audit = create_case(tmp_path / "data", files, TH)
    ctx = Ctx(cd, audit, TH)
    read_stage(case, ctx)
    classify_stage(case, ctx)
    return case, ctx


@ocr
def test_a_page_of_poor_quality_is_not_compared_and_the_limitation_says_so(tmp_path):
    *_, files = scan_pair("mild", "mild", 2)
    case, ctx = read_only(tmp_path, files)
    case.documents[0].pages[0].quality_class = "poor"
    add_findings(case, ctx, compare_signatures(case, ctx))
    only_limitation(case, ctx.audit.events(), "D1", "poor")


@ocr
def test_a_scan_with_too_few_words_to_find_its_turn_is_a_limitation(tmp_path):
    *_, files = scan_pair("mild", "mild", 2)
    case, ctx = read_only(tmp_path, files)
    page = case.documents[0].pages[0]
    page.words = [w for w in page.words if w.text in ("Applicant", "Signature")]
    add_findings(case, ctx, compare_signatures(case, ctx))
    only_limitation(case, ctx.audit.events(), "D1", "fewer than the 12 needed")


@ocr
def test_a_scan_turned_further_than_the_search_goes_is_a_limitation(tmp_path):
    (name, jpg), slip = scan_pair("mild", "mild", 2)[2]
    with Image.open(io.BytesIO(jpg)) as im:
        out = io.BytesIO()
        im.rotate(5, resample=Image.BICUBIC, fillcolor="white").save(out, "JPEG", quality=85)
    case, ctx = read_only(tmp_path, [(name, out.getvalue()), slip])
    assert [d.doc_type for d in case.documents] == ["loan_application", "payslip"]
    add_findings(case, ctx, compare_signatures(case, ctx))
    only_limitation(case, ctx.audit.events(), "D1", "turned by")
