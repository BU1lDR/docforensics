# Probe: numbers changed in documents printed by another program (7 Nov 2026)

This is a development measurement, not a held-out one. It asks two things the held-out splits cannot: does the tool still read documents whose producer, fonts and page designs it was not built around, and does it notice when a number in them has been changed? The documents are synthetic and fictional, like every document in this project. The pack and the edits were made by the same author as the tool, on the day of the runs, and the tool was changed between the first look at the unedited cases and the last run (see "Fixes made after looking"). The figures say what the current build does with these 24 cases and these edits. They are not a detection rate for documents that somebody else made, and no accuracy is claimed from them. The held-out figures are in the [README](../README.md).

## The pack

24 cases, `P5000000` to `P5000023` (generator seeds 5,000,000 to 5,000,023; no held-out split uses these seeds). A case holds a bank statement, a payslip and a loan application of one fictional person, written as HTML and printed to PDF by headless Microsoft Edge (producer "Skia/PDF m156", subset fonts embedded). They were not drawn by the generator the tool was developed on. There are nine page designs: statements in four houses (retail; serial, with S No. first and two-line headings; drcr, one Amount column with a Dr/Cr column beside it and balances printed with Cr; stacked, label above value), payslips in two (grid, stacked) and applications in three (numbered, sections, cards). They make 12 combinations of two cases each. Five statements (cases 0, 5, 10, 15, 20) run to two pages. The wordings are mostly ones the extraction specs list, but not all: the pay date of the 12 grid payslips is labelled "Paid On" and every payslip prints the net pay in words, and neither wording is in the specs. They are kept out of the specs on purpose, because the layout B figures in the README rely on wordings the specs have not seen. The tool ran with its defaults and without the local model.

## The edits

One document of a case is changed; the other two stay byte for byte as they were. What each kind of edit should trigger, and which kinds nothing should see, was written into the pack's list at 14:44, before the first run (14:45 to 15:03). Those marked "expected miss" in the table (88 edits) are the ones no check of the tool looks at.

| Kind | Edits | What was done |
|---|---|---|
| M1 | 168 | The text of one number is replaced inside the PDF (old text removed, new text inserted with PyMuPDF), in the built-in Helvetica or in the page's own font, file saved whole. Statement credit +10,000, payslip net pay +10,000, declared monthly income +20,000 (6 variants of 24), and the declared existing EMI halved, page's own font (24). |
| M2 | 144 | A white box is drawn over the number and the new number is written on it in the page's own font; the file is saved whole or as an incremental update. The same three numbers (6 variants of 24). |
| M3 | 96 | The file's metadata only, no number changed (4 variants of 24): a modification date 25 minutes after creation; Acrobat named as producer and creator with a modification date 40 minutes after creation; a producer name the metadata check does not list (PyMuPDF) with the date untouched; an incremental update that adds a catalog entry and changes nothing a reader sees. |
| M4 | 160 | The page's HTML is changed and printed again by Edge. Declared income +20,000 (24); net pay +10,000 and nothing else (24); net pay raised by cutting the TDS deduction so the payslip still adds up, which raises it by that cut only (24); gross and net pay both +10,000 (24); statement credit +10,000 and nothing else (24); statement credit +10,000 with every later balance carried through (24); one debit +5,000 with the balances carried through (8); loan amount +2,00,000 (8). |
| M6 | 20 | M1 and M2 on a debit of page 2 of the five two-page statements, +5,000, the balances left as they were (4 variants of 5). |
| M5 | 108 | Scanned pages: their own section below. |

## How an edit is scored

- **Found**: the edited case gives at least one finding that is not a limitation, that the unedited case did not give, and that cites the edited document. A finding of the same kind over fewer documents than before is not new. In 208 of the 588 edits above the same-producer observation (`cross_producer`) of the unedited case no longer covered the edited file, because the edit had changed its producer name (the 48 metadata edits that name an editor or an unlisted producer) or was a new print made later (the 160 reprints); that is counted neither as a find nor as a miss.
- **Located**: a box of such a finding, on the edited page, covers at least half of the rectangle that was edited. For all 413 edits located below, the smallest such box has 0.6 to 1.5 times the area of the edit, so none of them is a box around a page.
- **False**: a new finding that cites only documents that were not edited.

## Results on the current build

There are 588 edits of digital files. The first run was on 7 Nov from 14:45 to 15:03, on the build after the extraction fix described below. The second run, whose results are the current ones, was from 17:48 to 17:53 on commit `5411406`.

