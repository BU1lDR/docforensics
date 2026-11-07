"""Training and acceptance test of the learned patch detector (Task 29, branch feat/learned).

THE BAR. It was written and committed before the first training run and is not changed after it (a later commit may only fix words).

What is judged. `learned_patches`: for every word of a scanned page (JPEG-stored, quality class not poor) that has at least 100 paper
pixels and a box of at least 24 x 12 px, twelve measurements against the other words of the same page (forensics/learned_patches.py),
turned into a score by a numpy logistic regression. A page is flagged when its best word reaches a threshold t*; the words at or above
t* (at most 8, best first) are its regions. Nothing else about the model is fixed here (features, regularisation: chosen on the design
slices below); the numbers it is judged by are fixed.

Data. Synthetic, made by our own generator. Development seeds only: the dev split (1_000_000 up) and the ext-dev E pack (3_100_000 up).
The test split, ext-test and the 5_000_000 to 6_999_999 seeds of the main session's probe cases are never read. Slices (evaluation/
patches_data.py): dev-design (S1 cases 0-1079 of the dev plan, scanned genuine cases 0-215), dev-confirm (S1 3000-3539, genuine
3000-3143), xdev-design (E pack cases 0-179), xdev-confirm (E pack cases 5004-5111). A page is every OCR-read page of those cases.
Features, settings and the weights are chosen on the design slices only. The confirm slices are scored once, with everything fixed
(the script refuses a second run).

Words and pages. A training word is positive when at least half of its box lies inside the manifest's edit box, negative when it
does not touch it, and left out otherwise. A changed page is a page with a manifest edit box; an unedited page is any other page (the
pages of genuine cases, the untouched documents of changed cases, E-pack genuine and re-saved cases). A page is found when a flag's
region has IoU >= 0.1 with the edit box (evaluation/score.py NEAR); an unedited page is falsely flagged when it has any flag, and each
region of a flag on it is a false region.

Baseline. Today's grain and placement checks (forensics/scan_noise.py noise_residual and scan_layout.py layout_consistency) at the
default Thresholds, run on the same pages; a page is flagged or found by the baseline when either check flags or finds it. It is
measured again on the commit the confirm run is made on (the main session may change those files meanwhile).

Threshold. Folds are by case (a hash of the case id, 5 folds), pooled over dev-design and xdev-design. The out-of-fold page scores of
the unedited dev-design pages give t*: the smallest threshold at which the number of falsely flagged pages is no larger than the
baseline's on those pages. t* is fixed there, from development only, before any confirm slice is scored, and is used unchanged on
xdev-design and both confirm slices. The weights for the confirm run are trained on all design pages.

The bar. All of the following must hold, or the detector is dropped (the code stays on the branch, it is not registered, and the
numbers are reported). A margin of one page is noise, so "higher" means by at least max(2, 10 % of the changed pages, rounded up).
  (a) Changed dev scans (S1): recall of the learned detector is higher than the baseline's, on dev-design (out-of-fold, by case) and
      on dev-confirm.
  (b) False regions per unedited scan page and falsely flagged unedited pages are each no higher than the baseline's, on dev-design
      (out-of-fold), dev-confirm and xdev-confirm. Not "about equal": if the baseline has none, the learned detector has none.
  (c) The same two numbers on the ext-dev scans: recall higher than the baseline's on xdev-confirm, with t* from development.
Reported besides, not part of the bar: each check alone; the union with jpeg_history and what the learned detector adds to all three
existing scan checks; what a one-page allowance in (b) would have changed; every miss and every false region by case.

What a pass would not mean. Edits and detector come from the same author and the same generator: a pass says the detector finds these
synthetic edits (S1 aligned splices and the E-pack kinds), not forgeries made by anyone else. Scans stored as JPEG only. Run 2
measures new seeds and layout B of the same edit kinds, not unseen kinds. No probability is shown to a reviewer and no accuracy is claimed.

    python -m evaluation.train_patches features SLICE --root D:/tmp/patches   # measurements + baseline flags of a built slice, cached
    python -m evaluation.train_patches design --root D:/tmp/patches           # cross-validation on the design slices, t*
    python -m evaluation.train_patches confirm --root D:/tmp/patches --once   # the confirm slices, once; writes eval/patches/ and the weights
Heavy runs go under the window protocol (D:/tmp/eval-window.txt)."""
import argparse
import datetime
import hashlib
import json
import math
import os
import pickle
import platform
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from docforensics.audit import AuditLog
from docforensics.config import Thresholds
from docforensics.forensics.ela import jpeg_history
from docforensics.forensics.learned_patches import FEATURES, page_features
from docforensics.forensics.scan_layout import layout_consistency
from docforensics.forensics.scan_noise import noise_residual
from docforensics.pipeline import Ctx
from evaluation import patches_data as pdta
from evaluation.score import NEAR, iou

