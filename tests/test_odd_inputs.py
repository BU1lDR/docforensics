"""An odd input sent beside a good statement stops nothing: no step fails, the good statement is read exactly as it is read alone, and the
odd input is taken in as a document (it then holds what could be read of it, often nothing). The refusals (empty, too large, encrypted,
corrupt, too many pages, unsupported type) are in test_ingest. Found by sending 20 odd files through the whole tool on 7 Nov, all of
them handled; kept so that they stay handled."""
import io

import pymupdf
import pytest
from PIL import Image

from datagen.fictional import identity
from datagen.layouts.statement import draw_statement
from docforensics.config import Thresholds
from docforensics.ingest import create_case
from docforensics.pipeline import run_case

TH = Thresholds()
GOOD = draw_statement(identity(1), seed=1).pdf


def picture(mode, fmt, fill):
    buf = io.BytesIO()
    Image.new(mode, (300, 200), fill).save(buf, fmt)
    return buf.getvalue()


def blank_pdf(width, height):
    doc = pymupdf.open()
    doc.new_page(width=width, height=height)
    return doc.tobytes()


ODD = {
    "blank page": ("blank.pdf", blank_pdf(595, 842)),
    "page 20 points wide": ("tiny.pdf", blank_pdf(20, 20)),
    "page 14000 points wide": ("giant.pdf", blank_pdf(14000, 14000)),
    "cut-off pdf": ("cut.pdf", GOOD[: len(GOOD) // 2]),
    "grey png": ("grey.png", picture("L", "PNG", 200)),
    "rgba png": ("rgba.png", picture("RGBA", "PNG", (200, 200, 200, 128))),
    "palette png": ("palette.png", picture("P", "PNG", 200)),
    "16-bit grey png": ("grey16.png", picture("I;16", "PNG", 200)),
    "cmyk jpeg": ("cmyk.jpg", picture("CMYK", "JPEG", (200, 200, 200, 200))),
    "grey jpeg": ("grey.jpg", picture("L", "JPEG", 128)),
}


def good_fields(case):
    doc = next(d for d in case.documents if d.filename == "good.pdf")
    return [(f.name, f.row, f.value) for f in doc.fields]


@pytest.fixture(scope="module")
def alone(tmp_path_factory):
    _, cd, _ = create_case(tmp_path_factory.mktemp("alone"), [("good.pdf", GOOD)], TH)
    return good_fields(run_case(cd, TH))


@pytest.mark.parametrize("name, data", ODD.values(), ids=list(ODD))
def test_an_odd_input_beside_a_good_statement_stops_nothing(tmp_path, alone, name, data):
    _, cd, audit = create_case(tmp_path, [(name, data), ("good.pdf", GOOD)], TH)
    case = run_case(cd, TH)
    assert name in [d.filename for d in case.documents]
    assert alone and good_fields(case) == alone
    assert not [e for e in audit.events() if e.event == "stage_failed"]
