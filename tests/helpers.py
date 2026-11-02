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
