"""OCR reader: RapidOCR (PP-OCR models on ONNX Runtime, CPU, bundled in its wheel) behind a small wrapper that
returns Words in the pixel frame of the image it was given."""
import hashlib
import re
import threading
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from ..config import Thresholds
from ..model import Box, Page, Word
from ..understand.layout import sideways, upside_down
from .quality import quality_class, sharpness

MAX_SIDE_PX = 2400       # photographs are scaled down to this longest side
MAX_PIXELS = 50_000_000  # decoded size above which an image is refused


def _bbox(points) -> Box:
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return (float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys)))


def _split(text: str, box: Box) -> list[tuple[str, Box]]:
    """The words of a line, each with a box: the line's width is shared out by character count."""
    x0, y0, x1, y1 = box
    step = (x1 - x0) / max(len(text), 1)
    return [(m.group(), (x0 + m.start() * step, y0, x0 + m.end() * step, y1)) for m in re.finditer(r"\S+", text)]


def split_line_box(text: str, box: Box, doc_id: str, page_n: int, conf: float) -> list[Word]:
    """Fallback for a line the engine returned without word boxes."""
    return [Word(id=f"{doc_id}-p{page_n}-w{k}", text=t, box=b, conf=conf) for k, (t, b) in enumerate(_split(text, box), 1)]


class Ocr:
    _shared: "Ocr | None" = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        from rapidocr import RapidOCR  # lazy: onnxruntime is slow to load and digital-only cases never need it
        self._engine = RapidOCR(params={"Global.log_level": "error"})
        self.turned = (0, 0)  # of the last read: (lines the engine's angle test turned half a turn, lines it tested)
        classify = self._engine.cls_and_rotate
        self._engine.cls_and_rotate = lambda crops: self._count_turned(classify(crops))

    def _count_turned(self, out):
        """The engine turns an upside-down line before it reads it and does not say so: count the lines it turned. `out` is what its
        angle step returned, passed on as it is. The count reaches into the engine's own result: if that is not the shape the pinned
        version returns, the page loses the count (0, 0 says nothing) and keeps its reading."""
        try:
            tested = out[1].cls_res or ()
            sure = self._engine.text_cls.cls_thresh  # the engine's own bar for turning a line
            self.turned = (sum(1 for label, score in tested if "180" in label and score > sure), len(tested))
        except (AttributeError, IndexError, TypeError, ValueError):
            self.turned = (0, 0)
        return out

    @classmethod
    def shared(cls) -> "Ocr":
        """One engine per process: loading the models takes about a second and some memory."""
        with cls._lock:
            if cls._shared is None:
                cls._shared = cls()
            return cls._shared

    def read(self, rgb: np.ndarray, doc_id: str, page_n: int) -> list[Word]:
        # the engine keeps the flags of its previous call (a recogniser-only re-read would stick), so every call sets all
        self.turned = (0, 0)
        r = self._engine(np.ascontiguousarray(rgb[:, :, ::-1]),  # the engine takes BGR arrays
                         use_det=True, use_cls=True, use_rec=True, return_word_box=True)
        if not r.txts:  # nothing found: boxes, txts and scores are None
            return []
        lines = r.word_results or ()
        found: list[tuple[str, Box, float]] = []
        for i, text in enumerate(r.txts):
            line = lines[i] if i < len(lines) else None
            if isinstance(line, tuple) and line and all(isinstance(x, tuple) for x in line):
                found += [(w.strip(), _bbox(pts), float(s)) for w, s, pts in line if w.strip() and pts is not None]
            else:
                found += [(t, b, float(r.scores[i])) for t, b in _split(text, _bbox(r.boxes[i]))]
        return [Word(id=f"{doc_id}-p{page_n}-w{k}", text=t, box=b, conf=c) for k, (t, b, c) in enumerate(found, 1)]

    def model_files(self) -> dict[str, str]:
        """SHA-256 of every bundled ONNX model, for the audit trail."""
        import rapidocr
        folder = Path(rapidocr.__file__).parent / "models"
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.glob("*.onnx"))}


def ocr_page(page: Page, doc_id: str, th: Thresholds) -> None:
    """Read page.image_path: set the page's words, sharpness and quality class."""
    with Image.open(page.image_path) as im:
        rgb = np.asarray(im.convert("RGB"))
        gray = np.asarray(im.convert("L"), dtype=np.float32)
    page.sharpness = round(sharpness(gray), 4)
    page.quality_class = quality_class(page.sharpness, th)
    engine = Ocr.shared()
    page.words = engine.read(rgb, doc_id, page.n)
    page.upside_down = None if sideways(page.words) else upside_down(*engine.turned)  # a page on its side is turned too, but not upside down


def _to_rgb(im: Image.Image) -> Image.Image:
    """RGB with transparent pixels white: a plain convert would turn them black, and dark text with them."""
    if im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info:
        rgba = im.convert("RGBA")
        sheet = Image.new("RGBA", rgba.size, "white")
        sheet.alpha_composite(rgba)
        return sheet.convert("RGB")
    return im.convert("RGB")


def load_image_page(src: Path, doc_id: str, out_png: Path, th: Thresholds) -> Page:
    """An uploaded PNG or JPEG becomes one page: upright (EXIF), at most MAX_SIDE_PX long, saved as PNG, then read.
    The image's own pixels are the page's coordinate frame; the dpi is nominal."""
    with Image.open(src) as im:  # Pillow raises DecompressionBombError past twice MAX_IMAGE_PIXELS and only warns below
        limit = min(MAX_PIXELS, Image.MAX_IMAGE_PIXELS or MAX_PIXELS)
        if im.width * im.height > limit:
            raise Image.DecompressionBombError(f"image has {im.width * im.height} pixels, the limit is {limit}")
        upright = _to_rgb(ImageOps.exif_transpose(im))
    upright.thumbnail((MAX_SIDE_PX, MAX_SIDE_PX), Image.Resampling.LANCZOS)  # only ever shrinks
    upright.save(out_png)
    page = Page(n=1, width=upright.width, height=upright.height, image_path=Path(out_png).as_posix(),
                read_mode="ocr", quality_class="poor")
    ocr_page(page, doc_id, th)
    return page
