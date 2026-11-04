"""The demonstration datasets (design 8, Task 19). A split is a folder of cases and one manifest. A case is the three documents of one
fictional applicant (a bank statement, a payslip and a loan application) in one medium: digital PDFs, or scans at one of the three
levels of datagen.scan. A third of the cases are genuine; the rest carry one manipulation each, taken in turn from the methods the
split uses, so the counts differ by at most one. The manifest is the ground truth: what each document is and says, and what was
done to which document, where. Only the scorer (evaluation/) reads it; the product never does.

The dev split is what the detectors are fitted on. The test split is what they are measured on, once: it adds two manipulations the
dev split never shows (TEST_ONLY) and a second layout (B) the drawers of A were not written for. Seeds keep the splits apart: a case
is seeded at its split's base plus its number, and the second applicant that some cases borrow a hand, a bank or a scan from at
SECOND above that, so no seed of one split is a seed of the other."""
import hashlib
import io
import json
import random
from collections import Counter
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from itertools import count
from pathlib import Path

import pymupdf
from PIL import Image

from .fictional import FIRMS, Identity, identity
from .layouts import money
from .layouts.application import draw_application
from .layouts.payslip import draw_payslip
from .layouts.statement import draw_statement
from .manipulate import (TEST_ONLY, c1_consistent_change, c2_cross_document, c3_duplicate, c4_other_hand, c5_other_mark,
                         d1_incremental_edit, d2_cover_retype, d3_near_font_retype, d4_metadata_edit, d5_paste_image,
                         s1_splice, s2_erase_retype)
from .scan import simulate_scan, to_scan_frame

SPLIT_SPAN = 100_000  # the seeds a split may use: its base up to its base plus this
SPLIT_BASE = {"dev": 1_000_000, "test": 2_000_000}
SECOND = 500_000      # the second applicant of a case is seeded this far above the first: inside the split, outside its first seeds
LAYOUTS = {"dev": ("A",), "test": ("A", "B")}
DRAWERS = {"A": (draw_statement, draw_payslip, draw_application)}  # layout -> the drawers of a statement, a payslip and an application
ORDER = ("D1", "D2", "D3", "D4", "D5", "S1", "S2", "C1", "C2", "C3", "C4", "C5")
DIGITAL_ONLY = {"D1", "D2", "D3", "D4", "D5"}  # these act on the PDF: a scan would have lost what they leave
SCAN_ONLY = {"S1", "S2"}
MIXED = ("digital", "mild", "digital", "150dpi", "digital", "mild", "digital", "120dpi")  # for the cross-document cases and the genuine ones
SCANS = ("mild", "150dpi", "mild", "120dpi")                                           # for S1 and S2: the worse the scan, the fewer
KEYS = ("statement", "payslip", "application")
STEM = {"statement": "01_statement", "payslip": "02_payslip", "application": "03_application"}
PRODUCERS = ("PageForge Editor 4.1", "Docuweave Pro 7.0", "InkPress PDF Studio 2.3")  # invented: the tools a document was re-saved in
EDITS = {"D1": d1_incremental_edit, "D2": d2_cover_retype, "D3": d3_near_font_retype, "D5": d5_paste_image}
C2 = (("name", "minor"), ("address", "minor"), ("name", "major"), ("employer", "minor"), ("month", "shift"), ("employer", "major"),
      ("address", "major"))
CARRIES = {"name": KEYS, "address": ("statement", "application"), "employer": ("payslip", "application"), "month": ("statement", "payslip")}
C5 = (("logo", "large"), ("stamp", "large"), ("logo", "small"), ("stamp", "small"))


def methods_of(split: str) -> list[str]:
    return [m for m in ORDER if split == "test" or m not in TEST_ONLY]


