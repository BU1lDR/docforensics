"""Bank statement (design 8): a labelled header block, then one table; no header row on the continuation pages. Layout A is the
one the spec files were written from. Layout B is another bank's template, drawn once the spec files were final: other wording
for some labels and headings (see the wording the specs list), another order of the columns, a column the specs know nothing of,
dates written 03-Nov-2026, other margins and spacing. Amounts are whole paise inside, so nothing here depends on float rounding."""
import calendar
import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from .. import marks
from ..fictional import Identity
from . import MONTHS, Drawn, Sheet, money, norm, text_width

COLS = ("date", "description", "debit", "credit", "balance")
HEADS = dict(zip(COLS, ("Date", "Description", "Debit", "Credit", "Balance")))
KIND = {"bank": "text", "account_holder": "text", "address": "text", "account_no": "text", "period_start": "date",
        "period_end": "date", "opening_balance": "amount", "closing_balance": "amount"}

def _numeric(d: date) -> str:
    return f"{d:%d/%m/%Y}"


def _named(d: date) -> str:  # built from our own month names: strftime follows the machine's language
    return f"{d.day:02d}-{MONTHS[d.month - 1][:3]}-{d.year}"


# Everything that differs between the layouts. A: the header block runs from `top` in steps of `pitch` (account holder, address,
# account number, period, opening balance, closing balance), values at `value_x`; the table is drawn in the order of `order`.
STYLE = {
    "A": dict(x=40, name=(16, 62), sub=("Statement of Account", 80), top=108, pitch=14, value_x=150,
              labels=("Account Holder", "Address", "Account No", "Statement Period", "Opening Balance", "Closing Balance"),
              seal=(480, 192), head_y=206, row_y=224, step=13, per_page=30, order=COLS, heads=HEADS, show=_numeric,
              fmt="%d/%m/%Y", X={"date": (40, "left"), "description": (100, "left"), "debit": (380, "right"),
                                 "credit": (460, "right"), "balance": (555, "right")}),
    "B": dict(x=56, name=(15, 64), sub=("Account Statement", 84), top=112, pitch=15, value_x=200,
              labels=("Customer Name", "Address", "A/c Number", "Statement Period", "Balance Brought Forward",
                      "Balance Carried Forward"),
              seal=(470, 214), head_y=232, row_y=250, step=14, per_page=28,
              order=("date", "description", "ref", "credit", "debit", "balance"),
              heads={"date": "Txn Date", "description": "Narration", "ref": "Ref No", "credit": "Credit", "debit": "Debit",
                     "balance": "Balance"},
              show=_named, fmt="%d-%b-%Y",
              X={"date": (56, "left"), "description": (140, "left"), "ref": (290, "left"), "credit": (420, "right"),
                 "debit": (490, "right"), "balance": (560, "right")}),
}
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
    if layout not in STYLE:
        raise ValueError(f"unknown layout {layout!r}")
    st = STYLE[layout]
    if rows < 2:
        raise ValueError("a statement has at least two rows (the second is the salary)")
    over = dict(overrides or {})
    _check(over, rows)
    rng = random.Random(f"statement/{ident.account_no}/{seed}")
    first = ident.month
    last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
    opening, plan = _rows(ident, rows, last.day, rng)
    closing = plan[-1][4]
    pages = -(-rows // st["per_page"])
    created = datetime.combine(last + timedelta(days=1), time(rng.randrange(6, 11), rng.randrange(60)))

    fields = {"bank": ident.bank, "account_holder": ident.name, "address": ident.address, "account_no": ident.account_no,
              "period_start": first.isoformat(), "period_end": last.isoformat(), "opening_balance": _p(opening),
              "closing_balance": _p(closing)}
    shown = {"bank": ident.bank, "account_holder": ident.name, "address": ident.address, "account_no": ident.account_no,
             "period_start": st["show"](first), "period_end": st["show"](last), "opening_balance": _m(opening),
             "closing_balance": _m(closing)}
    for k in fields:
        if k in over:
            shown[k], fields[k] = over[k], norm(KIND[k], over[k], st["fmt"])

    sheet = Sheet(f"{ident.bank} Statement Service 4.2", created)
    sheet.new_page()
    pressing = random.Random(f"statement/{ident.account_no}/{seed}/marks")  # its own stream: the other draws do not move
    x0, size, base = st["x"], *st["name"]
    sheet.text(x0, base, shown["bank"], size, bold=True, key="bank")
    marks.logo(sheet, ident.logo or ident.bank, pressing, x0 + text_width(shown["bank"], size, True) + 14, base - 22)
    sheet.text(x0, st["sub"][1], st["sub"][0], 11)
    period = f"{shown['period_start']} to {shown['period_end']}"
    keys = ("account_holder", "address", "account_no", None, "opening_balance", "closing_balance")
    for i, (label, name) in enumerate(zip(st["labels"], keys)):
        y = st["top"] + st["pitch"] * i
        sheet.text(x0, y, label, 9)
        sheet.text(st["value_x"], y, period if name is None else shown[name], 9, bold=True,
                   key={0: "period_start", 2: "period_end"} if name is None else name)
    marks.seal(sheet, ident.stamp or ident.bank, pressing, *st["seal"], "Bank Seal")
    for col in st["order"]:
        x, align = st["X"][col]
        sheet.text(x, st["head_y"], over.get(f"head.{col}", st["heads"][col]), 9, bold=True, align=align)

    def footer() -> None:
        sheet.text(555, 810, f"Page {sheet.doc.page_count} of {pages}", 8, align="right")

    refs = random.Random(f"statement/{ident.account_no}/{seed}/ref")  # its own stream: layout A never draws from it
    table, y = [], st["row_y"]
    for i, (day, desc, kind, amt, bal) in enumerate(plan, 1):
        if i > 1 and (i - 1) % st["per_page"] == 0:
            footer()
            sheet.new_page()
            y = 60
        row = {"date": f"{first:%Y-%m}-{day:02d}", "description": desc, "debit": _p(amt) if kind == "debit" else None,
               "credit": _p(amt) if kind == "credit" else None, "balance": _p(bal)}
        text = {"date": st["show"](first.replace(day=day)), "description": desc, "ref": f"TXN{refs.randrange(10**6):06d}", "debit": _m(amt) if kind == "debit" else None,
                "credit": _m(amt) if kind == "credit" else None, "balance": _m(bal)}
        for col in COLS:
            if (key := f"{col}@{i}") in over:
                text[col], row[col] = over[key], norm("amount" if col in ("debit", "credit", "balance") else col, over[key], st["fmt"])
            if text[col] is not None:
                x, align = st["X"][col]
                sheet.text(x, y, text[col], 9, align=align, key=key)
        if "ref" in st["order"]:
            sheet.text(*st["X"]["ref"][:1], y, text["ref"], 9)
        table.append(row)
        y += st["step"]
    footer()
    truth = {"type": "bank_statement", "layout": layout, "fields": fields, "rows": table, "boxes": sheet.boxes,
             "overridden": over}
    return Drawn(sheet.pdf(), truth)
