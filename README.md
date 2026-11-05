# docforensics

Offline document forensics for a human investigator. A case of scanned and digital documents goes in. An investigation dossier comes out, and every finding in it is traced to a box on a page of a stored source file.

It is a solo entry by Aryan to the DataOps Innovation Hackathon 2026 (Hack The Core), for the problem statement on AI-powered document forensics and contextual intelligence.

The tool lists anomalies for a reviewer. It does not decide whether a document is authentic and it does not name intent. Observations, inconsistencies, candidates for closer review and limits of the analysis are kept apart, and what a finding means is the reviewer's decision. **Every document used to build and test it is synthetic:** read [docs/limitations.md](docs/limitations.md) before reading anything into a result.

## What it does

- **Several documents in one case.** PDF, PNG and JPEG, typed by their first bytes, limited in size, pages and number, hashed and stored read-only. A file that is refused or cannot be read becomes a visible limitation, not a crash.
- **Reading, offline.** The text layer of a digital PDF, or RapidOCR for a scan, gives every word a box. Scanned pages are classed by sharpness, because the recogniser's own confidence does not flag misread digits.
- **Understanding.** Each document is classified, and its fields and table cells are extracted with a confidence and a location. Bank statements, payslips and loan applications have a spec each (one drawn layout each). Document types are data, in TOML files; anything else is reported as `unknown`.
- **Visual and file forensics.** Digital PDFs: saved revisions, text covered by a shape or picture, hidden text, fonts of figures and dates, file metadata. Scans: image grain and the placement of words. Across documents: the shape of the signature, of the logo and of the stamp.
- **Contextual intelligence.** Within a document: balance chain, totals, net pay against its words, dates, weekday. Across documents: name, address, employer, account number, net pay against the bank credit, declared income against earnings, dates, duplicate files, the same producing software. Two context rules against a synthetic reference.
- **Relationships between findings.** Findings that cite the same field, the same place on a page or the same name, address, employer or account are grouped. A group is ranked by how many independent kinds of check fired in it.
- **Entities across documents.** The names, addresses, employers and account numbers that the documents write are listed as entities (two writings are one entity when the cross-document checks grade them as the same, or the same apart from form), with the places where each is written and the findings that touch it. Fixed rules on top of those checks, not a trained graph model; it finds no aliases and its accuracy was not measured.
- **An optional local model.** Off unless you ask for it. With `--llm`, a small model running on this computer words the headline of each group of findings and suggests relations, a summary and a reading order. A guard checks it first, it cannot add, change or remove a finding, and everything it says is labelled as inference. See [The language model](#the-language-model).
- **Evidence you can follow.** Each finding names its document, page and box, with a marked crop. `trace` follows it to the stored file and checks the file against its sha256.
- **A dossier.** One self-contained HTML file and one JSON file: overview, extracted information, contextual analysis, visual forensic findings, evidence and traceability, investigation summary, and appendices with the audit trail, the capability matrix and the limitations.
- **A review desk.** A page in the browser on this computer for upload, page images with word, field and finding boxes, evidence, reviewer actions and the dossier download.
- **An audit trail.** Every submission, step, failure, model use, dossier build and reviewer action is an event, each carrying the hash of the one before. `verify-audit` checks the chain.

How the pieces fit is in [docs/architecture.md](docs/architecture.md).

## Set up

Python 3.11 or newer. It was developed and tested on Windows 11 with Python 3.11.9; no other system has been tried.

```
git clone https://github.com/BU1lDR/docforensics.git
cd docforensics
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

On a system other than Windows, activate with `source .venv/bin/activate`. Installing needs the internet once. After that nothing in the tool uses the network: the OCR models are inside the RapidOCR package, and the review desk answers on `127.0.0.1` only.

## Use

Analyse documents as one case. Each path is a file, or a folder (the files directly inside it):

```
python -m docforensics run statement.pdf payslip.pdf application.pdf
```

It prints the case id, the documents it recognised and the findings, and writes everything to `data/cases/<case id>/`, including `dossier.html` and `dossier.json`. `--data DIR` changes where cases are kept and `--config thresholds.toml` overrides the thresholds it names (the names are the fields of `Thresholds` in [config.py](src/docforensics/config.py); every finding prints the thresholds it used). In the benchmark, OCR took 1 to 2 seconds per A4 page at 200 dpi on a CPU-only laptop.

Open the review desk, then go to http://127.0.0.1:8000/ in a browser:

```
python -m docforensics serve
```

Upload the documents on the Documents tab. The Findings tab lists what was found, with the evidence, the explanation and the reviewer actions; the Clusters tab shows related findings together; the Relationships tab draws the names, addresses, employers and account numbers the documents write, with the findings that touch them; the Audit trail, Capabilities and Dossier tabs hold the rest. `--port` changes the port.

Follow a finding to its source, and check that the audit trail has not been changed:

```
python -m docforensics trace C-20261104-153000-ab12 F-003
python -m docforensics verify-audit C-20261104-153000-ab12
```

`trace` prints the document, the stored file and its sha256 (and whether the file still matches it), the page and the box in pixels and in PDF points, and the value read there.

### Try it on the sample data

[sample_data/](sample_data/) holds five small cases, each a bank statement, a payslip and a loan application: one genuine, three with a planted change that the tool finds and one with a planted change that it misses. Run the first:

```
python -m docforensics run sample_data/dev-0000
```

It prints three findings: a closing balance changed in a later saved revision of the PDF, seen two ways (the earlier revision still holds the old text, and the transactions do not give the new balance), and the group that holds both. `run` ends with the command that follows a finding to its file. Use the case id and a finding id it printed:

```
python -m docforensics trace C-20261105-103000-ab12 F-001
python -m docforensics verify-audit C-20261105-103000-ab12
```

The date and time in a case id, in the audit trail and in the dossier are UTC. IST is UTC+05:30, so a run at 16:00 IST has 10:30 in its id. The dossier is `data/cases/<case id>/dossier.html`. One made from dev-0000 is kept as [sample_data/dossier-dev-0000.html](sample_data/dossier-dev-0000.html), with its data in [dossier-dev-0000.json](sample_data/dossier-dev-0000.json): open the HTML file in a browser after cloning, because GitHub shows only its source.

These five cases are from the development split, the split on which the thresholds were tuned. They show the tool working from files to dossier; they are not evidence of how well it detects. The held-out figures are in [eval/test.md](eval/test.md). One of the five, dev-0043 (a slightly changed logo), is a miss. [sample_data/README.md](sample_data/README.md) says what the tool reports on each case, and `python -m pytest tests/test_e2e_sample.py` checks those statements against a real run.

### Tests

```
pip install -r requirements-dev.txt
python -m pytest
```

The suite takes several minutes because some tests load the OCR engine; `python -m pytest -m "not ocr"` leaves those out. The tests run with connections to public addresses blocked.

## Demonstration documents

The `datagen/` package draws fictional bank statements, payslips and loan applications as PDFs whose content is known, applies one planted change to some of the cases (each change records what was done and where, in the pixel frame the tool reports) and simulates scans at several quality levels. Institutions carry TEST in their names; no real logo, person or identity document is used. The tests use it to check each detector against known truth. The generator's font-substitution manipulation reads Arial from the Windows fonts folder and does not run elsewhere. The tool does not use the generator.

The demonstration dataset is its output: a development split of 80 cases and a test split of 144, each case being one applicant's statement, payslip and loan application (a statement submitted twice adds a fourth file). In the test split 48 cases are genuine and 96 carry one change each, of twelve kinds: in a digital PDF an incremental edit, a cover retyped in the same font or in a near font, a metadata edit, a picture pasted over text; in a scan a paste from another scan, or text erased and retyped; across the documents a pay figure changed so that the payslip still adds up, a name, address, employer or month changed in one document, a statement submitted twice, a signature in another hand, another logo or stamp. A `manifest.json` per split holds the truth for every case. The test split is about 130 MB, so it is generated, not committed (from the repository folder; `data/` is not part of the repository):

```
python -m datagen.build test data/test-split --cases 144
```

## Evaluation

The figures below come from `python -m evaluation.run_eval`. Its reports are committed as they were written: [eval/dev.md](eval/dev.md) for the development split and [eval/test.md](eval/test.md) for the test split. Each one states how a result is counted, lists every miss and every flag on a genuine document, and ends with the limits of its measurement.

**How it was run.** The detectors were written and their thresholds set on the development split (80 cases, one drawn layout, "A"). The test split (144 cases, layouts A and B) was generated and run once, after the code was frozen (git tag `spec-freeze`, commit 28ef833), and nothing was changed in response to its results. It holds what development never showed: a second layout, "B", drawn after the extraction specs were final, and two kinds of change (a cover retyped in a near font, a scan erased and retyped). One defect in label matching, found by reading layout B once on digital drawings before the test split was built, was fixed; eval/test.md says so. A change counts as found when the tool raised an observation, an inconsistency or a potential-manipulation finding on the changed document, at the changed place where the change has one. A limitation ("could not be checked") is never a find. A finding on a genuine document is a flag.

**Result on the test split** (the pipeline without a language model):

- Changes found: 79 of 96 (82 %). Of the 48 with a place on a page, 37 were located (boxes overlapping at 0.5 or more).
- Genuine documents: 1 flag on 144 documents, a scan at 120 dpi (placement check). The tool also raised 116 limitations on genuine cases, apart from that flag.
- Document type recognised: 440 of 440.
- Time and memory on the author's laptop (6 cores, CPU only): 0.53 s per digital page and 4.39 s per scanned page, peak 866 MB. Timing depends on what else the machine is doing: the same splits run again on the final source took 0.35 s and 2.33 s per page for the test split (peak 868 MB), and 2.37 s per scanned page for the development split, which took 4.16 s in the committed report. The cause of the difference was not established.

| Change | What | Found (of 8) | Located |
|---|---|---|---|
| D1 | incremental edit of a PDF | 8 | 8 |
| D2 | white cover, text retyped in the same font | 8 | 8 |
| D3 | white cover, text retyped in a near font | 8 | 8 |
| D4 | metadata edit | 8 | n/a |
| D5 | picture pasted over text | 8 | 8 |
| S1 | scan spliced from another scan | 3 | 2 |
| S2 | scan erased and retyped | 3 | 3 |
| C1 | pay figure changed so the payslip still adds up | 5 | n/a |
| C2 | name, address, employer or month changed in one document | 6 | n/a |
| C3 | statement submitted twice | 8 | n/a |
| C4 | signed in another hand | 8 | n/a |
| C5 | another logo or stamp | 6 | n/a |

By medium: digital 58 of 60, mild scan 13 of 18, 150 dpi scan 6 of 9, 120 dpi scan 2 of 9. The development split, which the thresholds were set on and is therefore not a held-out figure, gave 50 of 54 changes found and no flag on 78 genuine documents.

**Misses.** All 17 are listed in eval/test.md, each with what the tool did raise. Fifteen left only limitations on the changed document: a value a check needed was not read, so the tool said it could not make the comparison, or a conflict on a 120 dpi scan was shown as a possible extraction error to verify. One has no finding on the changed document (test-0043) and one has a finding elsewhere on it (test-0079). They fall in these groups: spliced or retyped scans (10 of 16), a pay figure changed with fewer deductions (all 3), a small logo (both), a month shift (mild scan) and a major address change (120 dpi).

**Extraction**, on the documents nobody changed, value by value against the generator's truth (16,226 values: 13,105 read right, 155 wrong, 2,966 missing). Share read right:

| Layout | Medium | Amounts | Dates | Ids | Text |
|---|---|---|---|---|---|
| A | digital | 100 % | 100 % | 100 % | 100 % |
| A | mild scan | 100 % | 100 % | 100 % | 99.4 % |
| A | 150 dpi | 89.6 % | 100 % | 100 % | 97.9 % |
| A | 120 dpi | 20.3 % | 96.8 % | 95.8 % | 61.0 % |
| B | digital | 91.1 % | 96.8 % | 0 % | 34.0 % |
| B | mild scan | 85.6 % | 94.6 % | 0 % | 46.9 % |
| B | 150 dpi | 78.8 % | 91.6 % | 0 % | 49.1 % |
| B | 120 dpi | 11.4 % | 60.8 % | 0 % | 21.4 % |

A value the tool does not find is reported missing and never guessed. A value read wrongly and still given a confidence of 0.6 or more is the dangerous case, because nothing warns of it: there were 16, all of them text; no amount, date or id. Pages at 120 dpi are classed degraded by their sharpness, which caps the confidence of what is read from them and turns conflicts that rest on them into "verify" limitations.

**What these figures do not show.**

- They are about synthetic documents drawn by one generator. The two splits share its six logo and stamp designs and its lists of names, addresses and employers. Nothing is measured on real documents, scanners or layouts.
- The extraction specs list the wordings of labels, column headings and captions of layout A. Layout B uses other wordings for about half of them, and it is read far worse than A (no id, 34 % of the text on digital pages). Whatever depends on a value that is not read is left unchecked; for every genuine statement and payslip of layout B the within-document checks said so.
- 8 cases per kind of change is a small sample, and one run. A difference of one or two cases between kinds of change means little. The overall 82 % is a count over this particular mix of changes, not a property of the tool: it is 58 of 60 on digital files and 21 of 36 on scans.
- The flag rate of 1 in 144 holds for clean synthetic documents. Real genuine documents differ in more ways, and the ordinary causes of each finding are in [docs/limitations.md](docs/limitations.md).
- The obligations rule is not tested on genuine documents (the generator holds obligations to 40 % of income), the grouping of findings is not scored, and no language model took part in the evaluation.

No accuracy is claimed beyond these figures. A document with no finding is not thereby shown to be unchanged, and a finding is a lead for a reviewer.

**To repeat it.** The run takes about 20 minutes on the laptop and, like the generator's near-font cover, needs Windows with Arial. `--out` keeps it from overwriting the committed reports:

```
python -m evaluation.run_eval --split test --out data/eval-test
```

The report records the commit it ran on and whether the working tree had changes. The test split was run once, at `spec-freeze`. The tool's code has changed in two places since, besides the wording of the capability notes in `capabilities.json`, and `git diff spec-freeze HEAD -- src` shows them. `pdf_overlay.py` and `pdf_fonts.py` put the evidence boxes of a PDF page stored turned (`/Rotate`) in the wrong frame. `understand/layout.py` and `read/__init__.py` read a page that stands on its side (a scan or a PDF page turned a quarter turn) as poor quality, because such a page gave false conflicts between documents; one sentence in `checks/within.py` was reworded to match. Neither change was prompted by a result on the test split: the first came from reading the code against a list of inputs the tests did not cover, the second from trying turned pages on development cases. Neither split holds a turned page. [Limitation 36](docs/limitations.md) says what is still not handled. After these changes both splits were run again on the final source, from a copy of it: every count was the same as in the committed reports (test split 79 of 96 found and 1 flag on 144 genuine documents; development split 50 of 54 and none on 78), and only the times differ. Those two reports say "commit unknown" because the copy had no git history, and they are not kept.

## Capability matrix

Each capability is marked Implemented, Partial, Planned or Unsupported. A status changes only when the evidence for it does, and Tests counts the automated tests that back the row. The table is written from [capabilities.json](src/docforensics/capabilities.json), the file the dossier and the review desk print. After that file changes, rebuild this table with `python -m docforensics.capabilities --update` from the repository folder.

<!-- capabilities:start -->
| Capability | Status | Tests | Note |
|---|---|---|---|
| Multi-document ingestion with file-type checks, limits and hashing | Implemented | 3 | PDF, PNG and JPEG by their first bytes. By default 10 MB, 20 pages and 10 documents per case. Files are stored under their sha256; a rejected file becomes a limitation with a reason. |
| Document classification | Partial | 3 | Rules over words and layout. Three types have a spec at this build (bank statement, payslip, loan application), written for one drawn layout each; anything else is 'unknown' and says so. Wording that differs from the specs' may also read as 'unknown'. Held-out (eval/test.md): the type was recognised for all 440 documents, on both drawn layouts, digital and scanned; all of them are of the three supported types, so a fourth kind of document is not tested. A local-model fallback is not built. |
| Text-layer reading and OCR (offline) | Implemented | 6 | Every word has a box in page pixels. Scanned pages get a quality class from sharpness, not from the recogniser's score; numbers read from a degraded or poor page are flagged, not trusted. OCR output is a reading, not ground truth. A page that stands on its side (a scan or a PDF page turned a quarter turn) is read as poor and the dossier says why; a page turned half a turn is not recognised (limitation 36). Held-out (eval/test.md), on documents nobody changed: no amount, date or id was both wrong and trusted; 16 text values were. |
| Structured extraction: fields and tables, each with a confidence and a location | Partial | 4 | Bank statements, payslips and loan applications, digital and scanned (scans are simulated at three levels), on the drawn layouts the specs were written for. A column or label that is not found is reported as missing, never filled in, and nothing repairs a misread digit or separator. How many values come out right, wrong or missing, by kind of value and scan level, is measured by the evaluation, not by the tests (eval/test.md). Held-out, on documents nobody changed: layout A, which the specs were written for, is read right in every amount, date, id and text value on digital pages, and on mild scans in every amount, date and id and in 99.4 % of text values (4 of 625 wrong, and trusted); at 150 dpi 89.6 % of amounts are read and the rest are missing, and at 120 dpi 20.3 % are read (12 wrong, none trusted). Layout B was drawn after the specs were final, and about half of its labels, column headings and captions are wordings the specs do not list, so it is read much less: on digital pages 91 % of amounts, 97 % of dates and 34 % of text values, and no id. None of the values not read on those pages was wrong; each is reported missing. No amount, date or id was wrong and also trusted, in either layout; 16 text values were. A deduction beside an empty earnings cell is not read as a row. Other document types and layouts are not built. |
| Digital PDF forensics: comparison of saved revisions | Partial | 3 | Text that differs between a PDF's earlier saved version and a later one is reported as an observation, with the old and the new text. Held-out: found and located in 8 of 8 incremental edits (D1), and raised on no genuine document. The other digital checks are in the next row. |
| Digital PDF forensics: covered and hidden text, pictures over text, fonts, file metadata | Partial | 7 | Reported as observations with the measured values: text still in the file but drawn under a filled rectangle or a picture that comes after it (the text written over a covering rectangle is cited too); a figure or date set in a different font, size or colour from the others in its column or on its line; text that is invisible, under 2 pt or off the page; a producer or creator that names PDF-editing software; a modification date later than the creation date. Held-out, 8 cases each, all found and (for D2, D3 and D5) located at the changed place: a cover with the text retyped in the same font (D2), the same in a near font (D3, a change the development set never showed), a metadata edit (D4) and a picture over text (D5); none of these checks raised a finding on a genuine document. Every case comes from one generator, and real editing software varies. Not built: text hidden by its colour, covers that are not rectangles, bold against regular. |
| Scan and image forensics | Partial | 9 | Two checks on scanned pages that are not of poor quality, both shown as observations: words whose image grain differs from the page median, and words set out of line after the page is straightened (a word against its row, a figure's right edge against its column, a figure's height against the page's other figures). Held-out (eval/test.md): of 16 scans changed by pasting from another scan (S1) or by erasing and retyping (S2), 6 were found and 10 missed. The placement check found 1 of the 8 pasted scans and the grain check 2 of the 8 retyped ones; the other finds came from arithmetic and cross-document checks. Counting every kind of change, 21 of 36 changes on scans were found (mild 13 of 18, 150 dpi 6 of 9, 120 dpi 2 of 9). One genuine 120 dpi scan was flagged by the placement check, the only flag on 144 genuine documents. |
| Edits inside one picture: error-level analysis, cloned regions, reused signatures and stamps | Unsupported | 0 | Not built, and not planned before submission: the dataset has no such change, so a detector for it could not be measured. A changed part of a scan is looked for only through the grain and placement checks above. A region copied inside one page is not looked for, and a signature, logo or stamp reused unchanged on two documents is not flagged (they are compared for difference, not for sameness). Photographs are out of scope. |
| Signature comparison across documents | Partial | 4 | The drawn signature on each document that has a signature caption in its spec (loan application, payslip) is cut out above that caption, straightened by the page's turn if it is a scan, and compared with the signature on every other such document by shape. A pair that differs by more than the stated limit is an inconsistency with both signatures marked; every pair compared is written to the audit trail. A signature that cannot be found or read (no ink, no caption, a poor page, printed matter in the area) is a limitation, never a pass. Shapes only: it does not say who signed. Held-out: a signature in another hand (C4) was found in 8 of 8 cases (4 digital and 4 scanned, one of them at 120 dpi), and the check raised no finding on a genuine document. The held-out signatures come from the same generator and the same invented names as the development ones, so other styles of signature are untested. |
| Checks within one document | Partial | 7 | Bank statement balance chain and dates; payslip totals, net pay against its words, and pay date against pay month; the weekday printed on a loan application. Each states its tolerance. A conflict resting on a doubtful reading is shown as a possible extraction error. Held-out (eval/test.md): where a value these checks need is missing or unreadable they say so ('Cannot fully verify') and check no further. That happened for all 24 genuine statements and all 24 genuine payslips of layout B; for none of the 18 genuine cases of layout A that were digital or mild scans; and for the 6 genuine statements and 2 of the 6 genuine payslips of layout A scanned at 150 or 120 dpi. |
| Cross-document conflict checks | Partial | 12 | Name, address and employer across documents, graded as passing, written differently (observation), Minor mismatch or Mismatch; account number, which matches or is a Mismatch; net pay against the credits on a statement; declared income against gross earnings; the application date against the dates of the other documents; a file submitted twice; the same producing software on different kinds of document made minutes apart. A comparison that cannot be made is reported as a limitation, never as a pass. Built for three document types with one drawn layout each. Each finding prints its tolerance. Held-out (eval/test.md): a pay figure changed so that the payslip still adds up (C1) was found in 5 of 8 cases (0 of 3 where deductions were lowered), a name, address, employer or month changed in one document (C2) in 6 of 8, and a statement submitted twice (C3) in 8 of 8. The five misses left only limitations on the changed document: a comparison could not be made because a value was not read, or (a 120 dpi scan) a mismatch was shown as a possible extraction error to verify. |
| Context rules (income, obligations, date windows) | Partial | 2 | Two rules: monthly obligations (existing instalments plus the new loan over its tenure) as a share of declared income, and a document dated more than 90 days before the application. Both are observations for the reviewer, never conflicts. Their reference limits are synthetic values chosen for this prototype, not a lending standard, and the instalment sum ignores interest. Rules taken from a lender's own policy are not built. Not measured by the evaluation: the generator holds each applicant's obligations to 40 % of income, so the obligations rule has nothing to say about a genuine case (eval/test.md). |
| Relationships between findings (clusters) | Partial | 8 | Findings are grouped when they cite the same extracted field, lie on the same place of a page (half of the smaller box inside the other), or concern the same name, address, employer or account number in different documents. A group is ranked by how many independent kinds of check fired in it (visual, arithmetic, cross-document, metadata): a count, not a probability. A group with two or more kinds gets a headline finding, classed as potential manipulation, that lists its members and cites each of their places once. Context rules are linked but count as no kind, and limitations are never grouped. Findings that share none of these stay apart even where a person would relate them. The evaluation scores findings, not groups, so grouping has no measured accuracy of its own; the overlap limit is a starting value. |
| Entity relationship view: names, addresses, employers and account numbers across documents, and the findings that touch them | Partial | 9 | Every name, address, employer and account number the extraction read goes into one list of entities, numbered in the order the documents mention them. Two writings are one entity when the cross-document checks grade them as the same or as the same apart from form (case, spacing, punctuation, the order of the words of a name, titles, initials, an employer's legal form, the visible end of a masked account number); a writing those checks grade as a Minor mismatch or a Mismatch is an entity of its own, so a changed name appears as two entities and the finding that reports it touches both. An entity lists each place it is written (document, page, box, the confidence of the reading). A finding touches an entity when it cites a field that holds it or lies over its box; the headline of a group of findings and limitations are left out. The Relationships tab draws documents, entities and findings as boxes joined by lines, and the dossier lists the entities under contextual analysis. Partial: the rules are fixed and sit on the grading of the cross-document checks, with the limits stated there; this is not a trained graph model, it finds no aliases, nicknames or links by meaning, it covers these four kinds of value only, and its accuracy was not measured because the evaluation scores findings, not entities (limitation 37). Nothing in it says what a difference means. |
| Plain-language explanations and next steps from fixed templates | Implemented | 2 | Fixed wording per detector and class. Without --llm nothing is written by a model; the next row covers the optional model. |
| Explanation wording from a local language model | Partial | 16 | Optional, and off unless a run is started with --llm. A small model (phi4-mini 3.8B, MIT) runs through Ollama on this computer, and the client refuses any other host. It words the headline of each group of findings and reads the case once for relations between findings, a short summary and a reading order. It sees structured findings (ids, kinds of check, titles, the values the checks used) and no page text, and it cannot add, change or remove a finding. Each part of what it writes is used only if the guard accepts it (ids, figures, dates, verdict words), and a relation only if its kind is true of what the two findings cite; the rest is dropped and logged. It is labelled as inference. Partial because it was measured only on development-set prompts, CPU only, one run each (the guard accepted 18 of 24 headline wordings), the guard does not check meaning, and nothing was run on a held-out set. |
| Evidence traceability: finding to file, sha256, page and box, with a marked crop | Implemented | 3 | Every piece of evidence names its document, page and box; the trace command prints them and checks the stored file's hash. |
| Investigation dossier: HTML (self-contained) and JSON, with its own hash | Implemented | 4 | Observations, inconsistencies, potential-manipulation candidates and limitations are kept in separate places. The entities the documents write about (names, addresses, employers, account numbers), each with the places it is written and the findings that touch it, are listed under contextual analysis. |
| Dossier export as PDF | Planned | 0 | Print the HTML dossier to PDF from a browser meanwhile. |
| Tamper-evident audit trail with a verify command | Implemented | 3 | Each event carries the hash of the one before it. The dossier records the trail's length and last hash. |
| Safe failure: rejected files, failed or stuck steps become visible limitations | Implemented | 3 | A step that fails or times out is listed as a limitation and the case goes on. A step stuck in native code is abandoned, not killed. |
| Offline operation | Implemented | 1 | The OCR models ship inside the package. The test suite runs with connections to public addresses blocked. |
| Review interface in the browser | Partial | 8 | Runs on this computer only. Upload, a background run with progress, page images with word, field and finding boxes, evidence crops, reviewer actions written to the audit trail, the audit trail, this list and the dossier download. The server side is tested; how the page behaves in a browser was checked by hand, not by an automated browser test. Findings that share evidence are grouped in the Clusters tab, each group under its headline. The Relationships tab shows the entities the documents write about and the findings that touch them (see the entity relationship row); its page script was checked by hand in a browser, with keyboard use, and not by an automated browser test. |
| Handwriting and multilingual OCR | Planned | 0 | Not built; text is read as printed English. |
| Real-world document layouts at scale | Unsupported | 0 | Only synthetic documents were used. Nothing is claimed about real ones. The held-out layout B, drawn after the specs were final, was read much worse than layout A (no id, and 34 % of the text values on digital pages). |
| Logo and stamp comparison across documents of one issuer | Partial | 5 | The logo (right of the issuer's name) and the stamp (above its caption) on each document whose type spec lists them (bank statement, loan application) are cut out, straightened by the page's turn if it is a scan, and compared by shape with those on every other document whose issuer line reads alike; a stamp is compared at its best turn within 8 degrees. A pair that differs by more than the stated limit is an inconsistency with both marks marked; every pair compared is written to the audit trail. A mark that cannot be found or read (no ink, no caption, a poor page, printed matter in the window) is a limitation, never a pass. Built and measured on synthetic marks only: six invented designs, two of which (the same motif in a circle and in an octagon) are not told apart, and a small change to a logo is not found. Held-out (eval/test.md): another logo or stamp on one document (C5) was found in 6 of 8 cases (large logo 2 of 2, large stamp 2 of 2, small stamp 2 of 2, small logo 0 of 2), and the check raised no finding on a genuine document. The held-out documents use the same six designs as the development ones. |
| Verdicts on authenticity or intent; telling who signed; photographs and identity documents | Unsupported | 0 | Unsupported by design. The tool lists anomalies for a human reviewer and never concludes. Signatures, logos and stamps are compared by shape between documents, which does not say who signed or who issued them. Photographs and identity documents are not examined. |
<!-- capabilities:end -->

## Limitations

The full list of limitations and assumptions, and a table of the ordinary things that raise each finding, is in [docs/limitations.md](docs/limitations.md). In short:

- Nothing was evaluated on real documents, real scanners or real layouts.
- Extraction is tied to the wordings of labels that the specs list. On a layout that words them differently, values are reported missing and the checks that need them are not made, and the tool says so (held-out layout B: no id read, 34 % of the text on digital pages).
- On scans the tool found little: 6 of 16 pasted or retyped scans, and 2 of 9 changes at 120 dpi. A scan with no finding says little about whether it was changed.
- A finding is a measurement for a reviewer, with the ordinary causes of the same result written next to it. The tool never concludes anything about authenticity or intent.
- Files are opened by PDF and image parsers in the same process as the tool. Limits on size, pages and time apply, and there is no sandbox.
- A check that cannot run is reported as not checked. It is never reported as clear.

## The language model

A local language model is optional, and it is off unless you ask for it. Nothing depends on it: extraction, the detectors, the checks across documents and every number in the dossier come from code, and the evaluation is run without a model. Digits, arithmetic and revision differences are never left to a model.

```
ollama pull phi4-mini:3.8b
python -m docforensics run statement.pdf payslip.pdf application.pdf --llm
python -m docforensics serve --llm
```

`ollama pull` needs the internet once; after that the model runs offline. With `--llm`, a small model (phi4-mini 3.8B, MIT) runs through Ollama on this computer and does two things, and only these: it words the headline of each cluster of findings, and it reads the case once and suggests relations between findings, a short summary and an order to read them in. `--llm-model NAME` picks another model Ollama has; qwen3-4b-instruct-2507 was measured too. If Ollama is not running or does not have the model, the run stops before a case is made and says what to do. If a call fails during a run, the template wording stays and the audit trail says why.

- **What it sees.** Structured findings: ids, kinds of check, titles and the values the checks used. Never page text, a finding's detail or a box. The client talks to `127.0.0.1` only and refuses any other host; no hosted service is used at run time.
- **What it cannot do.** Add, change, confirm or remove a finding. It adds, ranks and explains.
- **What is kept.** A guard judges the summary and each relation apart. Ids must be ones it was given, figures and dates must be ones the findings hold, verdict words are refused, and a relation's kind must be true of what its two findings cite. What fails is dropped, and the dropped part is kept with the reading and shown as dropped. The order can only rank: every finding stays in it once, and a finding the model leaves out follows in the tool's own order.
- **How it is shown.** "AI-generated wording (inference)" on a headline. "AI reading of the case (inference)" in the dossier's investigation summary and in the review desk's Clusters tab. Every call is an audit event with the model, its digest, the hashes of what went in and came out, and the verdict.
- **What was measured.** On development-set prompts, CPU only, one run each: the guard accepted 18 of 24 headline wordings from phi4-mini (13 of 24 from qwen3), and a call took 17 to 26 s on average for a headline and 40 to 48 s for a reading (figures and sources in `docs/spike.md`). The guard checks ids, figures, dates and verdict words, not meaning, so wording it accepts can still be wrong; limitation 30 in [docs/limitations.md](docs/limitations.md) gives examples. Nothing was run with a model on the held-out split.
- **For a demo.** A case takes a minute or more with the model, and free RAM falls to about 2 GiB. Use three or more documents: the stage has 120 s per document plus 120 s, and a call starts only if it fits in what is left.

The design is in [docs/architecture.md](docs/architecture.md).

## Data

Everything used here is synthetic: fictional people and institutions, no real customer, logo or identity document. If you run real documents through the tool, you need the right to. A case is kept as plain files under `data/` (originals, page images, crops, extracted values, findings, audit trail), without encryption or user accounts, and `data/` is not part of the repository.

## AI assistance

This project was built with an AI assistant, and most of the code, the tests and the documents in it, this README included, are its output. The assistant is Claude, from Anthropic, used through Claude Code. It drafted the design and the task plan, wrote the source, the tests, the document generator and the documentation, and ran the test suite and the measurements the repository quotes. For part of the build two Claude Code sessions worked side by side, each on its own tasks and branches.

Aryan, the author, chose the problem statement, set the requirements and constraints (offline, synthetic data only, findings for a reviewer and no verdicts) and is responsible for what is submitted.

At run time the tool calls no hosted AI service. The only model that can take part is the optional local one above.

## Templates and reused code

- No starter project, template or code from an earlier project was used. The first commit in this repository is dated 2 November 2026, 18:18 IST.
- Libraries are components (credited below). The extraction, the forensic detectors, the checks across documents, the linking, the explanations, the dossier and the audit trail are written in this repository.
- The review desk is one HTML page with its own CSS and JavaScript, written for this project: no framework, no build step, and nothing is loaded from the internet.
- The scripts used to choose the OCR engine were throwaway and are not in the repository.

## Credits and licences

| Component | Version | Licence | Used for |
|---|---|---|---|
| [PyMuPDF](https://pymupdf.readthedocs.io/) (`pymupdf`) | 1.28.2 | AGPL-3.0 or Artifex commercial; used here under AGPL-3.0 | reading PDFs: text layer, fonts, draw order, saved revisions, page rendering |
| [RapidOCR](https://github.com/RapidAI/RapidOCR) (`rapidocr`) | 3.10.0 | Apache-2.0 | OCR of scans and images |
| ONNX Runtime (`onnxruntime`) | 1.31.1 | MIT | runs the OCR models on the CPU |
| OpenCV (`opencv-python-headless`) | 5.0.0.93 | Apache-2.0 | image processing in the grain and signature checks and in the generator |
| NumPy (`numpy`) | 2.4.6 | BSD-3-Clause, with other licences for parts of the wheel (listed in its metadata) | arrays |
| Pillow (`pillow`) | 13.0.0 | MIT-CMU | images, crops, scan simulation |
| pydantic (`pydantic`) | 2.14.2 | MIT | the data model |
| FastAPI (`fastapi`) | 0.162.0 | MIT | the review desk's server |
| Uvicorn (`uvicorn`) | 0.54.0 | BSD-3-Clause | serves it |
| python-multipart (`python-multipart`) | 0.0.33 | Apache-2.0 | reads uploads |
| pytest (`pytest`) | 9.2.0 | MIT | tests |
| httpx (`httpx`) | 0.28.1 | BSD-3-Clause | the test client for the review desk |
| psutil (`psutil`) | 7.2.2 | BSD-3-Clause | development only: `evaluation/run_eval.py` reads the peak memory of an evaluation run from it |

Versions are those pinned in `requirements.txt` and `requirements-dev.txt`; licences are those the packages declare at those versions.

**OCR models.** RapidOCR carries three ONNX models: PP-OCRv6 small detection (`PP-OCRv6_det_small.onnx`), PP-OCRv6 small recognition (`PP-OCRv6_rec_small.onnx`) and the text-angle classifier `ch_ppocr_mobile_v2.0_cls` (`ch_ppocr_mobile_v2.0_cls_mobile.onnx`). The weights come from PaddleOCR; the copyright in them is held by Baidu and the PaddleOCR rights holders, and RapidOCR converted them to ONNX. They are licensed under Apache-2.0. The notice, `MODEL_LICENSES.md`, is in the RapidOCR package (in its `.dist-info/licenses` folder).

**Ollama** (MIT) is the optional local model runtime. It is not a dependency of this package and is not bundled. **phi4-mini** (3.8B, from Microsoft, MIT) is the default model, and **qwen3-4b-instruct-2507** (q4_K_M, from the Qwen team at Alibaba, Apache-2.0, read with `ollama show --license`) was measured as the alternative. Neither model is in this repository: each is fetched with `ollama pull`, the one step that needs the internet.

**Arial.** The generator's font-substitution manipulation reads Arial from the Windows fonts folder of the machine it runs on. The font file is not in this repository; PDFs drawn with that manipulation embed a subset of it.

**Claude Code** and Claude (Anthropic) were used to build the project; see AI assistance above.

## Licence

docforensics is released under the GNU Affero General Public License v3.0 only ([LICENSE](LICENSE)). The reason is PyMuPDF, which is offered under the AGPL-3.0 or a commercial licence from Artifex. This project uses it under the AGPL-3.0 and so carries the same licence.

## Reference standards

No compliance with ISO/IEC 27037, 27041 or 27042, or with NIST SP 800-86, is claimed. What the tool does that touches them is small: original files are hashed and kept read-only. The OWASP ML Security Top 10 was a reference, not a checklist that is met: files are limited in size, pages and time, stored under their hash, and opened without a sandbox, which is stated as a limitation; what a model may say is guarded.
