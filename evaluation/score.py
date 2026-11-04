"""The scorer (design 8, Task 19): the manifest of a split (what is true) against the cases the pipeline produced (what it said). It is
the only code that reads the manifest. The counting rules below are fixed before a split is run and printed in its report, so a
"found" means the same on the dev split and on the test split."""
import re
from collections import Counter, defaultdict

from docforensics.model import Case, Finding
from docforensics.understand.specs import load_specs

NEAR, PLACE = 0.1, 0.5  # IoU at which a finding is near a changed place, and at which it is at it
ORDER = ("D1", "D2", "D3", "D4", "D5", "S1", "S2", "C1", "C2", "C3", "C4", "C5")
WHAT = {"D1": "incremental PDF edit", "D2": "white cover, retyped (same font)", "D3": "white cover, retyped (near font; test split only)",
        "D4": "metadata edit", "D5": "picture pasted over", "S1": "scan spliced from another scan", "S2": "scan erased, retyped (test split only)",
        "C1": "pay changed so the payslip still adds up", "C2": "name, address, employer or month changed in one document",
        "C3": "statement submitted twice", "C4": "signed in another hand", "C5": "another logo or stamp"}
EXPECT = {"D4": ("pdf_meta", "cross_producer"), "C3": ("cross_duplicate",), "C4": ("signature",), "C5": ("mark",)}  # C1 and C2: any cross_* check
MEDIA = ("digital", "mild", "150dpi", "120dpi")
SCANNED = "scan"


def iou(a, b) -> float:
    w, h = min(a[2], b[2]) - max(a[0], b[0]), min(a[3], b[3]) - max(a[1], b[1])
    inter = max(w, 0) * max(h, 0)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _flags(case: Case) -> list[Finding]:
    """What a reviewer is shown to look at: everything but processing limitations and clusters (a cluster repeats its members)."""
    return [f for f in case.findings if f.fclass != "processing_limitation" and f.family != "cluster"]


def _limits(case: Case) -> list[Finding]:
    return [f for f in case.findings if f.fclass == "processing_limitation"]


def _expected(method: str, detector: str) -> bool:
    return detector.startswith("cross_") if method in ("C1", "C2") else detector in EXPECT[method]


def _text(s: str) -> str:
    return " ".join(str(s).split())


def _same(kind: str, truth: str, got: str) -> bool:
    if kind == "text":
        return _text(truth).casefold() == _text(got).casefold()
    if kind == "id":
        return "".join(truth.split()) == "".join(got.split())
    return truth == got


def _outcome(entry: dict, m: dict, case: Case | None, errors: dict[str, str]) -> dict:
    """What became of one change: found or not, where, by which detectors, and if not, why."""
    o = {"case": entry["case"], "method": m["method"], "variant": re.sub(r"@\d+", "", m["variant"]), "medium": entry["medium"], "doc": m["doc"],
         "has_box": m["box"] is not None, "found": False, "located": False, "best": 0.0 if m["box"] else None, "flagged": False, "by": [], "why": ""}
    if case is None:
        o["why"] = "no result: " + errors.get(entry["case"], "the case did not finish")
        return o
    ids = {d.id for d in case.documents if d.filename in {m["doc"], *m["also"]}}
    own = {d.id for d in case.documents if d.filename == m["doc"]}
    flags = _flags(case)
    on_doc = [f for f in flags if any(e.doc in ids for e in f.evidence)]
    o["flagged"] = bool(on_doc)
    if m["box"]:
        near = [(iou(m["box"], e.box), f) for f in flags for e in f.evidence if e.doc in own and e.page == m["page"]]
        o["best"] = max((v for v, _ in near), default=0.0)
        o["found"], o["located"] = o["best"] >= NEAR, o["best"] >= PLACE
        o["by"] = sorted({f.detector for v, f in near if v >= NEAR})
    else:
        hit = [f for f in on_doc if _expected(m["method"], f.detector)]
        o["found"], o["by"] = bool(hit), sorted({f.detector for f in hit})
    if not o["found"]:
        limits = [f for f in _limits(case) if any(e.doc in ids for e in f.evidence)]
        if not on_doc and limits:
            o["why"] = "only a limitation cites the changed document: " + "; ".join(f"{f.detector}: {_text(f.title)}" for f in limits[:3])
        elif on_doc and m["box"]:
            o["why"] = f"flagged elsewhere on the changed document (best IoU {o['best']:.2f} against the changed box)"
        elif on_doc:
            o["why"] = "flagged, but by a detector not expected for this change: " + ", ".join(sorted({f.detector for f in on_doc}))
        else:
            o["why"] = "no finding cites the changed document"
    return o


