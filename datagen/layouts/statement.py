"""Bank statement, layout A (design 8): a labelled header block, then one table; 30 rows to a page and no header row on the
continuation pages. Amounts are whole paise inside, so nothing here depends on float rounding."""
import calendar
import random
from datetime import datetime, time, timedelta
from decimal import Decimal

from .. import marks
from ..fictional import Identity
from . import Drawn, Sheet, money, norm, text_width

COLS = ("date", "description", "debit", "credit", "balance")
HEADS = dict(zip(COLS, ("Date", "Description", "Debit", "Credit", "Balance")))
KIND = {"bank": "text", "account_holder": "text", "address": "text", "account_no": "text", "period_start": "date",
        "period_end": "date", "opening_balance": "amount", "closing_balance": "amount"}
PER_PAGE = 30
X = {"date": (40, "left"), "description": (100, "left"), "debit": (380, "right"), "credit": (460, "right"),
     "balance": (555, "right")}
DEBITS = ["UPI/Grocery/Orchid Stores", "ATM/Cash Withdrawal", "POS/Fuel Station", "ECS/Electricity Board", "UPI/Rent Payment",
          "POS/Restaurant", "UPI/Mobile Recharge", "NEFT/Insurance Premium", "POS/Pharmacy", "UPI/Online Shopping"]
CREDITS = ["IMPS/Transfer In", "Interest Credit", "Cheque Deposit", "UPI/Refund", "NEFT/Reimbursement"]


def _p(paise: int) -> str:
    return f"{paise // 100}.{paise % 100:02d}"


def _m(paise: int) -> str:
    return money(Decimal(paise).scaleb(-2))


def _check(over: dict[str, str], rows: int) -> None:
    for key, text in over.items():
        name, _, num = key.partition("@")
        ok = ((name in KIND or (name.startswith("head.") and name[5:] in COLS)) and not num) or (
            name in COLS and num.isascii() and num.isdigit() and 1 <= int(num) <= rows)
        if not ok:
            raise ValueError(f"unknown override {key!r}")
        if key in ("period_start", "period_end") and " " in text:
            raise ValueError(f"override {key!r} must be a single word")


def _rows(ident: Identity, n: int, last_day: int, rng: random.Random) -> tuple[int, list[tuple]]:
    """(opening, rows) in paise; a row is (day, description, 'debit'|'credit', amount, balance). Row 1 is a small debit and row 2
    the salary, then random ones; no debit is more than 12 % of the balance, so it never goes negative."""
    opening = bal = rng.randrange(2_000_000, 30_000_000)
    d0 = rng.randrange(1, 4)
    ds = rng.randrange(d0, 6)
    days = [d0, ds] + sorted(rng.randrange(ds, last_day + 1) for _ in range(n - 2))
    out = []
    for i, day in enumerate(days):
        if i == 1:
            amt, kind, desc = ident.net_pay * 100, "credit", f"NEFT/Salary {ident.employer.split()[0]}"
        elif i > 1 and rng.random() < 0.25:
            amt, kind, desc = rng.randrange(50_000, 4_000_000), "credit", rng.choice(CREDITS)
        else:
            amt = min(bal, max(100, int(bal * rng.uniform(0.005, 0.12 if i else 0.05))))
            kind, desc = "debit", rng.choice(DEBITS)
        bal += amt if kind == "credit" else -amt
        out.append((day, desc, kind, amt, bal))
    return opening, out


