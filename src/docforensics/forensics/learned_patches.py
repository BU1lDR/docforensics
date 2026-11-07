"""Measurements for the learned patch detector (Task 29). Each word of a scanned page that is large enough to measure gets one row of
numbers: how its grain, edges, strokes, ink, JPEG blocks, baseline and placement compare with the other words of the same page, and
how far it sits off the line of the words beside it. A weighting learned from synthetic edits (the file learned_patches.json, made by
evaluation/train_patches.py) turns a row into a score.
Every number is a difference from the page itself, so the page's scanner, resolution and lighting drop out; no number says where on
the page the word is, or what it reads, beyond whether it has a digit in it (digits and words are compared among their own kind).
The definitions are copied here, not imported from the grain and placement checks, so that the learned weights keep meaning what they
were trained on if those checks are tuned."""
import math
import re

import cv2
import numpy as np

from ..model import Page
from ..understand.layout import MIN_WORDS, page_turn, upright

FEATURES = ("grain", "ring_grain", "ring_step", "edge", "stroke", "ink", "grid_on", "grid_other", "drift", "z_centre", "z_height", "z_right",
            "line_pair", "line_mates")
_MIN_PIXELS = 100   # paper pixels a word needs before it is measured (as in the grain check)
_MIN_SIZE = (24, 12)  # px: narrower or lower boxes are fragments of a line, not words
_MIN_CLASS = 6      # words of its own kind (with a digit, or without) a word needs to be compared with; below it, with all words
_CLIPPED = 250      # paper brighter than this is cut at white by the scanner
_BLUR = 1.5
_RING = (3, 14)     # px: the ring of paper around a word starts this far outside its box and ends that far
_MIN_RING = 150     # paper pixels the ring needs
_GRID = 8           # the JPEG block size
_GRID_PAD = 4       # px of paper around a box that its block-grid measure looks at
_SHEAR = np.linspace(-0.07, 0.07, 29)  # slopes (rows per column) tried for the baseline of a word; 0.07 is four degrees
_MIN_SLOPE_WIDTH = 40
_AMOUNT = re.compile(r"^[\d,]*\d\.\d\d$")
_MAX_TURN = 2.9     # degrees; a page turned more than this has no placement measure
_FLOOR = {"centre": 1.5, "height": 2.5, "right edge": 2.5}
_ROW_TOL, _ROW_REACH, _COLUMN_TOL, _COLUMN_REACH, _MIN_GROUP = 0.25, 0.6, 5.0, 40.0, 4
_SAME_LINE = 0.6    # median word heights: words whose centres are closer than this across the line are on one line
_OVERLAP = 0.2      # median word heights: a word may reach this far over its neighbour's edge and still count as beside it


def _grid_excess(gray: np.ndarray, paper: np.ndarray, box, pad: int = _GRID_PAD) -> tuple[float, float]:
    """How much stronger the picture changes across the 8 x 8 block edges of the page's own grid than elsewhere, over the paper pixels
    of the box and `pad` px around it: (at the page's grid, at the strongest other phase), each the mean of the two directions.
    A part that was saved on another grid and pasted in has its block edges at another phase."""
    h, w = gray.shape
    x0, y0, x1, y1 = max(int(box[0]) - pad, 0), max(int(box[1]) - pad, 0), min(int(box[2]) + pad + 1, w), min(int(box[3]) + pad + 1, h)
    g, p = gray[y0:y1, x0:x1], paper[y0:y1, x0:x1]
    on, other = [], []
    for axis, origin in ((1, x0), (0, y0)):
        step = np.abs(np.diff(g, axis=axis))
        ok = p[:, 1:] & p[:, :-1] if axis == 1 else p[1:] & p[:-1]
        along = (step * ok).sum(axis=1 - axis), ok.sum(axis=1 - axis)  # per position across the other axis, summed away
        phase = (np.arange(step.shape[axis]) + origin) % _GRID
        # a step between pixel i and i + 1 lies on the block edge when i % 8 == 7 (the edge is after the last pixel of a block)
        mean = np.array([along[0][phase == k].sum() / max(along[1][phase == k].sum(), 1) for k in range(_GRID)])
        excess = np.array([mean[k] / max(np.delete(mean, k).mean(), 1e-6) - 1 for k in range(_GRID)])
        on.append(excess[_GRID - 1])
        other.append(np.delete(excess, _GRID - 1).max())
    return float(np.mean(on)), float(np.mean(other))


