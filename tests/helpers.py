"""Small file builders shared by the tests."""
import io

import pymupdf
from PIL import Image


def pdf_bytes(pages: int = 1, text: str = "TST-0001", **save) -> bytes:
    doc = pymupdf.open()
    for i in range(pages):
        doc.new_page().insert_text((72, 72), f"{text} page {i + 1}")
    data = doc.tobytes(**save)
    doc.close()
    return data


def _image(fmt: str) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(buf, fmt)
    return buf.getvalue()


def png_bytes() -> bytes:
    return _image("PNG")


def jpeg_bytes() -> bytes:
    return _image("JPEG")


STATEMENT_LINES = [
    (72, 90, "HALCYON TEST BANK", 16),
    (72, 120, "Statement of Account TST-0001 (synthetic specimen)", 11),
    (72, 150, "Account holder: Meera K. Varghese", 11),
    (72, 190, "01/04/2026 Opening balance 1,20,500.00", 10),
    (72, 210, "03/04/2026 Salary credit 52,000.00   1,72,500.00", 10),
    (72, 230, "07/04/2026 Rent debit 18,000.00   1,54,500.00", 10),
    (72, 250, "12/04/2026 Electricity debit 2,340.00   1,52,160.00", 10),
    (72, 270, "18/04/2026 Grocery debit 4,125.50   1,48,034.50", 10),
    (72, 290, "30/04/2026 Closing balance 1,48,034.50", 10),
]
SLIP_LINES = [
    (72, 100, "NORTHWIND TEST PRIVATE LIMITED", 18),
    (72, 140, "Payslip for April 2026", 12),
    (72, 180, "Employee EMP-4471 Meera K. Varghese", 11),
    (72, 220, "Basic 30,000.00 HRA 12,000.00 Special 10,000.00", 11),
    (72, 260, "Gross 52,000.00 Deductions 4,800.00 Net 47,200.00", 11),
]


def lines_pdf(lines, size=(595, 842)) -> bytes:
    """A digital one-page PDF with the given (x, y, text, fontsize) lines."""
    doc = pymupdf.open()
    page = doc.new_page(width=size[0], height=size[1])
    for x, y, text, fs in lines:
        page.insert_text((x, y), text, fontname="helv", fontsize=fs)
    data = doc.tobytes()
    doc.close()
    return data


def render_lines(lines, size=(595, 842), dpi=200):
    """The same page as lines_pdf, rendered clean as a PIL RGB image."""
    with pymupdf.open(stream=lines_pdf(lines, size), filetype="pdf") as doc:
        s = dpi / 72
        pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(s, s), alpha=False)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def tokens(lines):
    return {t for _, _, text, _ in lines for t in text.split()}


def recall(words, lines):
    got = {w.text for w in words}
    want = tokens(lines)
    return len(want & got) / len(want)


def iou(a, b):
    """Intersection over union of two (x0, y0, x1, y1) boxes."""
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    inter = max(w, 0) * max(h, 0)
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter)


def d1_edited_statement(new: str = "9,99,999.00") -> bytes:
    """A drawn bank statement whose first credit was re-typed in an incremental save: a revision change and a broken balance chain."""
    from datagen.fictional import identity
    from datagen.layouts import money
    from datagen.layouts.statement import draw_statement
    from datagen.manipulate import d1_incremental_edit

    drawn = draw_statement(identity(1), rows=12, seed=1)
    pdf, _ = d1_incremental_edit(drawn.pdf, money(next(r["credit"] for r in drawn.truth["rows"] if r["credit"])), new)
    return pdf
