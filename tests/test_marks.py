"""Issuer marks (Task 26): the logos and stamps the generator draws on a bank's documents, and the comparison across them."""
import itertools
import random
from dataclasses import replace

import pymupdf
import pytest

from datagen import marks
from datagen.fictional import BANKS, identity
from datagen.layouts import PX
from datagen.layouts.application import draw_application
from datagen.layouts.statement import draw_statement

NAMES = [f"{b} Test Bank" for b in BANKS]
KINDS = ("logo", "stamp")
CAPTIONS = {"statement": "Bank Seal", "application": "For Bank Use"}


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
