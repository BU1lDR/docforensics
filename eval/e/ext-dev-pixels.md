# Compression-history check on the ext-dev pack (pixels)

Run: 2026-11-06 00:52 India Standard Time, commit 4ff0a02, Windows 10, Python 3.11.9, 6 cores, CPU only.
36 cases (seeds 3100000 to 3100035), 31 s in all, 0.9 s a case.
Constants of forensics/ela.py: QUALITIES=25..95 step 5, GAP=10, MIN_DIP=1.3, INK=60, BLOCK=16, MIN_INK=24, Z=6.0, MAX_DIP=1.3, MIN_CELLS=4, MIN_RATIO=2.0, LISTED=6.

A case is `none` when the scan has no edit (saved once, or saved again unchanged), `seen` when its edit was made after an earlier save at least 10 quality points below the last, so that the earlier save left a mark the edited place does not share, and `blind` when the check cannot see it by construction (an edit with the page's own grid and quality, or a last save too close to the earlier one). That is fixed in datagen/ela_pack.py. Located: a region whose IoU with the edited box is above 0.3. Stray: a region that does not touch the edited box.

## In short

- Scans without an edit (12): a region on 0, which is a false flag.
- Edits the check is meant to see (16): a region at the edit on 16; a region anywhere on 16; a stray region on 0.
- Edits it cannot see (8, listed apart, not claimed): a region anyway on 3, touching the edit on 3, at the edit (IoU above 0.3) on 0.
- Missed among those it is meant to see: none.
- Pictures it declared not examined: 0.
- Saves found (cases meant to be seen): last save right on 16 of 16, earlier save right on 16 of 16.

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
| ext-dev-e-0000 | genuine | mild | none | 85 (found 85) | 85 (found -) | 0 | no | 0 | 0.53 |
| ext-dev-e-0001 | resaved | mild | none | 95 (found 95) | 85 (found 85) | 0 | no | 0 | 0.64 |
| ext-dev-e-0002 | pasted-field | mild | seen | 95 (found 95) | 85 (found 85) | 1 | yes | 0 | 0.66 |
| ext-dev-e-0003 | pasted-block | mild | seen | 95 (found 95) | 85 (found 85) | 1 | yes | 0 | 0.66 |
| ext-dev-e-0004 | retyped | mild | blind | 85 (found 85) | 85 (found -) | 0 | no | 0 | 0.51 |
| ext-dev-e-0005 | aligned | mild | blind | 85 (found 85) | 85 (found -) | 0 | no | 0 | 0.5 |
| ext-dev-e-0006 | genuine | 150dpi | none | 50 (found 50) | 50 (found -) | 0 | no | 0 | 0.57 |
| ext-dev-e-0007 | resaved | 150dpi | none | 95 (found 95) | 50 (found 50) | 0 | no | 0 | 0.65 |
| ext-dev-e-0008 | pasted-field | 150dpi | seen | 95 (found 95) | 50 (found 50) | 1 | yes | 0 | 0.67 |
| ext-dev-e-0009 | pasted-block | 150dpi | seen | 95 (found 95) | 50 (found 50) | 1 | yes | 0 | 0.68 |
| ext-dev-e-0010 | retyped | 150dpi | seen | 85 (found 85) | 50 (found 50) | 1 | yes | 0 | 0.8 |
| ext-dev-e-0011 | aligned | 150dpi | blind | 85 (found 85) | 50 (found 50) | 1 | no | 0 | 0.72 |
| ext-dev-e-0012 | genuine | 120dpi | none | 35 (found 35) | 35 (found -) | 0 | no | 0 | 0.84 |
| ext-dev-e-0013 | resaved | 120dpi | none | 95 (found 95) | 35 (found 35) | 0 | no | 0 | 1.03 |
| ext-dev-e-0014 | pasted-field | 120dpi | seen | 95 (found 95) | 35 (found 35) | 1 | yes | 0 | 1.02 |
| ext-dev-e-0015 | pasted-block | 120dpi | seen | 95 (found 95) | 35 (found 35) | 1 | yes | 0 | 1.01 |
| ext-dev-e-0016 | retyped | 120dpi | seen | 85 (found 85) | 35 (found 35) | 1 | yes | 0 | 1.21 |
| ext-dev-e-0017 | aligned | 120dpi | blind | 85 (found 85) | 35 (found 35) | 1 | no | 0 | 1.09 |
| ext-dev-e-0018 | genuine | mild | none | 85 (found 85) | 85 (found -) | 0 | no | 0 | 0.74 |
| ext-dev-e-0019 | resaved | mild | none | 95 (found 95) | 85 (found 85) | 0 | no | 0 | 0.9 |
| ext-dev-e-0020 | pasted-field | mild | seen | 95 (found 95) | 85 (found 85) | 1 | yes | 0 | 0.9 |
| ext-dev-e-0021 | pasted-block | mild | seen | 95 (found 95) | 85 (found 85) | 1 | yes | 0 | 0.92 |
| ext-dev-e-0022 | retyped | mild | blind | 85 (found 85) | 85 (found -) | 0 | no | 0 | 0.75 |
| ext-dev-e-0023 | aligned | mild | blind | 85 (found 85) | 85 (found -) | 0 | no | 0 | 0.87 |
| ext-dev-e-0024 | genuine | 150dpi | none | 50 (found 50) | 50 (found -) | 0 | no | 0 | 0.89 |
| ext-dev-e-0025 | resaved | 150dpi | none | 95 (found 95) | 50 (found 50) | 0 | no | 0 | 1.02 |
| ext-dev-e-0026 | pasted-field | 150dpi | seen | 95 (found 95) | 50 (found 50) | 1 | yes | 0 | 0.97 |
| ext-dev-e-0027 | pasted-block | 150dpi | seen | 95 (found 95) | 50 (found 50) | 1 | yes | 0 | 1.05 |
| ext-dev-e-0028 | retyped | 150dpi | seen | 85 (found 85) | 50 (found 50) | 1 | yes | 0 | 0.95 |
| ext-dev-e-0029 | aligned | 150dpi | blind | 85 (found 85) | 50 (found 50) | 0 | no | 0 | 0.94 |
| ext-dev-e-0030 | genuine | 120dpi | none | 35 (found 35) | 35 (found -) | 0 | no | 0 | 0.89 |
| ext-dev-e-0031 | resaved | 120dpi | none | 95 (found 95) | 35 (found 35) | 0 | no | 0 | 1.05 |
| ext-dev-e-0032 | pasted-field | 120dpi | seen | 95 (found 95) | 35 (found 35) | 1 | yes | 0 | 1.04 |
| ext-dev-e-0033 | pasted-block | 120dpi | seen | 95 (found 95) | 35 (found 35) | 1 | yes | 0 | 1.02 |
| ext-dev-e-0034 | retyped | 120dpi | seen | 85 (found 85) | 35 (found 35) | 1 | yes | 0 | 1.06 |
| ext-dev-e-0035 | aligned | 120dpi | blind | 85 (found 85) | 35 (found 35) | 1 | no | 0 | 1.04 |
