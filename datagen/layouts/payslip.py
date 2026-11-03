"""Payslip, layout A: employee details, the totals, then earnings on the left and deductions on the right, with a round
stamp and a caption at the foot. Amounts are whole rupees inside, so nothing here depends on float rounding."""
import math
import random
from datetime import datetime, time, timedelta

from ..fictional import Identity
from . import MONTHS, Drawn, Sheet, money, norm, words

COLS = ("earning_name", "earning_amount", "deduction_name", "deduction_amount")
HEADS = dict(zip(COLS, ("Earnings", "Amount Paid", "Deductions", "Amount Deducted")))  # no two columns share a wording
X = {"earning_name": (40, "left"), "earning_amount": (255, "right"), "deduction_name": (310, "left"),
     "deduction_amount": (555, "right")}
ROWS = 4
DATE_FORMATS = ("%d/%m/%Y", "%d %b %Y")  # the pay date is printed with a month name: 01/09/2026 reads two ways, 01 Sep 2026 one
# drawn top to bottom: (baseline y, label, field name, kind); values start at x = 150
DETAILS = ((108, "Employee Name", "employee_name", "text"), (122, "Employee ID", "employee_id", "id"),
           (136, "Designation", "designation", "text"), (150, "Bank Account", "bank_account", "id"),
           (164, "Pay Month", "pay_month", "text"), (178, "Pay Date", "pay_date", "date"),
           (200, "Gross Earnings", "gross_earnings", "amount"), (214, "Total Deductions", "total_deductions", "amount"),
           (228, "Net Pay", "net_pay", "amount"), (242, "Amount in Words", "net_pay_words", "text"))
KIND = {name: kind for _, _, name, kind in DETAILS} | {"employer": "text"}


def _check(over: dict[str, str]) -> None:
    for key in over:
        name, _, num = key.partition("@")
        if not ((name in KIND and not num) or (name in COLS and num.isascii() and num.isdigit() and 1 <= int(num) <= ROWS)):
            raise ValueError(f"unknown override {key!r}")


def _lines(ident: Identity) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """(earnings, deductions) as (name, whole rupees) pairs that add up to the identity's gross pay and deductions."""
    basic = ident.monthly_gross // 2 // 100 * 100
    earn = [("Basic Salary", basic), ("House Rent Allowance", basic * 2 // 5 // 100 * 100), ("Conveyance Allowance", 1600)]
    earn.append(("Special Allowance", ident.monthly_gross - sum(a for _, a in earn)))
    ded = [("Provident Fund", basic * 12 // 100 // 100 * 100), ("Professional Tax", 200)]
    ded.append(("Income Tax (TDS)", ident.deductions - sum(a for _, a in ded)))
    if min(a for _, a in earn + ded) <= 0:
        raise ValueError("this identity's pay is too small to split into the payslip's lines")
    return earn, ded


def _stamp(sheet: Sheet, rng: random.Random) -> None:
    """A round office stamp as strokes: two rings and a star, no text, a little off true as a pressed stamp is."""
    cx, cy, r = 480 + rng.uniform(-3, 3), 700 + rng.uniform(-3, 3), 36 + rng.uniform(-1, 1)
    ink = (0.1, 0.2, 0.6)
    sheet.page.draw_circle((cx, cy), r, color=ink, width=1.4)
    sheet.page.draw_circle((cx, cy), r - 4, color=ink, width=0.7)
    star = []
    for i in range(10):
        a, k = i * math.pi / 5, (r - 10) * (0.45 if i % 2 else 1)
        star.append((cx + k * math.sin(a), cy - k * math.cos(a)))
    sheet.page.draw_polyline(star, color=ink, width=0.8, closePath=True)
    sheet.region("stamp", cx - r - 1, cy - r - 1, cx + r + 1, cy + r + 1)


def draw_payslip(ident: Identity, layout: str = "A", seed: int = 0, overrides: dict[str, str] | None = None) -> Drawn:
    """A genuine payslip for the month before the identity's statement month. `overrides` replace one drawn text without
    recomputing anything else: a header field by name ('net_pay'), a table cell by column and 1-based row ('earning_amount@2').
    The truth holds what is drawn, normalised, and echoes the overrides."""
    if layout != "A":
        raise ValueError(f"unknown layout {layout!r}")
    over = dict(overrides or {})
    _check(over)
    rng = random.Random(f"payslip/{ident.employee_id}/{seed}")
    earn, ded = _lines(ident)
    prev = ident.month - timedelta(days=1)
    created = datetime.combine(ident.month, time(rng.randrange(9, 18), rng.randrange(60)))

    fields = {"employer": ident.employer, "employee_name": ident.name, "employee_id": ident.employee_id,
              "designation": ident.designation, "bank_account": ident.account_no,
              "pay_month": f"{MONTHS[prev.month - 1]} {prev.year}", "pay_date": ident.month.isoformat(),
              "gross_earnings": f"{ident.monthly_gross}.00", "total_deductions": f"{ident.deductions}.00",
              "net_pay": f"{ident.net_pay}.00", "net_pay_words": words(ident.net_pay)}
    shown = fields | {"pay_date": f"{ident.month.day:02d} {MONTHS[ident.month.month - 1][:3]} {ident.month.year}",
                      "gross_earnings": money(ident.monthly_gross), "total_deductions": money(ident.deductions),
                      "net_pay": money(ident.net_pay)}
    for k in fields:
        if k in over:
            shown[k], fields[k] = over[k], norm(KIND[k], over[k], DATE_FORMATS)

    sheet = Sheet(f"{ident.employer.split()[0]} Payroll Suite 7.1", created)
    sheet.new_page()
    sheet.text(40, 62, shown["employer"], 16, bold=True, key="employer")
    sheet.text(40, 80, "Payslip", 11)
    for y, label, name, _ in DETAILS:
        sheet.text(40, y, label, 9)
        sheet.text(150, y, shown[name], 9, bold=True, key=name)
    for col in COLS:
        x, align = X[col]
        sheet.text(x, 268, HEADS[col], 9, bold=True, align=align)

    table, y = [], 286
    for i in range(1, ROWS + 1):
        e, d = earn[i - 1], ded[i - 1] if i <= len(ded) else None  # the fourth deduction cell stays blank
        row = {"earning_name": e[0], "earning_amount": f"{e[1]}.00", "deduction_name": d and d[0],
               "deduction_amount": d and f"{d[1]}.00"}
        text = {"earning_name": e[0], "earning_amount": money(e[1]), "deduction_name": d and d[0],
                "deduction_amount": d and money(d[1])}
        for col in COLS:
            if (key := f"{col}@{i}") in over:
                text[col], row[col] = over[key], norm("amount" if col.endswith("amount") else "text", over[key])
            if text[col] is not None:
                x, align = X[col]
                sheet.text(x, y, text[col], 9, align=align, key=key)
        table.append(row)
        y += 13
    sheet.text(40, 790, "This is a computer generated payslip.", 8)
    _stamp(sheet, rng)
    sheet.text(440, 756, "Authorised Signatory", 8)
    truth = {"type": "payslip", "layout": layout, "fields": fields, "rows": table, "boxes": sheet.boxes, "overridden": over}
    return Drawn(sheet.pdf(), truth)