LISTED = 8       # regions named by one flag
FOLDS = 5
CLIP = 8.0       # standardised measurements are cut at this many standard deviations
DESIGN, CONFIRM = ("dev-design", "xdev-design"), ("dev-confirm", "xdev-confirm")
CHECKS = {"grain": noise_residual, "placement": layout_consistency, "jpeg_history": jpeg_history}
BASELINE = ("grain", "placement")


# ---- measurements of a slice, cached -------------------------------------------------------------------------------------------
def _regions(findings) -> dict[int, list[list[float]]]:
    """The regions of the flags (every finding but a processing limitation), by page."""
    out: dict[int, list[list[float]]] = {}
    for f in findings:
        if f.fclass != "processing_limitation":
            for e in f.evidence:
                if e.box is not None and e.page is not None:
                    out.setdefault(e.page, []).append([float(v) for v in e.box])
    return out


def features(name: str, root: Path, th: Thresholds | None = None) -> Path:
    """For every page of a built slice: who it is, its edit box, the measurements of its words, and the flags of the existing checks."""
    th = th or Thresholds()
    audit = AuditLog(Path(tempfile.gettempdir()) / "patches-unused-audit.jsonl")  # the checks run below never write to it
    checks: dict[tuple, dict[str, dict]] = {}
    rows = []
    for rec in pdta.pages(name, root):
        key = (rec.cd.root.as_posix(), rec.doc.id)
        if key not in checks:
            ctx = Ctx(rec.cd, audit, th)
            checks[key] = {c: _regions(fn(rec.loaded, rec.doc, ctx)) for c, fn in CHECKS.items()}
        idx, X = [], np.empty((0, len(FEATURES)))
        if rec.page.quality_class != "poor":
            with Image.open(rec.cd.root / rec.page.image_path) as im:
                gray = np.asarray(im.convert("L"), dtype=np.float32)
            idx, X = page_features(gray, rec.page)
        words = [rec.page.words[i] for i in idx]
        rows.append({"slice": name, "case": rec.case, "kind": rec.kind, "level": rec.level, "layout": rec.layout, "file": rec.file,
                     "page": rec.page.n, "quality": rec.page.quality_class, "edit": rec.edit, "n_words": len(rec.page.words),
                     "text": [w.text for w in words], "boxes": np.array([w.box for w in words]).reshape(-1, 4),
                     "share": np.array([pdta.share_inside(w.box, rec.edit) if rec.edit else 0.0 for w in words]), "X": X,
                     "flags": {c: checks[key][c].get(rec.page.n, []) for c in CHECKS}})
    path = root / "features" / f"{name}.pkl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        pickle.dump(rows, f)
    return path


def load(names, root: Path) -> list[dict]:
    rows: list[dict] = []
    for n in names:
        with (root / "features" / f"{n}.pkl").open("rb") as f:
            rows += pickle.load(f)  # our own file, written by features() above
    return rows


# ---- the model: class-weighted L2 logistic regression, numpy only ---------------------------------------------------------------
def fold_of(case: str) -> int:
    return int(hashlib.sha256(case.encode()).hexdigest(), 16) % FOLDS


def labels(page: dict) -> np.ndarray:
    """1 where at least half of the word is inside the edit box, 0 where it does not touch it, -1 (left out of training) between."""
    s = page["share"]
    return np.where(s >= 0.5, 1, np.where(s == 0, 0, -1))


def standardiser(X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    with np.errstate(all="ignore"):
        mu, sd = np.nanmean(X, 0), np.nanstd(X, 0)
    return np.where(np.isnan(mu), 0.0, mu), np.where(np.isnan(sd) | (sd < 1e-6), 1.0, sd)


def prep(X: np.ndarray, mu: np.ndarray, sd: np.ndarray) -> np.ndarray:
    return np.clip(np.nan_to_num((X - mu) / sd), -CLIP, CLIP)  # a measure that does not exist counts as the average one


def fit(X: np.ndarray, y: np.ndarray, lam: float, pos_weight: float, iters: int = 50) -> np.ndarray:
    """Newton steps (IRLS) on the weighted log loss with an L2 penalty on all but the bias. No random numbers: same data, same weights."""
    A = np.hstack([X, np.ones((len(X), 1))])
    sw = np.where(y == 1, pos_weight, 1.0)
    reg = lam * np.eye(A.shape[1])
    reg[-1, -1] = 0.0
    beta = np.zeros(A.shape[1])
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-np.clip(A @ beta, -30, 30)))
        grad = A.T @ (sw * (p - y)) + reg @ beta
        hess = (A * (sw * p * (1 - p))[:, None]).T @ A + reg + 1e-9 * np.eye(A.shape[1])
        step = np.linalg.solve(hess, grad)
        beta -= step
        if np.abs(step).max() < 1e-7:
            break
    return beta


