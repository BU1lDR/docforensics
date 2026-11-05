"""Documents of two types the tool has no spec for, to measure what the local model reads from a page it was not written for (scope D,
package X): an invoice and an electricity bill, each in two layouts that word and place their labels differently, digital or as a
scan. A case is one invoice and one bill of one fictional person. The truth lists every fact the generator printed on the page (not
the table rows): its label as printed, the text, the box, and a rubric of the names a reviewer would accept for it (regexes over the
lower-case letters and digits of a label, written here, before any model read these pages). Seeds: the split's base plus PACK, so
they never meet a seed of the dev or test split. Only the scorer (evaluation/score_x.py) reads the manifest."""
import hashlib
import io
import json
import random
from datetime import datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

from PIL import Image

from .fictional import FIRMS, Identity, identity
from .layouts import MONTHS, Drawn, Sheet, money
from .scan import simulate_scan, to_scan_frame

BASE = {"ext-dev": 3_000_000, "ext-test": 4_000_000}
PACK = 0       # the packs of the other detectors start further up in the same splits
SPAN = 10_000  # the seeds of this pack
MEDIA = ("digital", "mild", "150dpi", "120dpi")
FILES = ("01_invoice", "02_bill")

# name: (accept, reject): a label is acceptable if it matches `accept` and not `reject`. Applied to plain(label).
INVOICE_RUBRIC = {
    "seller": (r"seller|vendor|supplier|issuer|issued by|company|business|firm|\bfrom\b|billed by|payee|merchant|organi[sz]ation|trader|name",
               r"buyer|customer|bill(ed)? to|client|payer|purchaser"),
    "invoice_number": (r"invoice (no|number|num|id|ref)|^invoice$|^inv\b|^number$|document (no|number)|^no$",
                       r"date|due|\bpo\b|order|purchase|account|total|amount"),
    "invoice_date": (r"invoice date|issue|issued|billing date|bill date|^date$|dated", r"due|payment|delivery|expiry|valid"),
    "due_date": (r"due|pay(ment)? (by|before|date)|payable (by|before)|settle", r"invoice date|issue"),
    "po_number": (r"\bpo\b|purchase order|order (no|number|ref|reference|id)|your (order|reference)|customer (po|order)|reference|^order",
                  r"invoice|bank|account|terms"),
    "buyer": (r"bill(ed)? to|buyer|customer|client|purchaser|consignee|recipient|sold to|payer|^name$|billing name|ship to",
              r"seller|vendor|supplier|\bfrom\b|company"),
    "subtotal": (r"sub ?total|before tax|taxable|net amount|amount before|excl|pre tax|net total|total before", r"grand|payable|due"),
    "tax": (r"tax|gst|vat|igst|cgst|sgst|duty|levy", r"before|excl|taxable|sub|payable|incl|^total$|due"),
    "total": (r"total|payable|amount due|balance due|grand|invoice (amount|value)|net payable|gross", r"sub|before|taxable|excl|rate|discount|^(total )?(tax|gst|vat)"),
    "payment_terms": (r"terms|payment (terms|conditions|period)|credit (period|terms)|^net\b|conditions", r"bank|account"),
    "bank_account": (r"account|\ba c\b|acct|iban|bank|remit|pay(ment)? to|beneficiary|ifsc", r"terms|date"),
}
BILL_RUBRIC = {
    "consumer_no": (r"consumer|customer (no|number|id)|connection|service (no|number|connection)|account (no|number|id)|subscriber (no|number|id)|meter (no|number|id)",
                    r"bill|reading|date|name"),
    "bill_number": (r"bill (no|number|num|id|ref)|invoice (no|number|ref|id)|^bill$|^invoice$|receipt (no|number)|document (no|number)",
                    r"date|due|consumer|customer|amount|total|issued"),
    "customer": (r"name|customer|consumer|subscriber|account holder|bill(ed)? to|holder|owner", r"\bno\b|number|address|\bid\b|premises"),
    "service_address": (r"address|premises|service (location|address)|supply (address|location)|location|site|property", r"email|date"),
    "bill_date": (r"bill date|date of (bill|issue)|issued|issue date|billing date|invoice date|^date$|dated|generated", r"due|period|reading|last|payment|cycle"),
    "due_date": (r"due|last date|pay (by|before)|payable (by|before)|payment date", r"bill date|issue|after|late|amount"),
    "billing_period": (r"period|billing (cycle|month|from)|cycle|duration|consumption period|billing$", r"date of|due|issued"),
    "previous_reading": (r"previous|prev|opening|old|last|start|initial|earlier", r"current|present|closing|new|consumption|units"),
    "current_reading": (r"current|present|closing|new|latest|end|final", r"previous|prev|opening|old|units|consumption"),
    "units_consumed": (r"units|consumption|consumed|kwh|usage|energy consumed", r"charge|amount|rate|reading|cost"),
    "energy_charges": (r"energy|electricity charge|consumption charge|usage charge|variable|unit charge|cost of",
                       r"duty|fixed|tax|total|surcharge|late|consumed|reading|demand"),
    "fixed_charges": (r"fixed|demand|service charge|meter rent|connection charge|base|standing", r"energy|duty|tax|total|late"),
    "electricity_duty": (r"duty|tax|levy|gst|cess", r"total|late|surcharge|payable"),
    "total_due": (r"total|payable|amount due|net|due amount|pay\b|due$", r"after|late|surcharge|duty|fixed|energy|previous|reading|date|charges$"),
    "amount_after_due": (r"after|late|overdue|delay|surcharge|penalty|if paid", r"^(bill |issue |due )?date$"),
}
RUBRIC = {"invoice": INVOICE_RUBRIC, "bill": BILL_RUBRIC}

