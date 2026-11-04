"""Synthetic signatures: a person's hand as strokes in the unit box, and a way to draw it on a sheet with the small differences of
a new signing. Strokes only, no text, so nothing can sit beneath them. These are invented for the demonstration data; real
handwriting varies far more than the jitter here."""
import math
import random

from .layouts import Sheet

Stroke = list[tuple[float, float]]
W, H = 130.0, 44.0  # pt: the box a signature is drawn in
GAP = 14.0          # pt between the box's bottom edge and the baseline of the caption under it
INK = (0.1, 0.1, 0.5)


def _spline(pts: Stroke, steps: int = 8) -> Stroke:
    """A Catmull-Rom curve through the points."""
    p = [pts[0], *pts, pts[-1]]
    out: Stroke = []
    for i in range(1, len(p) - 2):
        for k in range(steps):
            t = k / steps
            out.append(tuple(0.5 * (2 * b + (-a + c) * t + (2 * a - 5 * b + 4 * c - d) * t * t + (-a + 3 * b - 3 * c + d) * t ** 3)
                             for a, b, c, d in zip(p[i - 1], p[i], p[i + 1], p[i + 2])))
    return [*out, pts[-1]]


def strokes(person: str, rng: random.Random | None = None) -> list[Stroke]:
    """The person's signature as polylines in the unit box (x right, y down): a scrawl through random points, one or two loops and
    usually an underline. The same every time for one person. With `rng` it is signed once more: the points are moved a little,
    and the whole is scaled and slanted a little."""
    r = random.Random(f"hand/{person}")
    jit = (lambda s: rng.uniform(-s, s)) if rng else (lambda s: 0.0)
    xs = sorted([0.0, 1.0, *(r.uniform(0.05, 0.95) for _ in range(r.randrange(4, 9)))])
    scrawl = _spline([(x + jit(0.02), r.uniform(0.1, 0.75) + jit(0.02)) for x in xs])
    out = [scrawl]
    for _ in range(r.randrange(1, 3)):
        cx, cy, rad = r.uniform(0.1, 0.9) + jit(0.02), r.uniform(0.2, 0.65) + jit(0.02), r.uniform(0.07, 0.16)
        out.append([(cx + rad * math.cos(a / 8 * math.pi), cy + rad * 0.6 * math.sin(a / 8 * math.pi)) for a in range(19)])
    if r.random() < 0.75:
        a, b, y = r.uniform(0.0, 0.3), r.uniform(0.7, 1.0), r.uniform(0.86, 0.96)
        out.append([(a + jit(0.02), y + jit(0.02)), (b + jit(0.02), y + 0.01 + jit(0.02))])
    sx, sy, shear = 1 + jit(0.06), 1 + jit(0.06), jit(0.06)
    return [[(0.5 + (x - 0.5) * sx + shear * (y - 0.5), 0.5 + (y - 0.5) * sy) for x, y in s] for s in out]


def draw(sheet: Sheet, person: str, rng: random.Random, x: float, caption_y: float) -> None:
    """Sign in a W x H pt box whose left edge is `x` and whose bottom edge stands GAP above the caption's baseline `caption_y`, and
    record the ink's box (with a point of margin) as the region "signature"."""
    top = caption_y - GAP - H
    drawn = [[(x + u * W, top + v * H) for u, v in s] for s in strokes(person, rng)]
    for s in drawn:
        sheet.page.draw_polyline(s, color=INK, width=1.1)
    xs, ys = zip(*(p for s in drawn for p in s))
    sheet.region("signature", min(xs) - 1, min(ys) - 1, max(xs) + 1, max(ys) + 1)
