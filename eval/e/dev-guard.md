# Compression-history check on the scans of the dev split (a guard, not a measure)

Run: 2026-11-06 00:59 India Standard Time, commit 4ff0a02, Windows 10, Python 3.11.9, 6 cores, CPU only.
Cases 0 to 79 of the dev split (the same cases as eval/dev.md), picture files only; the check looks at their pixels. The pack in eval/e/ is what the check was tuned on; nothing here was used to set a constant. Constants of forensics/ela.py: QUALITIES=25..95 step 5, GAP=10, MIN_DIP=1.3, INK=60, BLOCK=16, MIN_INK=24, Z=6.0, MAX_DIP=1.3, MIN_CELLS=4, MIN_RATIO=2.0, LISTED=6.
In this split every scan is a 200-DPI JPEG saved at its level's quality (85, 50, 35); S1 and S2 end with one more save at quality 85. On a `mild` scan that makes both saves 85, which the check cannot tell apart, so no region is expected there; at 150dpi and 120dpi the earlier save is 50 or 35.

## In short

- Scans of genuine cases (nothing changed): 45 scans, a region on 0.
- Scans in changed cases that were not themselves changed as a picture: 45 scans, a region on 0.
- S1 (part of another scan pasted in): 5 scans, a region on 1, touching the edit on 1, at the edit (IoU above 0.3) on 1.

## S1 and S2 scans

| case | file | edit | level | last save found | earlier save found | regions | touching | located |
|---|---|---|---|---|---|---|---|---|
| dev-0006 | 02_payslip.jpg | S1 | mild | 85 | - | 0 | no | no |
| dev-0021 | 01_statement.jpg | S1 | 150dpi | 85 | 50 | 1 | yes | yes |
| dev-0036 | 03_application.jpg | S1 | mild | 85 | - | 0 | no | no |
| dev-0051 | 03_application.jpg | S1 | 120dpi | 85 | 35 | 0 | no | no |
| dev-0066 | 01_statement.jpg | S1 | mild | 85 | - | 0 | no | no |

## Regions on scans nobody changed as a picture

None.

## Every scan