INVOICE_LABELS = {
    "A": dict(invoice_number="Invoice No", invoice_date="Invoice Date", due_date="Due Date", po_number="PO Reference", buyer="Bill To",
              payment_terms="Payment Terms", bank_account="Pay to Account", subtotal="Subtotal", tax="GST @ 18%", total="Total"),
    "B": dict(invoice_number="Invoice #", invoice_date="Date of Issue", due_date="Payment Due By", po_number="Your Order No.", buyer="Billed To",
              payment_terms="Terms", bank_account="Remit to A/c", subtotal="Amount before tax", tax="Tax (18%)", total="Amount Payable"),
}
BILL_LABELS = {
    "A": dict(consumer_no="Consumer No", bill_number="Bill No", customer="Customer Name", service_address="Service Address",
              bill_date="Bill Date", due_date="Due Date", billing_period="Billing Period", previous_reading="Previous Reading",
              current_reading="Current Reading", units_consumed="Units Consumed (kWh)", energy_charges="Energy Charges",
              fixed_charges="Fixed Charges", electricity_duty="Electricity Duty", total_due="Net Amount Payable",
              amount_after_due="Amount Payable After Due Date"),
    "B": dict(consumer_no="Connection ID", bill_number="Invoice Ref", customer="Name of Consumer", service_address="Premises",
              bill_date="Issued On", due_date="Pay By", billing_period="Cycle", previous_reading="Opening Meter Reading",
              current_reading="Closing Meter Reading", units_consumed="Consumption (units)", energy_charges="Cost of Energy",
              fixed_charges="Demand Charge", electricity_duty="Duty and Cess", total_due="Total Due", amount_after_due="If Paid Late"),
}
ITEMS = (("Cloud hosting, monthly", 1, 4800), ("Router replacement kit", 2, 3250), ("Annual maintenance contract", 1, 12000),
         ("Network cabling, 40 m", 1, 2600), ("Support hours", 6, 850), ("Laptop stand", 3, 1150), ("Backup storage, 1 TB", 2, 5400),
         ("Wireless access point", 2, 6900))
D2 = Decimal("0.01")


def _date(layout: str, d) -> str:
    return f"{d.day:02d}/{d.month:02d}/{d.year}" if layout == "A" else f"{d.day:02d} {MONTHS[d.month - 1][:3]} {d.year}"