def _shear_slope(ink: np.ndarray) -> float:
    """The slope (rows per column) at which the ink of a crop lines up best into horizontal lines: the one that makes the row profile
    after shearing the sharpest. 0 for a crop with no ink; the smaller slope on a tie."""
    h, w = ink.shape
    if not ink.any():
        return 0.0
    xs = np.round(np.arange(w) - (w - 1) / 2)
    cols, rows = np.arange(w)[None, :], np.arange(h)[:, None]
    best, slope = -1.0, 0.0
    for t in _SHEAR[np.argsort(np.abs(_SHEAR), kind="stable")]:
        prof = ink[np.clip(rows + np.round(t * xs).astype(int)[None, :], 0, h - 1), cols].sum(axis=1)
        score = float((prof * prof).sum())
        if score > best * (1 + 1e-9):
            best, slope = score, float(t)
    return slope


def _offsets(key: np.ndarray, tol: float, reach: float) -> np.ndarray:
    """Each value's distance from the nearest line (a run of at least four values within `tol` of the run's median), NaN beyond `reach`."""
    runs: list[list[int]] = []
    for i in np.argsort(key):
        if runs and key[i] - np.median(key[runs[-1]]) <= tol:
            runs[-1].append(int(i))
        else:
            runs.append([int(i)])
    at = np.array([np.median(key[r]) for r in runs if len(r) >= _MIN_GROUP])
    if not len(at):
        return np.full(len(key), np.nan)
    off = key - at[np.abs(key[:, None] - at[None, :]).argmin(axis=1)]
    return np.where(np.abs(off) <= reach, off, np.nan)


def _z(off: np.ndarray, floor: float) -> np.ndarray:
    """|offset| in units of the page's usual spread of such offsets (1.4826 times the median |offset|, never below `floor`)."""
    seen = np.abs(off[~np.isnan(off)])
    return np.abs(off) / max(1.4826 * float(np.median(seen)) if seen.size else 0.0, floor)


def _placement(page: Page) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """z of each word's centre against its row, and of each figure's height and right edge against the page's figures and its column;
    NaN where the word has no row or is no figure, or the page cannot be straightened."""
    n = len(page.words)
    nan = np.full(n, np.nan)
    if n < MIN_WORDS:
        return nan, nan, nan
    deg = page_turn(page.words, page.width, page.height)
    if abs(deg) > _MAX_TURN:
        return nan, nan, nan
    u, v, wd, ht = upright(page.words, page.width, page.height, deg)
    scale = 1.5 if page.quality_class == "degraded" else 1.0
    med = float(np.median(ht))
    centre = _z(_offsets(v, _ROW_TOL * med, _ROW_REACH * med), _FLOOR["centre"] * scale)
    figs = [i for i, w in enumerate(page.words) if _AMOUNT.match(w.text)]
    height, right = nan.copy(), nan.copy()
    if len(figs) >= _MIN_GROUP:
        off = nan.copy()
        off[figs] = ht[figs] - np.median(ht[figs])
        height = _z(off, _FLOOR["height"] * scale)
        off = nan.copy()
        off[figs] = _offsets((u + wd / 2)[figs], _COLUMN_TOL, _COLUMN_REACH)
        right = _z(off, _FLOOR["right edge"] * scale)
    return centre, height, right


def _line_offsets(page: Page) -> tuple[np.ndarray, np.ndarray]:
    """How far each word sits off the line of the words beside it, in px on the straightened page, as the smallest of its centre, top
    and bottom (a letter that hangs below the line moves the bottom and the centre, not the top). `pair`: against the nearest word to its
    left and to its right on the same line. `mates`: against the median of all the words on the line, with two at least. NaN where
    there is no such word, and for a page that has too few words or is turned too far to be straightened. Unlike the placement check,
    this needs no row of four, and works on any word."""
    n = len(page.words)
    pair, mates = np.full(n, np.nan), np.full(n, np.nan)
    if n < MIN_WORDS:
        return pair, mates
    deg = page_turn(page.words, page.width, page.height)
    if abs(deg) > _MAX_TURN:
        return pair, mates
    u, v, wd, ht = upright(page.words, page.width, page.height, deg)
    med = float(np.median(ht))
    lo, hi = u - wd / 2, u + wd / 2
    edge = np.stack([v, v - ht / 2, v + ht / 2])  # centre, top, bottom
    same = (np.abs(v[:, None] - v[None, :]) < _SAME_LINE * med) & ~np.eye(n, dtype=bool)
    for i in range(n):
        on = np.flatnonzero(same[i])
        if not on.size:
            continue
        left, right = on[hi[on] <= lo[i] + _OVERLAP * med], on[lo[on] >= hi[i] - _OVERLAP * med]
        near = ([left[np.argmax(hi[left])]] if left.size else []) + ([right[np.argmin(lo[right])]] if right.size else [])
        if near:
            pair[i] = np.abs(edge[:, near] - edge[:, [i]]).min()
        if on.size >= 2:
            mates[i] = np.abs(edge[:, i] - np.median(edge[:, on], axis=1)).min()
    return pair, mates


