"""Raw file-structure indicators (Task 27): facts read from the stored bytes of a PDF, JPEG or PNG. The files are built here from
bytes and PyMuPDF and carry structure only (an embedded text file, an empty /JS, an /OpenAction that is a GoTo); nothing is
executed, decoded or fetched. What they show is what a constructed file contains, nothing about files made by real tools."""
import io
import re
from pathlib import Path

import pymupdf
import pytest
from PIL import Image, PngImagePlugin

from datagen.manipulate import incremental
from docforensics import forensics
from docforensics.audit import AuditLog
from docforensics.config import Thresholds
from docforensics.forensics import run_forensics
from docforensics.forensics.structure import DETECTOR, action_names, file_structure
from docforensics.ingest import create_case
from docforensics.model import Case, Document, Page
from docforensics.pipeline import Ctx, run_case
from docforensics.read import read_stage
from docforensics.store import CaseDir
from tests.helpers import STATEMENT_LINES, jpeg_bytes, lines_pdf, pdf_bytes, png_bytes

TH = Thresholds()
SALARY = lines_pdf(STATEMENT_LINES)
INTENT = ("tamper", "manipulat", "forg", "fraud", "fake", "malicious", "intent", "suspici")
WHOLE = [("D1", 0, (0.0, 0.0, 0.0, 0.0))]


def detect(tmp_path, data: bytes, th=TH):
    """The detector on one stored file, without ingest (which would turn most of the broken files below away)."""
    cd = CaseDir.create(tmp_path)
    (cd.files / "f.bin").write_bytes(data)
    doc = Document(id="D1", sha256="0", filename="f", stored_path="files/f.bin")
    case = Case(id=cd.id, created="2026-11-06T00:00:00+00:00", documents=[doc])
    return file_structure(case, doc, Ctx(cd, AuditLog(cd.audit_path), th))


def one(found, limitations=0):
    """The one observation in `found` (checked for the shape every indicator shares); `limitations` more findings are limitations."""
    obs = [f for f in found if f.fclass == "observation"]
    assert len(obs) == 1 and len(found) == 1 + limitations and {f.fclass for f in found} <= {"observation", "processing_limitation"}, found
    (f,) = obs
    assert (f.detector, f.family, f.status) == (DETECTOR, "metadata", "open")
    assert [(e.doc, e.page, tuple(e.box)) for e in f.evidence] == WHOLE and f.evidence[0].note
    text = f"{f.title} {f.detail}".lower()
    assert not any(w in text for w in INTENT), text
    assert re.search(r"\d", f.detail), "a measurement is given"
    return f


# --- a file with nothing to report

CLEAN = {"pdf": pdf_bytes(), "statement": SALARY, "png": png_bytes(), "jpeg": jpeg_bytes(),
         "pdf with whitespace after the marker": SALARY + b"\r\n \n\x00"}


@pytest.mark.parametrize("name", CLEAN)
def test_a_clean_file_gives_nothing(tmp_path, name):
    assert detect(tmp_path, CLEAN[name]) == []


def test_the_genuine_sample_documents_give_nothing(tmp_path):
    files = sorted((Path(__file__).parent.parent / "sample_data" / "dev-0000").glob("*.pdf"))
    assert len(files) == 3
    for i, p in enumerate(files):
        assert detect(tmp_path / str(i), p.read_bytes()) == [], p.name


# --- 1: bytes after the last end-of-file marker

def test_bytes_after_the_last_end_of_file_marker(tmp_path):
    tail = b"APPENDED-LATER\x00\x01<b>"
    f = one(detect(tmp_path, SALARY + b"\n" + tail))
    assert f.title == "Bytes follow the last end-of-file marker"
    assert f"ends at byte offset {SALARY.rindex(b'%%EOF') + 5}." in f.detail
    assert f"{len(tail)} bytes begin at byte offset {len(SALARY) + 1}" in f.detail  # SALARY's own final newline, then the one added
    assert "41 50 50 45 4e 44 45 44" in f.detail and "APPENDED-LATER..<b>" in f.detail  # hex, then the same bytes as ASCII, non-printables as dots


def test_the_dump_is_cut_at_32_bytes(tmp_path):
    f = one(detect(tmp_path, SALARY + b"A" * 100))
    assert "100 bytes begin" in f.detail and "A" * 32 in f.detail and "A" * 33 not in f.detail


# --- 2: /Info record against the XMP packet

