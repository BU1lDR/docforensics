"""Cases for measuring the declared-EMI check (cross_emi: the existing EMI that a loan application declares, against the instalments that a
bank statement of one month shows being paid). Two files a case: the application and the statement as datagen/layouts draw them, with some
rows of the statement set by this pack (and every balance after them made to follow, so no other check has a reason to speak), as digital
PDFs or as mild JPEG scans (200 dpi) of the same pages. The base generator is not touched: it writes no instalment word, so the scored
splits cannot change. The kinds, fixed here before the check was run on them. `expect` is the one title below, or nothing.

Nothing to find:
- none: no row set; the application declares what the identity draws (0 to INR 10,000), with nothing on the statement to set it against.
- match: one debit narrated as an instalment (EMI, instalment or loan) and the application declares exactly that amount.
- rounded: one such debit of INR 1,000 k + 500 (k from 5 to 19), declared as INR 1,000 k: short by 9.1 % at most, inside the 10 % tolerance.
- two-loans: two such debits, declared as their sum.
- declared-higher: one such debit, declared INR 5,000 higher.
- fee-not-emi: three debits narrated as a loan fee, a tax on a loan fee and an EMI bounce charge; the declared figure is the identity's own.
- lookalike: three debits whose narration only holds the letters e, m, i inside another word (an airline, a remittance, a restaurant); likewise.

A gap to find (expect "Declared existing EMI is lower than the instalments on the bank statement", naming the total of the instalments):
- under-zero: one instalment debit (INR 2,000 to 20,000), declared 0.
- under-part: two instalment debits, declared as the first one only (the second at least half of it).
- under-some: one instalment debit of INR 1,000 k (k from 6 to 20), declared as 70 % of it, rounded down to the thousand.

A gap the check cannot see, in the pack so that the report counts it rather than leaves it out:
- lender-only: one debit narrated with a lender's name and a number and none of the words the check reads (EMI, instalment, loan), declared 0.
  A reviewer would want the note, so `expect` holds the title; the check reads narrations for those words and is expected to miss it.

The instalment narrations are the wordings the check was written to read, so a result here says what the check does with those wordings, on
statements and applications made by this project's generator: it does not say how often a real instalment is narrated like that, and it says
nothing about other layouts or other producers. Seeds: the split's base plus PACK, apart from every other pack."""
import hashlib
import json
import random
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from .fictional import BANKS, identity
from .layouts import Drawn, money
from .layouts.application import draw_application
from .layouts.statement import draw_statement
from .scan import simulate_scan

BASE = {"ext-dev": 3_000_000, "ext-test": 4_000_000}  # the seed bases of the ext splits, as in the packs of X, E, H and the structure check
PACK = 400_000  # X draws its seeds from BASE + 0 on, E from + 100_000, H from + 200_000, the structure check from + 300_000
SPAN = 10_000
KINDS = ("none", "match", "rounded", "two-loans", "declared-higher", "fee-not-emi", "lookalike", "under-zero", "under-part", "under-some",
         "lender-only")
PLANTED = KINDS[7:]  # a gap between the declared figure and the debits
BLIND = ("lender-only",)  # planted, and not readable by the check
TITLE = "Declared existing EMI is lower than the instalments on the bank statement"
LINES = {"none": 0, "match": 1, "rounded": 1, "two-loans": 2, "declared-higher": 1, "fee-not-emi": 3, "lookalike": 3, "under-zero": 1,
         "under-part": 2, "under-some": 1, "lender-only": 1}  # rows of the statement set
NOTES = {"none": "no instalment on the statement; the declared figure is the identity's own",
         "match": "one instalment debit, declared exactly", "rounded": "one instalment debit, declared rounded down to the thousand (under 10 % short)",
         "two-loans": "two instalment debits, declared as their sum", "declared-higher": "one instalment debit, declared INR 5,000 higher",
         "fee-not-emi": "a loan fee, a tax on a loan fee and an EMI bounce charge; none is an instalment",
         "lookalike": "an airline, a remittance and a restaurant: the letters e, m, i inside other words",
         "under-zero": "one instalment debit, declared 0", "under-part": "two instalment debits, only the first declared",
         "under-some": "one instalment debit, declared as 70 % of it (rounded down to the thousand)",
         "lender-only": "a debit narrated with a lender's name alone; the check cannot read it"}