| Kind | Edits | Found, first run | Found, now | Located, first run | Located, now | False, now |
|---|---|---|---|---|---|---|
| M1 | 168 | 135 | 141 | 135 | 141 | 0 |
| M2 | 144 | 144 | 144 | 144 | 144 | 0 |
| M3 | 96 | 48 | 48 | 0 | 0 | 0 |
| M4 | 160 | 102 | 120 | 84 | 108 | 0 |
| M6 | 20 | 18 | 20 | 18 | 20 | 0 |
| All | 588 | 447 | 473 | 381 | 413 | 0 |

No new finding cited an unedited document in either run. Of the 588 edits, 88 were expected misses and none of them was found. Of the other 500, 473 were found, 27 missed and 413 located. The table below gives every variant. The last column is the first run.

| Edit | Edits | Found | Located | Found, first run |
|---|---|---|---|---|
| M1 statement credit, built-in font | 24 | 23 | 23 | 23 |
| M1 statement credit, page's font | 24 | 22 | 22 | 16 |
| M1 net pay, built-in font | 24 | 24 | 24 | 24 |
| M1 net pay, page's font | 24 | 24 | 24 | 24 |
| M1 declared income, built-in font | 24 | 24 | 24 | 24 |
| M1 declared income, page's font | 24 | 24 | 24 | 24 |
| M1 declared EMI halved (expected miss) | 24 | 0 | 0 | 0 |
| M2 statement credit, saved whole | 24 | 24 | 24 | 24 |
| M2 statement credit, incremental update | 24 | 24 | 24 | 24 |
| M2 net pay, saved whole | 24 | 24 | 24 | 24 |
| M2 net pay, incremental update | 24 | 24 | 24 | 24 |
| M2 declared income, saved whole | 24 | 24 | 24 | 24 |
| M2 declared income, incremental update | 24 | 24 | 24 | 24 |
| M3 modification date after creation | 24 | 24 | 0 | 24 |
| M3 editor named as producer | 24 | 24 | 0 | 24 |
| M3 producer not listed (expected miss) | 24 | 0 | 0 | 0 |
| M3 incremental update, nothing visible (expected miss) | 24 | 0 | 0 | 0 |
| M4 declared income +20,000 | 24 | 24 | 24 | 24 |
| M4 net pay +10,000, nothing else | 24 | 24 | 24 | 24 |
| M4 net pay up through the TDS cut, payslip adds up | 24 | 12 | 12 | 6 |
| M4 gross and net pay +10,000, payslip adds up | 24 | 24 | 12 | 24 |
| M4 statement credit +10,000, nothing else | 24 | 24 | 24 | 18 |
| M4 statement credit +10,000, balances carried through | 24 | 12 | 12 | 6 |
| M4 one debit +5,000, balances carried through (expected miss) | 8 | 0 | 0 | 0 |
| M4 loan amount +2,00,000 (expected miss) | 8 | 0 | 0 | 0 |
| M6 page-2 debit, covered, saved whole | 5 | 5 | 5 | 5 |
| M6 page-2 debit, covered, incremental update | 5 | 5 | 5 | 5 |
| M6 page-2 debit, built-in font | 5 | 5 | 5 | 4 |
| M6 page-2 debit, page's font | 5 | 5 | 5 | 4 |

**What found them.** Found, by check; the same edit can be found by several, so the rows do not add up to 473.

