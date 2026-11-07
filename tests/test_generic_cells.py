"""The generic reader (a document of a type with no spec) reads 'label: value' pairs. Two pairs side by side on one row, or a name in
a cell to the left of a pair, are separate cells; the label of a pair is not glued to the text beside it."""
from tests.helpers import lines_pdf
from tests.test_statement_extraction import run

INVOICE = [(50, 60, "TAX INVOICE", 18),
           (50, 90, "Northwind Traders Pvt Ltd", 11), (350, 90, "Invoice No: INV-2026-00417", 11),
           (50, 110, "14 Example Road, Pune 411001", 11), (350, 110, "Date: 12 Oct 2026", 11),
           (50, 140, "Customer:", 11), (130, 140, "Contoso Retail LLP", 11), (350, 140, "GSTIN: 27AAAAA0000A1Z5", 11)]


def test_a_pair_beside_a_name_or_beside_another_pair_is_read_by_itself(tmp_path):
    doc = run(tmp_path, lines_pdf(INVOICE))[0].documents[0]
    assert doc.doc_type == "unknown"
    by = {f.name: f for f in doc.fields}
    assert by["invoice_no"].value == "INV-2026-00417"
    assert by["date"].kind == "date" and by["date"].value == "2026-10-12"
    assert by["customer"].value == "Contoso Retail LLP"
    assert by["gstin"].value == "27AAAAA0000A1Z5"
    assert not [name for name in by if "northwind" in name or "example" in name]
