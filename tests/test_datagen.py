"""The dataset generator is test equipment, but the extraction tests trust its truth, so it gets its own checks."""
from datetime import date, timedelta
from decimal import Decimal

import pymupdf
import pytest

from datagen.fictional import identity
from datagen.layouts import DAYS, MONTHS, PAGE, PX, money, words
from datagen.layouts.application import draw_application
from datagen.layouts.payslip import draw_payslip
from datagen.layouts.statement import draw_statement
from docforensics.read.pdf import pdf_meta
from docforensics.understand.normalise import amount_in_words


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


def test_words_are_the_indian_system_and_the_reader_reads_them_back():
    assert words(47200) == "Rupees Forty Seven Thousand Two Hundred Only" and words(120000) == "Rupees One Lakh Twenty Thousand Only"
    assert words(10_000_000) == "Rupees One Crore Only" and words(105) == "Rupees One Hundred Five Only" and words(19) == "Rupees Nineteen Only"
    for n in (1, 9, 10, 19, 20, 21, 99, 100, 101, 110, 999, 1000, 1001, 10_000, 47_200, 99_999, 100_000, 123_456, 1_234_567, 12_345_678, 99_999_999):
        assert amount_in_words(words(n)) == Decimal(n), n  # the generator and the reader were written apart and agree
    with pytest.raises(ValueError):
        words(-1)


def test_payslip_adds_up_and_comes_from_the_identity():
    for seed in range(1, 8):
        ident = identity(seed)
        t = draw_payslip(ident, seed=seed).truth
        f, rows = t["fields"], t["rows"]
        earn = [Decimal(r["earning_amount"]) for r in rows]
        ded = [Decimal(r["deduction_amount"]) for r in rows if r["deduction_amount"] is not None]
        assert t["type"] == "payslip" and t["layout"] == "A" and len(earn) == 4 and len(ded) == 3 and min(earn + ded) > 0, seed
        assert sum(earn) == Decimal(f["gross_earnings"]) == ident.monthly_gross, seed
        assert sum(ded) == Decimal(f["total_deductions"]) == ident.deductions, seed
        assert Decimal(f["net_pay"]) == ident.net_pay and f["net_pay_words"] == words(ident.net_pay), seed
        assert (f["employer"], f["employee_name"], f["employee_id"], f["designation"], f["bank_account"]) == (
            ident.employer, ident.name, ident.employee_id, ident.designation, ident.account_no), seed
        assert set(t["boxes"]) >= set(f) | {"stamp", "earning_amount@4", "deduction_amount@3"} and "deduction_amount@4" not in t["boxes"]  # a blank cell has no box
        assert rows[3]["deduction_name"] is None and rows[3]["deduction_amount"] is None


def test_payslip_months_follow_the_statement_month():
    for seed in range(1, 8):
        ident = identity(seed)
        f = draw_payslip(ident, seed=seed).truth["fields"]
        prev = ident.month - timedelta(days=1)
        assert f["pay_month"] == f"{MONTHS[prev.month - 1]} {prev.year}" and f["pay_date"] == ident.month.isoformat(), seed  # the 1st, before the salary credit


def test_application_comes_from_the_identity_and_prints_a_true_weekday():
    for seed in range(1, 8):
        ident = identity(seed)
        d = draw_application(ident, seed=seed)
        f = d.truth["fields"]
        assert d.truth["type"] == "loan_application" and d.truth["layout"] == "A", seed
        assert (f["applicant_name"], f["address"], f["employer"], f["account_no"]) == (ident.name, ident.address, ident.employer, ident.account_no), seed
        assert tuple(Decimal(f[k]) for k in ("declared_monthly_income", "loan_amount", "tenure_months", "existing_emi")) == (
            ident.monthly_gross, ident.loan_amount, ident.tenure_months, ident.existing_emi), seed
        day = date.fromisoformat(f["application_date"])
        after = ident.month + timedelta(days=31)  # always inside the next month
        assert (day.year, day.month) == (after.year, after.month) and 10 <= day.day <= 20, seed
        with pymupdf.open(stream=d.pdf, filetype="pdf") as pdf:
            assert f"{DAYS[day.weekday()]} {day.day:02d} {MONTHS[day.month - 1][:3]} {day.year}" in pdf[0].get_text(), seed