XMP = ('<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?><x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF '
       'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description rdf:about="" xmlns:pdf="http://ns.adobe.com/pdf/1.3/" '
       'xmlns:xmp="http://ns.adobe.com/xap/1.0/">{}</rdf:Description></rdf:RDF></x:xmpmeta><?xpacket end="w"?>')
INFO = {"producer": "Halcyon 4.2", "creator": "Halcyon Writer", "creationDate": "D:20260201092900+05'30'", "modDate": "D:20260201092900+05'30'"}
SAME = ("<pdf:Producer>Halcyon 4.2</pdf:Producer><xmp:CreatorTool>Halcyon Writer</xmp:CreatorTool>"
        "<xmp:CreateDate>2026-02-01T03:59:00Z</xmp:CreateDate><xmp:ModifyDate>2026-02-01T09:29:00+05:30</xmp:ModifyDate>")  # the same instants, spelled otherwise


def with_meta(info: dict, xmp: str) -> bytes:
    doc = pymupdf.open(stream=SALARY, filetype="pdf")
    doc.set_metadata(info)
    doc.set_xml_metadata(xmp if xmp.startswith("<") and "xpacket" in xmp else XMP.format(xmp))
    return doc.tobytes()


def test_info_and_xmp_that_agree_give_nothing(tmp_path):
    assert detect(tmp_path, with_meta(INFO, SAME)) == []


def test_info_and_xmp_that_disagree_show_both_values(tmp_path):
    xmp = ("<pdf:Producer>Adobe PDF Library 17</pdf:Producer><xmp:CreatorTool>Other Tool</xmp:CreatorTool>"
           "<xmp:CreateDate>2026-03-01T10:30:00+05:30</xmp:CreateDate><xmp:ModifyDate>2026-04-01T10:30:00+05:30</xmp:ModifyDate>")
    f = one(detect(tmp_path, with_meta(INFO, xmp)))
    assert f.title == "The /Info record and the XMP packet disagree"
    for both in ("Halcyon 4.2", "Adobe PDF Library 17", "Halcyon Writer", "Other Tool", "2026-02-01 09:29:00+05:30", "2026-03-01 10:30:00+05:30",
                 "2026-04-01 10:30:00+05:30"):
        assert both in f.detail, both


@pytest.mark.parametrize("field, xmp, shown", [
    ("producer", SAME.replace("<pdf:Producer>Halcyon 4.2", "<pdf:Producer>Other Maker 1.0"), "Other Maker 1.0"),
    ("creator tool", SAME.replace("<xmp:CreatorTool>Halcyon Writer", "<xmp:CreatorTool>Other Tool"), "Other Tool"),
    ("creation date", SAME.replace("2026-02-01T03:59:00Z", "2026-02-02T03:59:00Z"), "2026-02-02"),
    ("modification date", SAME.replace("<xmp:ModifyDate>2026-02-01T09:29:00+05:30", "<xmp:ModifyDate>2026-02-03T09:29:00+05:30"), "2026-02-03"),
])
def test_one_field_that_differs_is_named(tmp_path, field, xmp, shown):
    f = one(detect(tmp_path, with_meta(INFO, xmp)))
    assert field in f.detail and shown in f.detail
    assert sum(name in f.detail for name in ("producer", "creator tool", "creation date", "modification date")) == 1  # the others agree


def test_a_value_in_one_record_only_is_not_a_disagreement(tmp_path):
    assert detect(tmp_path, with_meta({"producer": "Halcyon 4.2"}, "<pdf:Producer>Halcyon 4.2</pdf:Producer>")) == []
    assert detect(tmp_path / "b", with_meta({}, "<xmp:CreatorTool>Only here</xmp:CreatorTool>")) == []


def test_xmp_values_written_as_attributes_are_read_too(tmp_path):
    attr = XMP.format("").replace('rdf:about=""', 'rdf:about="" xmp:CreatorTool="Other Tool"')
    assert "Other Tool" in one(detect(tmp_path, with_meta(INFO, attr))).detail


def test_document_text_in_a_value_is_one_clean_line(tmp_path):
    bad = "<img src=x onerror=alert(1)>\n‮\x07 more"
    f = one(detect(tmp_path, with_meta({**INFO, "producer": bad}, SAME)))
    assert "<img src=x onerror=alert(1)> more" in f.detail  # printed as text: the dossier escapes it, and no line break or bidi override gets through
    assert "\n" not in f.detail and "‮" not in f.detail and "\x07" not in f.detail


