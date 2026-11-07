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
