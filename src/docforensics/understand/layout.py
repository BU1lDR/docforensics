"""Page geometry shared by classification and extraction: words into lines, lines into cells. A scan is a little turned, so the
turn of a page is found from its words, and extraction reads a page as it would stand upright (straightened)."""
import math
from collections.abc import Iterable
from dataclasses import dataclass
from statistics import median

import numpy as np

from ..model import Box, Page, Word
from .normalise import text_similarity

LINE_TOL = 0.4  # a word joins a line when its centre is this share of a word height from the line's centre
CELL_GAP = 0.8  # words this share of a word height apart (or more) start a new cell: columns, not spaces. Drawn text keeps its words
#                 within 0.2 of it and its columns 1.2 or more apart; OCR boxes put the words of a name up to 0.6 apart
MIN_WORDS = 12      # words a page needs before its turn can be found
_SEARCH_DEG = 10.0  # the largest turn looked for, either way; one beyond it is not found, and the search then ends anywhere


@dataclass
class Line:
    page: int  # 1-based
    words: list[Word]  # left to right
    cells: list[list[Word]]  # runs of words with no wide gap between them
    box: Box
    height: float  # median word height


def text_of(words: Iterable[Word]) -> str:
    return " ".join(w.text for w in words)


def union(boxes: Iterable[Box]) -> Box:
    bs = list(boxes)
    return min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)


def similar(a: str, b: str, floor: float) -> float:
    """text_similarity(a, b) if it reaches `floor`, else 0.0. Strings whose lengths alone rule that out are not compared,
    so a hostile page cannot make matching slow."""
    la, lb = len(a), len(b)
    if not la or not lb or 2 * min(la, lb) / (la + lb) < floor:
        return 0.0
    s = text_similarity(a, b)
    return s if s >= floor else 0.0


def find_phrase(words: list[Word], phrase: str, floor: float) -> tuple[int, int, float] | None:
    """(start, count, similarity) of the run of words that best reads as `phrase`, the earliest and then the shortest on a
    tie; None if no run reaches `floor`. A colon counts as a space."""
    k = len(phrase.split())
    best = None
    for n in range(max(1, k - 1), k + 2):
        for i in range(len(words) - n + 1):
            s = similar(text_of(words[i:i + n]).replace(":", " "), phrase, floor)
            if s and (best is None or s > best[2] or (s == best[2] and (i, n) < best[:2])):
                best = (i, n, s)
    return best


_AS_TALL = 0.15  # a line this much shorter than the tallest counts as about as tall: the box of a short word with descenders (Payslip) can beat a longer line


def issuer_line(lines: list[Line]) -> Line | None:
    """The topmost line that reads as a name (three letters or digits at least) among those about as tall as the tallest such line,
    so a stray character that a logo or a stamp was read as does not become the issuer, and neither does a subtitle that a scan's
    boxes made as tall as the name above it. None if no line qualifies."""
    named = [ln for ln in lines if sum(c.isalnum() for c in text_of(ln.words)) >= 3]
    tall = max((ln.height for ln in named), default=0.0)
    return next((ln for ln in named if ln.height >= (1 - _AS_TALL) * tall), None)


def _centre(w: Word) -> float:
    return (w.box[1] + w.box[3]) / 2


def _cells(words: list[Word], gap: float) -> list[list[Word]]:
    cells, right = [[words[0]]], words[0].box[2]
    for w in words[1:]:
        if w.box[0] - right >= gap:
            cells.append([w])
        else:
            cells[-1].append(w)
        right = max(right, w.box[2])
    return cells


def lines_of(page: Page) -> list[Line]:
    """The page's words as lines, top to bottom. Words without height are left out: they cannot be placed."""
    groups: list[list[Word]] = []
    for w in sorted((w for w in page.words if w.box[3] > w.box[1]), key=_centre):
        if groups:
            g = groups[-1]
            h = min(w.box[3] - w.box[1], median(v.box[3] - v.box[1] for v in g))
            if abs(_centre(w) - sum(map(_centre, g)) / len(g)) <= LINE_TOL * h:
                g.append(w)
                continue
        groups.append([w])
    out = []
    for g in groups:
        g.sort(key=lambda w: w.box[0])
        h = median(w.box[3] - w.box[1] for w in g)
        out.append(Line(page.n, g, _cells(g, CELL_GAP * h), union(w.box for w in g), h))
    return out


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


def upright(words: list[Word], width: float, height: float, deg: float) -> tuple[np.ndarray, ...]:
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


def straightened(page: Page) -> tuple[Page, float]:
    """(the page with its words as they would stand upright, the turn in degrees). A page read from a text layer, or with too few
    words to find a turn, is returned as it is, at turn 0. Word ids and text are kept; only the boxes change."""
    if page.read_mode != "ocr" or len(page.words) < MIN_WORDS:
        return page, 0.0
    deg = page_turn(page.words, page.width, page.height)
    u, v, wd, ht = upright(page.words, page.width, page.height, deg)
    cx, cy = page.width / 2, page.height / 2
    words = [w.model_copy(update={"box": (float(u[i] - wd[i] / 2 + cx), float(v[i] - ht[i] / 2 + cy),
                                          float(u[i] + wd[i] / 2 + cx), float(v[i] + ht[i] / 2 + cy))})
             for i, w in enumerate(page.words)]
    return page.model_copy(update={"words": words}), deg


def unturned(box: Box, page: Page, deg: float) -> Box:
    """A box of the straightened page, as the box around it on the page as given (clipped to the page)."""
    t, cx, cy = math.radians(deg), page.width / 2, page.height / 2
    pts = [(x - cx, y - cy) for x in (box[0], box[2]) for y in (box[1], box[3])]
    xs = [cx + u * math.cos(t) + v * math.sin(t) for u, v in pts]
    ys = [cy - u * math.sin(t) + v * math.cos(t) for u, v in pts]
    return (max(min(xs), 0.0), max(min(ys), 0.0), min(max(xs), float(page.width)), min(max(ys), float(page.height)))
