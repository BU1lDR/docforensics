"""Issuer marks (Task 26): the logos and stamps the generator draws on a bank's documents, and the comparison across them."""
import io
import itertools
import random
import re
from dataclasses import replace

import pymupdf
import pytest
from PIL import Image

from datagen import marks
from datagen.fictional import BANKS, identity
from datagen.layouts import PX
from datagen.layouts.application import draw_application
from datagen.layouts.statement import draw_statement
from datagen.manipulate import c5_other_mark
from datagen.scan import simulate_scan, to_scan_frame
from docforensics.config import Thresholds
from docforensics.findings import add_findings
from docforensics.forensics.marks import compare_marks
from docforensics.model import Document, Page, Word
from docforensics.understand.extract import extract_document
from docforensics.understand.layout import issuer_line, lines_of, text_of
from docforensics.understand.specs import load_specs
from tests.helpers import iou
from tests.test_signature import blacken, pdfs, read_only, run, whiteout

TH = Thresholds()
ocr = pytest.mark.ocr
NAMES = [f"{b} Test Bank" for b in BANKS]
KINDS = ("logo", "stamp")
CAPTIONS = {"statement": "Bank Seal", "application": "For Bank Use"}
VERDICT = re.compile(r"fraud|forg|fake|counterfeit", re.I)
BANK, OTHER = NAMES[3], NAMES[4]  # two banks whose marks are clearly unlike: at the digital level their logos lie 38 percent apart, their stamps 31


def drawn_pages(ident, seed=1):
    return {"statement": draw_statement(ident, seed=seed), "application": draw_application(ident, seed=seed)}


@pytest.mark.parametrize("kind", KINDS)
def test_a_design_belongs_to_one_bank_and_a_new_pressing_moves_it_only_a_little(kind):
    base = marks.strokes(kind, NAMES[0])
    assert base == marks.strokes(kind, NAMES[0])
    a, b = marks.strokes(kind, NAMES[0], random.Random(1)), marks.strokes(kind, NAMES[0], random.Random(2))
    assert a != b and a != base and [len(s) for s in a] == [len(s) for s in b] == [len(s) for s in base]
    for s, t in zip(a, base):
        for (x, y), (u, v) in zip(s, t):
            assert abs(x - u) < 0.1 and abs(y - v) < 0.1
    assert all(-0.1 <= c <= 1.1 for s in a for p in s for c in p)  # stays in its box


@pytest.mark.parametrize("kind", KINDS)
def test_every_bank_has_its_own_mark_of_each_kind(kind):
    for x, y in itertools.combinations(NAMES, 2):
        assert marks.strokes(kind, x) != marks.strokes(kind, y), (x, y)
    assert all(marks.strokes("logo", n) != marks.strokes("stamp", n) for n in NAMES)


def test_a_small_edit_drops_a_ring_from_a_stamp_and_moves_one_point_of_a_logo():
    for name in NAMES:
        base, edited = marks.strokes("stamp", name), marks.strokes("stamp", f"{name}/edit")
        assert len(edited) == len(base) - 1 and edited[0] == base[0], name
        base, edited = marks.strokes("logo", name), marks.strokes("logo", f"{name}/edit")
        moved = [(i, j) for i, (s, t) in enumerate(zip(base, edited)) for j, (p, q) in enumerate(zip(s, t)) if p != q]
        assert [len(s) for s in base] == [len(s) for s in edited] and len(moved) == 1, name
        i, j = moved[0]
        (x, y), (u, v) = base[i][j], edited[i][j]
        assert 0.09 < ((x - u) ** 2 + (y - v) ** 2) ** 0.5 < 0.11, name


def test_an_unknown_kind_is_refused():
    with pytest.raises(ValueError):
        marks.strokes("seal", NAMES[0])