def _extraction(entry: dict, td: dict, doc, spec, extraction: dict) -> None:
    """Every value the truth of a document holds against the field the pipeline extracted for it (by name and, in a table, row)."""
    look: dict = {}
    for f in doc.fields:
        if (f.name, f.row) not in look or (look[(f.name, f.row)].value is None and f.value is not None):
            look[(f.name, f.row)] = f
    kinds = {f.name: f.kind for f in spec.fields}
    items = [(name, None, kinds[name], v) for name, v in td["fields"].items() if v is not None and name in kinds]
    if spec.table:
        cols = {c.name: c.kind for c in spec.table.columns}
        items += [(f"{spec.table.prefix}.{col}", i, cols[col], v) for i, row in enumerate(td["rows"], 1) for col, v in row.items()
                  if v is not None and col in cols]
    for name, row, kind, truth in items:
        b = extraction[(entry["layout"], entry["medium"], kind)]
        f = look.get((name, row))
        b["n"] += 1
        if f is None or f.value is None:
            b["missing"] += 1
        elif _same(kind, str(truth), f.value):
            b["correct"] += 1
        else:
            b["wrong"] += 1


def _method_rows(outcomes: list[dict]) -> dict:
    methods: dict = {}
    for o in outcomes:
        r = methods.setdefault(o["method"], {"n": 0, "found": 0, "located": 0 if o["has_box"] else None, "mean_iou": 0.0 if o["has_box"] else None,
                                             "flagged_document": 0, "by_detector": Counter(), "by_variant": defaultdict(lambda: {"n": 0, "found": 0})})
        r["n"] += 1
        r["found"] += o["found"]
        r["flagged_document"] += o["flagged"]
        r["by_detector"].update(o["by"] if o["found"] else ())
        r["by_variant"][o["variant"]]["n"] += 1
        r["by_variant"][o["variant"]]["found"] += o["found"]
        if o["has_box"]:
            r["located"] += o["located"]
            r["mean_iou"] += o["best"]
    for r in methods.values():
        r["mean_iou"] = r["mean_iou"] / r["n"] if r["mean_iou"] is not None else None
        r["by_detector"], r["by_variant"] = dict(r["by_detector"]), dict(r["by_variant"])
    return methods