def _log_vs_kind(values: np.ndarray, digit: np.ndarray) -> np.ndarray:
    """log of each value over the median of the words of its kind on the page (with a digit, or without; all words if the kind is small)."""
    out = np.empty(len(values))
    for kind in (True, False):
        m = digit == kind
        if m.any():
            ref = values[m] if m.sum() >= _MIN_CLASS else values
            out[m] = np.log((values[m] + 1e-3) / (np.median(ref) + 1e-3))
    return out


def page_features(gray: np.ndarray, page: Page) -> tuple[list[int], np.ndarray]:
    """The measurable words of a page (indices into page.words) and one row of FEATURES for each; NaN where a measure does not exist."""
    h, w = gray.shape
    background = cv2.medianBlur(gray.astype(np.uint8), 31)
    dark = gray < background.astype(np.float32) - 40
    paper = ~(cv2.dilate(dark.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0) & (background <= _CLIPPED)
    residual = gray - cv2.GaussianBlur(gray, (0, 0), _BLUR)
    grad = cv2.magnitude(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3))
    darkness = np.clip(background.astype(np.float32) - gray, 0, None)
    idx: list[int] = []
    raw: list[list[float]] = []   # grain, ring_grain, ring_step, edge, stroke, ink, grid_on, grid_other, slope, width
    for i, word in enumerate(page.words):
        x0, y0 = max(int(word.box[0]), 0), max(int(word.box[1]), 0)
        x1, y1 = min(int(word.box[2]) + 1, w), min(int(word.box[3]) + 1, h)
        if x1 - x0 < _MIN_SIZE[0] or y1 - y0 < _MIN_SIZE[1]:
            continue
        sl = (slice(y0, y1), slice(x0, x1))
        inside = paper[sl]
        if int(inside.sum()) < _MIN_PIXELS:
            continue
        grain = float(residual[sl][inside].std())
        ex0, ey0, ex1, ey1 = max(x0 - _RING[1], 0), max(y0 - _RING[1], 0), min(x1 + _RING[1], w), min(y1 + _RING[1], h)
        ring = paper[ey0:ey1, ex0:ex1].copy()
        ring[max(y0 - _RING[0] - ey0, 0):y1 + _RING[0] - ey0, max(x0 - _RING[0] - ex0, 0):x1 + _RING[0] - ex0] = False
        if int(ring.sum()) >= _MIN_RING:
            ring_grain = math.log((grain + 1e-3) / (float(residual[ey0:ey1, ex0:ex1][ring].std()) + 1e-3))
            ring_step = float(gray[sl][inside].mean() - gray[ey0:ey1, ex0:ex1][ring].mean())
        else:
            ring_grain = ring_step = float("nan")
        ink = dark[sl]
        starts = int((ink[:, 1:] & ~ink[:, :-1]).sum() + ink[:, 0].sum())
        on, other = _grid_excess(gray, paper, word.box)
        slope = _shear_slope(darkness[sl]) if x1 - x0 >= _MIN_SLOPE_WIDTH else float("nan")
        raw.append([grain, ring_grain, ring_step, float(np.percentile(grad[sl], 95)), ink.sum() / max(starts, 1), float(ink.mean()),
                    on, other, slope, float(x1 - x0)])
        idx.append(i)
    if not idx:
        return [], np.empty((0, len(FEATURES)))
    r = np.array(raw)
    digit = np.array([any(c.isdigit() for c in page.words[i].text) for i in idx])
    centre, height, right = _placement(page)
    pair, mates = _line_offsets(page)
    tall = float(np.median([w.box[3] - w.box[1] for w in page.words]))  # offsets in median word heights: the page's resolution drops out
    slope_ref = np.nanmedian(r[:, 8]) if not np.isnan(r[:, 8]).all() else 0.0
    x = np.column_stack([
        np.log((r[:, 0] + 1e-3) / (float(np.median(r[:, 0])) + 1e-3)), r[:, 1], r[:, 2],
        _log_vs_kind(r[:, 3], digit), _log_vs_kind(r[:, 4], digit), _log_vs_kind(r[:, 5], digit),
        r[:, 6] - np.median(r[:, 6]), r[:, 7] - np.median(r[:, 7]),
        np.abs(r[:, 8] - slope_ref) * r[:, 9], centre[idx], height[idx], right[idx], pair[idx] / tall, mates[idx] / tall])
    return idx, x
