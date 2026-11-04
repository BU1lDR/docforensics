"""Bank statement end to end: drawn truth in, fields out. Boxes are compared in 200-DPI pixels, values after normalisation."""
from pathlib import Path

import pymupdf
import pytest
from PIL import Image

from datagen.fictional import identity
from datagen.layouts.statement import draw_statement
from docforensics.config import Thresholds
from docforensics.ingest import create_case
from docforensics.pipeline import run_case
from docforensics.understand import specs as specs_module
from docforensics.understand.classify import classify
from docforensics.understand.extract import extract_document
from docforensics.understand.specs import FieldSpec, TypeSpec, load_specs
from tests.helpers import SLIP_LINES, iou, lines_pdf, png_bytes, within_only

TH = Thresholds()
SPECS = load_specs()
COLS = ("date", "description", "debit", "credit", "balance")
GARDEN = [(72, 100, "Minutes of the garden committee", 12), (72, 130, "Roses and tulips were discussed.", 11)]
QUOTE = [(72, 100, "Vendor Quotation", 14), (72, 130, "Quote Date: 31/03/2026", 11), (72, 150, "Quoted Total 45,000.00", 11),
         (72, 170, "Customer: Meera K. Varghese", 11)]
RENAMED_ALL = {"head.description": "Narration", "head.debit": "Withdrawal Amt", "head.credit": "Deposit Amt", "head.balance": "Bal"}
RENAMED_MONEY = {"head.debit": "Withdrawal Amt", "head.credit": "Deposit Amt"}


def period_pdf(period: str) -> bytes:
    """A bare statement: enough keywords to classify, one period line, no other dates."""
    return lines_pdf([(40, 60, "Halcyon Test Bank", 18), (40, 80, "Statement of Account", 11), (40, 130, "Statement Period", 9),
                      (160, 130, period, 9)])


def run(tmp_path, *pdfs):
    case, cd, audit = create_case(tmp_path / "data", [(f"d{i}.pdf", p) for i, p in enumerate(pdfs, 1)], TH)
    return within_only(run_case(cd, TH)), audit


def header(doc):
    return {f.name: f for f in doc.fields if f.row is None}


def cells(doc):
    return {(f.row, f.name.removeprefix("txn.")): f for f in doc.fields if f.row is not None}


def test_classify_statement_payslip_unknown(tmp_path):
    case, _ = run(tmp_path, draw_statement(identity(1)).pdf, lines_pdf(SLIP_LINES), lines_pdf(GARDEN))
    statement, slip, garden = case.documents
    assert statement.doc_type == "bank_statement" and statement.type_conf >= 0.5
    assert slip.doc_type == "unknown"  # five lines hold too little of a payslip to be called one
    assert garden.doc_type == "unknown" and garden.type_conf == 0.0
    assert classify(statement.pages, SPECS)[0] == "bank_statement" and classify([], SPECS) == ("unknown", 0.0)


def test_tie_between_types_is_unknown(tmp_path):
    text = (Path(specs_module.__file__).parent / "specs" / "bank_statement.toml").read_text(encoding="utf-8")
    (tmp_path / "twin.toml").write_bytes(text.replace('type = "bank_statement"', 'type = "twin"').encode())
    doc = run(tmp_path, draw_statement(identity(1)).pdf)[0].documents[0]
    assert classify(doc.pages, load_specs(tmp_path)) == ("unknown", 1.0)  # same score twice: no guessing between them


def test_specs_load_and_a_bad_file_names_itself(tmp_path):
    assert set(SPECS) == {"bank_statement", "payslip", "loan_application"}
    (tmp_path / "bad.toml").write_bytes(b'type = "x"\nmin_score = 1\nkeywords = {}\nsurprise = 1\n')
    with pytest.raises(ValueError, match="bad.toml"):
        load_specs(tmp_path)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_header_fields_match_truth(tmp_path, seed):
    drawn = draw_statement(identity(seed), seed=seed)
    got = header(run(tmp_path, drawn.pdf)[0].documents[0])
    assert set(got) == set(drawn.truth["fields"]) and len(got) == 8
    for name, want in drawn.truth["fields"].items():
        page, *box = drawn.truth["boxes"][name]
        assert got[name].value == want, name
        assert got[name].page == page and iou(got[name].box, box) >= 0.9, name
        assert got[name].conf >= TH.low_conf, name