class _Truth:
    """What was printed, as the page is drawn."""

    def __init__(self, sheet: Sheet, kind: str, layout: str, labels: dict[str, str]) -> None:
        self.sheet, self.kind, self.layout, self.labels = sheet, kind, layout, labels
        self.fields: dict[str, dict] = {}

    def put(self, name: str, kind: str, text: str, value: str, x: float, y: float, size: float = 9, bold: bool = True,
            align: str = "left", label: str | None = None) -> None:
        self.sheet.text(x, y, text, size, bold, align, key=name)
        accept, reject = RUBRIC[self.kind][name]
        self.fields[name] = {"label": self.labels.get(name, "") if label is None else label, "text": text, "kind": kind, "value": value,
                             "accept": accept, "reject": reject}

    def boxes(self) -> None:
        for name, f in self.fields.items():
            f["box"] = self.sheet.boxes[name]


def _amount(layout: str, v: Decimal, prefix: bool = True) -> tuple[str, str]:
    """(printed, stored): layout B writes the rupee amounts of the totals with 'Rs. ' in front."""
    return (("Rs. " if layout == "B" and prefix else "") + money(v)), f"{v:.2f}"


def draw_invoice(ident: Identity, layout: str, seed: int) -> Drawn:
    """A genuine invoice from a fictional trader to the identity: three lines, 18 % tax, a total."""
    if layout not in INVOICE_LABELS:
        raise ValueError(f"unknown layout {layout!r}")
    lab = INVOICE_LABELS[layout]
    rng = random.Random(f"invoice/{ident.employee_id}/{seed}")
    seller = f"{rng.choice(FIRMS)} Test Traders Pvt Ltd"
    issued = ident.month + timedelta(days=rng.randrange(2, 25))
    due = issued + timedelta(days=(terms := rng.choice((15, 30, 45))))
    lines = [(d, q, Decimal(r)) for d, q, r in rng.sample(ITEMS, 3)]
    subtotal = sum((q * r for _, q, r in lines), Decimal(0))
    tax = (subtotal * Decimal("0.18")).quantize(D2)
    sheet = Sheet(f"{seller.split()[0]} Billing Suite 3.2", datetime.combine(issued, time(rng.randrange(9, 18), rng.randrange(60))))
    sheet.new_page()
    t = _Truth(sheet, "invoice", layout, lab)
    a = layout == "A"
    x, vx = (40, 150) if a else (56, 0)
    t.put("seller", "text", seller, seller, x, 62 if a else 64, 16 if a else 15, label="")
    sheet.text(x, 80 if a else 86, "Tax Invoice" if a else "Invoice", 11 if a else 12)
    info = [("invoice_number", "id", f"INV-{issued.year}-{rng.randrange(1000, 9999)}", None), ("invoice_date", "date", _date(layout, issued), issued.isoformat()),
            ("due_date", "date", _date(layout, due), due.isoformat()), ("po_number", "id", f"PO-{rng.randrange(10000, 99999)}", None),
            ("buyer", "text", ident.name, None), ("payment_terms", "text", f"Net {terms} days", None),
            ("bank_account", "id", f"TST-{rng.randrange(10**9, 10**10)}", None)]
    grid = {"invoice_number": (0, 0), "invoice_date": (0, 1), "po_number": (1, 0), "due_date": (1, 1), "buyer": (2, 0), "payment_terms": (2, 1),
            "bank_account": (3, 0)}
    for i, (name, kind, text, value) in enumerate(info):
        if a:
            y = 108 + 14 * i
            sheet.text(x, y, lab[name], 9)
            t.put(name, kind, text, value or text, vx, y)
        else:
            row, col = grid[name]
            y, cx = 120 + 34 * row, (56, 330)[col]
            sheet.text(cx, y, lab[name], 7.5)
            t.put(name, kind, text, value or text, cx, y + 13, 10)
    heads = ("Description", "Qty", "Rate", "Amount") if a else ("Item", "Quantity", "Unit price", "Line total")
    cols = ((40, "left"), (330, "right"), (420, "right"), (555, "right")) if a else ((56, "left"), (340, "right"), (430, "right"), (560, "right"))
    y = 222 if a else 290
    for (cx, align), head in zip(cols, heads):
        sheet.text(cx, y, head, 9, bold=True, align=align)
    rows = []
    for i, (desc, qty, rate) in enumerate(lines):
        y += 13 if a else 14
        row = {}
        for (cx, align), (col, text) in zip(cols, (("description", desc), ("qty", str(qty)), ("rate", money(rate)), ("amount", money(qty * rate)))):
            sheet.text(cx, y, text, 9, align=align, key=f"{col}@{i + 1}")
            row[col] = {"text": text, "box": sheet.boxes[f"{col}@{i + 1}"]}
        rows.append(row)
    y += 30 if a else 40
    lx, vx2 = (380, 555) if a else (330, 560)
    for name, v in (("subtotal", subtotal), ("tax", tax), ("total", subtotal + tax)):
        text, stored = _amount(layout, v)
        sheet.text(lx, y, lab[name], 9, bold=name == "total")
        t.put(name, "amount", text, stored, vx2, y, 9 if a else 10, align="right")
        y += 14 if a else 16
    sheet.text(x, 790, "This is a computer generated invoice." if a else "Computer generated; no signature required.", 8)
    t.boxes()
    return Drawn(sheet.pdf(), {"type": "invoice", "layout": layout, "fields": t.fields, "rows": rows})