@pytest.mark.parametrize("which", ["statement", "application"])
def test_both_layouts_draw_a_logo_beside_the_name_and_a_stamp_above_its_caption(which):
    for seed in (1, 2, 3):
        drawn = drawn_pages(identity(seed), seed)[which]
        boxes = drawn.truth["boxes"]
        with pymupdf.open(stream=drawn.pdf, filetype="pdf") as pdf:
            page = pdf[0]
            (cap,) = page.search_for(CAPTIONS[which])
            name = page.search_for(identity(seed).bank)[0]
            words = [pymupdf.Rect(w[:4]) for w in page.get_text("words")]
            shapes = [d["rect"] for d in page.get_drawings()]
        for key in KINDS:
            page_no, x0, y0, x1, y1 = boxes[key]
            region = pymupdf.Rect(x0 / PX, y0 / PX, x1 / PX, y1 / PX)
            assert page_no == 1 and any(region.intersects(r) for r in shapes), key
            assert not any(region.intersects(w) for w in words), (key, seed)  # nothing printed under or over a mark
        _, lx0, ly0, lx1, ly1 = boxes["logo"]
        assert 80 < lx1 - lx0 < 120 and 80 < ly1 - ly0 < 120
        assert lx0 > name.x1 * PX and ly0 < name.y1 * PX and ly1 > name.y0 * PX  # right of the name, on its line
        _, sx0, sy0, sx1, sy1 = boxes["stamp"]
        assert 150 < sx1 - sx0 < 200 and 150 < sy1 - sy0 < 200
        assert 0 < cap.y0 * PX - sy1 < 40 and abs(sx0 - cap.x0 * PX) < 20, (which, seed)  # just above its caption, left edges alike


def strokes_of(drawn):
    with pymupdf.open(stream=drawn.pdf, filetype="pdf") as pdf:  # the bytes differ run to run (the trailer's file id), the strokes do not
        return [d["items"] for d in pdf[0].get_drawings()]


def test_the_marks_have_a_random_stream_of_their_own():
    ident = identity(1)
    a, b = draw_statement(ident, seed=1), draw_statement(ident, seed=1)
    assert strokes_of(a) == strokes_of(b) and a.truth["boxes"] == b.truth["boxes"]
    other = draw_statement(replace(ident, logo=NAMES[3], stamp=NAMES[4]), seed=1)  # other marks, and nothing else moves
    assert strokes_of(other) != strokes_of(a) and other.truth["rows"] == a.truth["rows"] and other.truth["fields"] == a.truth["fields"]
    assert draw_statement(ident, seed=2).truth["boxes"]["stamp"] != a.truth["boxes"]["stamp"]  # a new pressing each time


def test_c5_puts_another_banks_mark_or_a_slightly_edited_one_on_a_document_and_changes_nothing_else():
    ident, other = replace(identity(1), bank=BANK), replace(identity(2), bank=OTHER)
    for kind in KINDS:
        large, small = c5_other_mark(ident, kind, "large", other), c5_other_mark(ident, kind, "small", other)
        assert getattr(large, kind) == OTHER and replace(large, **{kind: ""}) == ident
        assert getattr(small, kind) == f"{BANK}/edit" and replace(small, **{kind: ""}) == ident
    for bad in (("seal", "large", other), ("logo", "huge", other), ("logo", "large", ident)):  # a kind, a strength, a bank that is no other
        with pytest.raises(ValueError):
            c5_other_mark(ident, *bad)


# --- the issuer line, which the marks are found by and grouped by

def line_page(*rows):
    """A page of one-word lines 100 px apart, top down; a row is (text, height)."""
    words = [Word(id=f"w{i}", text=t, box=(100.0, 100.0 * (i + 1), 100.0 + 20 * len(t), 100.0 * (i + 1) + h)) for i, (t, h) in enumerate(rows)]
    return Page(n=1, width=800, height=1200, read_mode="ocr", quality_class="good", words=words)


def test_the_issuer_line_is_the_tallest_line_that_reads_as_a_name_and_not_a_stray_mark():
    assert text_of(issuer_line(lines_of(line_page(("入", 60), ("Halcyon", 30), ("Statement", 20)))).words) == "Halcyon"  # a stamp read as one tall character
    assert text_of(issuer_line(lines_of(line_page(("Halcyon", 30), ("Statement", 30)))).words) == "Halcyon"  # of equals, the topmost
    assert issuer_line(lines_of(line_page(("入", 60), ("x1", 30)))) is None  # fewer than three letters or digits
    assert issuer_line([]) is None


def test_a_stray_character_taller_than_the_name_does_not_become_the_issuer_of_a_statement():
    page = line_page(("入", 70), ("Halcyon", 40), ("Statement", 20))
    doc = Document(id="D1", sha256="0", filename="a.png", stored_path="a.png", doc_type="bank_statement", pages=[page])
    fields = {f.name: f for f in extract_document(doc, load_specs()["bank_statement"], TH)}
    assert fields["bank"].raw == "Halcyon"


