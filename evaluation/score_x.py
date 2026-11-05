"""The scorer of package X (scope D): what the local model read from pages of a type the tool has no spec for, against what the generator
printed on them (datagen/unseen.py). Only this code and the generator know the manifest of that pack. The counting rules are fixed here,
before any model is run on the pack, and are printed in the report:

- Each fact the generator printed is looked for among the fields of its document, at its box. A field is AT the box at an IoU
  (intersection over union) of 0.5 or more, the bar the detection scorer calls 'located', and NEAR it at 0.1 or more.
- right: a model-read field is at the box and its name is acceptable. misnamed: one is at the box and its name is not. partial: one is
  near the box and none is at it. rules: only a field the rules read is at the box (the model is not asked about words the rules read).
  missing: no field is near the box.
- A name is acceptable when the generator's patterns for what a reviewer would call this fact match the lower-case words of the field's
  name (`accept`) and its patterns for what would be wrong do not (`reject`). They sit in the manifest, written before the model ran.
- exact: the value is as printed. The same text for text and ids (case and spacing aside); the same normalised value for dates and
  amounts. On a scan this measures the OCR as well as the model.
- A model-read field at no listed fact is an extra: a 'table cell' if it is at a cell of the table the generator printed, otherwise
  'unlisted'. Extras are counted, neither right nor wrong; the write-up looks at them.
- Items the model gave that code could not find on the page are counted from the audit events, by the reason logged."""
import re
import statistics
from collections import Counter

from docforensics.model import Case
from docforensics.understand.normalise import plain

from .score import _same, iou

AT, NEAR = 0.5, 0.1
OUTCOMES = ("right", "misnamed", "partial", "rules", "missing")


def _acceptable(t: dict, name: str) -> bool:
    label = plain(name.replace("_", " "))
    return bool(re.search(t["accept"], label)) and not re.search(t["reject"], label)


def _exact(t: dict, f) -> bool:
    return f.value == t["value"] if t["kind"] in ("amount", "date") else _same(t["kind"], t["text"], f.raw)


def score_case(entry: dict, case: Case | None, events: list[dict], seconds: list[float]) -> dict:
    """The facts of one case's documents with what became of each, the model's extras, the items it lost, and the calls."""
    docs = {d.filename: d for d in case.documents} if case else {}  # no case: it did not finish, every fact is missing
    rows, extras = [], []
    for td in entry["docs"]:
        doc = docs.get(td["file"])
        fields = [f for f in (doc.fields if doc else []) if f.page == 1]
        used: set[str] = set()
        for name, t in td["fields"].items():
            near = sorted(((iou(f.box, t["box"][1:]), f) for f in fields), key=lambda x: -x[0])
            near = [x for x in near if x[0] >= NEAR]
            model, rules = [x for x in near if x[1].model_read], [x for x in near if not x[1].model_read]
            at = [x for x in model if x[0] >= AT]
            hit, outcome = None, "missing"
            if at:
                hit = next((x for x in at if _acceptable(t, x[1].name)), at[0])
                outcome = "right" if _acceptable(t, hit[1].name) else "misnamed"
            elif any(v >= AT for v, _ in rules):
                hit, outcome = rules[0], "rules"
            elif model:
                hit, outcome = model[0], "partial"
            if hit and hit[1].model_read:
                used.add(hit[1].id)
            rows.append({"case": entry["case"], "doc": td["file"], "type": td["type"], "layout": td["layout"], "medium": entry["medium"], "field": name,
                         "kind": t["kind"], "label": t["label"], "text": t["text"], "outcome": outcome, "iou": round(hit[0], 2) if hit else 0.0,
                         "got": hit[1].name if hit else "", "got_text": hit[1].raw if hit else "",
                         "exact": _exact(t, hit[1]) if outcome in ("right", "misnamed", "rules") else None})
        cells = [c["box"][1:] for r in td["rows"] for c in r.values()]
        for f in fields:
            if f.model_read and f.id not in used:
                extras.append({"case": entry["case"], "doc": td["file"], "type": td["type"], "name": f.name, "text": f.raw,
                               "where": "table cell" if any(iou(f.box, c) >= NEAR for c in cells) else "unlisted"})
    calls = {"pages": len(events), "accepted": sum(1 for e in events if e["accepted"]), "items": sum(e.get("items", 0) for e in events),
             "kept": sum(e.get("kept", 0) for e in events), "unused": sum(e.get("unused", 0) for e in events)}  # a page that was skipped has none
    dropped = [{"case": entry["case"], "doc": e["doc"], **d} for e in events for d in e.get("dropped", [])]
    return {"fields": rows, "extras": extras, "dropped": dropped, "calls": calls, "seconds": list(seconds)}


