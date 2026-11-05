# Evaluation of the dev split

Cases 0 to 79 of the dev split (seeds 1000000 to 1000079), run on 2026-11-05 09:56 India Standard Time with the pipeline at commit 8e276c3. Windows 10, Python 3.11.9, 6 cores, CPU only. The numbers are what the run printed: nothing was selected or tuned to make them look better.

## How a result is counted

A change is **found** when the pipeline raised a finding that is an observation, an inconsistency or potential manipulation (never a processing limitation, and never a cluster, which repeats its members) and that

- for a change with a place on a page (D1, D2, D3, D5, S1, S2): cites the changed document, on the changed page, with a box that overlaps the changed box at an IoU (intersection over union) of at least 0.1. It is **located** at an IoU of at least 0.5. The IoU shown is the best of the document's findings, 0 for a miss;
- for a change without one: comes from a detector expected for that change (D4: pdf_meta or cross_producer; C1 and C2: any cross_* check; C3: cross_duplicate; C4: signature; C5: mark) and cites the changed document (for a duplicate, either copy).

A limitation is never a find. A case that produced no result is a miss. On a genuine case every such finding is a flag, counted per document; its limitations are counted apart. A flag in a changed case that cites no changed document is listed as off target; it is not counted against the pipeline, because a cross-document check may rightly cite only the other document of a pair. Extraction is scored on documents nobody changed, value by value (amounts, dates and ids exactly, text up to case and spacing), by the name of the field and, in a table, its row number. A value the pipeline did not extract counts as missing. A wrong value is **trusted** when its confidence is at or above the limit below which the pipeline doubts a value (0.6): nothing warned of it.

## Summary

- Cases: 80 (26 genuine, 54 with one change each); no result for 0.
- Changes found: 50 of 54 (93 %); of those with a place on a page, 19 of 23 located (IoU of 0.5 or more).
- Genuine documents: 0 flags on 78 documents (0.000 per document); 0 of 26 genuine cases carry at least one; 20 limitations raised apart from those.
- Type recognised, digital: 150 of 150 documents (100 %).
- Type recognised, mild: 51 of 51 documents (100 %).
- Type recognised, 150dpi: 22 of 22 documents (100 %).
- Type recognised, 120dpi: 22 of 22 documents (100 %).
- Seconds per page, whole pipeline: digital 0.58, scan 4.16.
- Peak memory of the process: 813 MB.

## Detection by kind of change

| change | what | n | found | located | mean IoU | flagged elsewhere only | found by (cases) |
|---|---|---|---|---|---|---|---|
| D1 | incremental PDF edit | 6 | 6 (100 %) | 6 | 1.00 | 0 | pdf_revisions 6, statement_balance 3, cross_income 1, payslip_sums 1 |
| D2 | white cover, retyped (same font) | 6 | 6 (100 %) | 6 | 0.98 | 0 | pdf_overlay 6 |
| D4 | metadata edit | 6 | 6 (100 %) | n/a | n/a | 0 | pdf_meta 6 |
| D5 | picture pasted over | 6 | 6 (100 %) | 6 | 1.00 | 0 | pdf_overlay 6 |
| S1 | scan spliced from another scan | 5 | 2 (40 %) | 1 | 0.23 | 0 | cross_income 1, payslip_sums 1, scan_layout 1 |
| C1 | pay changed so the payslip still adds up | 5 | 5 (100 %) | n/a | n/a | 0 | cross_net_pay 5, cross_income 3 |
| C2 | name, address, employer or month changed in one document | 5 | 5 (100 %) | n/a | n/a | 0 | cross_name 2, cross_address 1, cross_dates 1, cross_employer 1 |
| C3 | statement submitted twice | 5 | 5 (100 %) | n/a | n/a | 0 | cross_duplicate 5 |
| C4 | signed in another hand | 5 | 5 (100 %) | n/a | n/a | 0 | signature 5 |
| C5 | another logo or stamp | 5 | 4 (80 %) | n/a | n/a | 0 | mark 4 |

The IoU counts a miss as 0. "Flagged elsewhere only" counts the changes for which the pipeline raised something on the changed document, but not near the changed place.

### Changes that differ in kind

- D4, application, producer InkPress PDF Studio 2.3: 2 of 2 found
- D4, payslip, producer Docuweave Pro 7.0: 2 of 2 found
- D4, statement, producer PageForge Editor 4.1: 2 of 2 found
- C1, fewer deductions: 2 of 2 found
- C1, more gross pay: 2 of 2 found
- C1, more gross pay and deductions in proportion: 1 of 1 found
- C2, address, minor: 1 of 1 found
- C2, employer, minor: 1 of 1 found
- C2, month, shift: 1 of 1 found
- C2, name, major: 1 of 1 found
- C2, name, minor: 1 of 1 found
- C4, signed in another hand: 5 of 5 found
- C5, logo, large: 2 of 2 found
- C5, logo, small: 0 of 1 found
- C5, stamp, large: 1 of 1 found
- C5, stamp, small: 1 of 1 found

### By medium

| medium | changes | found |
|---|---|---|
| digital | 39 | 38 (97 %) |
| mild | 8 | 7 (88 %) |
| 150dpi | 3 | 2 (67 %) |
| 120dpi | 4 | 3 (75 %) |

## Misses (4, all listed)

