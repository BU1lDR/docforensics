"""The dataset generator is test equipment, but the extraction tests trust its truth, so it gets its own checks."""
from decimal import Decimal

import pymupdf
import pytest

from datagen.fictional import identity
from datagen.layouts import money
from datagen.layouts.statement import draw_statement
from docforensics.read.pdf import pdf_meta


def test_money_uses_lakh_grouping():
    assert money(Decimal("148034.5")) == "1,48,034.50" and money(999) == "999.00" and money(1234567) == "12,34,567.00"
    assert money(0) == "0.00" and money(Decimal("1000")) == "1,000.00" and money(Decimal("-52000")) == "-52,000.00"


def test_identity_and_statement_are_deterministic():
    assert identity(3) == identity(3) and identity(3) != identity(4)
    a, b = draw_statement(identity(3), seed=9), draw_statement(identity(3), seed=9)
    assert a.truth == b.truth and a.truth != draw_statement(identity(3), seed=10).truth
    assert identity(3).net_pay == identity(3).monthly_gross - identity(3).deductions > 0


def test_rows_chain_and_the_salary_row():
    ident = identity(7)
    t = draw_statement(ident, rows=40, seed=7).truth
    bal = Decimal(t["fields"]["opening_balance"])
    for row in t["rows"]:
        bal += Decimal(row["credit"] or 0) - Decimal(row["debit"] or 0)
        assert Decimal(row["balance"]) == bal >= 0
        assert (row["debit"] is None) != (row["credit"] is None)
    assert Decimal(t["fields"]["closing_balance"]) == bal
    assert Decimal(t["rows"][1]["credit"]) == ident.net_pay and t["rows"][1]["date"] <= f"{ident.month:%Y-%m}-05"
    dates = [r["date"] for r in t["rows"]]
    assert dates == sorted(dates) and t["fields"]["period_start"] <= dates[0] and dates[-1] <= t["fields"]["period_end"]


def test_override_replaces_one_cell_without_recomputing():
    base = draw_statement(identity(7), rows=12, seed=7)
    d = draw_statement(identity(7), rows=12, seed=7, overrides={"balance@4": "9,99,999.00", "closing_balance": "1.00"})
    assert d.truth["rows"][3]["balance"] == "999999.00" and d.truth["fields"]["closing_balance"] == "1.00"
    assert d.truth["overridden"] == {"balance@4": "9,99,999.00", "closing_balance": "1.00"}
    assert [r for i, r in enumerate(d.truth["rows"]) if i != 3] == [r for i, r in enumerate(base.truth["rows"]) if i != 3]
    with pymupdf.open(stream=d.pdf, filetype="pdf") as pdf:
        assert "9,99,999.00" in pdf[0].get_text() and base.truth["rows"][3]["balance"] != "999999.00"
    for bad in ("balance@99", "nonsense", "balance@0"):
        with pytest.raises(ValueError, match=bad):
            draw_statement(identity(7), overrides={bad: "1.00"})


def test_pages_and_metadata(tmp_path):
    drawn = draw_statement(identity(2), rows=70, seed=2)
    (tmp_path / "s.pdf").write_bytes(drawn.pdf)
    meta = pdf_meta(tmp_path / "s.pdf")
    assert meta["pages"] == "3" and meta["producer"] and "PyMuPDF" not in meta["producer"]
    assert meta["creationDate"].startswith("D:2026") and meta["creationDate"] == meta["modDate"]
    assert {p for p, *_ in drawn.truth["boxes"].values()} == {1, 2, 3}
    with pytest.raises(ValueError):
        draw_statement(identity(2), layout="Z")
