"""Payslip: employee details, the totals, then earnings on the left and deductions on the right, with a round stamp and a caption
at the foot. Layout A is the one the spec files were written from. Layout B is another employer's template, drawn once the spec
files were final: other wording for some labels and headings, dates written 01-Sep-2026, other margins and spacing. Amounts are
whole rupees inside, so nothing here depends on float rounding."""
import math
import random
from datetime import datetime, time, timedelta

from .. import signatures
from ..fictional import Identity
from . import MONTHS, Drawn, Sheet, money, norm, words

COLS = ("earning_name", "earning_amount", "deduction_name", "deduction_amount")
ROWS = 4
# drawn top to bottom as (field name, kind); the six lines of the person, then (after `gap` more points) the four of the pay
DETAILS = (("employee_name", "text"), ("employee_id", "id"), ("designation", "text"), ("bank_account", "id"),
           ("pay_month", "text"), ("pay_date", "date"), ("gross_earnings", "amount"), ("total_deductions", "amount"),
           ("net_pay", "amount"), ("net_pay_words", "text"))
KIND = dict(DETAILS) | {"employer": "text"}
# Everything that differs between the layouts. Values stand at `value_x`; the pay date is printed with a month name (01/09/2026
# reads two ways, 01 Sep 2026 one); no two column headings share a wording.
STYLE = {
    "A": dict(x=40, name=(16, 62), sub=("Payslip", 80), top=108, pitch=14, gap=8, value_x=150, head_y=268, row_y=286, step=13,
              labels=("Employee Name", "Employee ID", "Designation", "Bank Account", "Pay Month", "Pay Date", "Gross Earnings",
                      "Total Deductions", "Net Pay", "Amount in Words"),
              heads=dict(zip(COLS, ("Earnings", "Amount Paid", "Deductions", "Amount Deducted"))),
              X={"earning_name": (40, "left"), "earning_amount": (255, "right"), "deduction_name": (310, "left"),
                 "deduction_amount": (555, "right")},
              dates=("%d/%m/%Y", "%d %b %Y"), show=lambda d: f"{d.day:02d} {MONTHS[d.month - 1][:3]} {d.year}",
              foot=("This is a computer generated payslip.", 40, 790), stamp=(480, 700), sign=(40, 756, "Employee Signature"),
              office=(440, 756)),
    "B": dict(x=56, name=(15, 64), sub=("Salary Slip", 84), top=112, pitch=15, gap=10, value_x=200, head_y=284, row_y=302, step=14,
              labels=("Name of Employee", "Emp. Code", "Position", "Bank A/c No.", "Salary Month", "Paid On", "Gross Earnings",
                      "Total Deductions", "Net Pay", "In Words"),
              heads=dict(zip(COLS, ("Earnings", "Amount Paid", "Deductions", "Deducted Amount"))),
              X={"earning_name": (56, "left"), "earning_amount": (275, "right"), "deduction_name": (335, "left"),
                 "deduction_amount": (560, "right")},
              dates=("%d-%b-%Y",), show=lambda d: f"{d.day:02d}-{MONTHS[d.month - 1][:3]}-{d.year}",
              foot=("Computer generated, no seal needed.", 56, 790), stamp=(430, 690), sign=(56, 752, "Employee's Signature"),
              office=(430, 752)),
}


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


def _stamp(sheet: Sheet, rng: random.Random, at: tuple[float, float]) -> None:
    """A round office stamp as strokes: two rings and a star, no text, a little off true as a pressed stamp is."""
    cx, cy, r = at[0] + rng.uniform(-3, 3), at[1] + rng.uniform(-3, 3), 36 + rng.uniform(-1, 1)
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
    if layout not in STYLE:
        raise ValueError(f"unknown layout {layout!r}")
    st = STYLE[layout]
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
    shown = fields | {"pay_date": st["show"](ident.month),
                      "gross_earnings": money(ident.monthly_gross), "total_deductions": money(ident.deductions),
                      "net_pay": money(ident.net_pay)}
    for k in fields:
        if k in over:
            shown[k], fields[k] = over[k], norm(KIND[k], over[k], st["dates"])

    sheet = Sheet(f"{ident.employer.split()[0]} Payroll Suite 7.1", created)
    sheet.new_page()
    x0, (size, base) = st["x"], st["name"]
    sheet.text(x0, base, shown["employer"], size, bold=True, key="employer")
    sheet.text(x0, st["sub"][1], st["sub"][0], 11)
    for i, (label, (name, _)) in enumerate(zip(st["labels"], DETAILS)):
        y = st["top"] + st["pitch"] * i + (st["gap"] if i >= 6 else 0)
        sheet.text(x0, y, label, 9)
        sheet.text(st["value_x"], y, shown[name], 9, bold=True, key=name)
    for col in COLS:
        x, align = st["X"][col]
        sheet.text(x, st["head_y"], st["heads"][col], 9, bold=True, align=align)

    table, y = [], st["row_y"]
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
                x, align = st["X"][col]
                sheet.text(x, y, text[col], 9, align=align, key=key)
        table.append(row)
        y += st["step"]
    sheet.text(st["foot"][1], st["foot"][2], st["foot"][0], 8)
    _stamp(sheet, rng, st["stamp"])
    sheet.text(*st["office"], "Authorised Signatory", 8)
    sx, sy, caption = st["sign"]
    signatures.draw(sheet, ident.hand or ident.name, random.Random(f"payslip/{ident.employee_id}/{seed}/signature"), sx, sy)
    sheet.text(sx, sy, caption, 8)
    truth = {"type": "payslip", "layout": layout, "fields": fields, "rows": table, "boxes": sheet.boxes, "overridden": over}
    return Drawn(sheet.pdf(), truth)