- dev-0021, S1, statement closing_balance (150dpi): only a limitation cites the changed document: statement_checks: Cannot fully verify this statement
- dev-0036, S1, application loan_amount (mild): only a limitation cites the changed document: context_emi: Context rule not applied: an input could not be used
- dev-0043, C5, logo, small (digital): no finding cites the changed document
- dev-0051, S1, application declared_monthly_income (120dpi): only a limitation cites the changed document: cross_income: Possible extraction error, verify: Declared income differs from the payslip gross earnings; context_emi: Context rule not applied: an input could not be used

## Flags on genuine documents (0, all listed)

- none

Limitations raised on genuine cases: statement_checks: Cannot fully verify this statement x7; context_emi: Context rule not applied: an input could not be used x3; cross_checks: Some cross-document comparisons could not be made x3; payslip_checks: Cannot fully verify this payslip x2; payslip_sums: Possible extraction error, verify: Gross earnings do not equal the earnings listed x2; cross_address: Possible extraction error, verify: Minor mismatch: address differs between documents x1; payslip_sums: Possible extraction error, verify: Total deductions do not equal the deductions listed x1; signature: Signatures only partly compared x1.

## Flags in changed cases that cite no changed document (0, all listed)

- none

## Scanned pages by quality class

The class is set by the sharpness of the page alone, before any OCR, and it decides what the pipeline says from the page: a value read from a degraded page is capped at confidence 0.50, from a poor page at 0.20 (a good page: 0.95), under the 0.6 below which a value is doubted; a conflict that cites a degraded or poor scanned page is shown as a limitation to verify, not as a finding; the scan and mark checks skip a poor page. A change that was not found on a scan may therefore sit on a page the pipeline had already set aside.

| medium | pages | good | degraded | poor |
|---|---|---|---|---|
| mild | 51 | 51 | 0 | 0 |
| 150dpi | 22 | 22 | 0 | 0 |
| 120dpi | 22 | 0 | 22 | 0 |

## Extraction on documents nobody changed

| layout | medium | kind | values | correct | wrong | wrong, trusted | missing | accuracy |
|---|---|---|---|---|---|---|---|---|
| A | digital | amount | 2570 | 2570 | 0 | 0 | 0 | 100.0 % |
| A | digital | date | 1108 | 1108 | 0 | 0 | 0 | 100.0 % |
| A | digital | id | 175 | 175 | 0 | 0 | 0 | 100.0 % |
| A | digital | text | 1717 | 1717 | 0 | 0 | 0 | 100.0 % |
| A | mild | amount | 922 | 922 | 0 | 0 | 0 | 100.0 % |
| A | mild | date | 404 | 404 | 0 | 0 | 0 | 100.0 % |
| A | mild | id | 63 | 62 | 1 | 1 | 0 | 98.4 % |
| A | mild | text | 617 | 617 | 0 | 0 | 0 | 100.0 % |
| A | 150dpi | amount | 400 | 352 | 0 | 0 | 48 | 88.0 % |
| A | 150dpi | date | 172 | 172 | 0 | 0 | 0 | 100.0 % |
| A | 150dpi | id | 28 | 28 | 0 | 0 | 0 | 100.0 % |
| A | 150dpi | text | 270 | 263 | 7 | 7 | 0 | 97.4 % |
| A | 120dpi | amount | 382 | 77 | 14 | 0 | 291 | 20.2 % |
| A | 120dpi | date | 165 | 165 | 0 | 0 | 0 | 100.0 % |
| A | 120dpi | id | 28 | 28 | 0 | 0 | 0 | 100.0 % |
| A | 120dpi | text | 262 | 166 | 72 | 0 | 24 | 63.4 % |

## Limits of this measurement

- The documents are synthetic and drawn by one generator. The dev and test splits share its six logo and stamp designs and its lists of names, addresses and employers, so the dev figures say little about styles the generator cannot draw. The test split adds a second layout (B) and two kinds of change (D3, S2) that the dev split never shows. Layout B was drawn after the spec files were final: about half of its labels, column headings and captions are wordings the spec files do not list (so a value under one is reported missing, not guessed), and it prints dates as 03-Nov-2026 without a weekday. It was written and read once, on digital drawings, before the test split was built; that read showed one defect in label matching (a label that is the start of a longer listed one, "Employer" in "Employer Name", left the rest of the label as the value), which was fixed; nothing else was changed for B.
- Each applicant's obligations are held to 40 % of income by construction, so the rule on the ratio of obligations to income has nothing to say about a genuine case here. It is not tested on genuine documents.
- D3 writes the new text in Arial, which the generator takes from the Windows fonts folder; the files of the test split are bit-for-bit reproducible only where Arial is installed. The hashes in the manifest identify exactly what was run.
- Table cells are compared by row number: one statement row the reader drops moves every row after it, and those count as wrong or missing even when each was read correctly.
- A change to an amount that the arithmetic checks cover (a balance, a credit that must match the payslip) is caught by those checks whatever the pixels show: the "found by" column says which detector did it. The loan amount on the application is covered by none, so it is the clean test of the pixel-level detectors.
- A change found near its place may have been found for another reason than the one planted; the manifest cannot tell.
- Scans are simulated from the same PDFs (blur, noise, a small rotation, JPEG), at three levels. A real scanner or camera is not simulated.