def score(manifest: dict, cases: dict[str, Case], timings: dict[str, float], peak_rss_mb: float | None = None,
          errors: dict[str, str] | None = None) -> dict:
    errors = errors or {}
    specs = load_specs()
    counts = {"cases": len(manifest["cases"]), "genuine_cases": 0, "manipulated_cases": 0, "no_result": 0}
    outcomes, off_target, false_flags = [], [], []
    g = Counter()
    by_detector, by_fclass, by_limit = Counter(), Counter(), Counter()
    extraction: dict = defaultdict(Counter)
    classification: dict = defaultdict(Counter)
    seconds = {"digital": [0.0, 0], SCANNED: [0.0, 0]}
    for entry in manifest["cases"]:
        name, case = entry["case"], cases.get(entry["case"])
        counts["genuine_cases" if entry["genuine"] else "manipulated_cases"] += 1
        outcomes += [_outcome(entry, m, case, errors) for m in entry["manipulations"]]
        if case is None:
            counts["no_result"] += 1
            continue
        flags, limits = _flags(case), _limits(case)
        if entry["genuine"]:
            g.update(cases=1, documents=len(case.documents), flags=len(flags), cases_with_flags=bool(flags), limitations=len(limits))
            by_detector.update(f.detector for f in flags)
            by_fclass.update(f.fclass for f in flags)
            by_limit.update(f"{f.detector}: {_text(f.title)}" for f in limits)
            names = {d.id: d.filename for d in case.documents}
            false_flags += [{"case": name, "detector": f.detector, "fclass": f.fclass, "title": _text(f.title), "medium": entry["medium"],
                             "docs": sorted({names.get(e.doc, e.doc) for e in f.evidence})} for f in flags]
        else:
            changed = {n for m in entry["manipulations"] for n in (m["doc"], *m["also"])}
            ids = {d.id for d in case.documents if d.filename in changed}
            names = {d.id: d.filename for d in case.documents}
            off_target += [{"case": name, "detector": f.detector, "fclass": f.fclass, "title": _text(f.title), "medium": entry["medium"],
                            "docs": sorted({names.get(e.doc, e.doc) for e in f.evidence})} for f in flags if not any(e.doc in ids for e in f.evidence)]
        by_file = {d.filename: d for d in case.documents}
        for td in entry["docs"]:
            doc = by_file.get(td["file"])
            classification[entry["medium"]].update(n=1, correct=bool(doc and doc.doc_type == td["type"]))
            if doc is not None and td["truth_valid"] and td["type"] in specs:
                _extraction(entry, td, doc, specs[td["type"]], extraction)
        if name in timings:
            kind = "digital" if entry["medium"] == "digital" else SCANNED
            seconds[kind][0] += timings[name]
            seconds[kind][1] += sum(len(d.pages) for d in case.documents)
    by_medium: dict = {}
    for o in outcomes:
        b = by_medium.setdefault(o["medium"], {"n": 0, "found": 0})
        b["n"] += 1
        b["found"] += o["found"]
    rows = [{"layout": k[0], "medium": k[1], "kind": k[2], "n": b["n"], "correct": b["correct"], "wrong": b["wrong"], "missing": b["missing"],
             "accuracy": b["correct"] / b["n"]} for k, b in sorted(extraction.items(), key=lambda kv: (kv[0][0], MEDIA.index(kv[0][1]) if kv[0][1] in MEDIA else 9, kv[0][2]))]
    return {
        "counts": counts,
        "methods": _method_rows(outcomes),
        "misses": [{k: o[k] for k in ("case", "method", "variant", "medium", "doc", "why")} for o in outcomes if not o["found"]],
        "by_medium": by_medium,
        "genuine": {"cases": g["cases"], "documents": g["documents"], "flags": g["flags"], "cases_with_flags": g["cases_with_flags"],
                    "limitations": g["limitations"], "per_document": g["flags"] / g["documents"] if g["documents"] else 0.0, "list": false_flags,
                    "by_detector": dict(by_detector), "by_fclass": dict(by_fclass), "limitation_titles": dict(by_limit)},
        "off_target": off_target,
        "extraction": rows,
        "classification": {m: {"n": b["n"], "correct": b["correct"]} for m, b in classification.items()},
        "seconds_per_page": {k: s / p for k, (s, p) in seconds.items() if p},
        "peak_rss_mb": peak_rss_mb,
        "errors": errors,
    }


RULES = """\
A change is **found** when the pipeline raised a finding that is an observation, an inconsistency or potential manipulation (never a processing limitation, and never a cluster, which repeats its members) and that

- for a change with a place on a page (D1, D2, D3, D5, S1, S2): cites the changed document, on the changed page, with a box that overlaps the changed box at an IoU (intersection over union) of at least 0.1. It is **located** at an IoU of at least 0.5. The IoU shown is the best of the document's findings, 0 for a miss;
- for a change without one: comes from a detector expected for that change (D4: pdf_meta or cross_producer; C1 and C2: any cross_* check; C3: cross_duplicate; C4: signature; C5: mark) and cites the changed document (for a duplicate, either copy).

A limitation is never a find. A case that produced no result is a miss. On a genuine case every such finding is a flag, counted per document; its limitations are counted apart. A flag in a changed case that cites no changed document is listed as off target; it is not counted against the pipeline, because a cross-document check may rightly cite only the other document of a pair. Extraction is scored on documents nobody changed, value by value (amounts, dates and ids exactly, text up to case and spacing), by the name of the field and, in a table, its row number. A value the pipeline did not extract counts as missing."""

