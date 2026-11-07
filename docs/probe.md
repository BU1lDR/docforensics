# Probe: numbers changed in documents printed by another program (7 Nov 2026)

This is a development measurement, not a held-out one. It asks two things the held-out splits cannot: does the tool still read documents whose producer, fonts and page designs it was not built around, and does it notice when a number in them has been changed? The documents are synthetic and fictional, like every document in this project. The pack and the edits were made by the same author as the tool, on the day of the runs, and the tool was changed between the first look at the unedited cases and the last run (see "Fixes made after looking"). The figures say what the current build does with these 24 cases and these edits. They are not a detection rate for documents that somebody else made, and no accuracy is claimed from them. The held-out figures are in the [README](../README.md). A second probe, on 24 unedited cases in other page designs, is the last section of this document; its results are separate from everything above it.

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

There are 588 edits of digital files. The first run was on 7 Nov from 14:45 to 15:03, on the build after the extraction fix described below. The second run was from 17:48 to 17:53 on commit `5411406`. A third run, whose results are the current ones, repeated all 588 digital and all 126 scanned documents (the scanned ones are further down) from 19:38 to 19:54 on commit `e74c052`, which holds the last fix in the list below. Compared document by document with the earlier runs, it differs in one scanned control and in no digital edit.

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

Four changes to the tool came out of this probe, each made with these same documents in front of it. The figures after a fix therefore say whether it did what it was written to do, not how the tool behaves on documents it was not written for.

- **Unedited cases, first look (13:58, commit `2093034`).** 20 of the 24 genuine cases carried at least one inconsistency (names 17 cases, accounts 15, addresses 9), because values were read from the wrong place. The credit was read right in 6 of 24 cases, the net pay in 12, the declared income in 9, the declared EMI in 9; the payslip was classified right in 12. Extraction was changed (`fed87d7`, 14:37): after it no case carried an inconsistency and the credit was read right in 18. The first edit run was on `2093034` with that change.
- **A Dr/Cr column (`2af2ad6`, 17:39).** The six statements of the drcr design were not read: their credits were missing. A reader for one Amount column with a Dr or Cr mark beside it was written for them. After it the credit was read right in 24 of 24 cases, and of the 146 edits made in those six cases 124 were found instead of 98 (located 112 instead of 80). Found and located did not change for the other 442 edits, and none of the 588 got worse. It has not been run on any other statement of that design, and no held-out split holds one.
- **Printed pages that carry no scanner grain (`0a8c40a`).** The scanned edits below showed that 15 of 18 clean printed pages carried an observation from a scan check, because the checks assume scanner grain. A page without grain is now not given to those checks, and its document says so. After it, 0 of 18.
- **A table row left out (`e74c052`).** One of the 18 scanned controls, the 150 dpi PNG of the two-page statement `P5000000`, carried a false `statement_balance` inconsistency. It was traced to a transaction row the reader had left out: the recogniser had drawn the box of a date wider than its text, so date and narration became one cell, the cell stood under the narration heading, the row had no date in its first column and went missing with its amounts, and the balance chain broke by exactly that row. A date at the start of a cell that stands under the date heading now goes to that heading, and the rest of the cell to the heading it would have gone to (`tests/test_wide_date_box.py`, four tests, written first and failing before the change). The third run above repeated every document: only that control changed, and it now carries no finding. No number in the tables of this document moved.

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

None of the 18 controls carries a finding that is not a limitation line. The earlier runs had one: the 150 dpi PNG of the two-page statement `P5000000` carried a false `statement_balance` inconsistency, the only finding on any unedited case of either probe that was more than the same-producer observation. This document first put it down to a misread balance; it was a transaction row the reader had left out (the fix `e74c052`, above). It shows that a number the reader loses can look like an edited one, and the fix was made on this one case.

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

## Second probe: other page designs, unedited cases (7 Nov 2026)

