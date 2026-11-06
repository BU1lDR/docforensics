# Reused marks (scope D, package H): ext-dev, 06 Nov 2026 12:38

Tool: commit 39f1b03. Limit: repeat_ink = 2 % (ink gap; the 64-bit hash is logged and does not decide). 72 cases of datagen/reuse_pack.py, 348 s in all, peak memory 761 MB. Windows 10, Python 3.11.9.

A find is the observation of the right kind with both marks on the manifest's boxes (IoU of at least 0.5). A stray observation is any other reuse observation; in a genuine case every one is a false observation. ext-dev is what the limit was fitted on, so these figures are in-sample.

## Repeated marks found, by kind and medium

| Kind | Medium | Cases | Found at their place | Not compared | Stray observations |
|---|---|---|---|---|---|
| signature | digital | 12 | 12 | 0 | 6 |
| signature | mild | 6 | 6 | 0 | 2 |
| signature | 150dpi | 3 | 3 | 0 | 2 |
| signature | 120dpi | 3 | 1 | 0 | 0 |
| **signature** | all | 24 | 22 | 0 | 10 |
| stamp | digital | 12 | 12 | 0 | 0 |
| stamp | mild | 6 | 6 | 0 | 0 |
| stamp | 150dpi | 3 | 3 | 0 | 0 |
| stamp | 120dpi | 3 | 1 | 0 | 0 |
| **stamp** | all | 24 | 22 | 0 | 0 |

## Genuine cases (every document signed and pressed afresh)

| Medium | Cases | Cases with a reuse observation | Observations |
|---|---|---|---|
| digital | 12 | 3 | 3 |
| mild | 6 | 3 | 3 |
| 150dpi | 3 | 2 | 2 |
| 120dpi | 3 | 0 | 0 |
| **all** | 24 | 8 | 8 |

## The ink gap of the compared pairs (%)

Repeated pairs are the pair of the case's own kind in a case that repeats a mark; separate pairs are every other pair, which two signings or two pressings made.

| Pair | Medium | Pairs | Smallest | Median | Largest |
|---|---|---|---|---|---|
| signature, repeated | digital | 12 | 0.0 | 0.0 | 0.0 |
| signature, repeated | scanned | 12 | 0.0 | 0.3 | 6.7 |
| signature, repeated | all | 24 | 0.0 | 0.0 | 6.7 |
| signature, separate | digital | 24 | 8.8 | 19.7 | 44.2 |
| signature, separate | scanned | 23 | 9.3 | 20.3 | 42.5 |
| signature, separate | all | 47 | 8.8 | 20.1 | 44.2 |
| stamp, repeated | digital | 12 | 0.0 | 0.0 | 0.6 |
| stamp, repeated | scanned | 12 | 0.1 | 0.9 | 5.1 |
| stamp, repeated | all | 24 | 0.0 | 0.2 | 5.1 |
| stamp, separate | digital | 24 | 0.0 | 5.9 | 45.4 |
| stamp, separate | scanned | 24 | 0.0 | 3.2 | 28.3 |
| stamp, separate | all | 48 | 0.0 | 3.7 | 45.4 |

## The same counts at other limits

Repeated pairs at or under the limit would be found; separate pairs at or under it would be false observations.

| Limit (%) | Signatures found | Stamps found | Separate signature pairs flagged | Separate stamp pairs flagged |
|---|---|---|---|---|
| 0.5 | 18 of 24 | 15 of 24 | 0 of 47 | 11 of 48 |
| 1 | 21 of 24 | 19 of 24 | 0 of 47 | 13 of 48 |
| 2 | 22 of 24 | 22 of 24 | 0 of 47 | 18 of 48 |
| 3 | 23 of 24 | 23 of 24 | 0 of 47 | 20 of 48 |
| 5 | 23 of 24 | 23 of 24 | 0 of 47 | 27 of 48 |
| 8 | 24 of 24 | 24 of 24 | 0 of 47 | 34 of 48 |
| 10 | 24 of 24 | 24 of 24 | 3 of 47 | 34 of 48 |
| 15 | 24 of 24 | 24 of 24 | 11 of 47 | 40 of 48 |

## Cases

