"""Placement of text on a scan (design 7.5, S1 and S2). A scanned page is turned a little, so the page is first straightened by the
turn that puts its word centres into the sharpest rows. Rows (and columns of figures) are then the lines that at least four words (or
figures) share. A word is measured against the nearest row by its centre; a figure is also measured against the nearest column by its
right edge, and by its height against the other figures of the page (the height of a word's box depends on its glyphs and on the
slant of its whole line, so only the single-word boxes of figures are compared). A piece taken from another scan keeps the turn and
scale of that scan, and text typed over an erased place is seldom set exactly like the text beside it. The spread that a difference is
judged by is taken over the whole page, so that a few displaced words, or one displaced row, do not widen it. Only a difference is
reported, and only as an observation: scanners, folds and curled pages move words too."""
import math
import re

import numpy as np

from ..findings import doc_evidence, limitation, quote
from ..model import Case, Document, Evidence, Finding, Word
from ..pipeline import Ctx

DETECTOR = "scan_layout"
LISTED = 12         # words named in one finding; the rest are counted
MIN_WORDS = 12      # words a page needs before its rows can be found
_MIN_GROUP = 4      # words in a row, or figures in a column, that make a line to measure against
# The usual spread of differences is never taken below these (px; 1.5 times as much on a degraded page), so with layout_k = 4 a
# difference must be 6, 10 and 10 px. Set from the largest differences on genuine simulated statements (docs/spike.md, Task 17).
_FLOOR = {"centre": 1.5, "height": 2.5, "right edge": 2.5}
_ROW_TOL = 0.25     # words are in one row when their centres lie within this many median word heights of the row's median
_ROW_REACH = 0.6    # a word is measured against the nearest row when it lies within this many median word heights of it
_COLUMN_TOL = 5.0   # px: figures are in one column when their right edges lie this close to the column's median
_COLUMN_REACH = 40.0
_SEARCH_DEG = 3.0   # the largest turn looked for, either way
_AMOUNT = re.compile(r"^[\d,]*\d\.\d\d$")