def test_the_specs_say_which_documents_carry_a_logo_and_where_the_caption_of_the_stamp_is():
    specs = load_specs()
    assert specs["bank_statement"].logo and specs["bank_statement"].stamp == ["bank seal"]
    assert specs["loan_application"].logo and specs["loan_application"].stamp == ["for bank use"]
    assert not specs["payslip"].logo and specs["payslip"].stamp == []  # the round stamp of a payslip is not compared


# --- the comparison

def pair(bank=BANK, seed=1, **owners):
    """A statement and an application of one bank; `owners` (logo=, stamp=) give the application another bank's marks, as C5 does."""
    ident = replace(identity(seed), bank=bank)
    return draw_statement(ident, seed=seed), draw_application(replace(ident, **owners), seed=seed + 30)


def mark_findings(case):
    return [f for f in case.findings if f.detector == "mark"]


def compared(events, kind=None):
    return [e.data for e in events if e.event == "mark_compared" and kind in (None, e.data["kind"])]


@pytest.mark.parametrize("seed, bank", [(1, NAMES[3]), (2, NAMES[4]), (3, NAMES[1])])
def test_one_banks_marks_on_two_documents_are_compared_and_pass_without_a_finding(tmp_path, seed, bank):
    case, events = run(tmp_path, *pdfs(*pair(bank, seed)))
    assert case.findings == []  # no detector at all, this one or another, has anything to say about the genuine pair
    for kind, limit in (("logo", TH.logo_dist), ("stamp", TH.stamp_dist)):
        (done,) = compared(events, kind)
        assert sorted(done["docs"]) == ["D1", "D2"] and done["differs"] is False and done["distance"] < limit and done["limit"] == limit


@pytest.mark.parametrize("kind, noun", [("logo", "Logo"), ("stamp", "Stamp")])
def test_another_banks_mark_on_one_document_is_an_inconsistency_that_points_at_both_marks(tmp_path, kind, noun):
    st, ap = pair(**{kind: OTHER})
    case, events = run(tmp_path, *pdfs(st, ap))
    (f,) = mark_findings(case)
    assert (f.fclass, f.family) == ("inconsistency", "cross_document")
    assert f.title.startswith(f"{noun} differs between D1 ") and " and D2 " in f.title
    limit = getattr(TH, f"{kind}_dist")
    assert f"{limit:g}" in f.detail and not VERDICT.search(f.title + f.detail)
    (done,) = compared(events, kind)
    assert done["differs"] is True and done["distance"] > limit and done["limit"] == limit
    (rest,) = compared(events, "stamp" if kind == "logo" else "logo")
    assert rest["differs"] is False  # the mark that was left alone still passes
    boxes = {e.doc: e for e in f.evidence}
    assert sorted(boxes) == ["D1", "D2"] and {e.page for e in f.evidence} == {1} and {e.note for e in f.evidence} == {f"{kind} on page 1"}
    for doc, drawn in (("D1", st), ("D2", ap)):
        assert iou(boxes[doc].box, drawn.truth["boxes"][kind][1:]) > 0.6, doc


def test_with_three_documents_every_pair_is_compared_and_the_odd_one_is_in_each_finding(tmp_path):
    ident = replace(identity(1), bank=BANK)
    files = [("a.pdf", draw_statement(ident, seed=1).pdf), ("b.pdf", draw_application(ident, seed=31).pdf),
             ("c.pdf", draw_statement(replace(ident, stamp=OTHER), seed=61).pdf)]
    case, events = run(tmp_path, *files)
    found = mark_findings(case)
    assert len(found) == 2 and all(f.title.startswith("Stamp differs") and "D3" in f.title for f in found)
    assert len(compared(events, "stamp")) == 3 and len(compared(events, "logo")) == 3


def test_marks_of_other_issuers_are_not_compared_with_each_other(tmp_path):
    ident = identity(1)
    files = [("a.pdf", draw_statement(replace(ident, bank=BANK), seed=1).pdf), ("b.pdf", draw_application(replace(ident, bank=BANK), seed=31).pdf),
             ("c.pdf", draw_statement(replace(ident, bank=OTHER), seed=61).pdf)]
    case, events = run(tmp_path, *files)
    assert mark_findings(case) == []
    assert {(e["kind"], tuple(sorted(e["docs"]))) for e in compared(events)} == {("logo", ("D1", "D2")), ("stamp", ("D1", "D2"))}