def test_same_inputs_same_documents_and_the_stamp_and_signature_sit_on_the_page():
    ident = identity(4)
    slip, app = draw_payslip(ident, seed=4), draw_application(ident, seed=4)
    assert slip.truth == draw_payslip(ident, seed=4).truth != draw_payslip(identity(5), seed=4).truth
    assert app.truth == draw_application(ident, seed=4).truth != draw_application(identity(5), seed=4).truth
    for drawn, key in ((slip, "stamp"), (app, "signature")):
        page, x0, y0, x1, y1 = drawn.truth["boxes"][key]
        assert page == 1 and 0 <= x0 < x1 <= PAGE[0] * PX and 0 <= y0 < y1 <= PAGE[1] * PX, key
    for drawn in (slip, app):
        with pymupdf.open(stream=drawn.pdf, filetype="pdf") as pdf:
            assert len(pdf) == 1 and pdf[0].get_drawings()  # the stamp and the signature are strokes, not text
            assert "PyMuPDF" not in pdf.metadata["producer"] and pdf.metadata["creationDate"].startswith("D:2026")


def test_overrides_replace_one_text_and_bad_keys_are_refused():
    ident = identity(6)
    slip = draw_payslip(ident, seed=6)
    d = draw_payslip(ident, seed=6, overrides={"net_pay": "9,999.00", "deduction_amount@3": "1.00"})
    assert d.truth["fields"]["net_pay"] == "9999.00" and d.truth["rows"][2]["deduction_amount"] == "1.00"
    assert d.truth["overridden"] == {"net_pay": "9,999.00", "deduction_amount@3": "1.00"}
    assert {k: v for k, v in d.truth["fields"].items() if k != "net_pay"} == {k: v for k, v in slip.truth["fields"].items() if k != "net_pay"}
    changed = ("net_pay", "deduction_amount@3")  # the box follows the drawn text, so only these two may differ
    assert d.truth["rows"][0] == slip.truth["rows"][0]
    assert {k: v for k, v in d.truth["boxes"].items() if k not in changed} == {k: v for k, v in slip.truth["boxes"].items() if k not in changed}
    assert all(d.truth["boxes"][k] != slip.truth["boxes"][k] for k in changed)
    with pymupdf.open(stream=d.pdf, filetype="pdf") as pdf:
        assert "9,999.00" in pdf[0].get_text()
    a = draw_application(ident, seed=6, overrides={"application_date": "Tue 03 Nov 2025", "loan_amount": "7,50,000.00"})
    assert a.truth["fields"]["application_date"] == "2025-11-03" and a.truth["fields"]["loan_amount"] == "750000.00"
    with pymupdf.open(stream=a.pdf, filetype="pdf") as pdf:
        assert "Tue 03 Nov 2025" in pdf[0].get_text()
    plain = draw_application(ident, seed=6, overrides={"application_date": "03 Nov 2025"})  # no weekday printed
    assert plain.truth["fields"]["application_date"] == "2025-11-03"
    odd = draw_application(ident, seed=6, overrides={"application_date": "Mon 31 Nov 2025"})  # no such day: nothing to read
    assert odd.truth["fields"]["application_date"] is None
    assert draw_payslip(ident, seed=6, overrides={"net_pay": "N/A"}).truth["fields"]["net_pay"] is None
    for draw, bad in ((draw_payslip, "earning_amount@0"), (draw_payslip, "earning_amount@5"), (draw_payslip, "head.net_pay"),
                      (draw_payslip, "nonsense"), (draw_application, "net_pay"), (draw_application, "loan_amount@1")):
        with pytest.raises(ValueError, match=bad):
            draw(ident, overrides={bad: "1.00"})
    for draw in (draw_payslip, draw_application):
        with pytest.raises(ValueError, match="'Z'"):
            draw(ident, layout="Z")