This is a development measurement, not a held-out one, and nothing in it was edited. It asks two things: are genuine documents in page designs the readers were not written for read, and does the tool raise findings on them that it should not? The documents are synthetic and fictional. One author wrote the pack, the checks and the fixes, and every fix below was made with these documents in view, so a figure after a fix says whether the fix did what it was written to do, not how the tool behaves on documents it was not written for. No edit pass was made on this pack, so it says nothing about finding edited documents. The held-out figures are in the [README](../README.md).

### The pack

24 cases, `P5000024` to `P5000047` (generator seeds 5,000,024 to 5,000,047; no held-out split uses these seeds). A case holds a bank statement, a payslip and a loan application of one fictional person, saved as PDF by one of three programs: headless Microsoft Edge printing HTML (producer "Skia/PDF m156"; the first probe used Edge alone), Microsoft Word 2024, or PyMuPDF Story. Of the 72 PDFs, 44 are Edge, 14 Word and 14 Story, counted from the producer fields (statements 18, 3 and 3; payslips 14, 5 and 5; applications 12, 6 and 6). They were not drawn by the generator the tool was developed on, and their page designs are not the ones its specs were written for.

There are seven statement designs (3 or 4 cases each), five payslip designs (4 or 5 cases each) and four application designs (6 cases each). The statement designs differ in how they set the table: DR, CR and BAL headings; one Withdrawal(Dr) / Deposit(Cr) column in which every amount and balance ends in (Dr) or (Cr); one signed Amount column; separate debit, credit and balance columns (a ledger); credit and balance side by side; a layout made with PyMuPDF Story; and three long statements that run over several pages with a repeated heading. The payslip designs differ in where the earnings and deductions stand and in what the columns are: earnings and deductions side by side in one table with one amount column each; the same with Current and YTD columns; two stacked tables with Amount and YTD columns; a list of "name: amount" lines; and a deductions table above the earnings table. The application designs differ in how the form is set: a bordered grid of label and value cells; numbered questions; a label followed by an underlined value; and two columns of small blocks with the label above the value. The tool ran with its defaults and without the local model.

Every document was also rendered to a picture at 150 dpi and at 200 dpi and saved as an image-only PDF. These pages are renderings, not scans of paper: they carry no scanner grain or camera noise. The three long statements were rebuilt once. In the first version the repeated heading of page 2 was printed over a running banner, their baselines 3 pt apart, OCR merged the two lines, and the scanned statements read 406 of 1080 table cells at 150 dpi and 290 at 200 dpi. That was a fault of the pack, not of the tool, and the figures below are from the rebuilt statements.

### What the first look found

On the digital pass (build `1bdfe67`) the 24 unedited cases carried 17 inconsistency findings, in 15 cases. Eight were differences the pack plants on purpose: an employer written "(P) Ltd." against "Pvt. Ltd." (3 cases), a middle initial left out (3), and an address in another form (2). The tool should report these, as minor mismatches or as observations of form. One kind was graded in a way that did not match the limitation text: "(P)" kept its P and was graded a minor mismatch (3 cases). Reading the code for it showed a second gap that no case of the pack shows: a name with a whole word left out ("Rahul Kumar Sharma" against "Rahul Sharma", 0.80 alike) came out as a plain mismatch. Both were corrected in `3e9b0bc`. The other 9 were false: values read from the wrong place at confidence 0.90 to 1.00, namely the account number read as the neighbouring label "DeclaredMonthly" (6 applications), a year read as the opening balance (2 statements), and a tenure of 48 read as the employer (1 application).

### Fixes made after looking

Each fix has tests of its own, listed with it. None was measured on documents it was not written for.

