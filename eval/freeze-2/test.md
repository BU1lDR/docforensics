# Evaluation of the test split

Cases 0 to 143 of the test split (seeds 2000000 to 2000143), run on 2026-11-08 11:03 India Standard Time with the pipeline at commit bb08c8e. Windows 10, Python 3.11.9, 6 cores, CPU only. The numbers are what the run printed: nothing was selected or tuned to make them look better.

## How a result is counted

A change is **found** when the pipeline raised a finding that is an observation, an inconsistency or potential manipulation (never a processing limitation, and never a cluster, which repeats its members) and that

- for a change with a place on a page (D1, D2, D3, D5, S1, S2): cites the changed document, on the changed page, with a box that overlaps the changed box at an IoU (intersection over union) of at least 0.1. It is **located** at an IoU of at least 0.5. The IoU shown is the best of the document's findings, 0 for a miss;
- for a change without one: comes from a detector expected for that change (D4: pdf_meta or cross_producer; C1 and C2: any cross_* check; C3: cross_duplicate; C4: signature; C5: mark) and cites the changed document (for a duplicate, either copy).

A limitation is never a find. A case that produced no result is a miss. On a genuine case every such finding is a flag, counted per document; its limitations are counted apart. A flag in a changed case that cites no changed document is listed as off target; it is not counted against the pipeline, because a cross-document check may rightly cite only the other document of a pair. Extraction is scored on documents nobody changed, value by value (amounts, dates and ids exactly, text up to case and spacing), by the name of the field and, in a table, its row number. A value the pipeline did not extract counts as missing. A wrong value is **trusted** when its confidence is at or above the limit below which the pipeline doubts a value (0.6): nothing warned of it.

## Summary

- Cases: 144 (48 genuine, 96 with one change each); no result for 0.
- Changes found: 83 of 96 (86 %); of those with a place on a page, 40 of 48 located (IoU of 0.5 or more).
- Genuine documents: 2 flags on 144 documents (0.014 per document); 1 of 48 genuine cases carry at least one; 113 limitations raised apart from those.
- Type recognised, digital: 256 of 256 documents (100 %).
- Type recognised, mild: 92 of 92 documents (100 %).
- Type recognised, 150dpi: 46 of 46 documents (100 %).
- Type recognised, 120dpi: 46 of 46 documents (100 %).
- Seconds per page, whole pipeline: digital 0.41, scan 3.41.
- Peak memory of the process: 875 MB.

## Detection by kind of change

| change | what | n | found | located | mean IoU | flagged elsewhere only | found by (cases) |
|---|---|---|---|---|---|---|---|
| D1 | incremental PDF edit | 8 | 8 (100 %) | 8 | 1.00 | 0 | pdf_revisions 8, payslip_sums 3, statement_balance 3, cross_income 2, cross_net_pay 1, payslip_words 1 |
| D2 | white cover, retyped (same font) | 8 | 8 (100 %) | 8 | 0.98 | 0 | pdf_overlay 8 |
| D3 | white cover, retyped (near font; test split only) | 8 | 8 (100 %) | 8 | 0.98 | 0 | pdf_fonts 8, pdf_overlay 8 |
| D4 | metadata edit | 8 | 8 (100 %) | n/a | n/a | 0 | pdf_meta 8 |
| D5 | picture pasted over | 8 | 8 (100 %) | 8 | 1.00 | 0 | pdf_overlay 8 |
| S1 | scan spliced from another scan | 8 | 4 (50 %) | 2 | 0.33 | 1 | learned_patches 2, payslip_sums 2, ela 1, scan_layout 1 |
| S2 | scan erased, retyped (test split only) | 8 | 6 (75 %) | 6 | 0.62 | 0 | ela 4, learned_patches 3, scan_noise 2, statement_balance 2, cross_net_pay 1, payslip_sums 1, payslip_words 1 |
| C1 | pay changed so the payslip still adds up | 8 | 5 (62 %) | n/a | n/a | 0 | cross_income 5, cross_net_pay 2 |
| C2 | name, address, employer or month changed in one document | 8 | 6 (75 %) | n/a | n/a | 0 | cross_name 3, cross_employer 2, cross_address 1 |
| C3 | statement submitted twice | 8 | 8 (100 %) | n/a | n/a | 0 | cross_duplicate 8 |
| C4 | signed in another hand | 8 | 8 (100 %) | n/a | n/a | 0 | signature 8 |
| C5 | another logo or stamp | 8 | 6 (75 %) | n/a | n/a | 0 | mark 6 |

The IoU counts a miss as 0. "Flagged elsewhere only" counts the changes for which the pipeline raised something on the changed document, but not near the changed place.

### Changes that differ in kind

