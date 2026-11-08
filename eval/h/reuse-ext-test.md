# Reused marks (scope D, package H): ext-test, 08 Nov 2026 11:11

Tool: commit bb08c8e. Limit: repeat_ink = 5 % (ink gap of two signatures; the 64-bit hash is logged and does not decide; stamps and logos are not looked at). 72 cases of datagen/reuse_pack.py, 444 s in all, peak memory 765 MB. Windows 10, Python 3.11.9.

A find is the observation whose two signatures lie on the manifest's boxes (IoU of at least 0.5). A stray observation is any other reuse observation; in a genuine case every one is a false observation. The stamp cases are listed to show that they are not compared. This split was read once, on the frozen code.

## Repeated marks found, by kind and medium

| Kind | Medium | Cases | Found at their place | Not compared | Stray observations |
|---|---|---|---|---|---|
| signature | digital | 12 | 12 | 0 | 0 |
| signature | mild | 6 | 6 | 0 | 0 |
| signature | 150dpi | 3 | 3 | 0 | 0 |
| signature | 120dpi | 3 | 2 | 1 | 0 |
| **signature** | all | 24 | 23 | 1 | 0 |
| stamp | digital | 12 | 0 | 12 | 0 |
| stamp | mild | 6 | 0 | 6 | 0 |
| stamp | 150dpi | 3 | 0 | 3 | 0 |
| stamp | 120dpi | 3 | 0 | 3 | 0 |
| **stamp** | all | 24 | 0 | 24 | 0 |

## Genuine cases (every document signed afresh)

| Medium | Cases | Not compared | Cases with a reuse observation | Observations |
|---|---|---|---|---|
| digital | 12 | 0 | 0 | 0 |
| mild | 6 | 0 | 0 | 0 |
| 150dpi | 3 | 0 | 0 | 0 |
| 120dpi | 3 | 0 | 0 | 0 |
| **all** | 24 | 0 | 0 | 0 |

## The ink gap of the compared signature pairs (%)

Repeated pairs are the pair in a case that repeats the signature; separate pairs are every other pair, which two signings made.

| Pair | Medium | Pairs | Smallest | Median | Largest |
|---|---|---|---|---|---|
| repeated | digital | 12 | 0.0 | 0.0 | 0.0 |
| repeated | scanned | 11 | 0.0 | 0.1 | 3.1 |
| repeated | all | 23 | 0.0 | 0.0 | 3.1 |
| separate | digital | 24 | 7.5 | 21.1 | 34.9 |
| separate | scanned | 23 | 6.8 | 16.6 | 35.5 |
| separate | all | 47 | 6.8 | 19.4 | 35.5 |

Ink share of the canvases of the compared signatures (two to a pair): smallest 0.09, median 0.12, largest 0.17. A mark that fills more than 0.5 of its canvas is a bar, a dot or a block and is not compared: 0 marks skipped.

## The same counts at other limits

Repeated pairs at or under the limit would be found; separate pairs at or under it would be false observations.

| Limit (%) | Repeated pairs found | Separate pairs flagged |
|---|---|---|
| 0.5 | 21 of 23 | 0 of 47 |
| 1 | 21 of 23 | 0 of 47 |
| 2 | 21 of 23 | 0 of 47 |
| 3 | 22 of 23 | 0 of 47 |
| 5 | 23 of 23 | 0 of 47 |
| 8 | 23 of 23 | 3 of 47 |
| 10 | 23 of 23 | 5 of 47 |
| 15 | 23 of 23 | 11 of 47 |

## The 64-bit hash of the compared signature pairs (bits that differ; logged, does not decide)

| Pair | Medium | Pairs | Smallest | Median | Largest |
|---|---|---|---|---|---|
| repeated | digital | 12 | 0 | 2 | 3 |
| repeated | scanned | 11 | 0 | 3 | 7 |
| repeated | all | 23 | 0 | 2 | 7 |
| separate | digital | 24 | 2 | 8 | 14 |
| separate | scanned | 23 | 4 | 9 | 16 |
| separate | all | 47 | 2 | 8 | 16 |

