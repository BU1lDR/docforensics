# Compression-history check on the ext-dev pack (pixels) with hosts of the variant off-grid

Run: 2026-11-06 00:57 India Standard Time, commit 4ff0a02, Windows 10, Python 3.11.9, 6 cores, CPU only.
36 cases (seeds 3100000 to 3100035), 23 s in all, 0.6 s a case.
Constants of forensics/ela.py: QUALITIES=25..95 step 5, GAP=10, MIN_DIP=1.3, INK=60, BLOCK=16, MIN_INK=24, Z=6.0, MAX_DIP=1.3, MIN_CELLS=4, MIN_RATIO=2.0, LISTED=6.
The hosts were saved at qualities 82, 47 and 33 (the pack's 85, 50 and 35), between the steps of 5 the check tries. A robustness report: nothing was tuned on it.

A case is `none` when the scan has no edit (saved once, or saved again unchanged), `seen` when its edit was made after an earlier save at least 10 quality points below the last, so that the earlier save left a mark the edited place does not share, and `blind` when the check cannot see it by construction (an edit with the page's own grid and quality, or a last save too close to the earlier one). That is fixed in datagen/ela_pack.py. Located: a region whose IoU with the edited box is above 0.3. Stray: a region that does not touch the edited box.

## In short

- Scans without an edit (12): a region on 0, which is a false flag.
- Edits the check is meant to see (16): a region at the edit on 16; a region anywhere on 16; a stray region on 0.
- Edits it cannot see (8, listed apart, not claimed): a region anyway on 3, touching the edit on 3, at the edit (IoU above 0.3) on 0.
- Missed among those it is meant to see: none.
- Pictures it declared not examined: 0.
- Saves found (cases meant to be seen): last save right on 16 of 16, earlier save right on 0 of 16.

## By kind and level

| kind | level | expect | cases | region | touching | located | stray |
|---|---|---|---|---|---|---|---|
| genuine | mild | none | 2 | 0 | 0 | 0 | 0 |
| genuine | 150dpi | none | 2 | 0 | 0 | 0 | 0 |
| genuine | 120dpi | none | 2 | 0 | 0 | 0 | 0 |
| resaved | mild | none | 2 | 0 | 0 | 0 | 0 |
| resaved | 150dpi | none | 2 | 0 | 0 | 0 | 0 |
| resaved | 120dpi | none | 2 | 0 | 0 | 0 | 0 |
| pasted-field | mild | seen | 2 | 2 | 2 | 2 | 0 |
| pasted-field | 150dpi | seen | 2 | 2 | 2 | 2 | 0 |
| pasted-field | 120dpi | seen | 2 | 2 | 2 | 2 | 0 |
| pasted-block | mild | seen | 2 | 2 | 2 | 2 | 0 |
| pasted-block | 150dpi | seen | 2 | 2 | 2 | 2 | 0 |
| pasted-block | 120dpi | seen | 2 | 2 | 2 | 2 | 0 |
| retyped | mild | blind | 2 | 0 | 0 | 0 | 0 |
| retyped | 150dpi | seen | 2 | 2 | 2 | 2 | 0 |
| retyped | 120dpi | seen | 2 | 2 | 2 | 2 | 0 |
| aligned | mild | blind | 2 | 0 | 0 | 0 | 0 |
| aligned | 150dpi | blind | 2 | 1 | 1 | 0 | 0 |
| aligned | 120dpi | blind | 2 | 2 | 2 | 0 | 0 |

## Every case

| case | kind | level | expect | last save (pack) | earlier save (pack) | regions | located | stray | s |
|---|---|---|---|---|---|---|---|---|---|
| ext-dev-e-0000 | genuine | mild | none | 82 (found 95) | 82 (found 80) | 0 | no | 0 | 0.63 |
| ext-dev-e-0001 | resaved | mild | none | 95 (found 95) | 82 (found 80) | 0 | no | 0 | 0.59 |
| ext-dev-e-0002 | pasted-field | mild | seen | 95 (found 95) | 82 (found 80) | 1 | yes | 0 | 0.59 |
| ext-dev-e-0003 | pasted-block | mild | seen | 95 (found 95) | 82 (found 80) | 1 | yes | 0 | 0.6 |
| ext-dev-e-0004 | retyped | mild | blind | 85 (found 85) | 82 (found -) | 0 | no | 0 | 0.48 |
| ext-dev-e-0005 | aligned | mild | blind | 85 (found 85) | 82 (found -) | 0 | no | 0 | 0.48 |
| ext-dev-e-0006 | genuine | 150dpi | none | 47 (found 95) | 47 (found 75) | 0 | no | 0 | 0.65 |
| ext-dev-e-0007 | resaved | 150dpi | none | 95 (found 95) | 47 (found 75) | 0 | no | 0 | 0.64 |
| ext-dev-e-0008 | pasted-field | 150dpi | seen | 95 (found 95) | 47 (found 75) | 1 | yes | 0 | 0.65 |
| ext-dev-e-0009 | pasted-block | 150dpi | seen | 95 (found 95) | 47 (found 75) | 1 | yes | 0 | 0.65 |
| ext-dev-e-0010 | retyped | 150dpi | seen | 85 (found 85) | 47 (found 45) | 1 | yes | 0 | 0.64 |
| ext-dev-e-0011 | aligned | 150dpi | blind | 85 (found 85) | 47 (found 45) | 1 | no | 0 | 0.62 |
| ext-dev-e-0012 | genuine | 120dpi | none | 33 (found 95) | 33 (found 75) | 0 | no | 0 | 0.7 |
| ext-dev-e-0013 | resaved | 120dpi | none | 95 (found 95) | 33 (found 75) | 0 | no | 0 | 0.72 |
| ext-dev-e-0014 | pasted-field | 120dpi | seen | 95 (found 95) | 33 (found 75) | 1 | yes | 0 | 0.72 |
| ext-dev-e-0015 | pasted-block | 120dpi | seen | 95 (found 95) | 33 (found 75) | 1 | yes | 0 | 0.7 |
| ext-dev-e-0016 | retyped | 120dpi | seen | 85 (found 85) | 33 (found 75) | 1 | yes | 0 | 0.69 |
| ext-dev-e-0017 | aligned | 120dpi | blind | 85 (found 85) | 33 (found 75) | 1 | no | 0 | 0.69 |
| ext-dev-e-0018 | genuine | mild | none | 82 (found 95) | 82 (found 80) | 0 | no | 0 | 0.59 |
| ext-dev-e-0019 | resaved | mild | none | 95 (found 95) | 82 (found 80) | 0 | no | 0 | 0.59 |
| ext-dev-e-0020 | pasted-field | mild | seen | 95 (found 95) | 82 (found 80) | 1 | yes | 0 | 0.59 |
| ext-dev-e-0021 | pasted-block | mild | seen | 95 (found 95) | 82 (found 80) | 1 | yes | 0 | 0.59 |
| ext-dev-e-0022 | retyped | mild | blind | 85 (found 85) | 82 (found -) | 0 | no | 0 | 0.48 |
| ext-dev-e-0023 | aligned | mild | blind | 85 (found 85) | 82 (found -) | 0 | no | 0 | 0.49 |
| ext-dev-e-0024 | genuine | 150dpi | none | 47 (found 95) | 47 (found 75) | 0 | no | 0 | 0.69 |
| ext-dev-e-0025 | resaved | 150dpi | none | 95 (found 95) | 47 (found 75) | 0 | no | 0 | 0.64 |
| ext-dev-e-0026 | pasted-field | 150dpi | seen | 95 (found 95) | 47 (found 75) | 1 | yes | 0 | 0.63 |
| ext-dev-e-0027 | pasted-block | 150dpi | seen | 95 (found 95) | 47 (found 75) | 1 | yes | 0 | 0.63 |
| ext-dev-e-0028 | retyped | 150dpi | seen | 85 (found 85) | 47 (found 45) | 1 | yes | 0 | 0.63 |
| ext-dev-e-0029 | aligned | 150dpi | blind | 85 (found 85) | 47 (found 45) | 0 | no | 0 | 0.63 |
| ext-dev-e-0030 | genuine | 120dpi | none | 33 (found 95) | 33 (found 75) | 0 | no | 0 | 0.69 |
| ext-dev-e-0031 | resaved | 120dpi | none | 95 (found 95) | 33 (found 75) | 0 | no | 0 | 0.7 |
| ext-dev-e-0032 | pasted-field | 120dpi | seen | 95 (found 95) | 33 (found 75) | 1 | yes | 0 | 0.7 |
| ext-dev-e-0033 | pasted-block | 120dpi | seen | 95 (found 95) | 33 (found 75) | 1 | yes | 0 | 0.69 |
| ext-dev-e-0034 | retyped | 120dpi | seen | 85 (found 85) | 33 (found 75) | 1 | yes | 0 | 0.68 |
| ext-dev-e-0035 | aligned | 120dpi | blind | 85 (found 85) | 33 (found 75) | 1 | no | 0 | 0.69 |