| Check | Found | Of which |
|---|---|---|
| `pdf_overlay` (a box over text) | 154 | M2 144, M6 10 |
| `cross_net_pay` (net pay against the statement's credit) | 104 | M1 44, M4 60 |
| `cross_income` (declared income against the payslip's gross) | 96 | M1 48, M4 48 |
| `statement_balance` (the running balance) | 78 | M1 44, M4 24, M6 10 |
| `pdf_revisions` (a second revision of the file) | 77 | M2 72, M6 5 |
| `payslip_sums` (gross minus deductions against net) | 72 | M1 48, M4 24 |
| `pdf_meta` (producer, creator and dates) | 48 | M3 48 |
| `pdf_fonts` (a figure in another font than its neighbours) | 42 | M1 39, M6 3 |

**What was not found.** 115 edits: the 88 expected misses and 27 others.

- 24 of the 27 are the two consistent edits on the 12 grid payslips (net pay raised through the TDS cut, 12; statement credit with balances carried through, 12). Those edits leave the page adding up, so the only thing that disagrees is the net pay against the statement's credit, and that comparison needs the pay date, which the grid payslips label "Paid On" and the tool does not read. The dossier of each says "Cannot fully verify this payslip" and "Some cross-document comparisons could not be made". The other 12 of each kind, on the stacked payslips, were found.
- 3 of the 27 are statement credits (cases 7 and 19) where the new number grew a digit and its glyphs overlap the currency sign or the text under it; the reader gives no value for the cell and the dossier says it cannot fully verify the statement.
- The expected misses: a halved declared EMI (the probe's statements carry no instalment line for the EMI check to compare with), a producer name that is not on the metadata check's list, an incremental save that changes nothing a reader sees, a debit changed with the balances carried through, and a loan amount that no other document repeats.

**What the results say about single checks.**

- Covering a number is found every time (M2 144 of 144, M6 10 of 10): the cover is a box over text, and the reader returns no value for the number under it. Redaction in M1 and M6, which removes the old text, is found by the arithmetic and cross-document checks and by the font check (below).
- The font check (`pdf_fonts`) compares a figure only with a column of at least four figures or a line of at least three. Of 77 numbers set in the built-in Helvetica, 42 stood in such a group and all 42 were flagged; the 35 that did not (net pay in 24 payslips, declared income in 6 applications, a statement credit in 3, a page-2 debit in 2) were not, and another check found 34 of them. Numbers set in the page's own font were not flagged by it (0 of 96 in M1). The check was not loosened to reach the 35: that would tune it to this pack's tool and printer.
- The metadata check found an editor's name and a later modification date in 24 of 24 files each, and put them nowhere in the document (located 0 of 48). A producer name that is not on its list and an incremental update with no visible change were not found (0 of 48).
- A page changed in its HTML and printed again is a new file, with no covered text and no second revision. Such edits were found only when a number disagreed with another number: 24 of 24 for the declared income, for the net pay alone and for the credit alone; 12 of 24 for the net pay raised through the TDS cut and for the credit with the balances carried through (the 12 whose pay date the tool reads); 0 of 16 for the debit carried through (8) and the loan amount (8). Raising gross and net pay together was found in all 24, by the declared income against the gross, but located in 12: in the other 12 the only finding sits on the gross, which that edit also changed, and not on the net pay that was scored.
- The new value was read in 333 of the 492 edits with a number to read: M1 163 of 168, M4 160 of 160, M6 10 of 20, M2 0 of 144. Under a cover the reader returns no value for the number (all 154 covers, M2 and M6), where it read the original with a confidence of 0.9 to 1.0; the cover is found by the overlay check instead.
- 136 edits gained 202 limitation lines the unedited case did not have ("Some cross-document comparisons could not be made", "Cannot fully verify this statement", "Context rule not applied: an input could not be used").

## Fixes made after looking

Three changes to the tool came out of this probe, each made with these same documents in front of it. The figures after a fix therefore say whether it did what it was written to do, not how the tool behaves on documents it was not written for.

- **Unedited cases, first look (13:58, commit `2093034`).** 20 of the 24 genuine cases carried at least one inconsistency (names 17 cases, accounts 15, addresses 9), because values were read from the wrong place. The credit was read right in 6 of 24 cases, the net pay in 12, the declared income in 9, the declared EMI in 9; the payslip was classified right in 12. Extraction was changed (`fed87d7`, 14:37): after it no case carried an inconsistency and the credit was read right in 18. The first edit run was on `2093034` with that change.
- **A Dr/Cr column (`2af2ad6`, 17:39).** The six statements of the drcr design were not read: their credits were missing. A reader for one Amount column with a Dr or Cr mark beside it was written for them. After it the credit was read right in 24 of 24 cases, and of the 146 edits made in those six cases 124 were found instead of 98 (located 112 instead of 80). Found and located did not change for the other 442 edits, and none of the 588 got worse. It has not been run on any other statement of that design, and no held-out split holds one.
- **Printed pages that carry no scanner grain (`0a8c40a`).** The scanned edits below showed that 15 of 18 clean printed pages carried an observation from a scan check, because the checks assume scanner grain. A page without grain is now not given to those checks, and its document says so. After it, 0 of 18.

Every difference between the two runs in the digital figures is in those six cases. Three commits between the runs changed how a table is read: `9c67ea7` and `cab741c` (amounts and dates that a scan misreads, found with other cases) and `2af2ad6` (above); the runs do not separate their effects. The check of the declared EMI (`97ed34c`) took no part: none of the 24 statements has an instalment, EMI or loan narration (the 38 places where the letters "emi" occur are the word "Premium"), so this probe did not exercise it.

## Scanned edits

Six cases (`P5000000`, `P5000001`, `P5000003`, `P5000004`, `P5000007`, `P5000008`) were rendered and saved as pictures at 150 dpi PNG, 200 dpi PNG and 200 dpi JPEG (quality 90), one number was painted out and a new one drawn (statement credit, net pay, declared income; in the document's TrueType face or in OpenCV's Hershey stroke font), and the picture wrapped as an image-only PDF: 6 cases x 3 media x 3 numbers x 2 methods = 108 edits, and 18 unedited controls (the same cases saved the same way). These pages are renderings, not scans of paper: they have no scanner grain or camera noise.

| | Edits | Found | Located | False |
|---|---|---|---|---|
| All | 108 | 88 | 88 | 0 |
| Declared income / net pay / statement credit | 36 each | 31 / 31 / 26 | 31 / 31 / 26 | 0 |
| TrueType face / Hershey strokes | 54 each | 44 / 44 | 44 / 44 | 0 |
| 150 dpi PNG / 200 dpi PNG / 200 dpi JPEG | 36 each | 31 / 29 / 28 | 31 / 29 / 28 | 0 |

All 88 were found by the arithmetic and cross-document checks (`cross_income` 31, `payslip_sums` 31, `statement_balance` 26, `cross_net_pay` on 3 of the payslips as well), none by a scan check, which skips these pages and says so. A change that leaves the arithmetic and the other documents consistent would not be found here either (see the reprints above). Of the 20 misses, 13 are shown in the dossier as "Possible extraction error, verify" limitation lines, where the number read had too little confidence to be compared, and the scorer counts them as not found; 7 numbers were not read at all. None of the six cases has a Dr/Cr statement.

One of the 18 controls (150 dpi PNG, the two-page statement `P5000000`) carries a false `statement_balance` inconsistency: the recogniser misread a balance. It is the only finding on any unedited case of either probe that is more than the same-producer observation, and it is not explained away: a misread number can look like an edited one.

## Unedited cases

The 24 genuine cases, on the current build: all three documents classified right; credit, net pay, declared income and declared EMI read right in 24 of 24; no inconsistency and no potential manipulation. Each case carries one observation (`cross_producer`: the three documents name the same producing software and were made minutes apart, which is how the pack was made) and three or four limitation lines: signatures and issuer marks only partly compared (24 each), "Cannot fully verify this payslip" (24, the pay date or the net pay in words is unread), and in the 12 grid-payslip cases "Some cross-document comparisons could not be made". The result of zero inconsistencies was reached after the extraction fix above, which was written against these same 24 cases, so it shows that these cases no longer break the tool, not that other printers' documents will not.

## What these figures do not show

- Nothing is measured on real documents, real banks or editing software other than the PyMuPDF and Edge used here. Real programs write their files differently from the way this pack's tools do.
- One author wrote the pack, the edits, the checks and the fixes. Nine page designs and 24 cases are a small sample, and the fixes above were made on exactly this sample.
- Every edit changes one number by 5,000 or more. Small changes, several changes at once, and changes made by someone who knows what the checks compare are not tried, except the consistent reprints above, which are mostly missed.
- A found edit means a finding appeared where one did not before. It is a lead for a reviewer, not a statement that the document was changed.
- The scanned edits are renderings with no scanner noise, so what the scan checks would say about a real scan of paper is not measured here.
- The tooling that built and ran the pack is not in the repository: it is written for the author's laptop (absolute paths, Edge, Windows fonts), and the 600 generated PDFs are not included. A clone cannot repeat the run. The per-edit record is, below.

## The record

[`eval/probe/digital.csv`](../eval/probe/digital.csv) has one row for each of the 588 digital edits: `id`, `kind`, `variant`, `case`, `expected_miss` (1 where no check was expected to see it), `found_first` and `located_first` (the first run), `found_now` and `located_now` (the current build), `false_now` (new findings that cite only unedited documents), and `detectors_now` (the checks that gave a new finding on the edited document). [`eval/probe/raster.csv`](../eval/probe/raster.csv) has the 108 scanned edits (`found`, `located`, `false`, `detectors`) and the 18 controls, whose `detectors` column lists every finding that is not a limitation as `check:class`. The tables above are counted from these files by `tests/test_probe_record.py`, which fails if the document and the files disagree. The figures about the unedited cases, the limitation lines, what the reader read, the size of the located boxes and which numbers stood in a group the font check compares come from the same runs but are not in the files. The limitations that follow from this probe are in [limitations.md](limitations.md).
