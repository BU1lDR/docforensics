import hashlib
import io
import stat

import pymupdf
import pytest

from docforensics.config import Thresholds
from docforensics.ingest import create_case, sniff
from tests.helpers import jpeg_bytes, pdf_bytes, png_bytes

TH = Thresholds()


def test_sniff_by_magic_not_extension(tmp_path):
    assert sniff(pdf_bytes()) == "pdf"
    assert sniff(png_bytes()) == "png"
    assert sniff(jpeg_bytes()) == "jpeg"
    assert sniff(b"MZ\x90\x00\x03") is None
    assert sniff(b"") is None
    case, cd, _ = create_case(tmp_path, [("renamed.txt", pdf_bytes()), ("fake.pdf", b"hello there")], TH)
    assert [d.filename for d in case.documents] == ["renamed.txt"]
    assert case.documents[0].stored_path.endswith(".pdf")
    assert [d.kind for d in create_case(tmp_path, [("p.png", png_bytes()), ("j.jpg", jpeg_bytes())], TH)[0].documents] == ["image", "image"]


GOOD = pdf_bytes()
ENCRYPTED = pdf_bytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="u", owner_pw="o")
CORRUPT = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 9 0 R >>\nendobj\n" + bytes(range(256)) * 4


@pytest.mark.parametrize("name, bad, reason, before, after", [
    ("empty.pdf", b"", "empty", 1, 1),
    ("big.pdf", b"\0" * (TH.max_file_bytes + 1), "too large", 1, 1),
    ("notes.pdf", b"just some text\n", "unsupported", 1, 1),
    ("locked.pdf", ENCRYPTED, "encrypted", 1, 1),
    ("broken.pdf", CORRUPT, "corrupt", 1, 1),
    ("long.pdf", pdf_bytes(pages=TH.max_pages + 1), "pages", 1, 1),
    ("eleventh.pdf", GOOD, "limit", TH.max_docs, 0),
])
def test_rejections_have_reason_and_audit_event(tmp_path, name, bad, reason, before, after):
    files = [(f"ok{i}.pdf", GOOD) for i in range(before)] + [(name, bad)] + [("after.pdf", GOOD)] * after
    case, cd, audit = create_case(tmp_path, files, TH)
    assert len(case.documents) == before + after
    rejected = [e for e in audit.events() if e.event == "file_rejected"]
    assert len(rejected) == 1
    assert rejected[0].data["filename"] == name and reason in rejected[0].data["reason"]
    lims = [f for f in case.findings if f.fclass == "processing_limitation"]
    assert len(lims) == 1 and lims[0].detector == "ingest"
    assert reason in lims[0].title and name in lims[0].detail
    assert audit.verify() == (True, None)


def test_hostile_filename_stored_by_hash(tmp_path):
    data = pdf_bytes()
    sha = hashlib.sha256(data).hexdigest()
    case, cd, _ = create_case(tmp_path / "data", [("..\\..\\x.pdf", data), ("evil\n\x1b[31m.pdf", data)], TH)
    d = case.documents[0]
    assert d.filename == "..\\..\\x.pdf"
    assert d.stored_path == f"files/{sha}.pdf" and d.sha256 == sha
    stored = cd.root / d.stored_path
    assert stored.read_bytes() == data
    assert not stored.stat().st_mode & stat.S_IWRITE
    assert [p.name for p in cd.files.iterdir()] == [f"{sha}.pdf"]
    assert not list(tmp_path.rglob("x.pdf"))
    assert not any(c in case.documents[1].filename for c in "\n\x1b")


def test_same_file_twice_gets_two_documents(tmp_path):
    data = pdf_bytes()
    case, cd, audit = create_case(tmp_path, [("a.pdf", data), ("b.pdf", data)], TH)
    assert [d.id for d in case.documents] == ["D1", "D2"]
    assert case.documents[0].sha256 == case.documents[1].sha256
    assert len(list(cd.files.iterdir())) == 1
    assert [e.event for e in audit.events()].count("file_ingested") == 2
    assert [e.event for e in audit.events()][0] == "case_created"


def test_a_cut_off_pdf_is_read_without_the_library_printing_each_broken_object(tmp_path, monkeypatch):
    """MuPDF wrote a line to stdout for every broken object of a damaged file (440 lines for one cut-off statement), which buried the summary
    the command line prints; the damage is a finding of the case, so the library's own lines are switched off. What the library prints is
    caught where it is sent (pymupdf keeps the stdout it found at import, which a test's capture does not replace)."""
    from datagen.fictional import identity
    from datagen.layouts.statement import draw_statement
    from docforensics.pipeline import run_case

    printed = io.StringIO()
    monkeypatch.setattr(pymupdf, "_g_out_message", printed)
    good = draw_statement(identity(1), seed=1).pdf
    _, cd, _ = create_case(tmp_path / "data", [("cut.pdf", good[: len(good) // 2]), ("good.pdf", good)], TH)
    case = run_case(cd, TH)
    assert "MuPDF" not in printed.getvalue()
    assert any(f.detector == "file_structure" for f in case.findings)  # the damage is still reported, in the case