def test_table_cells_match_truth(tmp_path):
    drawn = draw_statement(identity(4), rows=12, seed=4)
    got = cells(run(tmp_path, drawn.pdf)[0].documents[0])
    assert len(drawn.truth["rows"]) == 12 and len(got) == 60
    for r, row in enumerate(drawn.truth["rows"], 1):
        for col in COLS:
            f = got[(r, col)]
            assert f.value == row[col], (r, col)
            if row[col] is None:
                assert f.word_ids == [] and f.raw == ""  # an empty cell is found empty, with the cell's place
            else:
                page, *box = drawn.truth["boxes"][f"{col}@{r}"]
                assert f.page == page and iou(f.box, box) >= 0.9, (r, col)
                assert f.conf >= TH.low_conf, (r, col)


def test_every_field_has_existing_word_ids_and_box_on_page(tmp_path):
    doc = run(tmp_path, draw_statement(identity(5), rows=40, seed=5).pdf)[0].documents[0]
    assert len(doc.pages) == 2 and doc.fields
    for f in doc.fields:
        if not f.word_ids:
            assert f.value is None, f.name  # a value always comes from words
            continue
        page = doc.pages[f.page - 1]
        words = {w.id: w for w in page.words}
        assert set(f.word_ids) <= set(words), f.name
        x0, y0, x1, y1 = f.box
        assert 0 <= x0 < x1 <= page.width and 0 <= y0 < y1 <= page.height, f.name
        assert f.raw == " ".join(words[i].text for i in f.word_ids)
    assert len({f.id for f in doc.fields}) == len(doc.fields)


def test_unknown_type_uses_generic_path_and_says_so(tmp_path):
    doc = run(tmp_path, lines_pdf(QUOTE))[0].documents[0]
    assert doc.doc_type == "unknown" and doc.fields
    assert all("unsupported type: generic extraction" in f.note for f in doc.fields)
    by = {f.name: f for f in doc.fields}
    assert by["quote_date"].kind == "date" and by["quote_date"].value == "2026-03-31"
    assert by["customer"].kind == "text" and by["customer"].value == "Meera K. Varghese"
    assert any(f.kind == "amount" and f.value == "45000.00" for f in doc.fields)
    assert {f.name for f in extract_document(doc, None, TH)} == set(by)  # the same without the stage


def test_unknown_type_adds_limitation_finding(tmp_path):
    case, audit = run(tmp_path, draw_statement(identity(1)).pdf, lines_pdf(QUOTE))
    lims = [f for f in case.findings if f.fclass == "processing_limitation"]
    assert [f.title for f in lims] == ["Unsupported document type: generic extraction only, no document-specific checks"]
    assert lims[0].family == "limitation" and lims[0].evidence[0].doc == "D2"
    names = [e.event for e in audit.events()]
    assert names.count("doc_classified") == 2 and names.count("doc_extracted") == 2


def test_document_that_was_not_read_is_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)  # the 20x20 image is over twice the limit: the read step fails
    case, audit = run(tmp_path, png_bytes())
    lims = [f for f in case.findings if f.fclass == "processing_limitation"]
    assert case.documents[0].pages == [] and [f.detector for f in lims] == ["read"]  # nothing added on top of the read failure
    assert "doc_classified" not in [e.event for e in audit.events()]


