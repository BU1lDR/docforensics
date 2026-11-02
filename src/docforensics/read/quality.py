"""Page-quality gate. OCR confidence does not flag misread digits (docs/spike.md), so a scan's reliability comes from
how sharp the page is, and the arithmetic checks stay the second line of defence."""
import numpy as np
from PIL import Image, ImageFilter

from ..config import Thresholds


def sharpness(gray: np.ndarray) -> float:
    """99.5th percentile of the gradient of a sigma-1 blurred copy, divided by the page's ink-to-paper span.
    The span makes it independent of contrast; a flat page (span under one grey level) scores 0."""
    blurred = np.asarray(Image.fromarray(np.clip(gray, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.0)),
                         dtype=np.float32)
    lo, hi = np.percentile(blurred, [0.5, 99])
    if hi - lo < 1:
        return 0.0
    gy, gx = np.gradient(blurred)
    return float(np.percentile(np.hypot(gx, gy), 99.5) / (hi - lo))


def quality_class(s: float, th: Thresholds) -> str:
    return "good" if s >= th.sharp_good else "degraded" if s >= th.sharp_poor else "poor"


def reliability(page_class: str, th: Thresholds) -> float:
    """How far a value read from a page of this class can be trusted (the text layer is exact)."""
    return {"text-layer": 1.0, "good": th.rel_good, "degraded": th.rel_degraded, "poor": th.rel_poor}[page_class]
