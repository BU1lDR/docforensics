"""Files for measuring the raw file-structure check (Task 27, the cut-down "hex-level" check). One file a case. The kinds, fixed here before the
check was run on them. Nothing in a file is a script or a payload: a planted file carries one change to the file's structure, and the check
reads names and positions only.

- statement, payslip: a digital PDF as datagen/layouts draw it. Nothing to find.
- padded: a digital PDF followed by a line break and three spaces (white space after the last marker is not reported). Nothing to find.
- scan-pdf: a JPEG scan (200 dpi, level mild) placed on a PDF page as it is. Nothing to find.
- scan-jpeg, scan-png: the same kind of scan as the scanner saved it, and saved as PNG. Nothing to find.
- tail: a digital PDF with 16 bytes appended after its last end-of-file marker.
- records: a digital PDF whose /Info record and XMP packet name different producers.
- signed-then-added: a digital PDF with a signature dictionary (no real signature, zero bytes where it would be) whose /ByteRange covers the
  file, and one more revision appended after it.
- attached: a digital PDF with an embedded plain-text file and an /OpenAction that is a destination.
- rebuilt: a digital PDF with its startxref keyword damaged, so that the index has to be rebuilt to read it.
- image-tail: a JPEG scan saved again with an EXIF Software field naming an image editor, and 16 bytes appended after its end-of-image marker.

`expect` lists the titles of the observations the check must show on the file, and no others; it is empty for the first six kinds. Planted
means by construction: the pack says what the check does with the changes it was written to look for, not how often a real edit
leaves one. Seeds: the split's base plus PACK, apart from every other pack."""
import hashlib
import io
import json
import random
from pathlib import Path

import pymupdf
from PIL import Image

from .fictional import identity
from .layouts.payslip import draw_payslip
from .layouts.statement import draw_statement
from .manipulate import incremental
from .scan import simulate_scan

BASE = {"ext-dev": 3_000_000, "ext-test": 4_000_000}  # the seed bases of the ext splits, as in the packs of X, E and H
PACK = 300_000  # X draws its seeds from BASE + 0 on, E from + 100_000, H from + 200_000
SPAN = 10_000
KINDS = ("statement", "payslip", "padded", "scan-pdf", "scan-jpeg", "scan-png",
         "tail", "records", "signed-then-added", "attached", "rebuilt", "image-tail")
PLANTED = KINDS[6:]
TITLES = {"tail": ["Bytes follow the last end-of-file marker"], "records": ["The /Info record and the XMP packet disagree"],
          "signed-then-added": ["Content follows the signed byte range"],
          "attached": ["PDF carries an embedded file", "PDF carries action keys"],
          "rebuilt": ["The file's index had to be rebuilt to be read"],
          "image-tail": ["Bytes follow the end of the image", "Image metadata names image-editing software"]}
NOTES = {"statement": "the digital statement as drawn", "payslip": "the digital payslip as drawn",
         "padded": "a digital statement followed by a line break and three spaces", "scan-pdf": "a mild JPEG scan on a PDF page, as it is",
         "scan-jpeg": "a mild JPEG scan as saved", "scan-png": "a mild scan saved as PNG",
         "tail": "16 bytes after the last end-of-file marker", "records": "the /Info producer and the XMP producer differ",
         "signed-then-added": "a signature dictionary over the whole file, then a revision appended",
         "attached": "an embedded text file and an /OpenAction destination", "rebuilt": "startxref damaged, index rebuilt on reading",
         "image-tail": "EXIF Software names an editor, 16 bytes after the end-of-image marker"}
EXT = {"scan-jpeg": "jpg", "image-tail": "jpg", "scan-png": "png"}
XMP = ('<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?><x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF '
       'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description rdf:about="" xmlns:pdf="http://ns.adobe.com/pdf/1.3/">'
       '<pdf:Producer>{}</pdf:Producer></rdf:Description></rdf:RDF></x:xmpmeta><?xpacket end="w"?>')