INSTALMENT = ("ECS/EMI Home Loan {n}", "NACH/EMI Car Loan {n}", "ACH/Instalment {n}", "ECS/Loan Repayment {n}")
OTHER = {"fee-not-emi": ("NEFT/Loan Processing Fee", "NEFT/GST on Loan Fee", "ECS/EMI Bounce Charges"),
         "lookalike": ("POS/Emirates Airlines", "IMPS/Remittance Family", "POS/Demi Glace Cafe")}
ROWS = (14, 16, 20)  # rows the statement is drawn with: the next count is tried when the first leaves no room for the amounts


class _Tight(Exception):
    """The balances of the statement leave no room for the amounts a kind needs."""


def plan_cases(split: str, n: int, start: int = 0) -> list[dict]:
    """Cases `start` to `start + n`: the kind cycles through the eleven, the layout changes every eleven cases, the medium every twenty-two."""
    if split not in BASE:
        raise ValueError(f"unknown split {split!r}")
    if start < 0 or n < 0 or start + n > SPAN:
        raise ValueError(f"cases {start} to {start + n} do not fit the {SPAN} seeds of the pack")
    return [{"case": f"{split}-m-{i:04d}", "seed": BASE[split] + PACK + i, "kind": KINDS[i % len(KINDS)],
             "layout": "AB"[(i // len(KINDS)) % 2], "medium": ("digital", "scan")[(i // (2 * len(KINDS))) % 2]} for i in range(start, start + n)]


def _amount(rng: random.Random, lo: int, hi: int) -> int:
    """Rupees, in steps of 500, from lo up to hi."""
    if hi < lo:
        raise _Tight
    return rng.randrange(-(-lo // 500), hi // 500 + 1) * 500


def _plan(kind: str, rng: random.Random, hi: int) -> tuple[list[tuple[str, int]], int | None]:
    """The narrations and amounts (rupees) of the rows to set, and the declared figure (None: the identity's own)."""
    def emi() -> str:
        return rng.choice(INSTALMENT).format(n=rng.randrange(1000, 10000))

    if kind == "none":
        return [], None
    if kind in OTHER:
        return [(text, _amount(rng, 500, min(hi, 5000))) for text in OTHER[kind]], None
    if kind == "lender-only":
        return [(f"ECS/{rng.choice(BANKS)} Test Finance {rng.randrange(1000, 10000)}", _amount(rng, 2000, hi))], 0
    if kind == "rounded":
        if hi < 5500:
            raise _Tight
        k = rng.randrange(5, (hi - 500) // 1000 + 1)
        return [(emi(), 1000 * k + 500)], 1000 * k
    if kind == "under-some":
        if hi < 6000:
            raise _Tight
        e = 1000 * rng.randrange(6, hi // 1000 + 1)
        return [(emi(), e)], e * 7 // 10 // 1000 * 1000
    a = _amount(rng, 2000, hi)
    if kind in ("two-loans", "under-part"):
        b = _amount(rng, max(2000, -(-a // 2)) if kind == "under-part" else 2000, hi)
        return [(emi(), a), (emi(), b)], a + b if kind == "two-loans" else a
    return [(emi(), a)], {"match": a, "declared-higher": a + 5000, "under-zero": 0}[kind]


def _statement(ident, layout: str, seed: int, kind: str, rng: random.Random) -> tuple[Drawn, list[tuple[int, str, int]], int | None]:
    """The statement with the rows of the kind set into its last debits (after the second row), every later balance moved by the same
    amount, and no balance below zero: the instalments may use four fifths of the lowest balance from the first of them on."""
    n = LINES[kind]
    for rows in ROWS:
        base = draw_statement(ident, layout, rows=rows, seed=seed).truth["rows"]
        debits = [i for i, r in enumerate(base, 1) if i >= 3 and r["debit"]]
        if len(debits) < n:
            continue
        chosen = debits[len(debits) - n:]
        old = [Decimal(r["balance"]) for r in base]
        room = Decimal("0.8") * min(old[chosen[0] - 1:]) if n else Decimal(0)
        try:
            lines, declared = _plan(kind, rng, min(20_000, int(room / n // 500 * 500)) if n else 0)
        except _Tight:
            continue
        over, delta = {}, Decimal(0)
        for j, r in enumerate(base, 1):
            if j in chosen:
                narration, amount = lines[chosen.index(j)]
                delta += Decimal(r["debit"]) - amount
                over[f"description@{j}"], over[f"debit@{j}"] = narration, money(amount)
            if delta:
                over[f"balance@{j}"] = money(old[j - 1] + delta)
        if delta:
            over["closing_balance"] = money(old[-1] + delta)
        return draw_statement(ident, layout, rows=rows, seed=seed, overrides=over), [(j, *lines[i]) for i, j in enumerate(chosen)], declared
    raise ValueError(f"no room for the rows of kind {kind!r} at seed {seed}")


def draw_case(p: dict) -> tuple[Drawn, Drawn, dict]:
    """The application, the statement and the manifest entry (without the files) of one planned case."""
    seed, kind = p["seed"], p["kind"]
    ident = identity(seed)
    statement, rows, declared = _statement(ident, p["layout"], seed, kind, random.Random(f"emi/{seed}"))
    own = ident.existing_emi if declared is None else declared
    application = draw_application(replace(ident, existing_emi=own), p["layout"], seed)
    instalment = kind not in OTHER and kind not in BLIND
    entry = {"case": p["case"], "seed": seed, "kind": kind, "layout": p["layout"], "medium": p["medium"], "declared": f"{own}.00",
             "set": [{"row": j, "narration": s, "amount": f"{a:.2f}", "instalment": instalment} for j, s, a in rows],
             "total": f"{sum(a for _, _, a in rows):.2f}" if kind in PLANTED else None,
             "expect": [TITLE] if kind in PLANTED else [], "note": NOTES[kind]}
    return application, statement, entry


def build_case(p: dict) -> tuple[dict[str, bytes], dict]:
    """The two files of one planned case, by name, and its manifest entry."""
    application, statement, entry = draw_case(p)
    ext = "pdf" if p["medium"] == "digital" else "jpg"
    files = {f"{name}.{ext}": drawn.pdf if ext == "pdf" else simulate_scan(drawn.pdf, "mild", p["seed"] * 10 + i)
             for i, (name, drawn) in enumerate((("application", application), ("statement", statement)))}
    return files, entry | {"files": sorted(files), "sha256": {n: hashlib.sha256(d).hexdigest() for n, d in files.items()}}


def build_split(split: str, out: Path | str, n: int, start: int = 0) -> Path:
    """Cases `start` to `start + n` written under `out`, one folder a case, and `out/manifest.json`. Returns the manifest's path."""
    out = Path(out)
    entries = []
    for p in plan_cases(split, n, start):
        files, entry = build_case(p)
        (out / p["case"]).mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            (out / p["case"] / name).write_bytes(data)
        entries.append(entry)
    path = out / "manifest.json"
    path.write_text(json.dumps({"split": split, "pack": "emi", "cases": entries}, indent=1), encoding="utf-8", newline="\n")
    return path


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="python -m datagen.emi_pack", description="Write the cases for the declared-EMI check and their manifest.")
    ap.add_argument("split", choices=sorted(BASE))
    ap.add_argument("out", help="the folder to write to")
    ap.add_argument("--cases", type=int, default=44, help="how many cases (default: 44, each kind in each layout and medium once)")
    ap.add_argument("--start", type=int, default=0, help="the first case (default: 0)")
    a = ap.parse_args()
    print(build_split(a.split, a.out, a.cases, a.start))
