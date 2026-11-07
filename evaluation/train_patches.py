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
import hashlib
import math
import pickle
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


def learned_flags(page: dict, s: np.ndarray, t: float) -> list[list[float]]:
    return [page["boxes"][j].tolist() for j in np.argsort(-s)[:LISTED] if s[j] >= t] if len(s) else []


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


def design(root: Path, grid=((0.1, 1.0), (1.0, 1.0), (10.0, 1.0), (1.0, 10.0), (1.0, 100.0))) -> None:
    pages = load(DESIGN, root)
    dev = [i for i, p in enumerate(pages) if p["slice"] == "dev-design"]
    base_false = len(tally([pages[i] for i in dev], [baseline_flags(pages[i]) for i in dev])["false"])
    for lam, pos_weight in grid:
        scores = out_of_fold(pages, lam, pos_weight)
        t = threshold([scores[i].max() if len(scores[i]) else -math.inf for i in dev if not pages[i]["edit"]], base_false)
        print(f"\n=== lambda {lam:g}, positive weight {pos_weight:g}, t* = {t:.3f} (baseline false pages on unedited dev-design: {base_false})")
        for name in DESIGN:
            b, n = judge(pages, scores, t, lambda p, name=name: p["slice"] == name)
            print(describe(b, n, name))
        for kind in sorted({p["kind"] for p in pages if p["slice"] == "xdev-design"}):
            b, n = judge(pages, scores, t, lambda p, kind=kind: p["slice"] == "xdev-design" and p["kind"] == kind)
            print("   " + describe(b, n, f"xdev-design {kind}"))


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m evaluation.train_patches")
    ap.add_argument("what", choices=("features", "design"))
    ap.add_argument("slice", nargs="?", choices=sorted(pdta.SLICES))
    ap.add_argument("--root", required=True, type=Path)
    a = ap.parse_args()
    if a.what == "features":
        print(features(a.slice, a.root))
    else:
        design(a.root)


if __name__ == "__main__":
    main()