def _sharp(v: np.ndarray) -> float:
    """How sharply the values pile up: the sum of the squared counts of 3 px bins, over three offsets of the bins."""
    return sum(float((np.bincount(((v - v.min() + o) // 3).astype(int)) ** 2).sum()) for o in (0, 1, 2))


def page_turn(words: list[Word], width: float, height: float) -> float:
    """The turn of the page in degrees (anticlockwise is positive): the one under which the word centres fall into the sharpest rows."""
    b = np.array([w.box for w in words], dtype=float)
    x, y = (b[:, 0] + b[:, 2]) / 2 - width / 2, (b[:, 1] + b[:, 3]) / 2 - height / 2
    angles = np.arange(-_SEARCH_DEG, _SEARCH_DEG + 1e-9, 0.05)
    score = [_sharp(x * math.sin(math.radians(a)) + y * math.cos(math.radians(a))) for a in angles]
    return float(angles[int(np.argmax(score))])


def _upright(words: list[Word], width: float, height: float, deg: float) -> tuple[np.ndarray, ...]:
    """Centre along the row, centre across it, width and height of each word as it would stand on a page that is not turned. The
    reader's box is the box around the word's turned quadrilateral, so width and height are recovered from it."""
    t = math.radians(deg)
    c, s = math.cos(t), abs(math.sin(t))
    b = np.array([w.box for w in words], dtype=float)
    x, y = (b[:, 0] + b[:, 2]) / 2 - width / 2, (b[:, 1] + b[:, 3]) / 2 - height / 2
    big_w, big_h = b[:, 2] - b[:, 0], b[:, 3] - b[:, 1]
    d = c * c - s * s
    return (x * c - y * math.sin(t), x * math.sin(t) + y * c,
            np.maximum((c * big_w - s * big_h) / d, 1.0), np.maximum((c * big_h - s * big_w) / d, 1.0))


def _offsets(key: np.ndarray, tol: float, reach: float) -> tuple[np.ndarray, np.ndarray]:
    """Each value's distance from the nearest line, and that line's number; NaN and -1 where no line lies within `reach`. A line is a
    run of at least _MIN_GROUP values, taken in order, each within `tol` of the median of the run so far."""
    runs: list[list[int]] = []
    for i in np.argsort(key):
        if runs and key[i] - np.median(key[runs[-1]]) <= tol:
            runs[-1].append(int(i))
        else:
            runs.append([int(i)])
    at = np.array([np.median(key[r]) for r in runs if len(r) >= _MIN_GROUP])
    if not len(at):
        return np.full(len(key), np.nan), np.full(len(key), -1)
    near = np.abs(key[:, None] - at[None, :]).argmin(axis=1)
    off = key - at[near]
    close = np.abs(off) <= reach
    return np.where(close, off, np.nan), np.where(close, near, -1)


def _spread(off: np.ndarray, floor: float) -> float:
    seen = np.abs(off[~np.isnan(off)])
    return max(1.4826 * float(np.median(seen)) if seen.size else 0.0, floor)


def layout_consistency(case: Case, doc: Document, ctx: Ctx) -> list[Finding]:
    k = ctx.th.layout_k
    out: list[Finding] = []
    issues: list[str] = []
    for pg in doc.pages:
        if pg.read_mode != "ocr":
            continue
        if pg.quality_class == "poor":
            issues.append(f"page {pg.n} is of poor quality (class poor), so the placement of its words was not compared")
            continue
        words = pg.words
        if len(words) < MIN_WORDS:
            issues.append(f"page {pg.n} has {len(words)} words, fewer than the {MIN_WORDS} needed to find its rows")
            continue
        deg = page_turn(words, pg.width, pg.height)
        if abs(deg) > _SEARCH_DEG - 0.1:
            issues.append(f"page {pg.n} is turned by {deg:+.1f} degrees or more, as far as the search goes, so its rows were not trusted")
            continue
        u, v, wd, ht = _upright(words, pg.width, pg.height, deg)
        scale = 1.5 if pg.quality_class == "degraded" else 1.0  # a degraded page is read less exactly
        med = float(np.median(ht))
        off_v, row = _offsets(v, _ROW_TOL * med, _ROW_REACH * med)
        if (row < 0).all():
            issues.append(f"page {pg.n} has no row of {_MIN_GROUP} words or more to measure against")
            continue
        figs = [i for i, w in enumerate(words) if _AMOUNT.match(w.text)]
        off_h, off_r = np.full(len(words), np.nan), np.full(len(words), np.nan)
        if len(figs) >= _MIN_GROUP:
            off_h[figs] = ht[figs] - np.median(ht[figs])
            off_r[figs] = _offsets((u + wd / 2)[figs], _COLUMN_TOL, _COLUMN_REACH)[0]
        offsets = {"centre": off_v, "height": off_h, "right edge": off_r}
        spreads = {name: _spread(off, _FLOOR[name] * scale) for name, off in offsets.items()}
        say = {"centre": ("lower", "higher", "than its row"), "height": ("taller", "shorter", "than the median of the page's figures"),
               "right edge": ("right", "left", "of its column")}
        why: dict[int, list[str]] = {}
        worst: dict[int, float] = {}
        for name, off in offsets.items():
            for i in np.flatnonzero(~np.isnan(off)):
                z = abs(off[i]) / spreads[name]
                if z > k:
                    why.setdefault(int(i), []).append(f"{name} {abs(off[i]):.1f} px {say[name][0 if off[i] > 0 else 1]} {say[name][2]} (z {z:.1f})")
                    worst[int(i)] = max(worst.get(int(i), 0.0), z)
        if not why:
            continue
        ranked = sorted(why, key=lambda i: -worst[i])
        ev = [Evidence(doc=doc.id, page=pg.n, box=tuple(float(b) for b in words[i].box), value=quote(words[i].text), note="; ".join(why[i]))
              for i in ranked[:LISTED]]
        top = "; ".join(f'"{quote(words[i].text)}": {why[i][0]}' for i in ranked[:3])
        usual = ", ".join(f"{n} {s:.1f} px" for n, s in spreads.items())
        floors = ", ".join(f"{_FLOOR[n] * scale:g}" for n in _FLOOR)
        weak = " The page is degraded, so the least spread is raised by half." if scale > 1 else ""
        out.append(Finding(
            fclass="observation", detector=DETECTOR, family="visual", title=f"Text lies out of line with the text around it (page {pg.n})",
            detail=f"On page {pg.n}, {len(why)} of {len(words)} words lie out of line with the text around them, after the page was straightened "
                   f"by {deg:+.2f} degrees. A word is listed when its centre differs from its row, or the height or the right edge of a figure "
                   f"from the page's other figures or its column, by more than {k:g} times the usual spread of such differences on the page "
                   f"({usual}; the spread is never taken below {floors} px). The largest: {top}.{weak}", evidence=ev))
    if issues:
        out.append(limitation(DETECTOR, "Placement of text only partly compared", "The placement of words was not compared everywhere: "
                              + "; ".join(issues[:10]) + ".", [doc_evidence(doc.id, "scanned pages")]))
    return out