LIMITS = """\
- The documents are synthetic and drawn by one generator. The dev and test splits share its six logo and stamp designs and its lists of names, addresses and employers, so the dev figures say little about styles the generator cannot draw. The test split adds a second layout (B) and two kinds of change (D3, S2) that the dev split never shows.
- Each applicant's obligations are held to 40 % of income by construction, so the rule on the ratio of obligations to income has nothing to say about a genuine case here. It is not tested on genuine documents.
- D3 writes the new text in Arial, which the generator takes from the Windows fonts folder; the files of the test split are bit-for-bit reproducible only where Arial is installed. The hashes in the manifest identify exactly what was run.
- Table cells are compared by row number: one statement row the reader drops moves every row after it, and those count as wrong or missing even when each was read correctly.
- A change to an amount that the arithmetic checks cover (a balance, a credit that must match the payslip) is caught by those checks whatever the pixels show: the "found by" column says which detector did it. The loan amount on the application is covered by none, so it is the clean test of the pixel-level detectors.
- A change found near its place may have been found for another reason than the one planted; the manifest cannot tell.
- Scans are simulated from the same PDFs (blur, noise, a small rotation, JPEG), at three levels. A real scanner or camera is not simulated."""


def _pct(a: int, b: int) -> str:
    return f"{100 * a / b:.0f} %" if b else "n/a"


def _num(v, fmt: str = "{:.2f}") -> str:
    return fmt.format(v) if v is not None else "n/a"


