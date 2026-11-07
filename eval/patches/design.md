# Learned patch detector: the design slices (Task 29)

Run: 2026-11-07 13:20 India Standard Time, commit 91aedb8, Windows 10, Python 3.11.9, 6 cores, CPU only.
Design slices only: dev-design (115 cases of the dev split, 345 scan pages: 72 cases with a part of another scan pasted in, S1, one changed page each, and 43 genuine scanned cases; 273 unedited pages) and xdev-design (the E pack, ext-dev cases 0 to 179: 180 pages, 120 changed, 60 unedited). No confirm slice (dev-confirm, xdev-confirm) was read or scored when this was written, and none was built when the settings were fixed (amendment 1, commit 2fb6484); the build of xdev-confirm was started at 13:17 IST, after that commit and before this record, and looked at no result. The test split, ext-test and the 5_000_000 to 6_999_999 seeds are never read. The weights are fitted on four folds and scored on the fifth, folds by case, pooled over both slices. "Baseline" is the grain check plus the placement check at the default thresholds. A page is found when a flag's region has IoU >= 0.1 with the edit box. The bar is in the docstring of evaluation/train_patches.py (commit 76c1f42, with amendment 1, committed before any confirm slice was built).

## In short

At the setting fixed for the confirm run (ridge 10, positive weight 1, lift 0.5, t* = 3.355):

- dev-design, S1 pasted-in parts: the learned detector finds 27 of 72 changed pages, the baseline 5. Unedited pages falsely flagged: 0 of 273 for both.
- xdev-design, E pack: 89 of 120 against 28. Unedited pages falsely flagged: 0 of 60 for both.
- By kind (xdev-design): aligned 18 of 30 (baseline 0), pasted-block 27 (0), pasted-field 22 (1), retyped 22 (27). The learned detector finds fewer retyped words than the baseline does.
- What does it: the two same-line alignment measures alone find 13 of 72 on dev-design and 11 of 120 on xdev-design; the other twelve measures alone find 0 of 72 and 28 of 120. Together 27 and 89. On the S1 splices the gain over the baseline rests on the alignment measures, which a person could have written by hand; what is learned is how they weigh against the pixel measures.
- The lift: a threshold set on four folds and tried on the unedited pages of the fifth flags 1 of 273 pages at lift 0 and none at 0.25, 0.5 and 1. The cost of lift 0.5 against 0 is 6 of 72 and 9 of 120 changed pages.
- These are out-of-fold numbers on the data the settings were chosen on; they are not the result of the bar. The bar is judged once, on the confirm slices.

## How the three values were chosen

- Ridge 10, positive weight 1: of the grid below. The highest out-of-fold score of the unedited dev-design pages falls as the ridge grows (1.31, 1.26, 0.86, 0.36, -0.19, -0.52 at 0.1, 1, 10, 30, 100, 300); the recall on xdev-design at lift 0.5 falls too (91, 90, 89, 87, 80, 69). 10 is where the tail is clearly thinner than at 0.1 or 1 and recall is still within two pages of them. A positive weight of 10 or 100 raises the unedited scores and gains nothing.
- Lift 0.5: see amendment 1 in the docstring. 0.25 would have held out clean on these 273 pages; 0.5 is twice that, because 0 of 273 does not exclude a rate of about 1 % per page, and the confirm slices hold about 195 unedited pages.

## Commands

    python -m evaluation.train_patches design --root D:/tmp/patches                      # the grid, lifts 0, 0.25, 0.5, 1
    design(root, grid=((30, 1), (100, 1), (300, 1)))                                       # more ridge values (called from Python)
    design(root, grid=((10, 1),), only=["line_pair", "line_mates"])                         # alignment measures only
    design(root, grid=((10, 1),), only=<the other twelve>)                                  # pixel and placement measures only

## The grid (ridge, positive weight)

