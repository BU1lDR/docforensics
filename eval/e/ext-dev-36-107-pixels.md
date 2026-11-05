# Compression-history check on the ext-dev pack (pixels)

Run: 2026-11-06 00:56 India Standard Time, commit 4ff0a02, Windows 10, Python 3.11.9, 6 cores, CPU only.
72 cases (seeds 3100036 to 3100107), 46 s in all, 0.6 s a case.
Constants of forensics/ela.py: QUALITIES=25..95 step 5, GAP=10, MIN_DIP=1.3, INK=60, BLOCK=16, MIN_INK=24, Z=6.0, MAX_DIP=1.3, MIN_CELLS=4, MIN_RATIO=2.0, LISTED=6.

A case is `none` when the scan has no edit (saved once, or saved again unchanged), `seen` when its edit was made after an earlier save at least 10 quality points below the last, so that the earlier save left a mark the edited place does not share, and `blind` when the check cannot see it by construction (an edit with the page's own grid and quality, or a last save too close to the earlier one). That is fixed in datagen/ela_pack.py. Located: a region whose IoU with the edited box is above 0.3. Stray: a region that does not touch the edited box.

## In short

- Scans without an edit (24): a region on 0, which is a false flag.
- Edits the check is meant to see (32): a region at the edit on 32; a region anywhere on 32; a stray region on 0.
- Edits it cannot see (16, listed apart, not claimed): a region anyway on 2, touching the edit on 2, at the edit (IoU above 0.3) on 0.
- Missed among those it is meant to see: none.
- Pictures it declared not examined: 0.
- Saves found (cases meant to be seen): last save right on 32 of 32, earlier save right on 32 of 32.

## By kind and level

| kind | level | expect | cases | region | touching | located | stray |
|---|---|---|---|---|---|---|---|
| genuine | mild | none | 4 | 0 | 0 | 0 | 0 |
| genuine | 150dpi | none | 4 | 0 | 0 | 0 | 0 |
| genuine | 120dpi | none | 4 | 0 | 0 | 0 | 0 |
| resaved | mild | none | 4 | 0 | 0 | 0 | 0 |
| resaved | 150dpi | none | 4 | 0 | 0 | 0 | 0 |
| resaved | 120dpi | none | 4 | 0 | 0 | 0 | 0 |
| pasted-field | mild | seen | 4 | 4 | 4 | 4 | 0 |
| pasted-field | 150dpi | seen | 4 | 4 | 4 | 4 | 0 |
| pasted-field | 120dpi | seen | 4 | 4 | 4 | 4 | 0 |
| pasted-block | mild | seen | 4 | 4 | 4 | 4 | 0 |
| pasted-block | 150dpi | seen | 4 | 4 | 4 | 4 | 0 |
| pasted-block | 120dpi | seen | 4 | 4 | 4 | 4 | 0 |
| retyped | mild | blind | 4 | 0 | 0 | 0 | 0 |
| retyped | 150dpi | seen | 4 | 4 | 4 | 4 | 0 |
| retyped | 120dpi | seen | 4 | 4 | 4 | 4 | 0 |
| aligned | mild | blind | 4 | 0 | 0 | 0 | 0 |
| aligned | 150dpi | blind | 4 | 0 | 0 | 0 | 0 |
| aligned | 120dpi | blind | 4 | 2 | 2 | 0 | 0 |

## Every case

| case | kind | level | expect | last save (pack) | earlier save (pack) | regions | located | stray | s |
|---|---|---|---|---|---|---|---|---|---|
| ext-dev-e-0036 | genuine | mild | none | 85 (found 85) | 85 (found -) | 0 | no | 0 | 0.52 |
| ext-dev-e-0037 | resaved | mild | none | 95 (found 95) | 85 (found 85) | 0 | no | 0 | 0.66 |
| ext-dev-e-0038 | pasted-field | mild | seen | 95 (found 95) | 85 (found 85) | 1 | yes | 0 | 0.66 |
| ext-dev-e-0039 | pasted-block | mild | seen | 95 (found 95) | 85 (found 85) | 1 | yes | 0 | 0.65 |
| ext-dev-e-0040 | retyped | mild | blind | 85 (found 85) | 85 (found -) | 0 | no | 0 | 0.54 |
| ext-dev-e-0041 | aligned | mild | blind | 85 (found 85) | 85 (found -) | 0 | no | 0 | 0.53 |
| ext-dev-e-0042 | genuine | 150dpi | none | 50 (found 50) | 50 (found -) | 0 | no | 0 | 0.57 |
| ext-dev-e-0043 | resaved | 150dpi | none | 95 (found 95) | 50 (found 50) | 0 | no | 0 | 0.68 |
| ext-dev-e-0044 | pasted-field | 150dpi | seen | 95 (found 95) | 50 (found 50) | 1 | yes | 0 | 0.69 |
| ext-dev-e-0045 | pasted-block | 150dpi | seen | 95 (found 95) | 50 (found 50) | 1 | yes | 0 | 0.68 |
| ext-dev-e-0046 | retyped | 150dpi | seen | 85 (found 85) | 50 (found 50) | 1 | yes | 0 | 0.69 |
| ext-dev-e-0047 | aligned | 150dpi | blind | 85 (found 85) | 50 (found 50) | 0 | no | 0 | 0.67 |
| ext-dev-e-0048 | genuine | 120dpi | none | 35 (found 35) | 35 (found -) | 0 | no | 0 | 0.6 |
| ext-dev-e-0049 | resaved | 120dpi | none | 95 (found 95) | 35 (found 35) | 0 | no | 0 | 0.72 |
| ext-dev-e-0050 | pasted-field | 120dpi | seen | 95 (found 95) | 35 (found 35) | 1 | yes | 0 | 0.74 |
| ext-dev-e-0051 | pasted-block | 120dpi | seen | 95 (found 95) | 35 (found 35) | 1 | yes | 0 | 0.76 |
| ext-dev-e-0052 | retyped | 120dpi | seen | 85 (found 85) | 35 (found 35) | 1 | yes | 0 | 0.74 |
| ext-dev-e-0053 | aligned | 120dpi | blind | 85 (found 85) | 35 (found 35) | 0 | no | 0 | 0.74 |
| ext-dev-e-0054 | genuine | mild | none | 85 (found 85) | 85 (found -) | 0 | no | 0 | 0.52 |
| ext-dev-e-0055 | resaved | mild | none | 95 (found 95) | 85 (found 85) | 0 | no | 0 | 0.65 |
| ext-dev-e-0056 | pasted-field | mild | seen | 95 (found 95) | 85 (found 85) | 1 | yes | 0 | 0.65 |
| ext-dev-e-0057 | pasted-block | mild | seen | 95 (found 95) | 85 (found 85) | 1 | yes | 0 | 0.64 |
| ext-dev-e-0058 | retyped | mild | blind | 85 (found 85) | 85 (found -) | 0 | no | 0 | 0.51 |
| ext-dev-e-0059 | aligned | mild | blind | 85 (found 85) | 85 (found -) | 0 | no | 0 | 0.51 |
| ext-dev-e-0060 | genuine | 150dpi | none | 50 (found 50) | 50 (found -) | 0 | no | 0 | 0.55 |
| ext-dev-e-0061 | resaved | 150dpi | none | 95 (found 95) | 50 (found 50) | 0 | no | 0 | 0.66 |
| ext-dev-e-0062 | pasted-field | 150dpi | seen | 95 (found 95) | 50 (found 50) | 1 | yes | 0 | 0.66 |
| ext-dev-e-0063 | pasted-block | 150dpi | seen | 95 (found 95) | 50 (found 50) | 1 | yes | 0 | 0.67 |
| ext-dev-e-0064 | retyped | 150dpi | seen | 85 (found 85) | 50 (found 50) | 1 | yes | 0 | 0.66 |
| ext-dev-e-0065 | aligned | 150dpi | blind | 85 (found 85) | 50 (found 50) | 0 | no | 0 | 0.68 |
| ext-dev-e-0066 | genuine | 120dpi | none | 35 (found 35) | 35 (found -) | 0 | no | 0 | 0.61 |
| ext-dev-e-0067 | resaved | 120dpi | none | 95 (found 95) | 35 (found 35) | 0 | no | 0 | 0.72 |
| ext-dev-e-0068 | pasted-field | 120dpi | seen | 95 (found 95) | 35 (found 35) | 1 | yes | 0 | 0.76 |
| ext-dev-e-0069 | pasted-block | 120dpi | seen | 95 (found 95) | 35 (found 35) | 1 | yes | 0 | 0.75 |
| ext-dev-e-0070 | retyped | 120dpi | seen | 85 (found 85) | 35 (found 35) | 1 | yes | 0 | 0.74 |
| ext-dev-e-0071 | aligned | 120dpi | blind | 85 (found 85) | 35 (found 35) | 1 | no | 0 | 0.72 |
| ext-dev-e-0072 | genuine | mild | none | 85 (found 85) | 85 (found -) | 0 | no | 0 | 0.52 |
| ext-dev-e-0073 | resaved | mild | none | 95 (found 95) | 85 (found 85) | 0 | no | 0 | 0.63 |
| ext-dev-e-0074 | pasted-field | mild | seen | 95 (found 95) | 85 (found 85) | 1 | yes | 0 | 0.62 |
| ext-dev-e-0075 | pasted-block | mild | seen | 95 (found 95) | 85 (found 85) | 1 | yes | 0 | 0.63 |
| ext-dev-e-0076 | retyped | mild | blind | 85 (found 85) | 85 (found -) | 0 | no | 0 | 0.51 |
| ext-dev-e-0077 | aligned | mild | blind | 85 (found 85) | 85 (found -) | 0 | no | 0 | 0.51 |
| ext-dev-e-0078 | genuine | 150dpi | none | 50 (found 50) | 50 (found -) | 0 | no | 0 | 0.54 |
| ext-dev-e-0079 | resaved | 150dpi | none | 95 (found 95) | 50 (found 50) | 0 | no | 0 | 0.66 |
| ext-dev-e-0080 | pasted-field | 150dpi | seen | 95 (found 95) | 50 (found 50) | 1 | yes | 0 | 0.68 |
| ext-dev-e-0081 | pasted-block | 150dpi | seen | 95 (found 95) | 50 (found 50) | 1 | yes | 0 | 0.67 |
| ext-dev-e-0082 | retyped | 150dpi | seen | 85 (found 85) | 50 (found 50) | 1 | yes | 0 | 0.66 |
| ext-dev-e-0083 | aligned | 150dpi | blind | 85 (found 85) | 50 (found 50) | 0 | no | 0 | 0.66 |
| ext-dev-e-0084 | genuine | 120dpi | none | 35 (found 35) | 35 (found -) | 0 | no | 0 | 0.6 |
| ext-dev-e-0085 | resaved | 120dpi | none | 95 (found 95) | 35 (found 35) | 0 | no | 0 | 0.73 |
| ext-dev-e-0086 | pasted-field | 120dpi | seen | 95 (found 95) | 35 (found 35) | 1 | yes | 0 | 0.71 |
| ext-dev-e-0087 | pasted-block | 120dpi | seen | 95 (found 95) | 35 (found 35) | 1 | yes | 0 | 0.73 |
| ext-dev-e-0088 | retyped | 120dpi | seen | 85 (found 85) | 35 (found 35) | 1 | yes | 0 | 0.71 |
| ext-dev-e-0089 | aligned | 120dpi | blind | 85 (found 85) | 35 (found 35) | 0 | no | 0 | 0.74 |
| ext-dev-e-0090 | genuine | mild | none | 85 (found 85) | 85 (found -) | 0 | no | 0 | 0.51 |
| ext-dev-e-0091 | resaved | mild | none | 95 (found 95) | 85 (found 85) | 0 | no | 0 | 0.62 |
| ext-dev-e-0092 | pasted-field | mild | seen | 95 (found 95) | 85 (found 85) | 1 | yes | 0 | 0.62 |
| ext-dev-e-0093 | pasted-block | mild | seen | 95 (found 95) | 85 (found 85) | 1 | yes | 0 | 0.62 |
| ext-dev-e-0094 | retyped | mild | blind | 85 (found 85) | 85 (found -) | 0 | no | 0 | 0.51 |
| ext-dev-e-0095 | aligned | mild | blind | 85 (found 85) | 85 (found -) | 0 | no | 0 | 0.5 |
| ext-dev-e-0096 | genuine | 150dpi | none | 50 (found 50) | 50 (found -) | 0 | no | 0 | 0.54 |
| ext-dev-e-0097 | resaved | 150dpi | none | 95 (found 95) | 50 (found 50) | 0 | no | 0 | 0.67 |
| ext-dev-e-0098 | pasted-field | 150dpi | seen | 95 (found 95) | 50 (found 50) | 1 | yes | 0 | 0.68 |
| ext-dev-e-0099 | pasted-block | 150dpi | seen | 95 (found 95) | 50 (found 50) | 1 | yes | 0 | 0.64 |
| ext-dev-e-0100 | retyped | 150dpi | seen | 85 (found 85) | 50 (found 50) | 1 | yes | 0 | 0.65 |
| ext-dev-e-0101 | aligned | 150dpi | blind | 85 (found 85) | 50 (found 50) | 0 | no | 0 | 0.64 |
| ext-dev-e-0102 | genuine | 120dpi | none | 35 (found 35) | 35 (found -) | 0 | no | 0 | 0.58 |
| ext-dev-e-0103 | resaved | 120dpi | none | 95 (found 95) | 35 (found 35) | 0 | no | 0 | 0.71 |
| ext-dev-e-0104 | pasted-field | 120dpi | seen | 95 (found 95) | 35 (found 35) | 1 | yes | 0 | 0.7 |
| ext-dev-e-0105 | pasted-block | 120dpi | seen | 95 (found 95) | 35 (found 35) | 1 | yes | 0 | 0.73 |
| ext-dev-e-0106 | retyped | 120dpi | seen | 85 (found 85) | 35 (found 35) | 1 | yes | 0 | 0.71 |
| ext-dev-e-0107 | aligned | 120dpi | blind | 85 (found 85) | 35 (found 35) | 1 | no | 0 | 0.71 |