@pytest.mark.parametrize("renamed, kept", [(RENAMED_ALL, {"date"}), (RENAMED_MONEY, {"date", "description", "balance"})])
def test_renamed_columns_give_missing_not_wrong(tmp_path, renamed, kept):
    drawn = draw_statement(identity(5), seed=5, overrides=renamed)
    got = cells(run(tmp_path, drawn.pdf)[0].documents[0])
    assert len(got) == 60
    for (r, col), f in got.items():
        want = drawn.truth["rows"][r - 1][col]
        assert f.value is None or f.value == want or f.conf < TH.low_conf, (r, col, f.value, want)
        if col in kept:
            assert f.value == want, (r, col)  # a column that is recognised still reads in full
        else:
            assert f.value is None and "column not found in the table header" in f.note, (r, col)  # missing, not misplaced


def test_ambiguous_date_field_is_low_confidence(tmp_path):
    doc = run(tmp_path, period_pdf("04/05/2026 to 06/05/2026"))[0].documents[0]
    start = header(doc)["period_start"]
    assert start.value == "2026-05-04" and start.conf < TH.low_conf and start.note == "ambiguous DD/MM or MM/DD"
    assert header(doc)["period_end"].conf < TH.low_conf


def test_ambiguous_date_inherits_documents_convention(tmp_path):
    doc = run(tmp_path, period_pdf("04/05/2026 to 30/05/2026"))[0].documents[0]
    start, end = header(doc)["period_start"], header(doc)["period_end"]
    assert end.value == "2026-05-30" and end.note == "" and end.conf == 1.0  # 30 can only be a day
    assert start.value == "2026-05-04" and start.conf >= TH.low_conf and "other dates show" in start.note


def test_absent_field_is_explicit_not_silent(tmp_path):
    doc = run(tmp_path, period_pdf("01/05/2026 to 31/05/2026"))[0].documents[0]
    gone = header(doc)["address"]
    assert (gone.value, gone.raw, gone.conf, gone.word_ids, gone.page, gone.note) == (None, "", 0.0, [], 0, "label not found")
    assert not [f for f in doc.fields if f.row is not None]  # no table header on the page: no cells invented


def test_value_below_the_label(tmp_path):
    spec = TypeSpec(type="t", min_score=1, keywords={"reference": 1},
                    fields=[FieldSpec(name="ref", kind="id", labels=["reference"], position="below")])
    near = run(tmp_path / "a", lines_pdf([(72, 100, "Reference", 11), (72, 118, "TST-9912", 11)]))[0].documents[0]
    far = run(tmp_path / "b", lines_pdf([(72, 100, "Reference", 11), (72, 400, "TST-9912", 11)]))[0].documents[0]
    assert extract_document(near, spec, TH)[0].value == "TST-9912"
    assert extract_document(far, spec, TH)[0].value is None  # a line far below is not the label's value


def test_continuation_page_without_header_uses_previous_columns(tmp_path):
    drawn = draw_statement(identity(6), rows=70, seed=6)
    with pymupdf.open(stream=drawn.pdf, filetype="pdf") as pdf:
        assert len(pdf) == 3 and "Debit" in pdf[0].get_text() and "Debit" not in pdf[1].get_text()
    doc = run(tmp_path, drawn.pdf)[0].documents[0]
    got = cells(doc)
    assert len(got) == 350
    for r, row in enumerate(drawn.truth["rows"], 1):
        for col in COLS:
            assert got[(r, col)].value == row[col], (r, col)
    assert [got[(r, "date")].page for r in (30, 31, 60, 61, 70)] == [1, 2, 2, 3, 3]


@pytest.mark.parametrize("page_class, cap", [("good", TH.rel_good), ("degraded", TH.rel_degraded), ("poor", TH.rel_poor)])
def test_scan_field_conf_follows_page_class(tmp_path, page_class, cap):
    doc = run(tmp_path, draw_statement(identity(2), seed=2).pdf)[0].documents[0]
    for page in doc.pages:
        page.quality_class = page_class
    conf = [f.conf for f in extract_document(doc, SPECS["bank_statement"], TH) if f.value is not None]
    assert conf and max(conf) == cap  # nothing is trusted more than its page, and a clean field is trusted exactly that much