```
=== lambda 0.1, positive weight 1
unedited dev-design pages, best word score out of fold: median -4.08, p90 -2.05, max 1.31; falsely flagged by a threshold set on the other folds, by lift: 0: 3 of 273, 0.25: 1 of 273, 0.5: 0 of 273, 1: 0 of 273
--- lift 0: t* = 1.314 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  33 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  99 (margin 12)  | unedited  60  false pages: baseline 0, learned 1; false regions: baseline 0, learned 1
   xdev-design aligned        changed  30  found: baseline   0, learned  20 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 1; false regions: baseline 0, learned 1
   xdev-design pasted-block   changed  30  found: baseline   0, learned  30 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  26 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  23 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 0.25: t* = 2.662 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  30 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  95 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  19 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  29 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  24 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  23 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 0.5: t* = 4.010 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  27 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  91 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  19 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  28 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  22 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  22 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 1: t* = 6.706 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  14 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  67 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  16 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  21 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  16 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  14 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0

=== lambda 1, positive weight 1
unedited dev-design pages, best word score out of fold: median -4.07, p90 -2.07, max 1.26; falsely flagged by a threshold set on the other folds, by lift: 0: 3 of 273, 0.25: 1 of 273, 0.5: 0 of 273, 1: 0 of 273
--- lift 0: t* = 1.258 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  33 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  98 (margin 12)  | unedited  60  false pages: baseline 0, learned 1; false regions: baseline 0, learned 1
   xdev-design aligned        changed  30  found: baseline   0, learned  19 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 1; false regions: baseline 0, learned 1
   xdev-design pasted-block   changed  30  found: baseline   0, learned  30 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  26 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  23 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 0.25: t* = 2.591 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  30 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  95 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  19 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  29 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  24 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  23 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 0.5: t* = 3.924 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  27 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  90 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  19 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  27 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  22 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  22 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 1: t* = 6.589 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  14 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  68 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  16 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  21 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  16 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  15 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0

=== lambda 10, positive weight 1
unedited dev-design pages, best word score out of fold: median -4.13, p90 -2.24, max 0.86; falsely flagged by a threshold set on the other folds, by lift: 0: 1 of 273, 0.25: 0 of 273, 0.5: 0 of 273, 1: 0 of 273
--- lift 0: t* = 0.860 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  33 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  98 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  19 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  30 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  26 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  23 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 0.25: t* = 2.108 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  30 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  94 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  19 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  29 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  23 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  23 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 0.5: t* = 3.355 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  27 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  89 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  18 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  27 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  22 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  22 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 1: t* = 5.851 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  14 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  70 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  17 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  21 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  16 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  16 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0

=== lambda 1, positive weight 10
unedited dev-design pages, best word score out of fold: median -1.80, p90 0.21, max 3.71; falsely flagged by a threshold set on the other folds, by lift: 0: 1 of 273, 0.25: 0 of 273, 0.5: 0 of 273, 1: 0 of 273
--- lift 0: t* = 3.710 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  33 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  97 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  20 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  29 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  25 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  23 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 0.25: t* = 5.086 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  30 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  92 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  19 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  28 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  23 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  22 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 0.5: t* = 6.463 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  28 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  82 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  18 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  26 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  18 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  20 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 1: t* = 9.217 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  19 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  64 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  17 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  21 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  15 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  11 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0

=== lambda 1, positive weight 100
unedited dev-design pages, best word score out of fold: median 0.65, p90 2.74, max 6.20; falsely flagged by a threshold set on the other folds, by lift: 0: 1 of 273, 0.25: 0 of 273, 0.5: 0 of 273, 1: 0 of 273
--- lift 0: t* = 6.203 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  33 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  95 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  20 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  28 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  24 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  23 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 0.25: t* = 7.591 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  30 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  87 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  19 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  27 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  21 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  20 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 0.5: t* = 8.979 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  29 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  74 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  18 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  24 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  17 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  15 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 1: t* = 11.756 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  20 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  64 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  18 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  22 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  16 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned   8 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
```

## More ridge values