@pytest.mark.parametrize("packet, why", [
    ('<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><x:xmpmeta xmlns:x="adobe:ns:meta/">&a;</x:xmpmeta>', "declares"),
    ('<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF', "could not be parsed"),
])
def test_an_xmp_packet_that_cannot_be_read_safely_is_a_limitation(tmp_path, packet, why):
    doc = pymupdf.open(stream=SALARY, filetype="pdf")
    doc.set_xml_metadata(packet)
    (lim,) = detect(tmp_path, doc.tobytes())
    assert (lim.fclass, lim.detector, lim.family) == ("processing_limitation", DETECTOR, "limitation") and "XMP" in lim.title and why in lim.detail


# --- 3: a signature that does not reach the end of the file

def signed(extra: int = 0) -> bytes:
    """A PDF with a signature dictionary (no real signature in it) whose /ByteRange covers the file but for the signature value
    (`extra` bytes more than the file has, to make the range run past its end)."""
    doc = pymupdf.open(stream=SALARY, filetype="pdf")
    doc.update_object(doc.get_new_xref(), "<< /Type /Sig /Filter /Adobe.PPKLite /SubFilter /adbe.pkcs7.detached "
                      "/ByteRange [0 999999999 999999999 999999999] /Contents <" + "00" * 64 + "> >>")
    data = doc.tobytes()
    old = b"[0 999999999 999999999 999999999]"
    i = data.index(old)
    a = data.index(b"/Contents<", i)
    b = data.index(b">", a) + 1
    return data[:i] + b"[0 %9d %9d %9d]" % (a, b, len(data) - b + extra) + data[i + len(old):]


def test_a_signature_that_covers_the_whole_file_is_a_limitation_only(tmp_path):
    (lim,) = detect(tmp_path, signed())
    assert lim.fclass == "processing_limitation" and "signature" in lim.title.lower()
    assert "not checked" in lim.detail and "cryptograph" in lim.detail


def test_content_added_after_the_signature_range(tmp_path):
    later = incremental(signed(), lambda pg: pg.insert_text((72, 400), "added later", fontname="helv", fontsize=10))
    found = detect(tmp_path, later)
    f = one(found, limitations=1)
    assert f.title == "Content follows the signed byte range"
    assert f"{len(later) - len(signed())} bytes" in f.detail and "/ByteRange" in f.detail
    (lim,) = [x for x in found if x.fclass == "processing_limitation"]
    assert "not checked" in lim.detail


def test_a_byte_range_that_runs_past_the_end_of_the_file(tmp_path):
    f = one(detect(tmp_path, signed(extra=1000)), limitations=1)
    assert f.title == "The signed byte range runs past the end of the file" and "1000 bytes" in f.detail


# --- 4: embedded files, action keys, a rebuilt index

def with_parts() -> bytes:
    doc = pymupdf.open(stream=SALARY, filetype="pdf")
    doc.embfile_add("note.txt", b"plain text note", filename="note.txt", desc="a note")
    doc.xref_set_key(doc.pdf_catalog(), "OpenAction", f"[{doc[0].xref} 0 R /Fit]")  # a destination: the first page, fitted
    doc.update_object(doc.get_new_xref(), "<< /S /JavaScript /JS () >>")  # an action with an empty script
    return doc.tobytes()


def test_embedded_file_and_action_keys_are_listed_by_name_only(tmp_path):
    found = detect(tmp_path, with_parts())
    assert [f.fclass for f in found] == ["observation", "observation"]
    emb, act = found
    assert (emb.detector, emb.family) == (DETECTOR, "metadata") and emb.title == "PDF carries an embedded file"
    assert "note.txt" in emb.detail and "15 bytes" in emb.detail and "plain text note" not in emb.detail  # the name and size, never the body
    assert act.title == "PDF carries action keys" and act.detail.count("/") >= 3
    for name in ("JavaScript", "JS", "OpenAction"):
        assert f"/{name}" in act.detail
    assert "/Launch" not in act.detail and "/AA" not in act.detail
    for f in found:
        assert [(e.doc, e.page, tuple(e.box)) for e in f.evidence] == WHOLE


def test_action_names_are_whole_names_outside_strings():
    src = "<< /S /Launch /Title (about /JavaScript here (nested /AA) too) /JavaScriptX 1 /J#53 () /Other [/OpenAction] /AAA 2 >>"
    assert action_names(src) == ["JS", "Launch", "OpenAction"]  # #53 is S; /JavaScriptX and /AAA are other names; the string hides its own


