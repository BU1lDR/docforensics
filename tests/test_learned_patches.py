"""The measurements of the learned patch detector (Task 29). These tests are about mechanisms: that each measurement sees what it is
named for on a picture built to show it, and that the features of a page are the same twice. How often the trained detector finds an
edit is measured by evaluation/train_patches.py and written to eval/patches/, not here."""
import io

import numpy as np
from PIL import Image

from docforensics.forensics import learned_patches as lp


def jpeg_grid_picture(size=(96, 160), seed=0, quality=30):
    """A smooth, slightly noisy picture saved as a JPEG and read back: its 8 x 8 blocks lie on the picture's own grid."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:size[0], 0:size[1]]
    base = 200 + 20 * np.sin(xx / 17.0) + 15 * np.cos(yy / 11.0) + rng.normal(0, 4, size)
    out = io.BytesIO()
    Image.fromarray(np.clip(base, 0, 255).astype(np.uint8)).save(out, "JPEG", quality=quality)
    return np.asarray(Image.open(io.BytesIO(out.getvalue())).convert("L"), dtype=np.float32)


def test_grid_excess_is_on_the_global_grid_for_a_picture_saved_once_and_elsewhere_for_a_shifted_one():
    img = jpeg_grid_picture()
    paper = np.ones(img.shape, bool)
    on, other = lp._grid_excess(img, paper, (8, 8, 152, 88))
    assert on > 0.15 and on > 2 * other  # the blocks stand where the picture's grid says
    shifted = jpeg_grid_picture()[5:, 3:]  # the same blocks, 3 px left and 5 px up of the grid that a crop's coordinates have
    on_s, other_s = lp._grid_excess(shifted, np.ones(shifted.shape, bool), (8, 8, 145, 83))
    assert other_s > 0.15 and other_s > 2 * on_s


def test_shear_slope_finds_the_slope_of_a_line_of_bars():
    h, w, slope = 40, 120, 0.03
    ink = np.zeros((h, w), np.float32)
    for x in range(w):
        for top in (8, 26):
            y = int(round(top + slope * (x - w / 2)))
            ink[y:y + 4, x] = 1.0
    assert abs(lp._shear_slope(ink) - slope) < 0.005
    assert abs(lp._shear_slope(ink[:, ::-1].copy()) + slope) < 0.005  # mirrored, the slope changes its sign
    assert abs(lp._shear_slope(np.zeros((h, w), np.float32))) < 1e-9  # no ink: no slope, not an arbitrary one


def page_of(rows):
    """A scanned-looking page of words; each row is (text, x0, y0, x1, y1)."""
    from docforensics.model import Page, Word
    words = [Word(id=f"w{i}", text=t, box=(x0, y0, x1, y1)) for i, (t, x0, y0, x1, y1) in enumerate(rows)]
    return Page(n=1, width=1654, height=2339, read_mode="ocr", quality_class="good", words=words)


def label_value_page(lines=8, off_line=None, drop=0.0, descender=None):
    """`lines` rows, each a label and a value of the same height on one line; the value of row `off_line` sits `drop` px lower, and the label
    of row `descender` has a box 6 px taller at the bottom (a letter that hangs below the line) with the same top."""
    rows = []
    for r in range(lines):
        y = 300 + 60 * r
        rows.append(("Label", 100, y, 260, y + 30 + (6 if r == descender else 0)))
        rows.append(("1,000.00", 400, y + (drop if r == off_line else 0), 560, y + 30 + (drop if r == off_line else 0)))
    return page_of(rows)


def test_a_word_that_sits_off_the_line_of_its_neighbour_is_named_by_it_and_a_hanging_letter_is_not():
    page = label_value_page(off_line=4, drop=8.0, descender=2)
    pair, mates = lp._line_offsets(page)
    value4, label4 = 2 * 4 + 1, 2 * 4
    assert abs(pair[value4] - 8.0) < 0.5 and abs(pair[label4] - 8.0) < 0.5  # a pair is off by the same amount from both sides
    assert np.nanmax(np.delete(pair, [label4, value4])) < 0.5               # the other rows are straight, the hanging letter included
    assert np.isnan(mates).all()                                            # two words on a line: no median of the others to compare with


def test_with_three_words_on_a_line_the_odd_one_out_is_the_one_far_from_the_median_of_the_others():
    rows = [(t, x, 300 + 60 * r + (6 if (r, t) == (3, "b") else 0), x + 100, 330 + 60 * r + (6 if (r, t) == (3, "b") else 0))
            for r in range(6) for t, x in (("a", 100), ("b", 300), ("c", 500))]
    pair, mates = lp._line_offsets(page_of(rows))
    b3 = 3 * 3 + 1
    assert abs(mates[b3] - 6.0) < 0.5 and np.delete(mates, [b3 - 1, b3, b3 + 1]).max() < 0.5
    assert abs(mates[b3 - 1] - 3.0) < 0.5 and abs(mates[b3 + 1] - 3.0) < 0.5  # its mates are half-way off the median of {themselves-and-the-other, b}


def test_a_page_turned_by_a_degree_is_straightened_before_the_lines_are_compared():
    import math
    t = math.radians(1.2)
    rows = []
    for r in range(8):
        for x in (100, 400):
            y = 300 + 60 * r + math.sin(t) * (x - 827)  # every row slopes the same, as on a turned scan
            rows.append(("w", x, y, x + 150, y + 30))
    pair, _ = lp._line_offsets(page_of(rows))
    assert np.nanmax(pair) < 1.0
