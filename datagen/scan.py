"""Scan simulation (design 8). A digital page is rendered and degraded the way a scanner or a photocopy would: a small turn,
uneven lighting, loss of resolution, blur, noise and JPEG. The levels are the ladder measured in docs/spike.md, where the name is
the effective resolution after the loss. The ladder was fitted on this generator, so it says how the tool copes with these scans
and nothing yet about real ones."""
import io
import math

import numpy as np
import pymupdf
from PIL import Image, ImageFilter

DPI = 200
# level: (share of the resolution kept, blur in px, noise sigma, lighting falloff, JPEG quality)
LEVELS = {"mild": (1.0, 0.6, 5, 0.06, 85), "150dpi": (0.75, 1.0, 15, 0.15, 50), "120dpi": (0.6, 1.3, 25, 0.25, 35)}


def _angle(rng: np.random.Generator) -> float:
    return float(rng.uniform(0.5, 2.0) * rng.choice((-1, 1)))


def turn(seed: int) -> float:
    """The degrees `simulate_scan` turns the page by for this seed (anticlockwise when positive): the first draws of its generator."""
    return _angle(np.random.default_rng(seed))


def to_scan_frame(box: list[float], size: tuple[int, int], seed: int) -> list[float]:
    """A box of the 200-dpi page, as it lies on the scan this seed makes: the box around its four turned corners. `size` is the
    scan's (width, height), which is the page's, since the levels lose resolution and keep the pixel grid."""
    t = math.radians(turn(seed))
    c, s = math.cos(t), math.sin(t)
    cx, cy = size[0] / 2, size[1] / 2
    pts = [(cx + (x - cx) * c + (y - cy) * s, cy - (x - cx) * s + (y - cy) * c) for x in (box[0], box[2]) for y in (box[1], box[3])]
    xs, ys = zip(*pts)
    return [min(xs), min(ys), max(xs), max(ys)]


def simulate_scan(pdf: bytes, level: str, seed: int, page: int = 0) -> bytes:
    """Page `page` (0-based) of the PDF as a JPEG scan at 200 dpi, turned by 0.5 to 2 degrees one way or the other."""
    keep, blur, sigma, shade, quality = LEVELS[level]
    rng = np.random.default_rng(seed)
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        png = doc[page].get_pixmap(dpi=DPI).tobytes("png")
    im = Image.open(io.BytesIO(png)).convert("L")
    w, h = im.size
    im = im.rotate(_angle(rng), resample=Image.BICUBIC, fillcolor=255)
    if keep < 1:
        im = im.resize((int(w * keep), int(h * keep)), Image.BILINEAR).resize((w, h), Image.BILINEAR)
    yy, xx = np.mgrid[0:h, 0:w]
    a = np.asarray(im, dtype=np.float32) * (1 - shade * xx / w - shade * 0.5 * yy / h)  # darker towards the right and the bottom
    a = np.asarray(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(blur)), dtype=np.float32)
    a = a + rng.normal(0, sigma, a.shape)
    out = io.BytesIO()
    Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).save(out, "JPEG", quality=quality)
    return out.getvalue()