```
=== lambda 30, positive weight 1
unedited dev-design pages, best word score out of fold: median -4.10, p90 -2.44, max 0.36; falsely flagged by a threshold set on the other folds, by lift: 0: 1 of 273, 0.25: 0 of 273, 0.5: 0 of 273, 1: 0 of 273
--- lift 0: t* = 0.361 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  33 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  98 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  19 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  30 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  26 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  23 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 0.25: t* = 1.476 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  30 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  94 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  19 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  29 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  23 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  23 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 0.5: t* = 2.591 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  27 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  87 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  18 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  27 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  22 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  20 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 1: t* = 4.820 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  14 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  69 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  17 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  21 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  16 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  15 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0

=== lambda 100, positive weight 1
unedited dev-design pages, best word score out of fold: median -4.17, p90 -2.90, max -0.19; falsely flagged by a threshold set on the other folds, by lift: 0: 1 of 273, 0.25: 0 of 273, 0.5: 0 of 273, 1: 0 of 273
--- lift 0: t* = -0.187 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  33 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  95 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  19 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  29 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  24 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  23 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 0.25: t* = 0.809 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  30 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  87 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  18 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  27 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  22 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  20 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 0.5: t* = 1.804 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  27 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  80 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  18 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  26 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  19 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  17 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 1: t* = 3.794 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  12 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  58 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  15 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  21 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  14 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned   8 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0

=== lambda 300, positive weight 1
unedited dev-design pages, best word score out of fold: median -4.23, p90 -3.28, max -0.52; falsely flagged by a threshold set on the other folds, by lift: 0: 1 of 273, 0.25: 0 of 273, 0.5: 0 of 273, 1: 0 of 273
--- lift 0: t* = -0.523 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  31 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  85 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  18 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  27 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  21 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  19 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 0.25: t* = 0.404 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  27 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  78 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  18 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  26 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  19 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  15 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 0.5: t* = 1.331 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  27 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  69 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  18 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  22 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  17 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  12 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 1: t* = 3.185 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned   0 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  35 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned   5 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  18 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  11 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned   1 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
```

## All fourteen measures, ridge 10, positive weight 1

```
=== lambda 10, positive weight 1
unedited dev-design pages, best word score out of fold: median -4.13, p90 -2.24, max 0.86; falsely flagged by a threshold set on the other folds, by lift: 0: 1 of 273, 0.25: 0 of 273, 0.5: 0 of 273, 1: 0 of 273
--- lift 0: t* = 0.860 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  33 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  98 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  19 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  30 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  26 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  23 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 0.25: t* = 2.108 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  30 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  94 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  19 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  29 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  23 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  23 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 0.5: t* = 3.355 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  27 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  89 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  18 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  27 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  22 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  22 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 1: t* = 5.851 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  14 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  70 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  17 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  21 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  16 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  16 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
```

## The two alignment measures only

```
=== lambda 10, positive weight 1, measures: line_pair line_mates
unedited dev-design pages, best word score out of fold: median -3.89, p90 -2.09, max 2.41; falsely flagged by a threshold set on the other folds, by lift: 0: 1 of 273, 0.25: 0 of 273, 0.5: 0 of 273, 1: 0 of 273
--- lift 0: t* = 2.406 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  28 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  49 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  18 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  20 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  11 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned   0 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 0.25: t* = 3.981 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  24 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  45 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned  17 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  18 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  10 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned   0 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 0.5: t* = 5.555 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned  13 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  11 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned   5 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned   4 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned   2 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned   0 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 1: t* = 8.704 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned   0 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned   0 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned   0 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned   0 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned   0 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned   0 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
```

## The other twelve measures only

```
=== lambda 10, positive weight 1, measures: grain ring_grain ring_step edge stroke ink grid_on grid_other drift z_centre z_height z_right
unedited dev-design pages, best word score out of fold: median -3.03, p90 -1.42, max 1.98; falsely flagged by a threshold set on the other folds, by lift: 0: 1 of 273, 0.25: 0 of 273, 0.5: 0 of 273, 1: 0 of 273
--- lift 0: t* = 1.976 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned   1 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  60 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned   1 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  25 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned  10 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  24 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 0.25: t* = 3.227 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned   0 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  43 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned   0 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned  18 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned   7 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  18 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 0.5: t* = 4.478 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned   0 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  28 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned   0 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned   9 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned   4 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  15 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
--- lift 1: t* = 6.979 (baseline false pages on unedited dev-design: 0)
dev-design                 changed  72  found: baseline   5, learned   0 (margin 8)  | unedited 273  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
xdev-design                changed 120  found: baseline  28, learned  12 (margin 12)  | unedited  60  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design aligned        changed  30  found: baseline   0, learned   0 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design genuine        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-block   changed  30  found: baseline   0, learned   0 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design pasted-field   changed  30  found: baseline   1, learned   2 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design resaved        changed   0  found: baseline   0, learned   0 (margin 2)  | unedited  30  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
   xdev-design retyped        changed  30  found: baseline  27, learned  10 (margin 3)  | unedited   0  false pages: baseline 0, learned 0; false regions: baseline 0, learned 0
```