def test_a_stamp_with_one_ring_less_is_found(tmp_path):
    ident = replace(identity(1), bank=BANK)
    edited = c5_other_mark(ident, "stamp", "small", identity(2))
    case, _ = run(tmp_path, ("a.pdf", draw_statement(ident, seed=1).pdf), ("b.pdf", draw_application(edited, seed=31).pdf))
    (f,) = mark_findings(case)
    assert f.title.startswith("Stamp differs")


def speck_beside(drawn, kind, gap, side=4):
    """The page with a black speck (side x side px) `gap` px right of the ink of this mark, level with its middle: pixels of the 200-dpi page."""
    _, x0, y0, x1, y1 = drawn.truth["boxes"][kind]
    mid = (y0 + y1) / 2
    return blacken(drawn.pdf, (x1 + gap, mid - side / 2, x1 + gap + side, mid + side / 2))


@pytest.mark.parametrize("side", [4, 8])
@pytest.mark.parametrize("kind, gap", [("logo", 70), ("stamp", 20)])
def test_a_speck_in_the_window_beside_a_genuine_mark_does_not_make_it_differ(tmp_path, kind, gap, side):
    st, ap = pair()
    case, events = run(tmp_path, ("a.pdf", speck_beside(st, kind, gap, side)), ("b.pdf", ap.pdf))
    assert case.findings == []
    (done,) = compared(events, kind)
    assert done["differs"] is False and done["distance"] < 2, done


def with_logo(drawn, draw):
    """The PDF with the area of the logo whited out and `draw(page, rect)` drawn in its place (rect in points)."""
    with pymupdf.open(stream=drawn.pdf, filetype="pdf") as d:
        _, x0, y0, x1, y1 = drawn.truth["boxes"]["logo"]
        r = pymupdf.Rect(x0 / PX, y0 / PX, x1 / PX, y1 / PX)
        d[0].draw_rect(pymupdf.Rect(r.x0 - 1, r.y0 - 1, r.x1 + 1, r.y1 + 1), color=None, fill=(1, 1, 1))
        draw(d[0], r)
        return d.tobytes()


FILLED = {  # logos with ink wider than the paper estimate's window: a solid disc, and a ring whose stroke is 20 px
    "disc": lambda page, r: page.draw_circle(r.tl + (r.br - r.tl) / 2, r.width / 2 - 1, color=None, fill=(0.05, 0.1, 0.3)),
    "wide ring": lambda page, r: page.draw_circle(r.tl + (r.br - r.tl) / 2, r.width / 2 - 10 / PX - 1, color=(0.05, 0.1, 0.3), width=20 / PX),
}


@pytest.mark.parametrize("shape", FILLED)
def test_a_filled_logo_is_found_and_compared_like_a_drawn_one(tmp_path, shape):
    st, ap = pair()
    case, events = run(tmp_path, ("a.pdf", with_logo(st, FILLED[shape])), ("b.pdf", with_logo(ap, FILLED[shape])))
    assert case.findings == []  # the logos were found (no limitation) and are alike (no inconsistency)
    (done,) = compared(events, "logo")
    assert done["differs"] is False and done["distance"] < 2, done


def test_one_marked_document_has_nothing_to_compare_and_says_nothing(tmp_path):
    case, events = run(tmp_path, ("a.pdf", pair()[0].pdf))
    assert mark_findings(case) == [] and compared(events) == []


# --- what cannot be compared is a limitation and never a pass

def one_limitation(case, doc, phrase):
    (f,) = mark_findings(case)
    assert (f.fclass, f.family, f.title) == ("processing_limitation", "limitation", "Issuer marks only partly compared"), f.title
    assert doc in f.detail and phrase in f.detail and not VERDICT.search(f.title + f.detail), f.detail
    return f


def caption_box(pdf, text):
    """Where a caption is printed, (x0, y0, x1, y1) in the pixels of the 200-dpi page."""
    with pymupdf.open(stream=pdf, filetype="pdf") as d:
        (r,) = d[0].search_for(text)
    return r.x0 * PX, r.y0 * PX, r.x1 * PX, r.y1 * PX