def test_a_file_whose_index_had_to_be_rebuilt(tmp_path):
    f = one(detect(tmp_path, SALARY.replace(b"startxref", b"startxrex")))
    assert f.title == "The file's index had to be rebuilt to be read" and "rebuilt" in f.detail and "cross-reference" in f.detail


# --- 5: JPEG and PNG

def jpeg_with(software=None, taken=None, saved=None, xmp=None) -> bytes:
    exif = Image.Exif()
    if software:
        exif[0x0131] = software
    if saved:
        exif[0x0132] = saved
    if taken:
        exif.get_ifd(0x8769)[0x9003] = taken
    buf = io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(buf, "JPEG", exif=exif, **({"xmp": xmp.encode()} if xmp else {}))
    return buf.getvalue()


def png_with(software=None, xmp=None) -> bytes:
    info = PngImagePlugin.PngInfo()
    if software:
        info.add_text("Software", software)
    if xmp:
        info.add_itxt("XML:com.adobe.xmp", xmp)
    buf = io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(buf, "PNG", pnginfo=info)
    return buf.getvalue()


CREATOR = XMP.format("").replace('rdf:about=""', 'rdf:about="" xmp:CreatorTool="Adobe Photoshop 25.1"')


@pytest.mark.parametrize("name, data, end", [("jpeg", jpeg_bytes(), "end-of-image"), ("png", png_bytes(), "IEND")])
def test_bytes_after_the_final_end_marker_of_an_image(tmp_path, name, data, end):
    tail = b"APPENDED\xff\xd9more\x00"  # a JPEG end marker inside the extra bytes is not taken for the end of the picture
    f = one(detect(tmp_path, data + tail))
    assert f.title == "Bytes follow the end of the image" and f"{len(tail)} bytes begin at byte offset {len(data)}" in f.detail and end in f.detail
    assert "41 50 50 45 4e 44 45 44" in f.detail


@pytest.mark.parametrize("name, data, where", [
    ("exif", jpeg_with(software="Adobe Photoshop 25.1 (Windows)"), "EXIF Software"),
    ("xmp in a jpeg", jpeg_with(xmp=CREATOR), "XMP CreatorTool"),
    ("png text", png_with(software="GIMP 2.10.34"), "PNG Software"),
    ("xmp in a png", png_with(xmp=CREATOR), "XMP CreatorTool"),
])
def test_an_editor_named_in_the_picture_metadata(tmp_path, name, data, where):
    f = one(detect(tmp_path, data))
    assert f.title == "Image metadata names image-editing software" and where in f.detail
    assert re.search(r"Photoshop|GIMP", f.detail) and "does not show" in f.detail


def test_a_software_name_that_is_not_an_editor_gives_nothing(tmp_path):
    assert detect(tmp_path, jpeg_with(software="Halcyon Test Camera 1.0")) == []
    assert detect(tmp_path / "b", png_with(software="Halcyon Test Renderer")) == []


def test_exif_saved_time_after_the_time_taken(tmp_path):
    f = one(detect(tmp_path, jpeg_with(taken="2026:02:01 09:29:00", saved="2026:03:01 10:30:00")))
    assert f.title == "Image saved after it was taken" and "2026-02-01 09:29:00" in f.detail and "2026-03-01 10:30:00" in f.detail
    assert detect(tmp_path / "b", jpeg_with(taken="2026:02:01 09:29:00", saved="2026:02:01 09:29:30")) == []  # within the limit for a file's own save
    assert detect(tmp_path / "c", jpeg_with(taken="2026:03:01 09:29:00", saved="2026:02:01 09:29:00")) == []  # earlier: not this indicator
    assert detect(tmp_path / "d", jpeg_with(taken="not a date", saved="2026:02:01 09:29:00")) == []


def with_picture(jpg: bytes) -> bytes:
    doc = pymupdf.open()
    doc.new_page().insert_image(pymupdf.Rect(50, 50, 250, 250), stream=jpg)  # the JPEG bytes go into the file as they are
    return doc.tobytes()


def test_bytes_after_the_end_of_a_picture_inside_a_pdf(tmp_path):
    assert detect(tmp_path, with_picture(jpeg_bytes())) == []
    tail = b"APPENDED-JUNK"
    f = one(detect(tmp_path / "b", with_picture(jpeg_bytes() + tail)))
    assert f.title == "Bytes follow the end of a picture inside the PDF" and re.search(r"stored in object \d+", f.detail)
    assert f"{len(tail)} bytes begin at byte offset {len(jpeg_bytes())} " in f.detail and "in a stream of" in f.detail and "APPENDED-JUNK" in f.detail