def decision(X: np.ndarray, beta: np.ndarray) -> np.ndarray:
    return np.hstack([X, np.ones((len(X), 1))]) @ beta


def training_words(pages: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    parts = [(p["X"][labels(p) >= 0], labels(p)[labels(p) >= 0]) for p in pages if len(p["X"])]
    return np.vstack([x for x, _ in parts]), np.concatenate([y for _, y in parts])


def train(pages: list[dict], lam: float, pos_weight: float) -> dict:
    X, y = training_words(pages)
    mu, sd = standardiser(X)
    return {"mu": mu, "sd": sd, "beta": fit(prep(X, mu, sd), y, lam, pos_weight), "words": len(y), "positives": int((y == 1).sum())}


def scores_of(model: dict, page: dict) -> np.ndarray:
    return decision(prep(page["X"], model["mu"], model["sd"]), model["beta"]) if len(page["X"]) else np.zeros(0)


def out_of_fold(pages: list[dict], lam: float, pos_weight: float) -> list[np.ndarray]:
    """The scores of every candidate word of every page, each from a model trained on the pages of the other folds (folds by case)."""
    fold = np.array([fold_of(p["case"]) for p in pages])
    out = [np.zeros(len(p["X"])) for p in pages]
    for k in range(FOLDS):
        model = train([p for p, f in zip(pages, fold) if f != k], lam, pos_weight)
        for i in np.flatnonzero(fold == k):
            out[i] = scores_of(model, pages[i])
    return out


# ---- judging --------------------------------------------------------------------------------------------------------------------
def threshold(page_best: list[float], allowed: int) -> float:
    """The smallest t at which at most `allowed` of these (unedited) pages have a best word score at or above t."""
    s = sorted(page_best, reverse=True)
    return float("-inf") if len(s) <= allowed else float(np.nextafter(s[allowed], np.inf))


def listed(s: np.ndarray, t: float) -> list[int]:
    """The words of a page that a flag at threshold t names: those scoring at least t, best first, at most LISTED."""
    return [int(j) for j in np.argsort(-s)[:LISTED] if s[j] >= t] if len(s) else []


def learned_flags(page: dict, s: np.ndarray, t: float) -> list[list[float]]:
    return [page["boxes"][j].tolist() for j in listed(s, t)]


def baseline_flags(page: dict, checks=BASELINE) -> list[list[float]]:
    return [b for c in checks for b in page["flags"][c]]


def tally(pages: list[dict], flags: list[list[list[float]]]) -> dict:
    changed = [i for i, p in enumerate(pages) if p["edit"]]
    unedited = [i for i, p in enumerate(pages) if not p["edit"]]
    return {"changed": len(changed), "found": [i for i in changed if any(iou(b, pages[i]["edit"]) >= NEAR for b in flags[i])],
            "unedited": len(unedited), "false": [i for i in unedited if flags[i]], "false_regions": sum(len(flags[i]) for i in unedited)}


def margin(changed: int) -> int:
    return max(2, math.ceil(0.10 * changed))


def describe(base: dict, new: dict, label: str) -> str:
    return (f"{label:<26} changed {base['changed']:>3}  found: baseline {len(base['found']):>3}, learned {len(new['found']):>3} "
            f"(margin {margin(base['changed'])})  | unedited {base['unedited']:>3}  false pages: baseline {len(base['false'])}, learned "
            f"{len(new['false'])}; false regions: baseline {base['false_regions']}, learned {new['false_regions']}")


def judge(pages: list[dict], scores: list[np.ndarray], t: float, only=lambda p: True) -> tuple[dict, dict]:
    keep = [i for i, p in enumerate(pages) if only(p)]
    sub = [pages[i] for i in keep]
    return (tally(sub, [baseline_flags(p) for p in sub]), tally(sub, [learned_flags(pages[i], scores[i], t) for i in keep]))


def design(root: Path, names=DESIGN, grid=((0.1, 1.0), (1.0, 1.0), (10.0, 1.0), (1.0, 10.0), (1.0, 100.0))) -> None:
    if set(names) & set(CONFIRM):
        raise SystemExit("the confirm slices are scored once, by `confirm`, not looked at while designing")
    pages = load(names, root)
    dev = [i for i, p in enumerate(pages) if p["slice"] == "dev-design"] or list(range(len(pages)))  # (no dev-design yet: exploring)
    base_false = len(tally([pages[i] for i in dev], [baseline_flags(pages[i]) for i in dev])["false"])
    for lam, pos_weight in grid:
        scores = out_of_fold(pages, lam, pos_weight)
        t = threshold([scores[i].max() if len(scores[i]) else -math.inf for i in dev if not pages[i]["edit"]], base_false)
        print(f"\n=== lambda {lam:g}, positive weight {pos_weight:g}, t* = {t:.3f} (baseline false pages on unedited dev-design: {base_false})")
        for name in names:
            b, n = judge(pages, scores, t, lambda p, name=name: p["slice"] == name)
            print(describe(b, n, name))
        for kind in sorted({p["kind"] for p in pages if p["slice"] == "xdev-design"}):
            b, n = judge(pages, scores, t, lambda p, kind=kind: p["slice"] == "xdev-design" and p["kind"] == kind)
            print("   " + describe(b, n, f"xdev-design {kind}"))


# ---- the one scoring of the confirm slices ---------------------------------------------------------------------------------------
REPO = Path(__file__).resolve().parents[1]
WEIGHTS = REPO / "src" / "docforensics" / "forensics" / "learned_patches.json"
EXISTING = ("grain", "placement", "jpeg_history")  # the scan checks that exist today
ORDER = ("dev-design", "xdev-design", "dev-confirm", "xdev-confirm")
COMBOS = {"grain": ("grain",), "placement": ("placement",), "jpeg_history": ("jpeg_history",), "baseline (grain, placement)": BASELINE,
          "learned": ("learned",), "the three existing": EXISTING, "the three existing and learned": EXISTING + ("learned",)}
BASE, NEW = "baseline (grain, placement)", "learned"


def flags_of(page: dict, s: np.ndarray, t: float, who: tuple[str, ...]) -> list[list[float]]:
    return [b for w in who for b in (learned_flags(page, s, t) if w == "learned" else page["flags"][w])]


def verdict(rows: dict) -> dict:
    """The parts of the bar from {slice: (baseline tally, learned tally)}; the last entry is for information, not part of the bar."""
    def higher(s):
        b, n = rows[s]
        return len(n["found"]) - len(b["found"]) >= margin(b["changed"])

    def no_more(s, allow=0):
        b, n = rows[s]
        return len(n["false"]) <= len(b["false"]) + allow and n["false_regions"] <= b["false_regions"] + allow * LISTED

    b_slices = ("dev-design", "dev-confirm", "xdev-confirm")
    return {"a": all(higher(s) for s in ("dev-design", "dev-confirm")), "b": all(no_more(s) for s in b_slices), "c": higher("xdev-confirm"),
            "b_with_one_page_allowed": all(no_more(s, 1) for s in b_slices)}


def confirm(root: Path, lam: float, pos_weight: float, out: Path = REPO / "eval" / "patches", weights: Path = WEIGHTS) -> dict:
    """Score the confirm slices, once: t* and the weights come from the design slices alone, with lam and pos_weight as fixed beforehand."""
    guard = root / "confirm.pkl"
    if guard.exists():
        raise SystemExit(f"{guard} exists: the confirm slices were scored already (`report` writes the same results up again)")
    design_pages, confirm_pages = load(DESIGN, root), load(CONFIRM, root)
    dev = [i for i, p in enumerate(design_pages) if p["slice"] == "dev-design"]
    allowed = len(tally([design_pages[i] for i in dev], [baseline_flags(design_pages[i]) for i in dev])["false"])
    oof = out_of_fold(design_pages, lam, pos_weight)
    t = threshold([oof[i].max() if len(oof[i]) else -math.inf for i in dev if not design_pages[i]["edit"]], allowed)
    model = train(design_pages, lam, pos_weight)
    git = lambda *a: subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True).stdout.strip()
    result = {"lam": lam, "pos_weight": pos_weight, "t": t, "model": model, "pages": design_pages + confirm_pages,
              "scores": oof + [scores_of(model, p) for p in confirm_pages], "commit": git("rev-parse", "--short", "HEAD"),
              "dirty": bool(git("status", "--porcelain", "--untracked-files=no")), "when": datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z"),
              "machine": f"{platform.system()} {platform.release()}, Python {platform.python_version()}, {os.cpu_count()} cores, CPU only"}
    with guard.open("xb") as f:  # exclusive: a second run cannot get past here, whatever happens to the report below
        pickle.dump(result, f)
    return report(root, out, weights)