- **A wrapped label is not a value** (`8cb5ca0`, `tests/test_wrapped_label.py`). In the application design that sets a four-column grid, a label such as "Declared Monthly Income" goes over two lines, and its first line was read as the account number (6 of 24 applications, each a false account conflict). The first line of a label that goes on, and the line that finishes it, are never read as a value; the value is left unread and the dossier says so. Not covered: the true value, centred between the two label lines, is still not read.
- **A balance dated in its label** (`b3fa7e1`, `tests/test_as_on_balance.py`). "Opening Balance as on 1 Jan 2026 : amount": the date qualifier is passed over, and a bare year under a dated label is never the value. Two false balance flags gone. Not covered: a colon glued to the amount on a scan (the last fix below).
- **A name or an employer needs a letter** (`3a7b508`, `tests/test_name_needs_letters.py`). The tenure "48" is not an employer. One false employer conflict gone. Not covered: a bare number elsewhere (an instalment of 2,000 is read as one), and an employer written with digits ("3M") is still read.
- **A short bracket at the end of a heading is a unit** (`42a999b`, `tests/test_extraction_layouts.py`). A scan that read the rupee sign in "Credit (₹)" as another glyph left a heading that named no column, so every credit or balance of the page was reported as not found in the table header (7 of 20 heading lines at 150 dpi, in all three long statements). On the three rebuilt long statements, scanned: 150 dpi, 1046 of 1080 cells right before and 1079 after; 200 dpi, 822 before and 835 after. Not covered: a bracket of more than three characters ("Credit (Cash)").
- **A date whose month a scan cut short is a row** (`5868d8f`, `tests/test_date_rows.py`). Once the previous fix made the column readable, a date read as "09-M-26" left its row out of the table, and the balance chain broke by exactly that row (a false "the balance in row 18 does not follow" on one long statement at 200 dpi). The row now stays a row with a date that does not read, as "O3/05/2026" already did; the dossier names "date in row 18" as not readable, and the row's amounts are read and checked. Not covered: letters among the digits of the day or the year ("03-Mar-2O26").
- **Two amounts read as one cell are two cells** (`19c37ae`, `tests/test_merged_amount_cells.py`, with the 242 OCR words of one stored page as a fixture). In the statement design that prints credit and balance side by side, a scan's line reader joins the two amounts into one cell; the Credit heading was then widened over the Balance column, balances were read as credits (confidence 0.95, and 1.00 on a digital page), and the balance chain broke by exactly that amount. A cell of amounts and nothing else is now cut where the heading it stands under changes. Replayed on the stored OCR words of 596 table documents from 46 stored runs: 10 documents change and 586 do not. Every changed cell was missing and is now right (54 at 200 dpi, 56 at 150 dpi, 38 on the digital pages), or was a wrong value in a column that is empty and is now empty (18, 18 and 16); none was right and is now wrong. The false inconsistencies of four statements at 200 dpi and two at 150 dpi are gone, and no finding is new. Not covered: a pair of which OCR damaged one digit, and a single balance whose box straddles two headings (both found by reading the code, not seen in these cases).
- **A space inside a word is a form** (`63aac7a`, `tests/test_cross.py`). A scan split "IRONWOOD" into "IRONW OOD" (employer read at confidence 0.90 on a genuine case, P5000043), and the employer and the payer were reported as different. Names, address parts and employers that have the same letters in the same order and differ only in where the spaces fall are now reported as written differently, an observation, not a mismatch. A changed letter is still a mismatch (guard test).
- **The title of a page is not a row of the form** (`1857f82`, `tests/test_title_above_labels.py`). The employer of a payslip and the bank of a statement are read from the tallest line of page 1. At 150 dpi the boxes of OCR are noisy by about three pixels on thirty-eight, so a row of the form can be the tallest: on two of the five payslips of one design, "Employee Name Kurian, Nikhil B. Employee Code EMP-9384" was read as the employer at 0.90 and gave a false employer conflict. When the tallest line holds a label or a column heading of the document type, the title is now the tallest line above the first line that holds one. A first form of the rule, which looked above the first label always, was tried on every stored case and replaced: it took "Page 1 of 1" for the bank of statements turned half a turn, where the tallest line had read the bank right. Checked on every stored document that has a title field (7,849, read again from their stored words): 4 pick another line than before (the two payslips, each stored twice), all 4 now the right one, none the other way. Not covered: when the first line holds both the bank name and a label (P5000024 at 150 dpi), nothing stands above the first row, so a tall row can still be taken as the bank. The bank name is compared with nothing, so no finding follows; for a payslip the same shape could give a false employer conflict.
- **A colon directly in front of an amount is not part of the amount** (`d928be0`, `tests/test_glued_colon.py`). A scan read "Opening Balance as on 1 Jan 2026 :2,53,102.32" with the colon and the amount as one word, ":2,53,102.32", which is not an amount, so the opening balance stayed unread, the statement was reported as not fully verifiable, and the first stretch of the balance chain, from the opening balance to the first row, was not tested. The shape handled is a colon directly in front of an amount with cents and nothing else, in a header field of kind amount; the field keeps what was printed as its raw text. A time ("12:30"), an amount without cents, a colon behind the amount, two colons, a colon in front of a word, a table cell and any text field stay as they were. Replayed on the stored OCR words of every stored run (61 run folders, 3,352 cases, 879 distinct documents): 15 documents change and 864 do not; the 16 changed fields were all unread and are now read (7 opening balances and 1 closing balance of scanned statements, and 8 declared instalments of scanned applications), and the checks run again on those 15 cases give the same inconsistency findings (7 and 7), the same observations (12 and 12) and no new finding of any class. Not covered: a colon glued to an account number or another id (kept in the value as printed, e.g. ":TST-6156967204" on 4 of 4 statements of the credit-and-balance design, at both resolutions; no finding came from it), a colon glued to a table cell, and an amount whose digits OCR damaged.

