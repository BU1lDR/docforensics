"""Scan simulation (Task 17) and the manipulations and detectors for scans. These tests are about mechanisms: that a simulated
scan lands in the quality class the ladder says, that a manipulation changes what it says it changes. How often a detector
finds a manipulation is measured by the evaluation, not here."""
import pytest

from datagen.fictional import identity
from datagen.layouts.statement import draw_statement
from datagen.scan import LEVELS, simulate_scan
from docforensics.config import Thresholds
from docforensics.read.ocr import load_image_page

TH = Thresholds()
ocr = pytest.mark.ocr


def statement_pdf(seed=1):
    return draw_statement(identity(seed), rows=12, seed=seed).pdf


@ocr
@pytest.mark.parametrize("level, classes", [("mild", {"good"}), ("150dpi", {"good", "degraded"}), ("120dpi", {"degraded", "poor"})])
def test_simulated_scan_gets_expected_quality_class(tmp_path, level, classes):
    src = tmp_path / "scan.jpg"
    src.write_bytes(simulate_scan(statement_pdf(), level, seed=1))
    page = load_image_page(src, "D1", tmp_path / "p.png", TH)
    print(level, page.quality_class, round(page.sharpness, 3))
    assert page.quality_class in classes and page.read_mode == "ocr"


def test_simulated_scan_is_a_jpeg_that_the_seed_decides():
    pdf = statement_pdf()
    a, b, c = (simulate_scan(pdf, "mild", s) for s in (1, 1, 2))
    assert a[:3] == b"\xff\xd8\xff" and a == b and a != c
    assert set(LEVELS) == {"mild", "150dpi", "120dpi"}
