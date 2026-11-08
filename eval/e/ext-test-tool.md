# Compression-history check on the ext-test pack (whole tool)

Run: 2026-11-08 11:21 India Standard Time, commit bb08c8e, Windows 10, Python 3.11.9, 6 cores, CPU only.
108 cases (seeds 4100000 to 4100107), 384 s in all, 3.6 s a case.
Constants of forensics/ela.py: QUALITIES=25..95 step 5, GAP=10, MIN_DIP=1.3, INK=60, BLOCK=16, MIN_INK=24, Z=6.0, MAX_DIP=1.3, MIN_CELLS=4, MIN_RATIO=2.0, LISTED=6.

A case is `none` when the scan has no edit (saved once, or saved again unchanged), `seen` when its edit was made after an earlier save at least 10 quality points below the last, so that the earlier save left a mark the edited place does not share, and `blind` when the check cannot see it by construction (an edit with the page's own grid and quality, or a last save too close to the earlier one). That is fixed in datagen/ela_pack.py. Located: a region whose IoU with the edited box is above 0.3. Stray: a region that does not touch the edited box.

## In short

- Scans without an edit (36): a region on 0, which is a false flag.
- Edits the check is meant to see (48): a region at the edit on 48; a region anywhere on 48; a stray region on 0.
- Edits it cannot see (24, listed apart, not claimed): a region anyway on 4, touching the edit on 4, at the edit (IoU above 0.3) on 0.
- Missed among those it is meant to see: none.
- Pictures it declared not examined: 0.

## By kind and level

| kind | level | expect | cases | region | touching | located | stray |
|---|---|---|---|---|---|---|---|
| genuine | mild | none | 6 | 0 | 0 | 0 | 0 |
| genuine | 150dpi | none | 6 | 0 | 0 | 0 | 0 |
| genuine | 120dpi | none | 6 | 0 | 0 | 0 | 0 |
| resaved | mild | none | 6 | 0 | 0 | 0 | 0 |
| resaved | 150dpi | none | 6 | 0 | 0 | 0 | 0 |
| resaved | 120dpi | none | 6 | 0 | 0 | 0 | 0 |
| pasted-field | mild | seen | 6 | 6 | 6 | 6 | 0 |
| pasted-field | 150dpi | seen | 6 | 6 | 6 | 6 | 0 |
| pasted-field | 120dpi | seen | 6 | 6 | 6 | 6 | 0 |
| pasted-block | mild | seen | 6 | 6 | 6 | 6 | 0 |
| pasted-block | 150dpi | seen | 6 | 6 | 6 | 6 | 0 |
| pasted-block | 120dpi | seen | 6 | 6 | 6 | 6 | 0 |
| retyped | mild | blind | 6 | 0 | 0 | 0 | 0 |
| retyped | 150dpi | seen | 6 | 6 | 6 | 6 | 0 |
| retyped | 120dpi | seen | 6 | 6 | 6 | 6 | 0 |
| aligned | mild | blind | 6 | 0 | 0 | 0 | 0 |
| aligned | 150dpi | blind | 6 | 2 | 2 | 0 | 0 |
| aligned | 120dpi | blind | 6 | 2 | 2 | 0 | 0 |

## Every case

| case | kind | level | expect | last save (pack) | earlier save (pack) | regions | located | stray | s |
|---|---|---|---|---|---|---|---|---|---|
| ext-test-e-0000 | genuine | mild | none | 85 | 85 | 0 | no | 0 | 4.34 |
| ext-test-e-0001 | resaved | mild | none | 95 | 85 | 0 | no | 0 | 3.5 |
| ext-test-e-0002 | pasted-field | mild | seen | 95 | 85 | 1 | yes | 0 | 3.83 |
| ext-test-e-0003 | pasted-block | mild | seen | 95 | 85 | 1 | yes | 0 | 3.64 |
| ext-test-e-0004 | retyped | mild | blind | 85 | 85 | 0 | no | 0 | 3.53 |
| ext-test-e-0005 | aligned | mild | blind | 85 | 85 | 0 | no | 0 | 3.62 |
| ext-test-e-0006 | genuine | 150dpi | none | 50 | 50 | 0 | no | 0 | 3.47 |
| ext-test-e-0007 | resaved | 150dpi | none | 95 | 50 | 0 | no | 0 | 3.48 |
| ext-test-e-0008 | pasted-field | 150dpi | seen | 95 | 50 | 1 | yes | 0 | 3.55 |
| ext-test-e-0009 | pasted-block | 150dpi | seen | 95 | 50 | 1 | yes | 0 | 3.74 |
| ext-test-e-0010 | retyped | 150dpi | seen | 85 | 50 | 1 | yes | 0 | 3.64 |
| ext-test-e-0011 | aligned | 150dpi | blind | 85 | 50 | 0 | no | 0 | 3.66 |
| ext-test-e-0012 | genuine | 120dpi | none | 35 | 35 | 0 | no | 0 | 3.39 |
| ext-test-e-0013 | resaved | 120dpi | none | 95 | 35 | 0 | no | 0 | 3.56 |
| ext-test-e-0014 | pasted-field | 120dpi | seen | 95 | 35 | 1 | yes | 0 | 3.63 |
| ext-test-e-0015 | pasted-block | 120dpi | seen | 95 | 35 | 1 | yes | 0 | 3.69 |
| ext-test-e-0016 | retyped | 120dpi | seen | 85 | 35 | 1 | yes | 0 | 3.7 |
| ext-test-e-0017 | aligned | 120dpi | blind | 85 | 35 | 1 | no | 0 | 3.7 |
| ext-test-e-0018 | genuine | mild | none | 85 | 85 | 0 | no | 0 | 3.4 |
| ext-test-e-0019 | resaved | mild | none | 95 | 85 | 0 | no | 0 | 3.42 |
| ext-test-e-0020 | pasted-field | mild | seen | 95 | 85 | 1 | yes | 0 | 3.77 |
| ext-test-e-0021 | pasted-block | mild | seen | 95 | 85 | 1 | yes | 0 | 3.73 |
| ext-test-e-0022 | retyped | mild | blind | 85 | 85 | 0 | no | 0 | 3.49 |
| ext-test-e-0023 | aligned | mild | blind | 85 | 85 | 0 | no | 0 | 3.62 |
| ext-test-e-0024 | genuine | 150dpi | none | 50 | 50 | 0 | no | 0 | 3.23 |
| ext-test-e-0025 | resaved | 150dpi | none | 95 | 50 | 0 | no | 0 | 3.61 |
| ext-test-e-0026 | pasted-field | 150dpi | seen | 95 | 50 | 1 | yes | 0 | 3.58 |
| ext-test-e-0027 | pasted-block | 150dpi | seen | 95 | 50 | 1 | yes | 0 | 3.8 |
| ext-test-e-0028 | retyped | 150dpi | seen | 85 | 50 | 1 | yes | 0 | 3.71 |
| ext-test-e-0029 | aligned | 150dpi | blind | 85 | 50 | 0 | no | 0 | 3.68 |
| ext-test-e-0030 | genuine | 120dpi | none | 35 | 35 | 0 | no | 0 | 3.36 |
| ext-test-e-0031 | resaved | 120dpi | none | 95 | 35 | 0 | no | 0 | 3.61 |
| ext-test-e-0032 | pasted-field | 120dpi | seen | 95 | 35 | 1 | yes | 0 | 3.55 |
| ext-test-e-0033 | pasted-block | 120dpi | seen | 95 | 35 | 1 | yes | 0 | 3.6 |
| ext-test-e-0034 | retyped | 120dpi | seen | 85 | 35 | 1 | yes | 0 | 3.65 |
| ext-test-e-0035 | aligned | 120dpi | blind | 85 | 35 | 0 | no | 0 | 3.34 |
| ext-test-e-0036 | genuine | mild | none | 85 | 85 | 0 | no | 0 | 3.38 |
| ext-test-e-0037 | resaved | mild | none | 95 | 85 | 0 | no | 0 | 3.38 |
| ext-test-e-0038 | pasted-field | mild | seen | 95 | 85 | 1 | yes | 0 | 3.68 |
| ext-test-e-0039 | pasted-block | mild | seen | 95 | 85 | 1 | yes | 0 | 3.74 |
| ext-test-e-0040 | retyped | mild | blind | 85 | 85 | 0 | no | 0 | 3.56 |
| ext-test-e-0041 | aligned | mild | blind | 85 | 85 | 0 | no | 0 | 3.64 |
| ext-test-e-0042 | genuine | 150dpi | none | 50 | 50 | 0 | no | 0 | 3.22 |
| ext-test-e-0043 | resaved | 150dpi | none | 95 | 50 | 0 | no | 0 | 3.37 |
| ext-test-e-0044 | pasted-field | 150dpi | seen | 95 | 50 | 1 | yes | 0 | 3.56 |
| ext-test-e-0045 | pasted-block | 150dpi | seen | 95 | 50 | 1 | yes | 0 | 3.65 |
| ext-test-e-0046 | retyped | 150dpi | seen | 85 | 50 | 1 | yes | 0 | 3.58 |
| ext-test-e-0047 | aligned | 150dpi | blind | 85 | 50 | 0 | no | 0 | 3.65 |
| ext-test-e-0048 | genuine | 120dpi | none | 35 | 35 | 0 | no | 0 | 3.59 |
| ext-test-e-0049 | resaved | 120dpi | none | 95 | 35 | 0 | no | 0 | 3.51 |
| ext-test-e-0050 | pasted-field | 120dpi | seen | 95 | 35 | 1 | yes | 0 | 3.62 |
| ext-test-e-0051 | pasted-block | 120dpi | seen | 95 | 35 | 1 | yes | 0 | 3.61 |
| ext-test-e-0052 | retyped | 120dpi | seen | 85 | 35 | 1 | yes | 0 | 3.62 |
| ext-test-e-0053 | aligned | 120dpi | blind | 85 | 35 | 0 | no | 0 | 3.67 |
| ext-test-e-0054 | genuine | mild | none | 85 | 85 | 0 | no | 0 | 3.32 |
| ext-test-e-0055 | resaved | mild | none | 95 | 85 | 0 | no | 0 | 3.53 |
| ext-test-e-0056 | pasted-field | mild | seen | 95 | 85 | 1 | yes | 0 | 3.59 |
| ext-test-e-0057 | pasted-block | mild | seen | 95 | 85 | 1 | yes | 0 | 3.76 |
| ext-test-e-0058 | retyped | mild | blind | 85 | 85 | 0 | no | 0 | 3.42 |
| ext-test-e-0059 | aligned | mild | blind | 85 | 85 | 0 | no | 0 | 3.68 |
| ext-test-e-0060 | genuine | 150dpi | none | 50 | 50 | 0 | no | 0 | 3.27 |
| ext-test-e-0061 | resaved | 150dpi | none | 95 | 50 | 0 | no | 0 | 3.45 |
| ext-test-e-0062 | pasted-field | 150dpi | seen | 95 | 50 | 1 | yes | 0 | 3.64 |
| ext-test-e-0063 | pasted-block | 150dpi | seen | 95 | 50 | 1 | yes | 0 | 3.58 |
| ext-test-e-0064 | retyped | 150dpi | seen | 85 | 50 | 1 | yes | 0 | 3.54 |
| ext-test-e-0065 | aligned | 150dpi | blind | 85 | 50 | 0 | no | 0 | 3.54 |
| ext-test-e-0066 | genuine | 120dpi | none | 35 | 35 | 0 | no | 0 | 3.3 |
| ext-test-e-0067 | resaved | 120dpi | none | 95 | 35 | 0 | no | 0 | 3.43 |
| ext-test-e-0068 | pasted-field | 120dpi | seen | 95 | 35 | 1 | yes | 0 | 3.61 |
| ext-test-e-0069 | pasted-block | 120dpi | seen | 95 | 35 | 1 | yes | 0 | 3.62 |
| ext-test-e-0070 | retyped | 120dpi | seen | 85 | 35 | 1 | yes | 0 | 3.66 |
| ext-test-e-0071 | aligned | 120dpi | blind | 85 | 35 | 0 | no | 0 | 3.7 |
| ext-test-e-0072 | genuine | mild | none | 85 | 85 | 0 | no | 0 | 3.21 |
| ext-test-e-0073 | resaved | mild | none | 95 | 85 | 0 | no | 0 | 3.4 |
| ext-test-e-0074 | pasted-field | mild | seen | 95 | 85 | 1 | yes | 0 | 3.61 |
| ext-test-e-0075 | pasted-block | mild | seen | 95 | 85 | 1 | yes | 0 | 3.7 |
| ext-test-e-0076 | retyped | mild | blind | 85 | 85 | 0 | no | 0 | 3.4 |
| ext-test-e-0077 | aligned | mild | blind | 85 | 85 | 0 | no | 0 | 3.42 |
| ext-test-e-0078 | genuine | 150dpi | none | 50 | 50 | 0 | no | 0 | 3.19 |
| ext-test-e-0079 | resaved | 150dpi | none | 95 | 50 | 0 | no | 0 | 3.35 |
| ext-test-e-0080 | pasted-field | 150dpi | seen | 95 | 50 | 1 | yes | 0 | 3.5 |
| ext-test-e-0081 | pasted-block | 150dpi | seen | 95 | 50 | 1 | yes | 0 | 3.73 |
| ext-test-e-0082 | retyped | 150dpi | seen | 85 | 50 | 1 | yes | 0 | 3.52 |
| ext-test-e-0083 | aligned | 150dpi | blind | 85 | 50 | 1 | no | 0 | 3.59 |
| ext-test-e-0084 | genuine | 120dpi | none | 35 | 35 | 0 | no | 0 | 3.49 |
| ext-test-e-0085 | resaved | 120dpi | none | 95 | 35 | 0 | no | 0 | 3.52 |
| ext-test-e-0086 | pasted-field | 120dpi | seen | 95 | 35 | 1 | yes | 0 | 3.48 |
| ext-test-e-0087 | pasted-block | 120dpi | seen | 95 | 35 | 1 | yes | 0 | 3.77 |
| ext-test-e-0088 | retyped | 120dpi | seen | 85 | 35 | 1 | yes | 0 | 3.61 |
| ext-test-e-0089 | aligned | 120dpi | blind | 85 | 35 | 0 | no | 0 | 3.49 |
| ext-test-e-0090 | genuine | mild | none | 85 | 85 | 0 | no | 0 | 3.35 |
| ext-test-e-0091 | resaved | mild | none | 95 | 85 | 0 | no | 0 | 3.37 |
| ext-test-e-0092 | pasted-field | mild | seen | 95 | 85 | 1 | yes | 0 | 3.58 |
| ext-test-e-0093 | pasted-block | mild | seen | 95 | 85 | 1 | yes | 0 | 3.54 |
| ext-test-e-0094 | retyped | mild | blind | 85 | 85 | 0 | no | 0 | 3.53 |
| ext-test-e-0095 | aligned | mild | blind | 85 | 85 | 0 | no | 0 | 3.69 |
| ext-test-e-0096 | genuine | 150dpi | none | 50 | 50 | 0 | no | 0 | 3.22 |
| ext-test-e-0097 | resaved | 150dpi | none | 95 | 50 | 0 | no | 0 | 3.48 |
| ext-test-e-0098 | pasted-field | 150dpi | seen | 95 | 50 | 1 | yes | 0 | 3.55 |
| ext-test-e-0099 | pasted-block | 150dpi | seen | 95 | 50 | 1 | yes | 0 | 3.43 |
| ext-test-e-0100 | retyped | 150dpi | seen | 85 | 50 | 1 | yes | 0 | 3.55 |
| ext-test-e-0101 | aligned | 150dpi | blind | 85 | 50 | 1 | no | 0 | 3.6 |
| ext-test-e-0102 | genuine | 120dpi | none | 35 | 35 | 0 | no | 0 | 3.28 |
| ext-test-e-0103 | resaved | 120dpi | none | 95 | 35 | 0 | no | 0 | 3.41 |
| ext-test-e-0104 | pasted-field | 120dpi | seen | 95 | 35 | 1 | yes | 0 | 3.53 |
| ext-test-e-0105 | pasted-block | 120dpi | seen | 95 | 35 | 1 | yes | 0 | 3.67 |
| ext-test-e-0106 | retyped | 120dpi | seen | 85 | 35 | 1 | yes | 0 | 3.63 |
| ext-test-e-0107 | aligned | 120dpi | blind | 85 | 35 | 1 | no | 0 | 3.68 |