### Where the tool stands on this pack

The figures below are from the whole pack run again on build `d928be0`, with the defaults and without the local model: the digital pass over the 24 cases, and the pictures at 150 dpi and 200 dpi (the 21 cases that are not long statements, plus the three rebuilt long statements run on their own). Every run finished and no case raised an error. The development report on the same build gives 52 of 54 changes found, 20 of 23 located and no flag on 78 genuine documents ([`eval/dev.md`](../eval/dev.md)). This pack is not part of that report, and its "no flag" cannot be repeated for it: the report counts every observation as a flag, and this pack plants differences that the tool reports as observations.

**Findings by class**, all 24 cases in every pass:

| Pass | Inconsistency | Observation | Potential manipulation |
|---|---|---|---|
| Digital | 5 | 58 | 0 |
| Pictures at 150 dpi | 5 | 32 | 0 |
| Pictures at 200 dpi | 5 | 31 | 0 |

The 5 inconsistency findings are the same in every pass, and each is a difference the pack plants: a middle initial left out of one document ("Minor mismatch" on the name; `P5000029`, `P5000037`, `P5000045`) and an address written in another form ("Minor mismatch" on the address; `P5000039`, where the state is added, and `P5000047`, where "No." stands in front of the flat number). There is no sixth finding of this class, and no difference of these two kinds went unreported. The other planted differences give observations or nothing: 12 employer names with the legal form written another way ("Employer is written differently"), name case, order and title ("Name is written differently", 18 in each pass), and 23 masked account numbers against full ones (no finding). In the digital pass the 58 observations are 20 "same producing software, made minutes apart" (`cross_producer`, one in each of 20 cases), 12 employer, 18 name and 8 from the font check. A picture has no producer field and no fonts, so the pictures show only the employer and name observations (14 and 18 at 150 dpi, 13 and 18 at 200 dpi); the employer observations above 12 are a scan splitting a word with a space ("IRONW OOD", 2 at 150 dpi and 1 at 200 dpi).

**The font check on genuine payslips.** The 8 font-check observations of the digital pass ("Value set in a different colour from the values beside it (page 1)") stand 2 on each of the 4 genuine payslips of the design that sets the deductions table above the earnings table (`P5000028`, `P5000033`, `P5000038`, `P5000043`). That design prints its two total rows in white on a dark bar, so a figure stands in a different colour from the others in its column. They are observations, not inconsistencies, and a reviewer can dismiss them, but they are alarms on genuine documents: the check cannot tell a design colour from a changed value (limitation 68). The pictures carry no fonts, so none appears there.