def plan_cases(split: str, n: int, start: int = 0) -> list[dict]:
    """Cases `start` to `start + n` of a split. Every third case is genuine; the others take the split's methods in turn. A case's
    layout is the next of the split's for its method (or for the genuine ones), so each method meets each layout alike; its
    medium follows from its method: the PDF edits are digital, the scan edits are scans, the rest alternate."""
    if split not in SPLIT_BASE:
        raise ValueError(f"unknown split {split!r}")
    if start < 0 or n < 0 or start + n > SPLIT_SPAN:
        raise ValueError(f"cases {start} to {start + n} do not fit the {SPLIT_SPAN} seeds of a split")
    methods, layouts = methods_of(split), LAYOUTS[split]
    seen: Counter = Counter()
    plan, manipulated = [], 0
    for i in range(start + n):
        method = None if i % 3 == 2 else methods[manipulated % len(methods)]
        manipulated += method is not None
        key = method or "genuine"
        k = seen[key]
        seen[key] += 1
        if method in DIGITAL_ONLY:
            medium = "digital"
        elif method in SCAN_ONLY:
            medium = SCANS[k % len(SCANS)]
        else:
            medium = MIXED[seen["mixed"] % len(MIXED)]
            seen["mixed"] += 1
        plan.append({"case": f"{split}-{i:04d}", "seed": SPLIT_BASE[split] + i, "layout": layouts[k % len(layouts)], "medium": medium,
                     "method": method, "genuine": method is None, "k": k})
    return plan[start:]