Separate pairs no farther apart than the farthest repeated pair (7 bits): 17 of 47.

## Cases

| Case | Kind | Medium | Layout | Found | Stray | Pairs (kind: ink gap, hash bits) |
|---|---|---|---|---|---|---|
| ext-test-h-0000 | genuine | digital | A | - | 0 | signature: 15.8, 6 |
| ext-test-h-0001 | signature | digital | A | yes | 0 | signature: 0.0, 0 |
| ext-test-h-0002 | stamp | digital | A | - | 0 | signature: 28.4, 14 |
| ext-test-h-0003 | genuine | mild | B | - | 0 | signature: 9.2, 6 |
| ext-test-h-0004 | signature | mild | B | yes | 0 | signature: 0.0, 0 |
| ext-test-h-0005 | stamp | mild | B | - | 0 | signature: 10.2, 6 |
| ext-test-h-0006 | genuine | digital | A | - | 0 | signature: 15.1, 7 |
| ext-test-h-0007 | signature | digital | A | yes | 0 | signature: 0.0, 2 |
| ext-test-h-0008 | stamp | digital | A | - | 0 | signature: 22.2, 8 |
| ext-test-h-0009 | genuine | 150dpi | B | - | 0 | signature: 23.0, 9 |
| ext-test-h-0010 | signature | 150dpi | B | yes | 0 | signature: 0.1, 7 |
| ext-test-h-0011 | stamp | 150dpi | B | - | 0 | signature: 19.7, 11 |
| ext-test-h-0012 | genuine | digital | A | - | 0 | signature: 23.1, 8 |
| ext-test-h-0013 | signature | digital | A | yes | 0 | signature: 0.0, 2 |
| ext-test-h-0014 | stamp | digital | A | - | 0 | signature: 33.9, 12 |
| ext-test-h-0015 | genuine | mild | B | - | 0 | signature: 10.8, 8 |
| ext-test-h-0016 | signature | mild | B | yes | 0 | signature: 0.0, 3 |
| ext-test-h-0017 | stamp | mild | B | - | 0 | signature: 22.4, 10 |
| ext-test-h-0018 | genuine | digital | A | - | 0 | signature: 28.6, 12 |
| ext-test-h-0019 | signature | digital | A | yes | 0 | signature: 0.0, 2 |
| ext-test-h-0020 | stamp | digital | A | - | 0 | signature: 7.5, 4 |
| ext-test-h-0021 | genuine | 120dpi | B | - | 0 | signature: 17.4, 6 |
| ext-test-h-0022 | signature | 120dpi | B | - | 0 |  |
| ext-test-h-0023 | stamp | 120dpi | B | - | 0 |  |
| ext-test-h-0024 | genuine | digital | A | - | 0 | signature: 20.8, 8 |
| ext-test-h-0025 | signature | digital | A | yes | 0 | signature: 0.0, 2 |
| ext-test-h-0026 | stamp | digital | A | - | 0 | signature: 34.9, 8 |
| ext-test-h-0027 | genuine | mild | B | - | 0 | signature: 16.6, 9 |
| ext-test-h-0028 | signature | mild | B | yes | 0 | signature: 0.0, 3 |
| ext-test-h-0029 | stamp | mild | B | - | 0 | signature: 27.0, 12 |
| ext-test-h-0030 | genuine | digital | A | - | 0 | signature: 12.8, 9 |
| ext-test-h-0031 | signature | digital | A | yes | 0 | signature: 0.0, 0 |
| ext-test-h-0032 | stamp | digital | A | - | 0 | signature: 18.0, 10 |
| ext-test-h-0033 | genuine | 150dpi | B | - | 0 | signature: 32.5, 7 |
| ext-test-h-0034 | signature | 150dpi | B | yes | 0 | signature: 0.0, 3 |
| ext-test-h-0035 | stamp | 150dpi | B | - | 0 | signature: 19.0, 5 |
| ext-test-h-0036 | genuine | digital | A | - | 0 | signature: 21.5, 10 |
| ext-test-h-0037 | signature | digital | A | yes | 0 | signature: 0.0, 2 |
| ext-test-h-0038 | stamp | digital | A | - | 0 | signature: 17.1, 9 |
| ext-test-h-0039 | genuine | mild | B | - | 0 | signature: 15.3, 4 |
| ext-test-h-0040 | signature | mild | B | yes | 0 | signature: 0.1, 4 |
| ext-test-h-0041 | stamp | mild | B | - | 0 | signature: 10.4, 11 |
| ext-test-h-0042 | genuine | digital | A | - | 0 | signature: 22.9, 5 |
| ext-test-h-0043 | signature | digital | A | yes | 0 | signature: 0.0, 3 |
| ext-test-h-0044 | stamp | digital | A | - | 0 | signature: 19.4, 2 |
| ext-test-h-0045 | genuine | 120dpi | B | - | 0 | signature: 34.6, 13 |
| ext-test-h-0046 | signature | 120dpi | B | yes | 0 | signature: 2.3, 1 |
| ext-test-h-0047 | stamp | 120dpi | B | - | 0 | signature: 7.7, 8 |
| ext-test-h-0048 | genuine | digital | A | - | 0 | signature: 19.7, 3 |
| ext-test-h-0049 | signature | digital | A | yes | 0 | signature: 0.0, 2 |
| ext-test-h-0050 | stamp | digital | A | - | 0 | signature: 23.0, 8 |
| ext-test-h-0051 | genuine | mild | B | - | 0 | signature: 15.5, 9 |
| ext-test-h-0052 | signature | mild | B | yes | 0 | signature: 0.1, 2 |
| ext-test-h-0053 | stamp | mild | B | - | 0 | signature: 15.6, 10 |
| ext-test-h-0054 | genuine | digital | A | - | 0 | signature: 25.1, 6 |
| ext-test-h-0055 | signature | digital | A | yes | 0 | signature: 0.0, 1 |
| ext-test-h-0056 | stamp | digital | A | - | 0 | signature: 21.7, 11 |
| ext-test-h-0057 | genuine | 150dpi | B | - | 0 | signature: 20.4, 4 |
| ext-test-h-0058 | signature | 150dpi | B | yes | 0 | signature: 0.1, 2 |
| ext-test-h-0059 | stamp | 150dpi | B | - | 0 | signature: 6.8, 6 |
| ext-test-h-0060 | genuine | digital | A | - | 0 | signature: 21.8, 11 |
| ext-test-h-0061 | signature | digital | A | yes | 0 | signature: 0.0, 1 |
| ext-test-h-0062 | stamp | digital | A | - | 0 | signature: 18.8, 9 |
| ext-test-h-0063 | genuine | mild | B | - | 0 | signature: 12.6, 5 |
| ext-test-h-0064 | signature | mild | B | yes | 0 | signature: 0.0, 3 |
| ext-test-h-0065 | stamp | mild | B | - | 0 | signature: 13.6, 9 |
| ext-test-h-0066 | genuine | digital | A | - | 0 | signature: 8.2, 3 |
| ext-test-h-0067 | signature | digital | A | yes | 0 | signature: 0.0, 1 |
| ext-test-h-0068 | stamp | digital | A | - | 0 | signature: 16.4, 10 |
| ext-test-h-0069 | genuine | 120dpi | B | - | 0 | signature: 35.5, 12 |
| ext-test-h-0070 | signature | 120dpi | B | yes | 0 | signature: 3.1, 5 |
| ext-test-h-0071 | stamp | 120dpi | B | - | 0 | signature: 28.8, 16 |