**Table cells.** A table cell is one value of a transaction row or a payslip line (date, narration, debit, credit, balance; item name, amount). "Right" means read as printed, "wrong" read differently from what was printed, "not read" nothing read, which the dossier says. Every column counts all 24 cases: the pictures of the three long statements are in the long row, and their payslips in the payslip rows. The loan applications have no table (24 documents, header fields only).

| Design (cases) | Digital: right / wrong / not read | 150 dpi | 200 dpi |
|---|---|---|---|
| Statement, DR, CR and BAL headings (4) | 28 / 0 / 300 | 14 / 0 / 314 | 14 / 0 / 314 |
| Statement, one signed Amount column (3) | 126 / 0 / 42 | 124 / 0 / 44 | 126 / 0 / 42 |
| Statement, one Withdrawal(Dr) / Deposit(Cr) column (4) | 56 / 0 / 168 | 50 / 5 / 169 | 56 / 0 / 168 |
| Statement, ledger (3) | 272 / 0 / 0 | 272 / 0 / 0 | 272 / 0 / 0 |
| Statement, credit and balance side by side (4) | 188 / 36 / 0 | 179 / 42 / 3 | 182 / 42 / 0 |
| Statement, PyMuPDF Story layout (3) | 204 / 0 / 68 | 204 / 0 / 68 | 173 / 25 / 74 |
| Statement, long (3) | 1080 / 0 / 0 | 1079 / 1 / 0 | 1073 / 4 / 3 |
| Payslip, deductions table above earnings (4) | 0 / 0 / 56 | 0 / 0 / 56 | 0 / 0 / 56 |
| Payslip, side by side, one amount column each (5) | 40 / 8 / 22 | 40 / 5 / 25 | 40 / 7 / 23 |
| Payslip, list of "name: amount" lines (5) | 0 / 0 / 70 | 0 / 0 / 70 | 0 / 0 / 70 |
| Payslip, side by side with Current and YTD columns (5) | 0 / 0 / 70 | 0 / 0 / 70 | 0 / 0 / 70 |
| Payslip, two stacked tables with Amount and YTD columns (5) | 40 / 0 / 30 | 40 / 0 / 30 | 40 / 0 / 30 |

- Four of the seven statement designs, and all five payslip designs, are read in part or not at all (limitation 65). Where the amounts of a statement are not read, the balance chain is not tested. In the digital pass exactly the 14 statements of those four designs carry a limitation line of their own (3 "Cannot verify the transactions: no table found", 11 "Cannot fully verify this statement", which names what is missing, for example "balance in all 14 rows; debit or credit in all 14 rows"); the other 10 carry none. All 24 payslips carry "Cannot fully verify this payslip". No inconsistency came from a gap.
- The side-by-side statements are read in every date, amount and balance. Their wrong cells (36 digital, 42 on the pictures) are narrations of two or three lines that are read in part.
- Header fields of the loan applications the tool left unread: 36 in the digital pass (declared monthly income 12, tenure 12, address 6, account number 6), 38 at 150 dpi and 34 at 200 dpi. Each is named in a limitation line of the cross-checks ("the address in D3 (loan application) could not be read").
- Compared with the same 21 cases that are not long statements, run on `5868d8f` (the build before `1857f82`; the commit is identified from the times of those runs, because their logs do not record it), header fields and table cells together, 2,362 per picture pass: at 150 dpi 61 cells that were not read and 2 that were wrong (an employer) are right now, at 200 dpi 57 that were not read; no cell that was right is wrong or missing. The three rebuilt long statements (1,206 cells per pass) do not differ. No finding of any class is new.