def realistic(ident: Identity) -> Identity:
    """An applicant whose obligations are 40 % of income at most (the instalment of the loan asked for and the existing ones): the
    context rule on the ratio then has nothing to say about a genuine case, so what it flags in these datasets is by design."""
    emi = min(ident.existing_emi, ident.monthly_gross * 15 // 100 // 1000 * 1000)
    room, loan = ident.monthly_gross * 2 // 5 - emi, ident.loan_amount
    while loan > 50_000 and loan / ident.tenure_months > room:
        loan -= 50_000
    return replace(ident, existing_emi=emi, loan_amount=loan)


def _other(seed: int, ident: Identity) -> Identity:
    """Another applicant, of another bank and with another name: whose hand, bank marks and scans some cases borrow."""
    for j in count():
        o = realistic(identity(seed + SECOND + j))
        if o.bank != ident.bank and o.name != ident.name:
            return o
    raise AssertionError("unreachable")


def _draw(layout: str, idents: dict[str, Identity], rows: int, seed: int) -> dict:
    statement, payslip, application = DRAWERS[layout]
    return {"statement": statement(idents["statement"], layout, rows=rows, seed=seed), "payslip": payslip(idents["payslip"], layout, seed=seed),
            "application": application(idents["application"], layout, seed=seed)}


def _text(truth: dict, key: str) -> str:
    """What is drawn at a box key of a document: a header field, or a table cell as 'column@row'."""
    name, _, num = key.partition("@")
    return money(Decimal(truth["rows"][int(num) - 1][name] if num else truth["fields"][name]))


def _bump(text: str) -> str:
    """The same amount with its first digit changed, as a hand would: the column stays straight."""
    i = next(i for i, c in enumerate(text) if c.isdigit())
    return text[:i] + str(int(text[i]) % 9 + 1) + text[i + 1:]


def _targets(drawn: dict, rng: random.Random) -> list[tuple[str, str]]:
    """(document, box key) of the amounts a change may touch, all on page 1: some that the checks across a case cover and some,
    like the loan asked for, that they do not."""
    rows = drawn["statement"].truth["rows"][:30]
    credit = [i for i, r in enumerate(rows, 1) if r["credit"]]
    debit = [i for i, r in enumerate(rows, 1) if r["debit"]]
    return [("statement", "closing_balance"), ("statement", f"credit@{rng.choice(credit)}"), ("payslip", "net_pay"),
            ("application", "loan_amount"), ("statement", f"debit@{rng.choice(debit)}"), ("payslip", "gross_earnings"),
            ("application", "declared_monthly_income"), ("payslip", "earning_amount@1")]


def _slip(text: str, rng: random.Random) -> str:
    """The text with one small slip, as a clerk makes: a digit, or a letter inside a word, changed."""
    for _ in range(200):
        i = rng.randrange(len(text))
        c = text[i]
        if c.isdigit():
            new = str((int(c) + rng.randrange(1, 10)) % 10)
        elif c.isalpha() and i > 0 and text[i - 1].isalpha():
            new = rng.choice([x for x in "aeiounrstl" if x != c.lower()])
            new = new.upper() if c.isupper() else new
        else:
            continue
        return text[:i] + new + text[i + 1:]
    raise ValueError(f"nothing to change in {text!r}")


def _month(ident: Identity, rng: random.Random) -> str:
    y, m = divmod(ident.month.year * 12 + ident.month.month - 1 + rng.choice((-2, -1, 1, 2)), 12)
    return date(y, m + 1, 1).isoformat()


def _modified(pdf: bytes, rng: random.Random) -> str:
    """A modification date some days after the PDF was created, in the form PDF writes it."""
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        made = datetime.strptime(doc.metadata["creationDate"][2:16], "%Y%m%d%H%M%S")
    return (made + timedelta(days=rng.randrange(3, 40), hours=rng.randrange(1, 20))).strftime("D:%Y%m%d%H%M%S+05'30'")


def build_case(p: dict) -> tuple[dict[str, bytes], dict]:
    """The files of one planned case, by name in upload order, and its manifest entry."""
    seed, layout, medium, method, k = p["seed"], p["layout"], p["medium"], p["method"], p["k"]
    if layout not in DRAWERS:
        raise ValueError(f"no drawer for layout {layout!r}")
    rng = random.Random(f"{p['case']}/build")
    ident = realistic(identity(seed))
    other = _other(seed, ident)
    rows = rng.choice((10, 14, 20, 28) if medium != "digital" else (10, 14, 20, 28, 36))  # a scan holds one page
    idents, mans, valid, why = dict.fromkeys(KEYS, ident), [], dict.fromkeys(KEYS, True), ""
    ext = ".pdf" if medium == "digital" else ".jpg"
    names = {key: STEM[key] + ext for key in KEYS}

    if method == "C1":  # the payslip's pay changed so that it still adds up
        up, ratio = rng.randrange(5, 31) * 1000, ident.deductions / ident.monthly_gross
        gross = ident.monthly_gross + up
        options = [("more gross pay", dict(monthly_gross=gross)), ("fewer deductions", dict(deductions=round(ident.deductions * 0.9 / 100) * 100)),
                   ("more gross pay and deductions in proportion", dict(monthly_gross=gross, deductions=round(gross * ratio / 100) * 100))]
        for why, change in options[k % 3:] + options[:k % 3]:
            idents["payslip"] = c1_consistent_change(ident, **change)
            try:
                drawn = _draw(layout, idents, rows, seed)
                break
            except ValueError:  # the lines of the payslip no longer add up to something positive
                continue
        else:
            raise ValueError("no pay change fits this applicant")
        mans.append(dict(method="C1", doc="payslip", variant=why, field="payslip.gross_earnings,net_pay"))
    else:
        if method == "C2":
            field, how = C2[k % len(C2)]
            doc = rng.choice(CARRIES[field])
            if how == "minor":
                new = _slip(getattr(ident, field), rng)
            elif field == "month":
                new = _month(ident, rng)
            elif field == "employer":
                first = ident.employer.split()[0]
                new = f"{FIRMS[(FIRMS.index(first) + rng.randrange(1, len(FIRMS))) % len(FIRMS)]} Test Pvt Ltd"
            else:
                new = getattr(other, field)
            idents[doc] = c2_cross_document(ident, field, new)
            mans.append(dict(method="C2", doc=doc, variant=f"{field}, {how}", field=f"{doc}.{field}"))
        elif method == "C4":
            doc = rng.choice(("payslip", "application"))
            idents[doc] = c4_other_hand(ident, other)
            mans.append(dict(method="C4", doc=doc, variant="signed in another hand", field=f"{doc}.signature"))
        elif method == "C5":
            kind, strength = C5[k % len(C5)]
            doc = rng.choice(("statement", "application"))
            idents[doc] = c5_other_mark(ident, kind, strength, other)
            mans.append(dict(method="C5", doc=doc, variant=f"{kind}, {strength}", field=f"{doc}.{kind}"))
        drawn = _draw(layout, idents, rows, seed)
    pdfs = {key: drawn[key].pdf for key in KEYS}
    truths = {key: drawn[key].truth for key in KEYS}

    if method in DIGITAL_ONLY:
        if method == "D4":
            doc = KEYS[k % 3]
            producer = PRODUCERS[k % len(PRODUCERS)]
            pdfs[doc], m = d4_metadata_edit(pdfs[doc], producer, _modified(pdfs[doc], rng))
            mans.append(dict(asdict(m), doc=doc, variant=f"{doc}, producer {producer}", field=f"{doc}.metadata"))
        else:
            targets = _targets(drawn, rng)
            for j in range(len(targets)):  # the next target when the text of this one stands more than once on its page
                doc, key = targets[(3 * k + ORDER.index(method) + j) % len(targets)]
                old = _text(truths[doc], key)
                try:
                    pdfs[doc], m = EDITS[method](pdfs[doc], old, _bump(old))
                except ValueError:
                    continue
                mans.append(dict(asdict(m), doc=doc, variant=f"{doc} {key}", field=f"{doc}.{key}"))
                valid[doc] = False
                break
            else:
                raise ValueError("no amount to change")

    scan_seed = {key: seed * 10 + i for i, key in enumerate(KEYS, 1)}
    if medium == "digital":
        data = {key: pdfs[key] for key in KEYS}
    else:
        data = {key: simulate_scan(pdfs[key], medium, scan_seed[key]) for key in KEYS}
    size = {key: Image.open(io.BytesIO(data[key])).size for key in KEYS} if medium != "digital" else {}
    if method in SCAN_ONLY:
        targets = _targets(drawn, rng)
        doc, key = targets[(3 * k + ORDER.index(method)) % len(targets)]
        x0, y0, x1, y1 = to_scan_frame(truths[doc]["boxes"][key][1:], size[doc], scan_seed[doc])
        box = [round(x0 - 3, 2), round(y0 - 2, 2), round(x1 + 3, 2), round(y1 + 2, 2)]
        old = _text(truths[doc], key)
        if method == "S1":
            donor = _draw(layout, dict.fromkeys(KEYS, other), rows, seed)[doc].pdf
            data[doc], m = s1_splice(data[doc], simulate_scan(donor, medium, scan_seed[doc] + 1), box)
        else:
            data[doc], m = s2_erase_retype(data[doc], box, _bump(old))
        mans.append(dict(asdict(m), doc=doc, variant=f"{doc} {key}", field=f"{doc}.{key}"))
        valid[doc] = False

    files = {names[key]: data[key] for key in KEYS}
    docs = []
    for key in KEYS:
        t = truths[key]
        boxes = t["boxes"] if medium == "digital" else {b: [v[0], *to_scan_frame(v[1:], size[key], scan_seed[key])] for b, v in t["boxes"].items()}
        docs.append({"file": names[key], "type": t["type"], "fields": t["fields"], "rows": t["rows"], "boxes": boxes, "truth_valid": valid[key]})
    if method == "C3":
        copy = f"04_statement_copy{ext}"
        files[copy] = c3_duplicate(list(files.values()))[-1]
        docs.append(dict(docs[0], file=copy))
        mans.append(dict(method="C3", doc=copy, variant="the statement submitted twice", field="statement.file", also=[names["statement"]]))
    for d in docs:
        d["sha256"] = hashlib.sha256(files[d["file"]]).hexdigest()
    manipulations = []
    for m in mans:
        doc = m["doc"]
        manipulations.append({"method": m["method"], "variant": m["variant"], "doc": names.get(doc, doc), "page": m.get("page", 0),
                              "box": m.get("box"), "field": m["field"], "note": m.get("note", ""), "also": m.get("also", [])})
    entry = {"case": p["case"], "seed": seed, "layout": layout, "medium": medium, "genuine": method is None, "rows": rows, "docs": docs,
             "manipulations": manipulations}
    return files, entry


def build_split(split: str, out: Path | str, n: int, start: int = 0) -> Path:
    """Cases `start` to `start + n` of a split written under `out`, one folder a case, and `out/manifest.json`. Returns the manifest's path."""
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
    path.write_text(json.dumps({"split": split, "cases": entries}, indent=1), encoding="utf-8", newline="\n")
    return path


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="python -m datagen.build", description="Write cases of the demonstration dataset and their manifest.")
    ap.add_argument("split", choices=sorted(SPLIT_BASE))
    ap.add_argument("out", help="the folder to write to")
    ap.add_argument("--cases", type=int, default=12, help="how many cases (default: 12)")
    ap.add_argument("--start", type=int, default=0, help="the first case (default: 0)")
    a = ap.parse_args()
    print(build_split(a.split, a.out, a.cases, a.start))