| case | file | kind | level | last save found | earlier save found | regions |
|---|---|---|---|---|---|---|
| dev-0005 | 01_statement.jpg | genuine | mild | 85 | - | 0 |
| dev-0005 | 02_payslip.jpg | genuine | mild | 85 | - | 0 |
| dev-0005 | 03_application.jpg | genuine | mild | 85 | - | 0 |
| dev-0006 | 01_statement.jpg | other | mild | 85 | - | 0 |
| dev-0006 | 02_payslip.jpg | S1 | mild | 85 | - | 0 |
| dev-0006 | 03_application.jpg | other | mild | 85 | - | 0 |
| dev-0008 | 01_statement.jpg | genuine | 150dpi | 50 | - | 0 |
| dev-0008 | 02_payslip.jpg | genuine | 150dpi | 50 | - | 0 |
| dev-0008 | 03_application.jpg | genuine | 150dpi | 50 | - | 0 |
| dev-0010 | 01_statement.jpg | other | mild | 85 | - | 0 |
| dev-0010 | 02_payslip.jpg | other | mild | 85 | - | 0 |
| dev-0010 | 03_application.jpg | other | mild | 85 | - | 0 |
| dev-0010 | 04_statement_copy.jpg | other | mild | 85 | - | 0 |
| dev-0012 | 01_statement.jpg | other | 120dpi | 35 | - | 0 |
| dev-0012 | 02_payslip.jpg | other | 120dpi | 35 | - | 0 |
| dev-0012 | 03_application.jpg | other | 120dpi | 35 | - | 0 |
| dev-0014 | 01_statement.jpg | genuine | mild | 85 | - | 0 |
| dev-0014 | 02_payslip.jpg | genuine | mild | 85 | - | 0 |
| dev-0014 | 03_application.jpg | genuine | mild | 85 | - | 0 |
| dev-0020 | 01_statement.jpg | genuine | 150dpi | 50 | - | 0 |
| dev-0020 | 02_payslip.jpg | genuine | 150dpi | 50 | - | 0 |
| dev-0020 | 03_application.jpg | genuine | 150dpi | 50 | - | 0 |
| dev-0021 | 01_statement.jpg | S1 | 150dpi | 85 | 50 | 1 |
| dev-0021 | 02_payslip.jpg | other | 150dpi | 50 | - | 0 |
| dev-0021 | 03_application.jpg | other | 150dpi | 50 | - | 0 |
| dev-0023 | 01_statement.jpg | genuine | mild | 85 | - | 0 |
| dev-0023 | 02_payslip.jpg | genuine | mild | 85 | - | 0 |
| dev-0023 | 03_application.jpg | genuine | mild | 85 | - | 0 |
| dev-0025 | 01_statement.jpg | other | 120dpi | 35 | - | 0 |
| dev-0025 | 02_payslip.jpg | other | 120dpi | 35 | - | 0 |
| dev-0025 | 03_application.jpg | other | 120dpi | 35 | - | 0 |
| dev-0025 | 04_statement_copy.jpg | other | 120dpi | 35 | - | 0 |
| dev-0027 | 01_statement.jpg | other | mild | 85 | - | 0 |
| dev-0027 | 02_payslip.jpg | other | mild | 85 | - | 0 |
| dev-0027 | 03_application.jpg | other | mild | 85 | - | 0 |
| dev-0029 | 01_statement.jpg | genuine | 150dpi | 50 | - | 0 |
| dev-0029 | 02_payslip.jpg | genuine | 150dpi | 50 | - | 0 |
| dev-0029 | 03_application.jpg | genuine | 150dpi | 50 | - | 0 |
| dev-0035 | 01_statement.jpg | genuine | mild | 85 | - | 0 |
| dev-0035 | 02_payslip.jpg | genuine | mild | 85 | - | 0 |
| dev-0035 | 03_application.jpg | genuine | mild | 85 | - | 0 |
| dev-0036 | 01_statement.jpg | other | mild | 85 | - | 0 |
| dev-0036 | 02_payslip.jpg | other | mild | 85 | - | 0 |
| dev-0036 | 03_application.jpg | S1 | mild | 85 | - | 0 |
| dev-0038 | 01_statement.jpg | genuine | 120dpi | 35 | - | 0 |
| dev-0038 | 02_payslip.jpg | genuine | 120dpi | 35 | - | 0 |
| dev-0038 | 03_application.jpg | genuine | 120dpi | 35 | - | 0 |
| dev-0040 | 01_statement.jpg | other | mild | 85 | - | 0 |
| dev-0040 | 02_payslip.jpg | other | mild | 85 | - | 0 |
| dev-0040 | 03_application.jpg | other | mild | 85 | - | 0 |
| dev-0040 | 04_statement_copy.jpg | other | mild | 85 | - | 0 |
| dev-0042 | 01_statement.jpg | other | 150dpi | 50 | - | 0 |
| dev-0042 | 02_payslip.jpg | other | 150dpi | 50 | - | 0 |
| dev-0042 | 03_application.jpg | other | 150dpi | 50 | - | 0 |
| dev-0044 | 01_statement.jpg | genuine | mild | 85 | - | 0 |
| dev-0044 | 02_payslip.jpg | genuine | mild | 85 | - | 0 |
| dev-0044 | 03_application.jpg | genuine | mild | 85 | - | 0 |
| dev-0050 | 01_statement.jpg | genuine | 120dpi | 35 | - | 0 |
| dev-0050 | 02_payslip.jpg | genuine | 120dpi | 35 | - | 0 |
| dev-0050 | 03_application.jpg | genuine | 120dpi | 35 | - | 0 |
| dev-0051 | 01_statement.jpg | other | 120dpi | 35 | - | 0 |
| dev-0051 | 02_payslip.jpg | other | 120dpi | 35 | - | 0 |
| dev-0051 | 03_application.jpg | S1 | 120dpi | 85 | 35 | 0 |
| dev-0053 | 01_statement.jpg | genuine | mild | 85 | - | 0 |
| dev-0053 | 02_payslip.jpg | genuine | mild | 85 | - | 0 |
| dev-0053 | 03_application.jpg | genuine | mild | 85 | - | 0 |
| dev-0055 | 01_statement.jpg | other | 150dpi | 50 | - | 0 |
| dev-0055 | 02_payslip.jpg | other | 150dpi | 50 | - | 0 |
| dev-0055 | 03_application.jpg | other | 150dpi | 50 | - | 0 |
| dev-0055 | 04_statement_copy.jpg | other | 150dpi | 50 | - | 0 |
| dev-0057 | 01_statement.jpg | other | mild | 85 | - | 0 |
| dev-0057 | 02_payslip.jpg | other | mild | 85 | - | 0 |
| dev-0057 | 03_application.jpg | other | mild | 85 | - | 0 |
| dev-0059 | 01_statement.jpg | genuine | 120dpi | 35 | - | 0 |
| dev-0059 | 02_payslip.jpg | genuine | 120dpi | 35 | - | 0 |
| dev-0059 | 03_application.jpg | genuine | 120dpi | 35 | - | 0 |
| dev-0065 | 01_statement.jpg | genuine | mild | 85 | - | 0 |
| dev-0065 | 02_payslip.jpg | genuine | mild | 85 | - | 0 |
| dev-0065 | 03_application.jpg | genuine | mild | 85 | - | 0 |
| dev-0066 | 01_statement.jpg | S1 | mild | 85 | - | 0 |
| dev-0066 | 02_payslip.jpg | other | mild | 85 | - | 0 |
| dev-0066 | 03_application.jpg | other | mild | 85 | - | 0 |
| dev-0068 | 01_statement.jpg | genuine | 150dpi | 50 | - | 0 |
| dev-0068 | 02_payslip.jpg | genuine | 150dpi | 50 | - | 0 |
| dev-0068 | 03_application.jpg | genuine | 150dpi | 50 | - | 0 |
| dev-0070 | 01_statement.jpg | other | mild | 85 | - | 0 |
| dev-0070 | 02_payslip.jpg | other | mild | 85 | - | 0 |
| dev-0070 | 03_application.jpg | other | mild | 85 | - | 0 |
| dev-0070 | 04_statement_copy.jpg | other | mild | 85 | - | 0 |
| dev-0072 | 01_statement.jpg | other | 120dpi | 35 | - | 0 |
| dev-0072 | 02_payslip.jpg | other | 120dpi | 35 | - | 0 |
| dev-0072 | 03_application.jpg | other | 120dpi | 35 | - | 0 |
| dev-0074 | 01_statement.jpg | genuine | mild | 85 | - | 0 |
| dev-0074 | 02_payslip.jpg | genuine | mild | 85 | - | 0 |
| dev-0074 | 03_application.jpg | genuine | mild | 85 | - | 0 |