**Wrong values.** Counted from the stored runs, header and table cells together. Most are compared by no check, which is why they gave no finding; they are listed because they are wrong at a high confidence.

| Kind of value | Digital | 150 dpi | 200 dpi |
|---|---|---|---|
| Narration read in part, or of a row read one row off | 36 | 43 | 55 |
| Bank name read as another line of page 1 | 7 | 7 | 7 |
| Deduction name with an amount in front of it | 8 | 5 | 7 |
| Account number with a colon in front, kept as printed | 0 | 11 | 11 |
| Masked account number with its star lost | 0 | 0 | 3 |
| Date or balance of a row read one row off | 0 | 5 | 16 |
| Period start (a range whose hyphen a scan glues to the first date) | 0 | 1 | 2 |
| Employer with a space inside a word | 0 | 2 | 1 |
| Address cut short | 0 | 1 | 0 |
| Wrong cells in all | 51 | 75 | 102 |
| Of these, at confidence 0.90 or more | 51 | 69 | 92 |

The confidence of a value does not separate these from the right ones, so the sentence "no amount, date or id was both wrong and trusted" of the held-out report holds for the documents of the project's own generator, not for these designs (limitation 66). Of the wrong cells, 5 at 150 dpi and 25 at 200 dpi are not misreadings of a value: a row was lost, and the cells after it were read one row off, which the scorer, pairing rows by number, counts as wrong.

**Lost rows.** Three statements read 13 of their 14 rows on a picture: `P5000037` and `P5000044` at 200 dpi (the Story layout) and `P5000039` at 150 dpi (the Withdrawal(Dr) / Deposit(Cr) column). In the first two, OCR read a date and the first word of the narration as one word ("11.05.2026ECS/Electricity", confidence 1.00). A word that starts with a date and goes on with letters is not a date, so the row had nothing to hold it, its wrapped narration line joined the next row, and every later row was read one row off; these are the only two words of that shape among the words of the six runs behind these figures. In `P5000039` the three words of the date are in the OCR output, with the position and height of the dates around them, and the cause is not found. In these two designs the debit and credit of every row are not read, so the balance chain is not tested and no finding follows.

### What the second probe does not show

- **Real documents.** Every document is synthetic, from three programs and sixteen page designs. The renderings carry no scanner grain, skew or camera noise.
- **Documents the tool was not changed for.** One author wrote the pack, the checks and the fixes, and each fix was made with these documents in view. A figure above says what the tool does after the fix, on these documents; it does not say what it does on a fourth program's output or a seventeenth design.
- **Edits.** No edit pass was made on this pack, so it says nothing about finding edited documents in these designs.
- **A table that is not read.** For documents in the designs that are read in part or not at all, the tool says what it could not read and checks nothing in the missing part (limitation 65).
- **Values wrong at a high confidence that no check compares.** Narrations, the bank name, deduction names and an account number or id with a colon in front (limitation 66). The colon is kept as printed, and no account-number finding came from it.
- **A statement period.** Printed as one range, whose hyphen a scan glues to the first date, it is read as the second date alone (`P5000041` at both resolutions, `P5000034` at 200 dpi, confidence 0.90) or, written as one word, not at all (`P5000027`). The date check needs both ends, so none was made. A masked account number lost its star in three cases at 200 dpi (confidence 0.67 to 0.81), and the postcode of one address was cut at 150 dpi (`P5000040`). None gave a finding.
- **The title of a page.** When the first line holds both the bank name and a label (`P5000024` at 150 dpi), nothing stands above a row of the form, and a tall row can be taken for the bank (limitation 67).
- **Lost rows.** Three statements, one with a cause not found (above).
- **Two shapes of an amount cell** found by reading the code, not seen in a case: a pair of amounts of which OCR damaged one digit, and a single balance whose box straddles two headings.
- **The font check** reports a design colour (limitation 68).
- **The tooling.** The code that built and ran this pack is not in the repository, and the documents are not included, so a clone cannot repeat the run. The figures are counts from the stored runs.