- D4, application, producer InkPress PDF Studio 2.3: 2 of 2 found
- D4, payslip, producer Docuweave Pro 7.0: 3 of 3 found
- D4, statement, producer PageForge Editor 4.1: 3 of 3 found
- C1, fewer deductions: 0 of 3 found
- C1, more gross pay: 3 of 3 found
- C1, more gross pay and deductions in proportion: 2 of 2 found
- C2, address, major: 0 of 1 found
- C2, address, minor: 1 of 1 found
- C2, employer, major: 1 of 1 found
- C2, employer, minor: 1 of 1 found
- C2, month, shift: 0 of 1 found
- C2, name, major: 1 of 1 found
- C2, name, minor: 2 of 2 found
- C4, signed in another hand: 8 of 8 found
- C5, logo, large: 2 of 2 found
- C5, logo, small: 0 of 2 found
- C5, stamp, large: 2 of 2 found
- C5, stamp, small: 2 of 2 found

### By medium

| medium | changes | found |
|---|---|---|
| digital | 60 | 58 (97 %) |
| mild | 18 | 13 (72 %) |
| 150dpi | 9 | 7 (78 %) |
| 120dpi | 9 | 5 (56 %) |

## Misses (13, all listed)

- test-0009, S2, application declared_monthly_income (mild): only a limitation cites the changed document: cross_checks: Some cross-document comparisons could not be made; context_emi: Context rule not applied: an input could not be used
- test-0025, S1, statement closing_balance (150dpi): only a limitation cites the changed document: statement_checks: Cannot fully verify this statement; cross_checks: Some cross-document comparisons could not be made
- test-0028, C1, fewer deductions (digital): only a limitation cites the changed document: payslip_checks: Cannot fully verify this payslip; cross_checks: Some cross-document comparisons could not be made
- test-0043, S1, application loan_amount (mild): no finding cites the changed document
- test-0052, C5, logo, small (120dpi): only a limitation cites the changed document: statement_checks: Cannot fully verify this statement; cross_checks: Some cross-document comparisons could not be made
- test-0079, S1, statement credit (mild): flagged elsewhere on the changed document (best IoU 0.00 against the changed box)
- test-0082, C1, fewer deductions (120dpi): only a limitation cites the changed document: payslip_checks: Cannot fully verify this payslip; cross_checks: Some cross-document comparisons could not be made
- test-0084, C2, month, shift (mild): only a limitation cites the changed document: cross_checks: Some cross-document comparisons could not be made
- test-0117, S2, statement closing_balance (mild): only a limitation cites the changed document: statement_checks: Cannot fully verify this statement
- test-0120, C2, address, major (120dpi): only a limitation cites the changed document: cross_address: Possible extraction error, verify: Mismatch: address differs between documents; context_emi: Context rule not applied: an input could not be used
- test-0124, C5, logo, small (150dpi): only a limitation cites the changed document: statement_checks: Cannot fully verify this statement
- test-0133, S1, payslip net_pay (120dpi): only a limitation cites the changed document: payslip_checks: Cannot fully verify this payslip; cross_checks: Some cross-document comparisons could not be made
- test-0136, C1, fewer deductions (digital): only a limitation cites the changed document: payslip_checks: Cannot fully verify this payslip; cross_checks: Some cross-document comparisons could not be made

## Flags on genuine documents (2, all listed)

By detector: learned_patches 1, scan_layout 1.

- test-0143 (120dpi), scan_layout, observation: Text lies out of line with the text around it (page 1) [01_statement.jpg]
- test-0143 (120dpi), learned_patches, observation: Words that learned measures set apart from the page (page 1) [01_statement.jpg]

Limitations raised on genuine cases: statement_checks: Cannot fully verify this statement x30; context_emi: Context rule not applied: an input could not be used x27; payslip_checks: Cannot fully verify this payslip x27; cross_checks: Some cross-document comparisons could not be made x26; cross_account: Possible extraction error, verify: Mismatch: account number differs between documents x1; cross_address: Possible extraction error, verify: Minor mismatch: address differs between documents x1; cross_income: Possible extraction error, verify: Declared income differs from the payslip gross earnings x1.

## Flags in changed cases that cite no changed document (0, all listed)

- none

## Scanned pages by quality class

The class is set by the sharpness of the page alone, before any OCR, and it decides what the pipeline says from the page: a value read from a degraded page is capped at confidence 0.50, from a poor page at 0.20 (a good page: 0.95), under the 0.6 below which a value is doubted; a conflict that cites a degraded or poor scanned page is shown as a limitation to verify, not as a finding; the scan and mark checks skip a poor page. A change that was not found on a scan may therefore sit on a page the pipeline had already set aside.

| medium | pages | good | degraded | poor |
|---|---|---|---|---|
| mild | 92 | 92 | 0 | 0 |
| 150dpi | 46 | 46 | 0 | 0 |
| 120dpi | 46 | 0 | 46 | 0 |

## Extraction on documents nobody changed