def _by(rows: list[dict], key: str) -> dict:
    out: dict[str, Counter] = {}
    for r in rows:
        out.setdefault(r[key], Counter())[r["outcome"]] += 1
    return dict(sorted(out.items()))


def summarise(results: list[dict]) -> dict:
    rows = [r for res in results for r in res["fields"]]
    secs = [s for res in results for s in res["seconds"]]
    calls = Counter()
    for res in results:
        calls.update(res["calls"])
    return {"cases": len(results), "facts": len(rows), "outcomes": Counter(r["outcome"] for r in rows),
            "exact": sum(1 for r in rows if r["outcome"] == "right" and r["exact"]),
            "by_kind": _by(rows, "kind"), "by_medium": _by(rows, "medium"), "by_type": _by(rows, "type"), "by_layout": _by(rows, "layout"),
            "extras": Counter(x["where"] for res in results for x in res["extras"]),
            "dropped": Counter(d["reason"] for res in results for d in res["dropped"]), "calls": dict(calls),
            "seconds": {"calls": len(secs), "mean": round(statistics.fmean(secs), 1) if secs else 0.0,
                        "median": round(statistics.median(secs), 1) if secs else 0.0, "max": round(max(secs), 1) if secs else 0.0},
            "misses": [r for r in rows if r["outcome"] in ("missing", "misnamed", "partial")],
            "extra_list": [x for res in results for x in res["extras"]]}


def _pct(a: int, b: int) -> str:
    return f"{100 * a / b:.0f} %" if b else "-"


def _table(title: str, groups: dict) -> list[str]:
    out = [f"| {title} | facts | " + " | ".join(OUTCOMES) + " |", "|---|---|" + "---|" * len(OUTCOMES)]
    for k, c in groups.items():
        n = sum(c.values())
        out.append(f"| {k} | {n} | " + " | ".join(f"{c[o]} ({_pct(c[o], n)})" for o in OUTCOMES) + " |")
    return out


def format_report(s: dict) -> str:
    run, o, n = s.get("run", {}), s["outcomes"], s["facts"]
    lines = ["# Template-free extraction by the local model: measured on the pack of invoices and electricity bills", "",
             f"Model: {run.get('model', '?')} ({run.get('digest', 'digest not recorded')}). Split {run.get('split', '?')}, {s['cases']} cases, "
             f"{n} printed facts in {2 * s['cases']} documents. {run.get('date', '')} {run.get('commit', '')}", "",
             "Every value the model read is **inference** (10.4): the words come from the page, the name comes from the model, and nothing here "
             "feeds a check or a finding. The counting rules are in the docstring of `evaluation/score_x.py`; in short: a fact is *right* when a "
             "model-read field sits at its box (IoU 0.5 or more) under an acceptable name, *misnamed* when the name is not acceptable, "
             "*partial* when the field only touches the box (IoU 0.1 to 0.5), *rules* when only the rules' own reading is there, *missing* "
             "when nothing is near.", "",
             f"Of {n} printed facts: " + ", ".join(f"{o[k]} {k}" for k in OUTCOMES) + f". Of the {o['right']} right, {s['exact']} carry the "
             "value as printed.", ""]
    for title, key in (("kind", "by_kind"), ("medium", "by_medium"), ("document", "by_type"), ("layout", "by_layout")):
        lines += _table(title, s[key]) + [""]
    c = s["calls"]
    lines += [f"Calls: {c.get('pages', 0)} pages considered, {c.get('accepted', 0)} replies accepted, {c.get('items', 0)} items given, "
              f"{c.get('kept', 0)} kept. Dropped: " + (", ".join(f"{v} {k}" for k, v in s["dropped"].most_common()) or "none")
              + f"; {c.get('unused', 0)} beyond the limit.",
              f"Seconds per page: mean {s['seconds']['mean']}, median {s['seconds']['median']}, longest {s['seconds']['max']} "
              f"({s['seconds']['calls']} calls).", "",
              "Extras (model-read fields at no listed fact): " + (", ".join(f"{v} {k}" for k, v in s["extras"].items()) or "none") + ".", ""]
    if s["misses"]:
        lines += ["## Facts not read right", "", "| case | document | fact | printed | outcome | the model's name and words |", "|---|---|---|---|---|---|"]
        lines += [f"| {r['case']} | {r['doc']} | {r['field']} | {r['text']} | {r['outcome']} | {r['got'] or '-'}: {r['got_text'] or '-'} |" for r in s["misses"]]
        lines.append("")
    if s["extra_list"]:
        lines += ["## Extras", "", "| case | document | name | words | where |", "|---|---|---|---|---|"]
        lines += [f"| {x['case']} | {x['doc']} | {x['name']} | {x['text']} | {x['where']} |" for x in s["extra_list"]]
        lines.append("")
    return "\n".join(lines)
