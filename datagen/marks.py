"""Synthetic issuer marks (Task 26): a logo and a stamp for each fictional bank, as strokes in the unit box. Strokes only, no text, so
OCR has nothing to read or misread inside a mark. A design is seeded by the kind and the bank's name, so every document of one bank
carries the same drawing; each pressing is moved, scaled and turned a little, so two genuine marks are close but never identical.
A name ending in "/edit" is the bank's design with one element changed. Invented for the demonstration data: no real logo is used."""
import math
import random

from .layouts import Sheet

Stroke = list[tuple[float, float]]
SIZE = {"logo": 34.0, "stamp": 60.0}                   # pt: the box a mark is drawn in
INK = {"logo": (0.05, 0.1, 0.3), "stamp": (0.1, 0.2, 0.6)}
WIDTH = {"logo": 1.4, "stamp": 1.4}                    # pt
GAP = {"logo": 0.12, "stamp": 0.075}                   # between rings, in box widths
TURN = {"logo": 1.0, "stamp": 4.0}                     # degrees a pressing may be turned, either way
EDGE = 0.48                                            # the outer ring's flat sides stand this far from the middle (box widths)
SHAPES = {"circle": (48, 0.0, EDGE), "octagon": (8, math.pi / 8, EDGE / math.cos(math.pi / 8)),
          "square": (4, math.pi / 4, EDGE * math.sqrt(2))}  # corners, turn of the first, distance of a corner from the middle
MOTIFS = ("star", "spokes", "bars", "wave")
EDIT = 0.1                                             # a moved point goes this far (box widths)
CAPTION_DROP = 45.5                                    # pt from the middle of a stamp's box to the baseline of its caption


def _polygon(n: int, r: float, phase: float) -> Stroke:
    """A closed polygon of n corners on a circle of radius r around the middle of the box."""
    pts = [(0.5 + r * math.sin(phase + 2 * math.pi * i / n), 0.5 - r * math.cos(phase + 2 * math.pi * i / n)) for i in range(n)]
    return [*pts, pts[0]]


def _motif(kind: str, n: int, m: float, phase: float) -> list[Stroke]:
    """What stands inside the innermost ring, within radius m; n is a count of points, spokes or bars (at most 4 bars)."""
    if kind == "star":
        pts = [(0.5 + (m if i % 2 == 0 else 0.45 * m) * math.sin(phase + math.pi * i / n),
                0.5 - (m if i % 2 == 0 else 0.45 * m) * math.cos(phase + math.pi * i / n)) for i in range(2 * n)]
        return [[*pts, pts[0]]]
    if kind == "spokes":
        return [[(0.5 + k * m * math.sin(phase + 2 * math.pi * i / n), 0.5 - k * m * math.cos(phase + 2 * math.pi * i / n))
                 for k in (0.4, 1.0)] for i in range(n)]
    if kind == "bars":
        n = min(n, 4)
        out = []
        for i in range(n):
            dy = m * (1.4 * (i + 0.5) / n - 0.7)
            half = 0.9 * math.sqrt(max(m * m - dy * dy, 0.0))
            out.append([(0.5 - half, 0.5 + dy), (0.5 + half, 0.5 + dy)])
        return out
    return [[(0.5 + m * (2 * i / 40 - 1), 0.5 + 0.35 * m * math.sin(math.pi * n * i / 40)) for i in range(41)]]  # wave


def _design(kind: str, bank: str, edit: bool) -> list[Stroke]:
    r = random.Random(f"mark/{kind}/{bank}")
    corners, phase, reach = SHAPES[r.choice(list(SHAPES))]
    rings = r.randrange(1, 3) if kind == "logo" else r.randrange(2, 4)
    motif, n, turn = r.choice(MOTIFS), r.randrange(3, 7), r.uniform(0, 2 * math.pi)
    drop = int(edit and kind == "stamp")  # the edit of a stamp leaves its innermost ring out
    out = [_polygon(corners, reach * (1 - k * GAP[kind] / EDGE), phase) for k in range(rings - drop)]
    inner = _motif(motif, n, EDGE - (rings - 1) * GAP[kind] - 0.08, turn)
    if edit and kind == "logo":  # one point of the motif moves toward the middle (up, when it stands on it)
        s = inner[0]
        x, y = s[len(s) // 2]
        d = math.hypot(x - 0.5, y - 0.5)
        ux, uy = ((0.5 - x) / d, (0.5 - y) / d) if d > 1e-9 else (0.0, -1.0)
        s[len(s) // 2] = (x + EDIT * ux, y + EDIT * uy)
    return out + inner


def strokes(kind: str, name: str, rng: random.Random | None = None) -> list[Stroke]:
    """The mark of the bank `name` as polylines in the unit box (x right, y down): the same every time. With `rng` it is pressed once
    more: the whole is moved, scaled and turned a little."""
    if kind not in SIZE:
        raise ValueError(f"a mark is a logo or a stamp, not {kind!r}")
    bank, _, edit = name.partition("/")
    if edit not in ("", "edit"):
        raise ValueError(f"unknown change {edit!r}")
    out = _design(kind, bank, bool(edit))
    if rng is None:
        return out
    s, a = 1 + rng.uniform(-0.04, 0.04), math.radians(rng.uniform(-TURN[kind], TURN[kind]))
    dx, dy = rng.uniform(-0.03, 0.03), rng.uniform(-0.03, 0.03)
    c, k = math.cos(a), math.sin(a)
    return [[(0.5 + dx + s * ((x - 0.5) * c - (y - 0.5) * k), 0.5 + dy + s * ((x - 0.5) * k + (y - 0.5) * c)) for x, y in st] for st in out]


def _draw(sheet: Sheet, kind: str, name: str, rng: random.Random, x: float, y: float) -> None:
    """Press the mark in the box whose top left corner is (x, y), and record the ink's box (with a point of margin) as the region
    named by its kind."""
    size = SIZE[kind]
    drawn = [[(x + u * size, y + v * size) for u, v in s] for s in strokes(kind, name, rng)]
    for s in drawn:
        sheet.page.draw_polyline(s, color=INK[kind], width=WIDTH[kind])
    xs, ys = zip(*(p for s in drawn for p in s))
    sheet.region(kind, min(xs) - 1, min(ys) - 1, max(xs) + 1, max(ys) + 1)


def logo(sheet: Sheet, bank: str, rng: random.Random, x: float, y: float) -> None:
    """The bank's logo in a 34 pt box with its top left corner at (x, y)."""
    _draw(sheet, "logo", bank, rng, x, y)


def stamp(sheet: Sheet, bank: str, rng: random.Random, cx: float, cy: float) -> None:
    """The bank's stamp in a 60 pt box centred on (cx, cy)."""
    _draw(sheet, "stamp", bank, rng, cx - SIZE["stamp"] / 2, cy - SIZE["stamp"] / 2)


def seal(sheet: Sheet, bank: str, rng: random.Random, x: float, caption_y: float, caption: str) -> None:
    """The bank's stamp in a 60 pt box whose left edge is x, and under it the caption (8 pt, left edge x, baseline caption_y), which
    is what the comparison finds the stamp by."""
    stamp(sheet, bank, rng, x + SIZE["stamp"] / 2, caption_y - CAPTION_DROP)
    sheet.text(x, caption_y, caption, 8)
