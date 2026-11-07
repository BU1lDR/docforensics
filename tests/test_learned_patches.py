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