def plan_cases(split: str, n: int, start: int = 0) -> list[dict]:
    """Cases `start` to `start + n`: the kind cycles through the twelve, the layout changes every twelve cases."""
    if split not in BASE:
        raise ValueError(f"unknown split {split!r}")
    if start < 0 or n < 0 or start + n > SPAN:
        raise ValueError(f"cases {start} to {start + n} do not fit the {SPAN} seeds of the pack")
    return [{"case": f"{split}-s-{i:04d}", "seed": BASE[split] + PACK + i, "kind": KINDS[i % len(KINDS)], "layout": "AB"[(i // len(KINDS)) % 2]}
            for i in range(start, start + n)]


def _signed(pdf: bytes) -> bytes:
    """The PDF with a signature dictionary added: its /ByteRange covers everything but the (zero-filled) value, which is no signature."""
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        doc.update_object(doc.get_new_xref(), "<< /Type /Sig /Filter /Adobe.PPKLite /SubFilter /adbe.pkcs7.detached "
                          "/ByteRange [0 999999999 999999999 999999999] /Contents <" + "00" * 64 + "> >>")
        data = doc.tobytes(no_new_id=True)
    old = b"[0 999999999 999999999 999999999]"
    i = data.index(old)
    a = data.index(b"/Contents<", i)
    b = data.index(b">", a) + 1
    return data[:i] + b"[0 %9d %9d %9d]" % (a, b, len(data) - b) + data[i + len(old):]


def _with(pdf: bytes, edit) -> bytes:
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        edit(doc)
        return doc.tobytes(no_new_id=True)


def _records(doc: pymupdf.Document) -> None:
    doc.set_metadata({"producer": "Halcyon Statement Engine 4.2", "creator": "Halcyon Writer"})
    doc.set_xml_metadata(XMP.format("Other Maker 1.0"))


def _attached(doc: pymupdf.Document) -> None:
    doc.embfile_add("note.txt", b"plain text note, synthetic specimen", filename="note.txt", desc="a note")
    doc.xref_set_key(doc.pdf_catalog(), "OpenAction", f"[{doc[0].xref} 0 R /Fit]")  # a destination: the first page, fitted


def _scan_pdf(jpeg: bytes) -> bytes:
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_image(page.rect, stream=jpeg)  # the JPEG bytes go into the file as they are
        return doc.tobytes(no_new_id=True)  # a new /ID is random


def _edited_jpeg(jpeg: bytes) -> bytes:
    """The scan saved again with an EXIF Software field naming an image editor."""
    exif = Image.Exif()
    exif[0x0131] = "Adobe Photoshop 25.1 (Windows)"
    out = io.BytesIO()
    Image.open(io.BytesIO(jpeg)).save(out, "JPEG", quality=85, exif=exif)
    return out.getvalue()


def build_case(p: dict) -> tuple[bytes, dict]:
    """The file of one planned case and its manifest entry."""
    seed, kind = p["seed"], p["kind"]
    ident = identity(seed)
    pdf = draw_payslip(ident, p["layout"], seed).pdf if kind == "payslip" else draw_statement(ident, p["layout"], seed=seed).pdf
    junk = random.Random(seed).randbytes(16)
    jpeg = simulate_scan(pdf, "mild", seed * 10) if kind in ("scan-pdf", "scan-jpeg", "scan-png", "image-tail") else b""
    data = {"statement": pdf, "payslip": pdf, "padded": pdf + b"\r\n   ", "scan-pdf": lambda: _scan_pdf(jpeg), "scan-jpeg": jpeg,
            "scan-png": lambda: _png(jpeg), "tail": pdf + b"\n" + junk, "records": lambda: _with(pdf, _records),
            "signed-then-added": lambda: incremental(_signed(pdf), lambda pg: pg.insert_text((72, 400), "added after signing", fontname="helv", fontsize=10)),
            "attached": lambda: _with(pdf, _attached), "rebuilt": pdf.replace(b"startxref", b"startxrex"),
            "image-tail": lambda: _edited_jpeg(jpeg) + junk}[kind]
    data = data() if callable(data) else data
    return data, {"case": p["case"], "seed": seed, "kind": kind, "layout": p["layout"], "file": f"document.{EXT.get(kind, 'pdf')}",
                  "expect": TITLES.get(kind, []), "note": NOTES[kind], "sha256": hashlib.sha256(data).hexdigest()}


def _png(jpeg: bytes) -> bytes:
    out = io.BytesIO()
    Image.open(io.BytesIO(jpeg)).save(out, "PNG")
    return out.getvalue()


def build_split(split: str, out: Path | str, n: int, start: int = 0) -> Path:
    """Cases `start` to `start + n` written under `out`, one folder a case, and `out/manifest.json`. Returns the manifest's path."""
    out = Path(out)
    entries = []
    for p in plan_cases(split, n, start):
        data, entry = build_case(p)
        (out / p["case"]).mkdir(parents=True, exist_ok=True)
        (out / p["case"] / entry["file"]).write_bytes(data)
        entries.append(entry)
    path = out / "manifest.json"
    path.write_text(json.dumps({"split": split, "pack": "structure", "cases": entries}, indent=1), encoding="utf-8", newline="\n")
    return path


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="python -m datagen.structure_pack", description="Write files for the file-structure check and their manifest.")
    ap.add_argument("split", choices=sorted(BASE))
    ap.add_argument("out", help="the folder to write to")
    ap.add_argument("--cases", type=int, default=12, help="how many cases (default: 12)")
    ap.add_argument("--start", type=int, default=0, help="the first case (default: 0)")
    a = ap.parse_args()
    print(build_split(a.split, a.out, a.cases, a.start))