| Case | Kind | Medium | Layout | Found | Stray | Pairs (kind: ink gap, hash bits) |
|---|---|---|---|---|---|---|
| ext-dev-h-0000 | genuine | digital | A | - | 1 | signature: 17.7, 5; stamp: 0.1, 8 |
| ext-dev-h-0001 | signature | digital | A | yes | 1 | signature: 0.0, 0; stamp: 0.0, 9 |
| ext-dev-h-0002 | stamp | digital | A | yes | 0 | signature: 30.5, 6; stamp: 0.0, 15 |
| ext-dev-h-0003 | genuine | mild | A | - | 0 | signature: 23.1, 11; stamp: 3.5, 10 |
| ext-dev-h-0004 | signature | mild | A | yes | 0 | signature: 0.0, 5; stamp: 2.5, 4 |
| ext-dev-h-0005 | stamp | mild | A | yes | 0 | signature: 19.8, 8; stamp: 0.9, 8 |
| ext-dev-h-0006 | genuine | digital | A | - | 0 | signature: 44.2, 12; stamp: 13.5, 12 |
| ext-dev-h-0007 | signature | digital | A | yes | 1 | signature: 0.0, 4; stamp: 1.6, 9 |
| ext-dev-h-0008 | stamp | digital | A | yes | 0 | signature: 13.7, 1; stamp: 0.0, 8 |
| ext-dev-h-0009 | genuine | 150dpi | A | - | 1 | signature: 20.3, 8; stamp: 1.8, 4 |
| ext-dev-h-0010 | signature | 150dpi | A | yes | 1 | signature: 1.0, 8; stamp: 0.7, 4 |
| ext-dev-h-0011 | stamp | 150dpi | A | yes | 0 | signature: 18.4, 14; stamp: 0.8, 6 |
| ext-dev-h-0012 | genuine | digital | A | - | 1 | signature: 23.5, 5; stamp: 0.0, 5 |
| ext-dev-h-0013 | signature | digital | A | yes | 0 | signature: 0.0, 0; stamp: 45.4, 20 |
| ext-dev-h-0014 | stamp | digital | A | yes | 0 | signature: 10.3, 7; stamp: 0.1, 6 |
| ext-dev-h-0015 | genuine | mild | A | - | 1 | signature: 22.8, 14; stamp: 0.0, 5 |
| ext-dev-h-0016 | signature | mild | A | yes | 0 | signature: 0.1, 3; stamp: 3.2, 12 |
| ext-dev-h-0017 | stamp | mild | A | yes | 0 | signature: 30.6, 7; stamp: 1.1, 5 |
| ext-dev-h-0018 | genuine | digital | A | - | 0 | signature: 22.7, 6; stamp: 11.8, 14 |
| ext-dev-h-0019 | signature | digital | A | yes | 0 | signature: 0.0, 0; stamp: 6.7, 9 |
| ext-dev-h-0020 | stamp | digital | A | yes | 0 | signature: 20.1, 2; stamp: 0.1, 2 |
| ext-dev-h-0021 | genuine | 120dpi | A | - | 0 | signature: 38.2, 8; stamp: 22.6, 10 |
| ext-dev-h-0022 | signature | 120dpi | A | - | 0 | signature: 3.0, 8; stamp: 16.6, 15 |
| ext-dev-h-0023 | stamp | 120dpi | A | - | 0 | signature: 11.0, 3; stamp: 2.4, 6 |
| ext-dev-h-0024 | genuine | digital | A | - | 0 | signature: 31.3, 10; stamp: 5.1, 11 |
| ext-dev-h-0025 | signature | digital | A | yes | 0 | signature: 0.0, 3; stamp: 39.8, 17 |
| ext-dev-h-0026 | stamp | digital | A | yes | 0 | signature: 36.0, 10; stamp: 0.1, 7 |
| ext-dev-h-0027 | genuine | mild | A | - | 0 | signature: 14.1, 7; stamp: 4.1, 6 |
| ext-dev-h-0028 | signature | mild | A | yes | 1 | signature: 0.5, 0; stamp: 0.4, 6 |
| ext-dev-h-0029 | stamp | mild | A | yes | 0 | signature: 9.3, 11; stamp: 0.8, 8 |
| ext-dev-h-0030 | genuine | digital | A | - | 0 | signature: 16.3, 2; stamp: 15.9, 15 |
| ext-dev-h-0031 | signature | digital | A | yes | 1 | signature: 0.0, 1; stamp: 0.3, 9 |
| ext-dev-h-0032 | stamp | digital | A | yes | 0 | signature: 9.6, 4; stamp: 0.0, 15 |
| ext-dev-h-0033 | genuine | 150dpi | A | - | 1 | signature: 12.9, 8; stamp: 1.4, 3 |
| ext-dev-h-0034 | signature | 150dpi | A | yes | 0 | signature: 0.0, 2; stamp: 25.9, 9 |
| ext-dev-h-0035 | stamp | 150dpi | A | yes | 0 | signature: 17.6, 9; stamp: 1.2, 7 |
| ext-dev-h-0036 | genuine | digital | A | - | 1 | signature: 20.1, 6; stamp: 0.0, 5 |
| ext-dev-h-0037 | signature | digital | A | yes | 1 | signature: 0.0, 1; stamp: 0.1, 6 |
| ext-dev-h-0038 | stamp | digital | A | yes | 0 | signature: 8.8, 0; stamp: 0.0, 3 |
| ext-dev-h-0039 | genuine | mild | A | - | 1 | signature: 12.7, 2; stamp: 0.8, 4 |
| ext-dev-h-0040 | signature | mild | A | yes | 0 | signature: 0.6, 3; stamp: 7.9, 13 |
| ext-dev-h-0041 | stamp | mild | A | yes | 0 | signature: 13.5, 9; stamp: 0.1, 4 |
| ext-dev-h-0042 | genuine | digital | A | - | 0 | signature: 15.9, 4; stamp: 10.2, 13 |
| ext-dev-h-0043 | signature | digital | A | yes | 0 | signature: 0.0, 1; stamp: 5.9, 6 |
| ext-dev-h-0044 | stamp | digital | A | yes | 0 | signature: 11.1, 6; stamp: 0.0, 3 |
| ext-dev-h-0045 | genuine | 120dpi | A | - | 0 | stamp: 3.2, 4 |
| ext-dev-h-0046 | signature | 120dpi | A | - | 0 | signature: 6.7, 3; stamp: 4.8, 6 |
| ext-dev-h-0047 | stamp | 120dpi | A | yes | 0 | signature: 32.3, 13; stamp: 1.5, 2 |
| ext-dev-h-0048 | genuine | digital | A | - | 0 | signature: 35.0, 16; stamp: 13.2, 14 |
| ext-dev-h-0049 | signature | digital | A | yes | 0 | signature: 0.0, 1; stamp: 14.9, 12 |
| ext-dev-h-0050 | stamp | digital | A | yes | 0 | signature: 15.8, 6; stamp: 0.0, 6 |
| ext-dev-h-0051 | genuine | mild | A | - | 1 | signature: 42.5, 4; stamp: 1.4, 6 |
| ext-dev-h-0052 | signature | mild | A | yes | 0 | signature: 0.0, 5; stamp: 5.9, 10 |
| ext-dev-h-0053 | stamp | mild | A | yes | 0 | signature: 24.6, 9; stamp: 0.4, 13 |
| ext-dev-h-0054 | genuine | digital | A | - | 0 | signature: 16.6, 10; stamp: 32.1, 23 |
| ext-dev-h-0055 | signature | digital | A | yes | 0 | signature: 0.0, 0; stamp: 5.9, 12 |
| ext-dev-h-0056 | stamp | digital | A | yes | 0 | signature: 23.9, 9; stamp: 0.6, 6 |
| ext-dev-h-0057 | genuine | 150dpi | A | - | 0 | signature: 19.4, 6; stamp: 2.9, 9 |
| ext-dev-h-0058 | signature | 150dpi | A | yes | 1 | signature: 0.0, 7; stamp: 1.5, 9 |
| ext-dev-h-0059 | stamp | 150dpi | A | yes | 0 | signature: 29.0, 13; stamp: 0.2, 8 |
| ext-dev-h-0060 | genuine | digital | A | - | 0 | signature: 22.9, 7; stamp: 12.5, 13 |
| ext-dev-h-0061 | signature | digital | A | yes | 1 | signature: 0.0, 3; stamp: 0.1, 6 |
| ext-dev-h-0062 | stamp | digital | A | yes | 0 | signature: 29.4, 7; stamp: 0.0, 10 |
| ext-dev-h-0063 | genuine | mild | A | - | 0 | signature: 22.8, 12; stamp: 5.5, 17 |
| ext-dev-h-0064 | signature | mild | A | yes | 1 | signature: 0.2, 4; stamp: 0.1, 2 |
| ext-dev-h-0065 | stamp | mild | A | yes | 0 | signature: 31.8, 10; stamp: 0.4, 4 |
| ext-dev-h-0066 | genuine | digital | A | - | 0 | signature: 19.1, 7; stamp: 3.4, 9 |
| ext-dev-h-0067 | signature | digital | A | yes | 1 | signature: 0.0, 0; stamp: 0.2, 2 |
| ext-dev-h-0068 | stamp | digital | A | yes | 0 | signature: 19.4, 4; stamp: 0.0, 12 |
| ext-dev-h-0069 | genuine | 120dpi | A | - | 0 | signature: 36.7, 15; stamp: 28.3, 16 |
| ext-dev-h-0070 | signature | 120dpi | A | yes | 0 | signature: 1.0, 3; stamp: 3.9, 5 |
| ext-dev-h-0071 | stamp | 120dpi | A | - | 0 | signature: 18.1, 5; stamp: 5.1, 4 |