def export(r: dict, path: Path) -> None:
    """The weights, with what they were trained on. Only a detector that passed the bar gets this file."""
    m, trained = r["model"], [p for p in r["pages"] if p["slice"] in DESIGN]
    assert math.isfinite(r["t"])
    manifest = sorted((p["slice"], p["case"], p["file"], p["page"], p["edit"]) for p in trained)
    path.write_text(json.dumps({
        "features": list(FEATURES), "mean": m["mu"].tolist(), "scale": m["sd"].tolist(), "clip": CLIP, "beta": m["beta"].tolist(),
        "threshold": r["t"], "listed": LISTED, "ridge": r["lam"], "positive_weight": r["pos_weight"],
        "random_numbers": "none: Newton steps from zero weights, so the same data gives the same weights",
        "training": {"slices": list(DESIGN), "cases": len({p["case"] for p in trained}), "pages": len(trained), "words": m["words"],
                     "positive_words": m["positives"], "manifest_sha256": hashlib.sha256(json.dumps(manifest).encode()).hexdigest(),
                     "manifest_is": "sha256 of the sorted (slice, case, file, page, edit box) of every page trained on"}},
        indent=1) + "\n", encoding="utf-8")


def report(root: Path, out: Path = REPO / "eval" / "patches", weights: Path = WEIGHTS) -> dict:
    """Write the results of the one confirm run (read back from root/confirm.pkl) to out/acceptance.md and .json; the weights on a pass."""
    with (root / "confirm.pkl").open("rb") as f:
        r = pickle.load(f)
    pages, scores, t = r["pages"], r["scores"], r["t"]
    ids = {n: [i for i, p in enumerate(pages) if p["slice"] == n] for n in ORDER}
    tallies, found, false = {}, {}, {}  # by combination and slice; the sets hold indices into `pages`
    for name, who in COMBOS.items():
        found[name], false[name] = set(), set()
        for n in ORDER:
            tl = tally([pages[i] for i in ids[n]], [flags_of(pages[i], scores[i], t, who) for i in ids[n]])
            tallies[name, n] = tl
            found[name] |= {ids[n][k] for k in tl["found"]}
            false[name] |= {ids[n][k] for k in tl["false"]}
    ok = verdict({n: (tallies[BASE, n], tallies[NEW, n]) for n in ORDER})
    go = ok["a"] and ok["b"] and ok["c"]

    def cells(tl):
        return f"{len(tl['found'])} of {tl['changed']} | {len(tl['false'])} of {tl['unedited']} | {tl['false_regions']}"

    md = [f"# Learned patch detector: the confirm run (Task 29)\n",
          f"Run: {r['when']}, commit {r['commit']}{' (tree with uncommitted changes)' if r['dirty'] else ''}, {r['machine']}.",
          f"Fixed before the run, from the design slices: ridge {r['lam']:g}, positive weight {r['pos_weight']:g}, threshold t* = {t:.4f} "
          f"(the smallest at which the out-of-fold unedited dev-design pages are flagged no more often than the baseline flags them). "
          f"Weights trained on {len([i for n in DESIGN for i in ids[n]])} design pages ({r['model']['words']} words, {r['model']['positives']} positive).",
          "The bar is in the docstring of evaluation/train_patches.py (commit 76c1f42). \"Higher\" means by at least max(2, 10 % of the changed pages).\n",
          "## Verdict\n",
          f"- (a) recall higher on dev-design (out of fold) and dev-confirm: **{'met' if ok['a'] else 'not met'}**",
          f"- (b) false regions and falsely flagged unedited pages no higher, on dev-design, dev-confirm, xdev-confirm: **{'met' if ok['b'] else 'not met'}**",
          f"- (c) recall higher on xdev-confirm: **{'met' if ok['c'] else 'not met'}**",
          f"- {'All three met: the detector goes in.' if go else 'The bar is not met: the detector is dropped (code on the branch, not registered).'}",
          f"- For information, not part of the bar: (b) with one more falsely flagged page allowed would be "
          f"{'met' if ok['b_with_one_page_allowed'] else 'not met'}.\n",
          "## Every combination on every slice\n", "A page is found when a region of a flag has IoU >= 0.1 with the edit box.\n",
          "| slice | checks | changed pages found | unedited pages falsely flagged | false regions |", "|---|---|---|---|---|"]
    for n in ORDER:
        md += [f"| {n} | {name} | {cells(tallies[name, n])} |" for name in COMBOS]
    md += ["\n## What the learned detector adds to the three existing checks\n", "| slice | changed pages only the learned detector finds | "
           "changed pages the three existing find that it does not | unedited pages only it flags |", "|---|---|---|---|"]
    for n in ORDER:
        s, e, l = set(ids[n]), "the three existing", NEW
        md.append(f"| {n} | {len((found[l] - found[e]) & s)} | {len((found[e] - found[l]) & s)} | {len((false[l] - false[e]) & s)} |")
    md += ["\n## By kind\n", "| slice | kind | changed: baseline | changed: learned | unedited falsely flagged: baseline | learned |", "|---|---|---|---|---|---|"]
    for n in ORDER:
        for kind in sorted({pages[i]["kind"] for i in ids[n]}):
            g = [i for i in ids[n] if pages[i]["kind"] == kind]
            ch, un = [i for i in g if pages[i]["edit"]], [i for i in g if not pages[i]["edit"]]
            md.append(f"| {n} | {kind} | {len(set(ch) & found[BASE])} of {len(ch)} | {len(set(ch) & found[NEW])} of {len(ch)} | "
                      f"{len(set(un) & false[BASE])} of {len(un)} | {len(set(un) & false[NEW])} of {len(un)} |")
    md += ["\n## Every changed page\n", "| slice | case | kind | level | baseline | jpeg_history | learned |", "|---|---|---|---|---|---|---|"]
    for n in ORDER:
        for i in ids[n]:
            if pages[i]["edit"]:
                p, yes = pages[i], lambda name, i=i: "found" if i in found[name] else "missed"
                md.append(f"| {n} | {p['case']} | {p['kind']} | {p['level']} | {yes(BASE)} | {yes('jpeg_history')} | {yes(NEW)} |")
    md += ["\n## Every false region on an unedited page\n", "| slice | case | file | page | by | regions |", "|---|---|---|---|---|---|"]
    for n in ORDER:
        for i in ids[n]:
            p = pages[i]
            if p["edit"]:
                continue
            for name, who in ((BASE, BASELINE), (NEW, ("learned",))):
                boxes = flags_of(p, scores[i], t, who)
                if boxes:
                    words = ", ".join(f"{p['text'][j]!r}" for j in listed(scores[i], t)) if name == NEW else ""
                    md.append(f"| {n} | {p['case']} | {p['file']} | {p['page']} | {name} | {len(boxes)} {words} |")
    out.mkdir(parents=True, exist_ok=True)
    (out / "acceptance.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    summary = {"run": {k: r[k] for k in ("when", "commit", "dirty", "machine", "lam", "pos_weight", "t")}, "verdict": ok, "go": go,
               "counts": {f"{name} | {n}": {k: (len(v) if isinstance(v, list) else v) for k, v in tallies[name, n].items()}
                          for name in COMBOS for n in ORDER}}
    (out / "acceptance.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    if go:
        export(r, weights)
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m evaluation.train_patches")
    ap.add_argument("what", choices=("features", "design", "confirm", "report"))
    ap.add_argument("slice", nargs="?", choices=sorted(pdta.SLICES))
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--slices", nargs="+", default=list(DESIGN), choices=sorted(pdta.SLICES))
    ap.add_argument("--once", action="store_true", help="confirm: yes, this is the one scoring of the confirm slices")
    ap.add_argument("--lam", type=float)
    ap.add_argument("--pos-weight", type=float)
    a = ap.parse_args()
    if a.what == "features":
        print(features(a.slice, a.root))
    elif a.what == "design":
        design(a.root, tuple(a.slices))
    elif a.what == "report":
        print(json.dumps(report(a.root)["verdict"]))
    else:
        if not (a.once and a.lam is not None and a.pos_weight is not None):
            raise SystemExit("confirm needs --once --lam L --pos-weight W (the values fixed on the design slices)")
        print(json.dumps(confirm(a.root, a.lam, a.pos_weight)["verdict"]))


if __name__ == "__main__":
    main()
