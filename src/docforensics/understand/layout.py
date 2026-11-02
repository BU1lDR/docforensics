"""Page geometry shared by classification and extraction: words into lines, lines into cells."""
from collections.abc import Iterable
from dataclasses import dataclass
from statistics import median

from ..model import Box, Page, Word
from .normalise import text_similarity

LINE_TOL = 0.4  # a word joins a line when its centre is this share of a word height from the line's centre
CELL_GAP = 0.5  # words this share of a word height apart (or more) start a new cell: columns, not spaces


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