def without(pdf, text, then=None):
    """The PDF with this caption redacted; `then` puts it back somewhere: (x, y) in points."""
    with pymupdf.open(stream=pdf, filetype="pdf") as d:
        for r in d[0].search_for(text):
            d[0].add_redact_annot(r)
        d[0].apply_redactions()
        assert not d[0].search_for(text)
        if then:
            d[0].insert_text(then, text, fontsize=8)
        return d.tobytes()


def test_a_blank_logo_area_is_a_limitation_and_not_a_pass(tmp_path):
    st, ap = pair()
    case, events = run(tmp_path, ("a.pdf", whiteout(st.pdf, st.truth["boxes"]["logo"])), ("b.pdf", ap.pdf))
    one_limitation(case, "D1", "no ink")
    assert compared(events, "logo") == [] and len(compared(events, "stamp")) == 1  # the stamps were still compared


def test_a_stamp_caption_that_is_not_found_is_a_limitation_and_not_a_pass(tmp_path):
    st, ap = pair()
    case, events = run(tmp_path, ("a.pdf", st.pdf), ("b.pdf", without(ap.pdf, "For Bank Use")))
    one_limitation(case, "D2", "caption")
    assert compared(events, "stamp") == [] and len(compared(events, "logo")) == 1


def test_a_stamp_area_full_of_printed_matter_is_a_limitation_and_not_a_comparison(tmp_path):
    st, ap = pair()
    x0, y0, *_ = caption_box(ap.pdf, "For Bank Use")
    hatched = blacken(ap.pdf, *[(x0 - 40, y0 - 300 + 7 * k, x0 + 360, y0 - 297 + 7 * k) for k in range(42)])  # 3 px bars on a 7 px pitch: 43 % ink
    case, events = run(tmp_path, ("a.pdf", st.pdf), ("b.pdf", hatched))
    one_limitation(case, "D2", "mostly ink")
    assert compared(events, "stamp") == [] and len(compared(events, "logo")) == 1


def test_a_line_across_the_stamp_area_is_a_limitation_and_not_a_comparison(tmp_path):
    st, ap = pair()
    _, _, y0, *_ = ap.truth["boxes"]["stamp"]
    case, events = run(tmp_path, ("a.pdf", st.pdf), ("b.pdf", blacken(ap.pdf, (0, y0 + 20, 1653, y0 + 28))))
    one_limitation(case, "D2", "reaches the edge")
    assert compared(events, "stamp") == [] and len(compared(events, "logo")) == 1


def test_a_stamp_caption_with_too_little_page_above_it_is_a_limitation(tmp_path):
    st, ap = pair()
    case, events = run(tmp_path, ("a.pdf", st.pdf), ("b.pdf", without(ap.pdf, "For Bank Use", then=(40, 30))))
    one_limitation(case, "D2", "too little of page 1")
    assert compared(events, "stamp") == [] and len(compared(events, "logo")) == 1


def test_a_page_of_poor_quality_is_not_compared_and_the_limitation_says_so(tmp_path):
    case, ctx = read_only(tmp_path, pdfs(*pair()))
    case.documents[0].pages[0].quality_class = "poor"
    add_findings(case, ctx, compare_marks(case, ctx))
    one_limitation(case, "D1", "poor")
    assert compared(ctx.audit.events()) == []


def test_a_page_with_no_line_to_take_for_the_issuer_is_a_limitation(tmp_path):
    case, ctx = read_only(tmp_path, pdfs(*pair()))
    case.documents[0].pages[0].words = []
    add_findings(case, ctx, compare_marks(case, ctx))
    one_limitation(case, "D1", "issuer line")
    assert compared(ctx.audit.events()) == []


@pytest.mark.parametrize("bank", ["SBI", "HDFC", "ICICI", "Canara", "Merid"])
def test_a_short_issuer_name_does_not_pull_the_line_under_it_into_the_logo_window(tmp_path, bank):
    st, ap = pair(bank)  # under a short name the subtitle ("Statement of Account", "Personal Loan Application") runs on past the whole logo
    case, events = run(tmp_path, ("a.pdf", st.pdf), ("b.pdf", ap.pdf))
    assert case.findings == []
    (done,) = compared(events, "logo")
    assert done["differs"] is False and done["distance"] < 2, done