def draw_bill(ident: Identity, layout: str, seed: int) -> Drawn:
    """A genuine electricity bill to the identity: the readings, the charges, the amount due and the amount after the due date."""
    if layout not in BILL_LABELS:
        raise ValueError(f"unknown layout {layout!r}")
    lab = BILL_LABELS[layout]
    rng = random.Random(f"bill/{ident.consumer_no}/{seed}")
    issuer = f"{rng.choice(FIRMS)} Test Electricity Board"
    start = ident.month
    end = (start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    billed = end + timedelta(days=rng.randrange(2, 8))
    due = billed + timedelta(days=15)
    units = rng.randrange(120, 640)
    before = rng.randrange(1000, 90000)
    energy = (units * Decimal(rng.choice(("5.50", "6.25", "7.10")))).quantize(D2)
    fixed = Decimal(rng.choice((120, 150, 210)))
    duty = (energy * Decimal("0.06")).quantize(D2)
    total = energy + fixed + duty
    late = total + (total * Decimal("0.02")).quantize(D2)
    period = (f"{_date('A', start)} to {_date('A', end)}" if layout == "A" else f"{_date('B', start)} - {_date('B', end)}")
    sheet = Sheet(f"{issuer.split()[0]} Utility Billing 5.0", datetime.combine(billed, time(rng.randrange(9, 18), rng.randrange(60))))
    sheet.new_page()
    t = _Truth(sheet, "bill", layout, lab)
    a = layout == "A"
    x = 40 if a else 56
    sheet.text(x, 60 if a else 64, issuer, 15, bold=True)
    sheet.text(x, 78 if a else 86, "Electricity Bill" if a else "Monthly Power Bill", 11 if a else 12)
    facts = [("consumer_no", "id", ident.consumer_no, None), ("bill_number", "id", f"EB-{billed.year}-{rng.randrange(100000, 999999)}", None),
             ("customer", "text", ident.name, None), ("service_address", "text", ident.address, None),
             ("bill_date", "date", _date(layout, billed), billed.isoformat()), ("due_date", "date", _date(layout, due), due.isoformat()),
             ("billing_period", "text", period, None), ("previous_reading", "text", str(before), None),
             ("current_reading", "text", str(before + units), None), ("units_consumed", "text", str(units), None)]
    grid = {"consumer_no": (0, 0), "bill_number": (0, 1), "customer": (1, 0), "bill_date": (1, 1), "service_address": (2, 0),
            "billing_period": (3, 0), "due_date": (3, 1), "previous_reading": (4, 0), "current_reading": (4, 1), "units_consumed": (5, 0)}
    for i, (name, kind, text, value) in enumerate(facts):
        if a:
            y = 104 + 14 * i + (8 if i >= 7 else 0)
            sheet.text(x, y, lab[name], 9)
            t.put(name, kind, text, value or text, 190, y)
        else:
            row, col = grid[name]
            y, cx = 120 + 34 * row, (56, 330)[col]
            sheet.text(cx, y, lab[name], 7.5)
            t.put(name, kind, text, value or text, cx, y + 13, 10)
    y = 104 + 14 * len(facts) + 24 if a else 120 + 34 * 6 + 20
    for name, v in (("energy_charges", energy), ("fixed_charges", fixed), ("electricity_duty", duty), ("total_due", total), ("amount_after_due", late)):
        text, stored = _amount(layout, v)
        sheet.text(x, y, lab[name], 9, bold=name == "total_due")
        t.put(name, "amount", text, stored, 190 if a else 330, y, 10 if name == "total_due" else 9, align="left" if a else "right")
        y += 14 if a else 16
    sheet.text(x, 790, "Pay at any authorised collection centre or online." if a else "Late payment attracts a surcharge.", 8)
    t.boxes()
    return Drawn(sheet.pdf(), {"type": "bill", "layout": layout, "fields": t.fields, "rows": []})


def plan_cases(split: str, n: int, start: int = 0) -> list[dict]:
    """Cases `start` to `start + n`. The medium cycles through the four, the invoice's layout alternates every case and the bill's every
    two, so each medium meets each layout (over eight cases, every medium twice)."""
    if split not in BASE:
        raise ValueError(f"unknown split {split!r}")
    if start < 0 or n < 0 or start + n > SPAN:
        raise ValueError(f"cases {start} to {start + n} do not fit the {SPAN} seeds of the pack")
    return [{"case": f"{split}-x-{i:04d}", "seed": BASE[split] + PACK + i, "medium": MEDIA[i % 4], "invoice_layout": "AB"[i % 2],
             "bill_layout": "AB"[(i // 2) % 2]} for i in range(start, start + n)]


def build_case(p: dict) -> tuple[dict[str, bytes], dict]:
    """The files of one planned case, by name in upload order, and its manifest entry."""
    seed, medium = p["seed"], p["medium"]
    ident = identity(seed)
    drawn = [draw_invoice(ident, p["invoice_layout"], seed), draw_bill(ident, p["bill_layout"], seed)]
    ext = ".pdf" if medium == "digital" else ".jpg"
    files, docs = {}, []
    for i, (stem, d) in enumerate(zip(FILES, drawn), 1):
        name = stem + ext
        truth = d.truth
        if medium == "digital":
            files[name] = d.pdf
        else:
            files[name] = simulate_scan(d.pdf, medium, scan_seed := seed * 10 + i)
            size = Image.open(io.BytesIO(files[name])).size
            fix = lambda b: [b[0], *to_scan_frame(b[1:], size, scan_seed)]
            truth = dict(truth, fields={k: dict(f, box=fix(f["box"])) for k, f in truth["fields"].items()},
                         rows=[{c: dict(v, box=fix(v["box"])) for c, v in r.items()} for r in truth["rows"]])
        docs.append({"file": name, "type": truth["type"], "layout": truth["layout"], "fields": truth["fields"], "rows": truth["rows"],
                     "sha256": hashlib.sha256(files[name]).hexdigest()})
    return files, {"case": p["case"], "seed": seed, "medium": medium, "docs": docs}


def build_split(split: str, out: Path | str, n: int, start: int = 0) -> Path:
    """Cases `start` to `start + n` written under `out`, one folder a case, and `out/manifest.json`. Returns the manifest's path."""
    out = Path(out)
    entries = []
    for p in plan_cases(split, n, start):
        files, entry = build_case(p)
        folder = out / p["case"]
        folder.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            (folder / name).write_bytes(data)
        entries.append(entry)
    path = out / "manifest.json"
    path.write_text(json.dumps({"split": split, "pack": "x", "cases": entries}, indent=1), encoding="utf-8", newline="\n")
    return path


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="python -m datagen.unseen", description="Write cases of invoices and electricity bills and their manifest.")
    ap.add_argument("split", choices=sorted(BASE))
    ap.add_argument("out", help="the folder to write to")
    ap.add_argument("--cases", type=int, default=8, help="how many cases (default: 8)")
    ap.add_argument("--start", type=int, default=0, help="the first case (default: 0)")
    a = ap.parse_args()
    print(build_split(a.split, a.out, a.cases, a.start))
