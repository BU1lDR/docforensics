"""Does a page carry scanner grain? The checks of image grain, of placement and of learned word measures compare a word with the rest of
its page. They were built and measured on scans, whose paper has noise. A page that has none, such as a page printed or rendered to a
picture, differs from word to word by its typeface, its tinted bands and its layout, and those checks then note design. Such a page is
not given to them, and `grain_gate` says so once per document, so the silence is not read as a clean result.
The measure uses pixels only. Flat paper is bright (at least 200) with a 5 x 5 neighbourhood that spans less than 20 grey levels; its
grain share is the share of those pixels that lie more than half a grey level from a blur of their surroundings. The limit was set on
the project's simulated scans (0.885 to 0.914) against noise-free pages saved as pictures (0.004 to 0.153); no real scanner was measured."""
from functools import lru_cache

import cv2
import numpy as np
from PIL import Image

from ..findings import doc_evidence, limitation
from ..model import Case, Document, Finding, Page
from ..pipeline import Ctx

DETECTOR = "scan_grain"
MIN_FLAT = 50_000  # flat paper pixels a page needs before it is judged: with fewer the checks run as before
MIN_SHARE = 0.5    # a page whose flat paper has a smaller grain share than this carries no scanner grain
_PAPER = 200       # grey level from which a pixel is paper
_FLAT = 20         # a 5 x 5 neighbourhood that spans fewer grey levels is flat
_STEP = 0.5        # a pixel carries grain when it lies further than this many grey levels from the blur of its surroundings
_BLUR = 1.5        # sigma in px of that blur, as in scan_noise


@lru_cache(maxsize=32)
def _share(path: str, mtime_ns: int, size: int) -> float | None:
    """Keyed on the file as well as its name, so a picture written again is measured again; the three checks and the gate share one measure."""
    try:
        with Image.open(path) as im:
            gray = np.asarray(im.convert("L"))
    except OSError:
        return None
    box = np.ones((5, 5), np.uint8)
    flat = (cv2.dilate(gray, box).astype(np.int16) - cv2.erode(gray, box) < _FLAT) & (gray >= _PAPER)
    if flat.sum() < MIN_FLAT:
        return None
    residual = gray - cv2.GaussianBlur(gray.astype(np.float32), (0, 0), _BLUR)
    return float((np.abs(residual[flat]) > _STEP).mean())


def grain_share(ctx: Ctx, page: Page) -> float | None:
    """The share of the page's flat paper that carries grain; None when the picture cannot be opened or has too little flat paper to judge."""
    path = ctx.cd.root / page.image_path
    try:
        st = path.stat()
    except OSError:
        return None
    return _share(str(path), st.st_mtime_ns, st.st_size)


def lacks_grain(ctx: Ctx, page: Page) -> bool:
    share = grain_share(ctx, page)
    return share is not None and share < MIN_SHARE


def grain_gate(case: Case, doc: Document, ctx: Ctx) -> list[Finding]:
    left = [(p.n, grain_share(ctx, p)) for p in doc.pages if p.read_mode == "ocr" and p.quality_class != "poor" and lacks_grain(ctx, p)]
    if not left:
        return []
    pages = "; ".join(f"page {n} (grain share {share:.2f})" for n, share in left)
    return [limitation(
        DETECTOR, "Grain checks not applied: the page carries no scanner grain",
        f"The checks of image grain, of placement and of learned word measures were not applied to {pages}. The grain share is the share of a "
        f"page's flat paper that carries grain; below {MIN_SHARE:g} the picture has no scanner grain on its paper, as a page printed or rendered "
        "to an image has none, and those checks were built on scans that do. This is not a clean result for these pages: a changed word there "
        "was not looked for by these checks. The other checks are not affected.", [doc_evidence(doc.id, "scanned pages")])]