def draw_statement(ident: Identity, layout: str = "A", rows: int = 12, seed: int = 0,
                   overrides: dict[str, str] | None = None) -> Drawn:
    """A genuine statement. `overrides` replace one drawn text without recomputing anything else: a header field by name
    ('closing_balance'), a table cell by column and 1-based row ('balance@4'), a column heading ('head.debit'). The truth
    holds what is drawn, normalised, and echoes the overrides."""
    if layout != "A":
        raise ValueError(f"unknown layout {layout!r}")
    if rows < 2:
        raise ValueError("a statement has at least two rows (the second is the salary)")
    over = dict(overrides or {})
    _check(over, rows)
    rng = random.Random(f"statement/{ident.account_no}/{seed}")
    first = ident.month
    last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
    opening, plan = _rows(ident, rows, last.day, rng)
    closing = plan[-1][4]
    pages = -(-rows // PER_PAGE)
    created = datetime.combine(last + timedelta(days=1), time(rng.randrange(6, 11), rng.randrange(60)))

    fields = {"bank": ident.bank, "account_holder": ident.name, "address": ident.address, "account_no": ident.account_no,
              "period_start": first.isoformat(), "period_end": last.isoformat(), "opening_balance": _p(opening),
              "closing_balance": _p(closing)}
    shown = {"bank": ident.bank, "account_holder": ident.name, "address": ident.address, "account_no": ident.account_no,
             "period_start": f"{first:%d/%m/%Y}", "period_end": f"{last:%d/%m/%Y}", "opening_balance": _m(opening),
             "closing_balance": _m(closing)}
    for k in fields:
        if k in over:
            shown[k], fields[k] = over[k], norm(KIND[k], over[k])

    sheet = Sheet(f"{ident.bank} Statement Service 4.2", created)
    sheet.new_page()
    pressing = random.Random(f"statement/{ident.account_no}/{seed}/marks")  # its own stream: the other draws do not move
    sheet.text(40, 62, shown["bank"], 16, bold=True, key="bank")
    marks.logo(sheet, ident.logo or ident.bank, pressing, 40 + text_width(shown["bank"], 16, True) + 14, 40)
    sheet.text(40, 80, "Statement of Account", 11)
    for y, label, name in ((108, "Account Holder", "account_holder"), (122, "Address", "address"),
                           (136, "Account No", "account_no")):
        sheet.text(40, y, label, 9)
        sheet.text(150, y, shown[name], 9, bold=True, key=name)
    sheet.text(40, 150, "Statement Period", 9)
    sheet.text(150, 150, f"{shown['period_start']} to {shown['period_end']}", 9, bold=True,
               key={0: "period_start", 2: "period_end"})
    for y, label, name in ((164, "Opening Balance", "opening_balance"), (178, "Closing Balance", "closing_balance")):
        sheet.text(40, y, label, 9)
        sheet.text(150, y, shown[name], 9, bold=True, key=name)
    marks.seal(sheet, ident.stamp or ident.bank, pressing, 480, 192, "Bank Seal")
    for col in COLS:
        x, align = X[col]
        sheet.text(x, 206, over.get(f"head.{col}", HEADS[col]), 9, bold=True, align=align)

    def footer() -> None:
        sheet.text(555, 810, f"Page {sheet.doc.page_count} of {pages}", 8, align="right")

    table, y = [], 224
    for i, (day, desc, kind, amt, bal) in enumerate(plan, 1):
        if i > 1 and (i - 1) % PER_PAGE == 0:
            footer()
            sheet.new_page()
            y = 60
        row = {"date": f"{first:%Y-%m}-{day:02d}", "description": desc, "debit": _p(amt) if kind == "debit" else None,
               "credit": _p(amt) if kind == "credit" else None, "balance": _p(bal)}
        text = {"date": f"{day:02d}/{first:%m/%Y}", "description": desc, "debit": _m(amt) if kind == "debit" else None,
                "credit": _m(amt) if kind == "credit" else None, "balance": _m(bal)}
        for col in COLS:
            if (key := f"{col}@{i}") in over:
                text[col], row[col] = over[key], norm("amount" if col in ("debit", "credit", "balance") else col, over[key])
            if text[col] is not None:
                x, align = X[col]
                sheet.text(x, y, text[col], 9, align=align, key=key)
        table.append(row)
        y += 13
    footer()
    truth = {"type": "bank_statement", "layout": layout, "fields": fields, "rows": table, "boxes": sheet.boxes,
             "overridden": over}
    return Drawn(sheet.pdf(), truth)
