import numpy as np
from PIL import ImageFilter

from docforensics.config import Thresholds
from docforensics.read.quality import quality_class, reliability, sharpness
from tests.helpers import SLIP_LINES, STATEMENT_LINES, render_lines

TH = Thresholds(sharp_good=0.24, sharp_poor=0.18)  # the spike's starting values; Task 19 refits the defaults


def gray(img, blur=0.0):
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    return np.asarray(img.convert("L"), dtype=np.float32)


def test_sharpness_falls_with_blur_and_classes_follow():
    page = render_lines(STATEMENT_LINES)
    s = [sharpness(gray(page, b)) for b in (0, 1, 2, 3)]
    print("sharpness at blur 0, 1, 2, 3:", [round(x, 3) for x in s])
    assert s[0] > s[1] > s[2] > s[3]
    c = [quality_class(x, TH) for x in s]
    assert c[0] == "good" and c[1] == "good" and c[2] == "degraded" and c[3] == "poor"


def test_sharpness_similar_across_pages():
    for blur in (0, 1.5):
        a = sharpness(gray(render_lines(STATEMENT_LINES), blur))
        b = sharpness(gray(render_lines(SLIP_LINES), blur))
        print(f"blur {blur}: statement {a:.3f} payslip {b:.3f}")
        assert abs(a - b) <= 0.03


def test_blank_page_is_poor_not_a_crash():
    flat = np.full((200, 200), 255, dtype=np.float32)
    assert quality_class(sharpness(flat), TH) == "poor"


def test_reliability_by_class():
    assert [reliability(c, TH) for c in ("text-layer", "good", "degraded", "poor")] == [1.0, TH.rel_good, TH.rel_degraded, TH.rel_poor]