@pytest.mark.parametrize("bank", ["Axis Bank", "Meridian Te"])
def test_a_line_that_stops_inside_the_logo_is_a_limitation_and_not_a_difference(tmp_path, bank):
    st, ap = pair(bank)  # the subtitle of the statement ends under the logo, the one of the application past it: the two cut it differently
    case, events = run(tmp_path, ("a.pdf", st.pdf), ("b.pdf", ap.pdf))
    one_limitation(case, "D1", "ends inside the logo")
    assert compared(events, "logo") == []


def test_two_marked_documents_that_name_different_issuers_are_one_limitation_and_not_silence(tmp_path):
    ident = identity(1)
    st = draw_statement(replace(ident, bank="Axis Bank"), seed=1)
    ap = draw_application(replace(ident, bank="Axis Bank Ltd.", stamp=OTHER), seed=31)  # a stamp of another bank too: nothing said so far
    case, events = run(tmp_path, ("a.pdf", st.pdf), ("b.pdf", ap.pdf))
    f = one_limitation(case, "D1", "no other document has an issuer line like")
    assert "D2" in f.detail and "Axis Bank Ltd." in f.detail and {e.doc for e in f.evidence} == {"D1", "D2"}, f.detail
    assert compared(events) == []


def test_a_scan_with_too_few_words_to_find_its_turn_is_a_limitation(tmp_path):
    case, ctx = read_only(tmp_path, pdfs(*pair()))
    page = case.documents[0].pages[0]
    page.read_mode, page.words = "ocr", sorted(page.words, key=lambda w: w.box[1])[:5]  # the name and a little more
    add_findings(case, ctx, compare_marks(case, ctx))
    one_limitation(case, "D1", "fewer than the 12 needed")
    assert compared(ctx.audit.events()) == []


# --- scans, read by the real reader

def scan_files(st, ap, la, lb):
    """The pair as files: a level of None leaves that document digital; seeds 1 and 2 turn the scans differently."""
    return [("a.jpg", simulate_scan(st.pdf, la, seed=1)) if la else ("a.pdf", st.pdf),
            ("b.jpg", simulate_scan(ap.pdf, lb, seed=2)) if lb else ("b.pdf", ap.pdf)]


@ocr
@pytest.mark.parametrize("la, lb", [("mild", "150dpi"), (None, "150dpi"), ("120dpi", None)])
def test_scans_are_straightened_and_compared_like_digital_pages(tmp_path, la, lb):
    st, ap = pair()
    case, events = run(tmp_path / "same", *scan_files(st, ap, la, lb))
    print([(f.title, f.detail) for f in mark_findings(case)], compared(events))
    assert mark_findings(case) == [] and len(compared(events)) == 2 and not any(e["differs"] for e in compared(events))

    st, ap = pair(logo=OTHER, stamp=OTHER)
    files = scan_files(st, ap, la, lb)
    case, events = run(tmp_path / "other", *files)
    print([(f.title, f.detail) for f in mark_findings(case)], compared(events))
    found = {f.title.split()[0].lower(): f for f in mark_findings(case)}
    assert sorted(found) == ["logo", "stamp"] and all(f.fclass == "inconsistency" for f in found.values())
    for kind, f in found.items():
        for e, drawn, level, angle in zip(sorted(f.evidence, key=lambda e: e.doc), (st, ap), (la, lb), (1, 2)):
            want = drawn.truth["boxes"][kind][1:]
            if level:
                with Image.open(io.BytesIO(files[angle - 1][1])) as im:
                    want = to_scan_frame(want, im.size, angle)
            assert iou(e.box, want) > 0.6, (kind, e.doc, e.box, want)


@ocr
@pytest.mark.parametrize("la, lb", [("mild", "150dpi"), ("120dpi", None)])
def test_a_short_issuer_name_is_handled_in_scans_like_on_digital_pages(tmp_path, la, lb):
    st, ap = pair("SBI")  # its subtitles run on past the whole logo: compared, with the words under it erased
    case, events = run(tmp_path / "clear", *scan_files(st, ap, la, lb))
    assert case.findings == []
    (done,) = compared(events, "logo")
    assert done["differs"] is False and done["distance"] < 5, done

    st, ap = pair("Axis Bank")  # the subtitle of the statement stops under the logo: not compared, and no difference reported
    case, events = run(tmp_path / "cut", *scan_files(st, ap, la, lb))
    one_limitation(case, "D1", "ends inside the logo")
    assert compared(events, "logo") == []