| layout | medium | kind | values | correct | wrong | wrong, trusted | missing | accuracy |
|---|---|---|---|---|---|---|---|---|
| A | digital | amount | 2228 | 2228 | 0 | 0 | 0 | 100.0 % |
| A | digital | date | 975 | 975 | 0 | 0 | 0 | 100.0 % |
| A | digital | id | 143 | 143 | 0 | 0 | 0 | 100.0 % |
| A | digital | text | 1469 | 1469 | 0 | 0 | 0 | 100.0 % |
| A | mild | amount | 908 | 908 | 0 | 0 | 0 | 100.0 % |
| A | mild | date | 385 | 385 | 0 | 0 | 0 | 100.0 % |
| A | mild | id | 69 | 69 | 0 | 0 | 0 | 100.0 % |
| A | mild | text | 625 | 621 | 4 | 4 | 0 | 99.4 % |
| A | 150dpi | amount | 260 | 233 | 0 | 0 | 27 | 89.6 % |
| A | 150dpi | date | 106 | 106 | 0 | 0 | 0 | 100.0 % |
| A | 150dpi | id | 24 | 24 | 0 | 0 | 0 | 100.0 % |
| A | 150dpi | text | 190 | 186 | 4 | 4 | 0 | 97.9 % |
| A | 120dpi | amount | 300 | 80 | 0 | 0 | 220 | 26.7 % |
| A | 120dpi | date | 126 | 122 | 0 | 0 | 4 | 96.8 % |
| A | 120dpi | id | 24 | 23 | 1 | 0 | 0 | 95.8 % |
| A | 120dpi | text | 210 | 166 | 44 | 0 | 0 | 79.0 % |
| B | digital | amount | 2580 | 2351 | 0 | 0 | 229 | 91.1 % |
| B | digital | date | 1141 | 1104 | 0 | 0 | 37 | 96.8 % |
| B | digital | id | 153 | 0 | 0 | 0 | 153 | 0.0 % |
| B | digital | text | 1667 | 567 | 0 | 0 | 1100 | 34.0 % |
| B | mild | amount | 444 | 380 | 0 | 0 | 64 | 85.6 % |
| B | mild | date | 184 | 174 | 0 | 0 | 10 | 94.6 % |
| B | mild | id | 42 | 0 | 0 | 0 | 42 | 0.0 % |
| B | mild | text | 326 | 153 | 3 | 3 | 170 | 46.9 % |
| B | 150dpi | amount | 306 | 241 | 0 | 0 | 65 | 78.8 % |
| B | 150dpi | date | 119 | 109 | 1 | 0 | 9 | 91.6 % |
| B | 150dpi | id | 32 | 0 | 0 | 0 | 32 | 0.0 % |
| B | 150dpi | text | 232 | 114 | 5 | 5 | 113 | 49.1 % |
| B | 120dpi | amount | 438 | 55 | 1 | 0 | 382 | 12.6 % |
| B | 120dpi | date | 194 | 118 | 48 | 0 | 28 | 60.8 % |
| B | 120dpi | id | 31 | 0 | 0 | 0 | 31 | 0.0 % |
| B | 120dpi | text | 295 | 108 | 5 | 0 | 182 | 36.6 % |

## Limits of this measurement

- The documents are synthetic and drawn by one generator. The dev and test splits share its six logo and stamp designs and its lists of names, addresses and employers, so the dev figures say little about styles the generator cannot draw. The test split adds a second layout (B) and two kinds of change (D3, S2) that the dev split never shows. Layout B was drawn after the spec files were final: about half of its labels, column headings and captions are wordings the spec files do not list (so a value under one is reported missing, not guessed), and it prints dates as 03-Nov-2026 without a weekday. It was written and read once, on digital drawings, before the test split was built; that read showed one defect in label matching (a label that is the start of a longer listed one, "Employer" in "Employer Name", left the rest of the label as the value), which was fixed; nothing else was changed for B.
- Each applicant's obligations are held to 40 % of income by construction, so the rule on the ratio of obligations to income has nothing to say about a genuine case here. It is not tested on genuine documents.
- D3 writes the new text in Arial, which the generator takes from the Windows fonts folder; the files of the test split are bit-for-bit reproducible only where Arial is installed. The hashes in the manifest identify exactly what was run.
- Table cells are compared by row number: one statement row the reader drops moves every row after it, and those count as wrong or missing even when each was read correctly.
- A change to an amount that the arithmetic checks cover (a balance, a credit that must match the payslip) is caught by those checks whatever the pixels show: the "found by" column says which detector did it. The loan amount on the application is covered by none, so it is the clean test of the pixel-level detectors.
- A change found near its place may have been found for another reason than the one planted; the manifest cannot tell.
- Scans are simulated from the same PDFs (blur, noise, a small rotation, JPEG), at three levels. A real scanner or camera is not simulated.