def test_pictures_past_the_first_fifty_are_said_not_skipped(tmp_path):
    doc = pymupdf.open()
    for i in range(52):  # each picture differs, or PyMuPDF stores one for all
        buf = io.BytesIO()
        Image.new("RGB", (20 + i, 20), (i, 5, 5)).save(buf, "JPEG")
        doc.new_page().insert_image(pymupdf.Rect(50, 50, 250, 250), stream=buf.getvalue())
    (lim,) = detect(tmp_path, doc.tobytes())
    assert lim.fclass == "processing_limitation" and "52" in lim.detail and "50" in lim.detail


# --- what cannot be read

TRUNCATED_PDF = SALARY[:300]
BROKEN = {"empty": b"", "text": b"plain text, not a document", "pdf header only": b"%PDF-1.7\nnot really a pdf", "pdf cut short": TRUNCATED_PDF,
          "jpeg cut short": jpeg_bytes()[:40], "jpeg without its end": jpeg_bytes()[:-2], "png cut short": png_bytes()[:20],
          "png without IEND": png_bytes()[:-12], "png chunk too long": png_bytes()[:16] + b"\xff\xff\xff\xff" + png_bytes()[20:],
          "jpeg of zeros": b"\xff\xd8\xff" + b"\x00" * 40, "png of ones": b"\x89PNG\r\n\x1a\n" + b"\xff" * 40}


@pytest.mark.parametrize("name", BROKEN)
def test_a_file_that_cannot_be_read_is_a_limitation_not_a_pass(tmp_path, name):
    found = detect(tmp_path, BROKEN[name])
    assert found and {f.fclass for f in found} == {"processing_limitation"}
    assert all((f.detector, f.family) == (DETECTOR, "limitation") and f.detail for f in found)


def test_a_pdf_without_an_end_marker_is_said_not_skipped(tmp_path):
    found = detect(tmp_path, SALARY[:-6])  # still opens, but there is no marker to measure the extra bytes from
    assert any(f.fclass == "processing_limitation" and "no end-of-file marker" in f.detail for f in found)


def test_the_limits_of_the_check_are_stated(tmp_path):
    (lim,) = detect(tmp_path, signed())
    assert "malware" in lim.detail or "does not check" in lim.detail


# --- the stage

def case_with(*modes):
    pages = [Page(n=i, width=10, height=10, read_mode=m, quality_class="text-layer" if m == "text-layer" else "good") for i, m in enumerate(modes, 1)]
    doc = Document(id="D1", sha256="0", filename="a.pdf", stored_path="a.pdf", pages=pages)
    return Case(id="C", created="2026-11-06T00:00:00+00:00", documents=[doc])


def test_file_detectors_run_on_every_document_that_was_read_whatever_its_read_mode(monkeypatch, tmp_path):
    assert forensics.FILE_DETECTORS == [file_structure]
    calls = []
    monkeypatch.setattr(forensics, "FILE_DETECTORS", [lambda case, doc, ctx: calls.append(doc.id) or []])
    monkeypatch.setattr(forensics, "DIGITAL_DETECTORS", [])
    monkeypatch.setattr(forensics, "SCAN_DETECTORS", [])
    for modes, want in ((("text-layer",), ["D1"]), (("ocr",), ["D1"]), (("text-layer", "ocr"), ["D1"]), ((), [])):
        calls.clear()
        cd = CaseDir.create(tmp_path / str(len(modes)) / "_".join(modes))
        run_forensics(case_with(*modes), Ctx(cd, AuditLog(cd.audit_path), TH))
        assert calls == want  # a document the read step could not read has no pages and is skipped, as by every later step


def test_through_the_stage_a_finding_has_an_id_and_the_run_is_logged(tmp_path):
    case, cd, _ = create_case(tmp_path, [("a.pdf", SALARY + b"\nAPPENDED-LATER")], TH)
    case = run_case(cd, TH, stages={"read": read_stage, "forensics": run_forensics})
    (f,) = [x for x in case.findings if x.detector == DETECTOR]
    assert f.id.startswith("F-") and f.fclass == "observation" and "APPENDED-LATER" in f.detail
    ran = [e.data for e in AuditLog(cd.audit_path).events() if e.event == "doc_forensics" and e.data["detector"] == "file_structure"]
    assert ran == [{"doc": "D1", "detector": "file_structure", "findings": 1}]