def format_report(res: dict) -> str:
    out: list[str] = []
    add = out.append
    run, c, g = res.get("run"), res["counts"], res["genuine"]
    add(f"# Evaluation of the {run['split']} split" if run else "# Evaluation")
    add("")
    if run:
        add(f"Cases {run['start']} to {run['start'] + run['cases'] - 1} of the {run['split']} split (seeds {run['seeds'][0]} to {run['seeds'][1]}), run on "
            f"{run['date']} with the pipeline at commit {run['commit']}{' plus uncommitted changes' if run['dirty'] else ''}. {run['machine']}. "
            "The numbers are what the run printed: nothing was selected or tuned to make them look better.")
        add("")
    add("## How a result is counted")
    add("")
    add(RULES)
    add("")
    total = sum(r["n"] for r in res["methods"].values())
    found = sum(r["found"] for r in res["methods"].values())
    placed = [r for r in res["methods"].values() if r["located"] is not None]
    add("## Summary")
    add("")
    add(f"- Cases: {c['cases']} ({c['genuine_cases']} genuine, {c['manipulated_cases']} with one change each); no result for {c['no_result']}.")
    add(f"- Changes found: {found} of {total} ({_pct(found, total)}); of those with a place on a page, {sum(r['located'] for r in placed)} of "
        f"{sum(r['n'] for r in placed)} located (IoU of 0.5 or more).")
    add(f"- Genuine documents: {g['flags']} flags on {g['documents']} documents ({g['per_document']:.3f} per document); {g['cases_with_flags']} of "
        f"{g['cases']} genuine cases carry at least one; {g['limitations']} limitations raised apart from those.")
    for m, b in sorted(res["classification"].items(), key=lambda kv: MEDIA.index(kv[0]) if kv[0] in MEDIA else 9):
        add(f"- Type recognised, {m}: {b['correct']} of {b['n']} documents ({_pct(b['correct'], b['n'])}).")
    spp = res["seconds_per_page"]
    if spp:
        add("- Seconds per page, whole pipeline: " + ", ".join(f"{k} {v:.2f}" for k, v in spp.items()) + ".")
    if res["peak_rss_mb"] is not None:
        add(f"- Peak memory of the process: {res['peak_rss_mb']:.0f} MB.")
    add("")
    add("## Detection by kind of change")
    add("")
    add("| change | what | n | found | located | mean IoU | flagged elsewhere only | found by (cases) |")
    add("|---|---|---|---|---|---|---|---|")
    for m in ORDER:
        r = res["methods"].get(m)
        if r:
            by = ", ".join(f"{d} {n}" for d, n in sorted(r["by_detector"].items(), key=lambda kv: (-kv[1], kv[0])))
            add(f"| {m} | {WHAT[m]} | {r['n']} | {r['found']} ({_pct(r['found'], r['n'])}) | {_num(r['located'], '{}')} | {_num(r['mean_iou'])} | "
                f"{r['flagged_document'] - r['found']} | {by or '-'} |")
    add("")
    add("The IoU counts a miss as 0. \"Flagged elsewhere only\" counts the changes for which the pipeline raised something on the changed document, but not near the changed place.")
    add("")
    add("### Changes that differ in kind")
    add("")
    for m in ("D4", "C1", "C2", "C4", "C5"):
        r = res["methods"].get(m)
        for v, b in sorted((r or {"by_variant": {}})["by_variant"].items()):
            add(f"- {m}, {v}: {b['found']} of {b['n']} found")
    add("")
    add("### By medium")
    add("")
    add("| medium | changes | found |")
    add("|---|---|---|")
    for m, b in sorted(res["by_medium"].items(), key=lambda kv: MEDIA.index(kv[0]) if kv[0] in MEDIA else 9):
        add(f"| {m} | {b['n']} | {b['found']} ({_pct(b['found'], b['n'])}) |")
    add("")
    add(f"## Misses ({len(res['misses'])}, all listed)")
    add("")
    for x in res["misses"]:
        add(f"- {x['case']}, {x['method']}, {x['variant']} ({x['medium']}): {x['why']}")
    if not res["misses"]:
        add("- none")
    add("")
    add(f"## Flags on genuine documents ({g['flags']}, all listed)")
    add("")
    if g["by_detector"]:
        add("By detector: " + ", ".join(f"{d} {n}" for d, n in sorted(g["by_detector"].items(), key=lambda kv: (-kv[1], kv[0]))) + ".")
        add("")
    for x in g["list"]:
        add(f"- {x['case']} ({x['medium']}), {x['detector']}, {x['fclass']}: {x['title']} [{', '.join(x['docs'])}]")
    if not g["list"]:
        add("- none")
    if g["limitation_titles"]:
        add("")
        add("Limitations raised on genuine cases: " + "; ".join(f"{t} x{n}" for t, n in sorted(g["limitation_titles"].items(), key=lambda kv: (-kv[1], kv[0]))) + ".")
    add("")
    add(f"## Flags in changed cases that cite no changed document ({len(res['off_target'])}, all listed)")
    add("")
    for x in res["off_target"]:
        add(f"- {x['case']} ({x['medium']}), {x['detector']}, {x['fclass']}: {x['title']} [{', '.join(x['docs'])}]")
    if not res["off_target"]:
        add("- none")
    add("")
    add("## Extraction on documents nobody changed")
    add("")
    add("| layout | medium | kind | values | correct | wrong | missing | accuracy |")
    add("|---|---|---|---|---|---|---|---|")
    for r in res["extraction"]:
        add(f"| {r['layout']} | {r['medium']} | {r['kind']} | {r['n']} | {r['correct']} | {r['wrong']} | {r['missing']} | {r['accuracy'] * 100:.1f} % |")
    if res["errors"]:
        add("")
        add(f"## Cases that raised an error ({len(res['errors'])})")
        add("")
        for k, v in sorted(res["errors"].items()):
            add(f"- {k}: {_text(v)}")
    add("")
    add("## Limits of this measurement")
    add("")
    add(LIMITS)
    add("")
    return "\n".join(out)
