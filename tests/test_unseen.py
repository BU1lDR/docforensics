"""Documents of two types the tool has no spec for (an invoice and an electricity bill), made to measure the local model's reading
(scope D, package X). The truth lists every fact the generator printed, with the words and the box; the scorer trusts it."""
import hashlib
import io
from decimal import Decimal

import pymupdf
import pytest
from PIL import Image

from datagen import build
from datagen.fictional import identity
from datagen.unseen import BASE, PACK, SPAN, build_case, draw_bill, draw_invoice, plan_cases
from docforensics.config import Thresholds
from docforensics.ingest import create_case
from docforensics.pipeline import run_case

PX = 200 / 72


def amount(t, name):
    return Decimal(t["fields"][name]["value"])


@pytest.mark.parametrize("layout", ["A", "B"])
def test_the_invoice_adds_up_and_every_fact_has_its_box(layout):
    d = draw_invoice(identity(5), layout, 5)
    t = d.truth
    assert t["type"] == "invoice" and t["layout"] == layout
    assert amount(t, "subtotal") + amount(t, "tax") == amount(t, "total") > 0
    assert sum(Decimal(r["amount"]["text"].replace(",", "")) for r in t["rows"]) == amount(t, "subtotal")
    assert all(c["text"] and len(c["box"]) == 5 for r in t["rows"] for c in r.values())
    assert {"seller", "invoice_number", "invoice_date", "due_date", "po_number", "buyer", "subtotal", "tax", "total",
            "payment_terms", "bank_account"} == set(t["fields"])
    assert t["fields"]["invoice_date"]["value"] < t["fields"]["due_date"]["value"]  # ISO dates compare as text
    _boxes_hold_the_printed_words(d)


@pytest.mark.parametrize("layout", ["A", "B"])
def test_the_bill_adds_up_and_every_fact_has_its_box(layout):
    d = draw_bill(identity(6), layout, 6)
    t = d.truth
    assert t["type"] == "bill" and t["layout"] == layout
    assert amount(t, "energy_charges") + amount(t, "fixed_charges") + amount(t, "electricity_duty") == amount(t, "total_due")
    assert amount(t, "amount_after_due") > amount(t, "total_due")
    assert int(t["fields"]["current_reading"]["text"]) - int(t["fields"]["previous_reading"]["text"]) == int(t["fields"]["units_consumed"]["text"])
    assert t["fields"]["customer"]["text"] == identity(6).name and t["fields"]["consumer_no"]["text"] == identity(6).consumer_no
    assert t["fields"]["bill_date"]["value"] < t["fields"]["due_date"]["value"]
    _boxes_hold_the_printed_words(d)


def _boxes_hold_the_printed_words(d):
    """The text layer's words inside each box read as the text the truth says was printed there."""
    with pymupdf.open(stream=d.pdf, filetype="pdf") as pdf:
        words = pdf[0].get_text("words")
    assert d.truth["fields"]
    for name, f in d.truth["fields"].items():
        page, x0, y0, x1, y1 = f["box"]
        assert page == 1 and 0 <= x0 < x1 <= 595 * PX and 0 <= y0 < y1 <= 842 * PX, name
        inside = [w for w in words if x0 <= (w[0] + w[2]) / 2 * PX <= x1 and y0 <= (w[1] + w[3]) / 2 * PX <= y1]
        assert " ".join(w[4] for w in sorted(inside, key=lambda w: (round(w[1]), w[0]))) == f["text"], name


def test_drawing_is_deterministic_and_the_seed_changes_it():
    a, b = draw_invoice(identity(5), "A", 5), draw_invoice(identity(5), "A", 5)
    assert a.pdf == b.pdf and a.truth == b.truth and draw_invoice(identity(5), "A", 6).truth != a.truth
    assert draw_bill(identity(5), "B", 5).pdf == draw_bill(identity(5), "B", 5).pdf


def test_the_layouts_word_the_labels_differently():
    labels = lambda draw, layout: {n: f["label"] for n, f in draw(identity(5), layout, 5).truth["fields"].items()}
    for draw in (draw_invoice, draw_bill):
        a, b = labels(draw, "A"), labels(draw, "B")
        assert a.keys() == b.keys() and sum(a[k] != b[k] for k in a) >= len(a) // 2


def test_the_plan_keeps_to_its_own_seeds_and_covers_every_medium_and_layout():
    plan = plan_cases("ext-dev", 8)
    assert [p["case"] for p in plan][:2] == ["ext-dev-x-0000", "ext-dev-x-0001"]
    assert {p["seed"] for p in plan} == set(range(BASE["ext-dev"] + PACK, BASE["ext-dev"] + PACK + 8))
    assert {p["medium"] for p in plan} == {"digital", "mild", "150dpi", "120dpi"}
    assert {(p["invoice_layout"], p["bill_layout"]) for p in plan} == {("A", "A"), ("A", "B"), ("B", "A"), ("B", "B")}
    assert SPAN > 100 and max(build.SPLIT_BASE.values()) + build.SPLIT_SPAN <= BASE["ext-dev"] < BASE["ext-test"]
    assert plan_cases("ext-dev", 3, 5)[0]["case"] == "ext-dev-x-0005"
    with pytest.raises(ValueError):
        plan_cases("dev", 1)
    with pytest.raises(ValueError):
        plan_cases("ext-dev", 1, SPAN)


def test_a_digital_case_is_two_pdfs_and_a_scanned_one_two_jpegs_with_boxes_in_the_scan():
    digital, scanned = (build_case(p) for p in (plan_cases("ext-dev", 4)[0], plan_cases("ext-dev", 4)[1]))
    files, entry = digital
    assert entry["medium"] == "digital" and list(files) == ["01_invoice.pdf", "02_bill.pdf"]
    assert [d["type"] for d in entry["docs"]] == ["invoice", "bill"]
    assert all(d["sha256"] == hashlib.sha256(files[d["file"]]).hexdigest() for d in entry["docs"])
    files, entry = scanned
    assert entry["medium"] == "mild" and list(files) == ["01_invoice.jpg", "02_bill.jpg"]
    for d in entry["docs"]:
        w, h = Image.open(io.BytesIO(files[d["file"]])).size
        for f in d["fields"].values():
            _, x0, y0, x1, y1 = f["box"]
            assert -5 <= x0 < x1 <= w + 5 and -5 <= y0 < y1 <= h + 5
    assert build_case(plan_cases("ext-dev", 4)[1])[0] == files  # the same bytes again


def test_the_tool_has_no_type_for_these_documents(tmp_path):
    """Both layouts of both documents are 'unknown' to the keyword classifier: that is what the model is asked about."""
    files = []
    for n, (draw, layout) in enumerate([(draw_invoice, "A"), (draw_invoice, "B"), (draw_bill, "A"), (draw_bill, "B")], 1):
        files.append((f"d{n}.pdf", draw(identity(n), layout, n).pdf))
    _, cd, _ = create_case(tmp_path / "data", files, Thresholds())
    assert [d.doc_type for d in run_case(cd, Thresholds()).documents] == ["unknown"] * 4
