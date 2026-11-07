# Sample data

Eleven small cases to run the tool on. A case is one folder with the documents of one fictional applicant: a bank statement, a payslip and a loan application in eight of the cases, a single payslip scan in the other three. Everything in them is synthetic: the institutions carry TEST in their names, the people, account numbers and amounts are made up, and no real logo or identity document is used. The generator that drew them is [datagen/](../datagen/).

## What they are, and what they are not

Five of the cases come from the **development split** of the generator, the split on which the tool's thresholds were tuned. The other six come from the **ext-dev split** of the two packs made for the two newer checks, the reused-signature check ([datagen/reuse_pack.py](../datagen/reuse_pack.py)) and the compression-history check ([datagen/ela_pack.py](../datagen/ela_pack.py)); that is the split on which the limit and the constants of those two checks were set. Every case here is in-sample: the tool was set up on this data. Running them shows the tool working from files to dossier, with each finding traced to its place in a file. It is a demonstration, not evidence of how well the tool detects.

- The two newer checks have their own reports on ext-dev, [eval/h/reuse-ext-dev.md](../eval/h/reuse-ext-dev.md) and [eval/e/ext-dev-tool.md](../eval/e/ext-dev-tool.md). Those figures are in-sample too.
- On the whole development split the tool, as of commit d928be0, finds 52 of 54 planted changes and raises no flag on 78 genuine documents ([eval/dev.md](../eval/dev.md)); its first report said 50 of 54. Those are figures on the data the thresholds were tuned on and the learned word check was fitted on.
- The figures that count are from the held-out test split, run once and reported whole in [eval/test.md](../eval/test.md): 79 of 96 changes found (82 %), 37 of the 48 that have a place on a page located, and 1 flag on 144 genuine documents (a 120 dpi scan). By medium, changes found: digital 58 of 60, mild scan 13 of 18, 150 dpi scan 6 of 9, 120 dpi scan 2 of 9. These held-out figures are those of the tool at spec-freeze plus two fixes, not of the final tool: the newer checks are not in them (main README, Evaluation).
- All eleven cases use the first of the generator's two page layouts. On the second layout, which only the test split has, extraction is weak: about half of its labels are wordings the spec files do not list, and a value under one of them is reported as missing, not guessed (on digital documents none of the ids and 34 % of the text values are read).
- One generator drew everything, and its scans are simulated. The figures say little about documents drawn in other styles or scanned on other devices.

## Run one

From the repository folder, after the set-up in the main README:

```
python -m docforensics run sample_data/dev-0000
```

It prints the case id, the documents it recognised and the findings, and writes the case, with `dossier.html` and `dossier.json`, to `data/cases/<case id>/`. The last line shows how to follow a finding to its source (`trace`); `verify-audit` checks the audit trail. Run another case the same way, with its folder. A scanned case takes longer, because OCR reads its pages (0.53 s per digital page and 4.39 s per scanned page in the held-out run at spec-freeze on a CPU-only laptop; the same split run again took 0.35 s and 2.33 s). Those runs are from before the JPEG-history check was added. On 6 Nov, with it in, `run` took 4 to 5 s for a case of one scanned JPEG and 10 s for a case of three (single runs on the same laptop; how much of that is the check was not measured).

The date and time in a case id, in the audit trail and in the dossier are UTC. IST is UTC+05:30, so a run at 16:00 IST has 10:30 in its id.

`python -m pytest tests/test_e2e_sample.py` runs the five cases of the development split through the whole pipeline, and `python -m pytest tests/test_e2e_sample_packs.py` runs the six ext-dev cases the same way. Both block connections to public addresses and check that what comes out is what is written below.

## The five cases of the development split

| Case | Medium | Planted change | Result |
|---|---|---|---|
| dev-0000 | digital PDFs | closing balance on the statement edited in a later saved revision of the PDF (D1) | found, located |
| dev-0002 | digital PDFs | none: a genuine case | no finding |
| dev-0006 | mild scans | gross earnings on the payslip replaced by the same place from another scan (S1) | found, located, through arithmetic only |
| dev-0009 | digital PDFs | one letter of the name changed in one document (C2) | found (this kind of change has no place on a page) |
| dev-0043 | digital PDFs | logo on the statement changed slightly (C5) | **missed** |

### dev-0000: an edited PDF

The closing balance on the statement was changed from 1,10,102.52 to 2,10,102.52 in an incremental save, so the earlier text is still in the file as the first revision. The tool raises three findings:

- an observation, `pdf_revisions`: "Text changed in revision 2 (page 1)", with the old and the new text;
- an inconsistency, `statement_balance`: "The closing balance does not follow from the transactions": closing balance INR 210102.52 against INR 110102.52 on the last row, a difference of INR 100000.00 (tolerance INR 1.00);
- potential manipulation, a group: "Closing balance on 01_statement.pdf: 2 findings from 2 kinds of check", which holds the two above because they cite the same place.

Both findings point at the changed figure. Found and located.

### dev-0002: a genuine case

Nothing was changed. The tool raises no finding and no limitation. Genuine cases can still raise findings: the held-out run has one on 144 genuine documents (test-0143, a 120 dpi scan, listed in [eval/test.md](../eval/test.md)).

### dev-0006: a spliced scan, found through arithmetic

The gross earnings on the payslip (83,000.00) were replaced by the same place cut from another scan. The tool reads 118000.10 there and raises four findings: two inconsistencies on the payslip's own sums ("Net pay does not equal gross earnings less total deductions", "Gross earnings do not equal the earnings listed"), one across documents ("Declared income differs from the payslip gross earnings": the application declares 83000.00) and a group of those three, potential manipulation. Found and located.

Look at how it was found: by arithmetic and by comparing figures, not by the pixels. Neither scan check (grain, alignment) reported anything about the pasted part. As [eval/test.md](../eval/test.md) notes, a change to an amount that the arithmetic checks cover is caught by those checks whatever the pixels show. A spliced scan is found in 2 of 5 cases on the development split and in 3 of 8 on the test split, and this is one of the two.

### dev-0009: a name that differs by one letter

The account holder on the statement reads "Divyu C. Menon"; the payslip and the application read "Divya C. Menon". The tool raises one inconsistency, `cross_name`: "Minor mismatch: name differs between documents", citing all three documents. Found. Whether it is a slip of the clerk or something else is for a person to decide; the tool does not decide it.

### dev-0043: a miss

The logo on the statement is the bank's design with one point moved by a tenth (C5, "logo, small"). The tool raises nothing: no finding and no limitation. That is a miss, and the development report lists it as one ([eval/dev.md](../eval/dev.md)). Small logo changes were missed on the test split as well (0 of 2).

## The six cases of the ext-dev split

Three cases of each of the two packs. Run one the same way, for instance `python -m docforensics run sample_data/ext-dev-h-0001`. A case of the reused-signature pack has the three documents of the cases above. A case of the compression-history pack is one payslip scan, a JPEG picture, so the checks that compare documents have nothing to compare and its dossier carries the limitation "Cannot check across documents: one document submitted". That limitation belongs to the cross-document step, not to the compression-history check. What is named below for the two 120 dpi cases (ext-dev-h-0046 and ext-dev-e-0012) depends on OCR: the limitations they raise and, for the first, the measured ink gap are what OCR gave on the author's machine. Another machine can read a borderline digit or caption word differently and get another set of limitations or a slightly different gap; `tests/test_e2e_sample_packs.py` pins the result of this one.

| Case | Medium | Planted change | Result |
|---|---|---|---|
| ext-dev-h-0000 | digital PDFs | none: a genuine case, each document signed afresh | no finding; the two signatures were compared and are not the same image |
| ext-dev-h-0001 | digital PDFs | the same signature image on the payslip and on the loan application | found, located |
| ext-dev-h-0046 | 120 dpi scans | the same signature image on the payslip and on the loan application | **missed**; four limitations from reading the 120 dpi pages |
| ext-dev-e-0000 | one mild scan | none: a genuine case, the picture saved once, at quality 85 | no finding from the check |
| ext-dev-e-0002 | one mild scan | a field of another payslip's scan pasted in off the page's JPEG grid, then saved again at quality 95 | found, located; also found through the payslip's own sums and words |
| ext-dev-e-0012 | one 120 dpi scan | none: a genuine case, the picture saved once, at quality 35 | **the check cannot examine this picture** and reports nothing |

### ext-dev-h-0000: a genuine case, two signatures compared

Nothing was changed: the payslip and the loan application were each signed afresh. The tool raises no finding and no limitation. It did compare the two signatures, and the audit trail (`audit.jsonl` in the case folder) records how: `reuse_compared`, with an ink gap of 17.7 % against the limit of 5 %, so the pair is not called the same image. The ink gap is the share of one signature's ink that lies more than one pixel from the other's ink at the best one-pixel slide (the larger of the two shares); the pixels are those of the 192 x 64 canvas that each signature is scaled to, not of the page. A 64-bit hash of each signature is logged too, 5 bits apart here; it does not decide. Nothing is flagged on a genuine case.

### ext-dev-h-0001: a signature on two documents

The payslip and the loan application carry the same signature image. The tool raises one finding, an observation from the `reuse` check: "The signatures on D2 (payslip) and on D3 (loan application) are the same image", with two places, one on each document (page 1, "signature on page 1"). The ink gap is 0.0 % against the limit of 5 %, and the two hashes do not differ. Both boxes lie on the planted signatures: each overlaps the manifest's box by more than 0.9 (intersection over union), where the evaluation counts 0.5 as placed. Found and located.

The finding's explanation is a fixed text (marked `template`). It names ordinary causes (software that places one stored image of a signature on every document it makes, one page submitted in two forms, one scan used for two documents) and says that the comparison reads shapes only, not who signed or how the image came to be on both.

### ext-dev-h-0046: a miss

The same planted change as in ext-dev-h-0001, on three 120 dpi scans: one signature image on the payslip and on the loan application, each page scanned on its own. The tool compared the pair and measured an ink gap of 6.7 % against the limit of 5 % (3 bits apart in the hash, which does not decide). That is over the limit, so the pair is not called the same image and the tool raises no finding about the signatures. That is a miss, and the check's report on ext-dev lists it as the one signature case it misses ([eval/h/reuse-ext-dev.md](../eval/h/reuse-ext-dev.md)). The dossier's findings say nothing about the signatures; the comparison appears only as a line in the audit trail.

The dossier is not empty. OCR reads 120 dpi pages less reliably, and the checks that depend on the figures say when they could not run in full. The tool raises four limitations and no inconsistency: "Cannot fully verify this statement", "Cannot fully verify this payslip" (among the cells it names are amounts that OCR gave as something that is not an amount, such as 57.500.00 for 57,500.00: the comma read as a point), "Some cross-document comparisons could not be made" and "Context rule not applied: an input could not be used". None of the four is about the signatures.

### ext-dev-e-0000: a genuine scan, saved once

A payslip scan with nothing changed: a mild scan saved once as a JPEG, at quality 85. The compression-history check examines the picture. A page saved once has no earlier save to compare with, so there is nothing for the check to report and it raises no finding. The only finding in the dossier is a limitation, "Cannot check across documents: one document submitted", which every case of a single document raises and which is not this check's. Nothing is flagged on a genuine case. The audit trail holds one line for the check on this document: `doc_forensics`, detector `jpeg_history`, `findings` 0.

### ext-dev-e-0002: a field pasted into a scan

A mild scan saved at quality 85. A field of another payslip's scan was pasted in off the page's JPEG grid (the manifest gives the shift as 3 and 5 pixels) and the picture was saved again at quality 95. The tool raises five findings:

- an observation from the compression-history check: "Part of the page has no trace of the page's earlier JPEG save (page 1)", with one region. Its note: "saving again at quality 85 changes its ink by 3.8 grey levels on average, against 0.5 for the page's median cell". The region and the pasted box overlap by 0.66 (intersection over union), where the evaluation counts above 0.3 as located;
- two inconsistencies within the payslip, one in its sums and one between its words and its figures: "Net pay does not equal gross earnings less total deductions" and "Net pay in words does not match net pay in figures";
- a limitation, "Cannot check across documents: one document submitted", which is not this check's;
- potential manipulation, a group: "Net pay on scan.jpg: 3 findings from 2 kinds of check", which holds the observation and the two inconsistencies because they cite the same place.

Found and located. The pasted field is the net pay, so the payslip's own sums and words fail too, and the case is found by two kinds of check. It therefore does not show the compression-history check on its own. The observation's explanation is a fixed text (marked `template`) that names the ordinary causes: a page put together from more than one scan, and a stamp, date, page number or sticker that the scanner or a program added later leave the same mark.

### ext-dev-e-0012: a picture the check cannot examine

A genuine payslip scan at 120 dpi, saved once as a JPEG at quality 35. The compression-history check cannot examine a picture whose last save is under quality 40, and this one is under it. It says nothing: no finding, and no limitation about the picture. This is a limit of the tool, stated in the compression-history row of the capability matrix in the [main README](../README.md); it is not something to rely on. Nothing in the dossier about the compression-history check tells this case from ext-dev-e-0000: in both the check made no finding and the audit trail holds the same line (`jpeg_history`, `findings` 0). A dossier without a compression-history finding therefore does not mean that the picture was examined and found clean.

The case raises two limitations: "Cannot fully verify this payslip", from reading a 120 dpi page by OCR (the cells it names are amounts that OCR gave as something that is not an amount, such as 23.500.00 for 23,500.00: the comma read as a point), and "Cannot check across documents: one document submitted". Nothing is flagged on a genuine case.

## Why these cases

**Development split.** Four are the first case of their kind in the split, so their position picked them and not their result: the first case (a PDF edited in a later saved revision), the first genuine case, the first spliced scan and the first changed name. The fifth, dev-0043, was picked because the development report lists it as a miss. They are not the best cases of the split, and they are not its worst: the other three development misses are spliced scans (dev-0021, dev-0036, dev-0051) and are not here.

**ext-dev split.** The same rule, by position and by the pack's own report, and not by how the result looks. Reused-signature pack: ext-dev-h-0000 is its first case (a genuine one), ext-dev-h-0001 its first case with a planted signature, and ext-dev-h-0046 the signature case its report lists as a miss. Compression-history pack: ext-dev-e-0000 is its first case (a genuine one), ext-dev-e-0002 the first case with a planted edit (a field pasted in), and ext-dev-e-0012 the first case whose last save is under quality 40. The packs have cases that are not here. The reused-signature pack has cases that reuse a stamp, which the check does not compare. The compression-history pack has cases that the check cannot see by construction, such as an edit made with the page's own grid and quality; its report lists them apart.

## A sample dossier

`dossier-dev-0000.html` and `dossier-dev-0000.json` are the dossier of dev-0000 as the tool wrote it, copied without editing. The HTML is one file with the images of the changed places inside it; open it in a browser after cloning (GitHub shows its source, not the page). The JSON holds the same data for programs.

- Sections 3 to 5 hold the three findings and where each sits in the statement. Appendices B and C hold the capability matrix and the limitations, which say what the tool does not do.
- Made by `python -m docforensics run sample_data/dev-0000`, without `--llm`. No language model was used, so the explanations are the tool's fixed texts (marked `template`), and section 6 says so.
- The case is C-20261107-191014-a47d, created at 19:10:14 UTC on 7 November 2026 (00:40 IST on 8 November). Every time in the files is UTC.
- Made with the tool as of commit 1f858e1.
- dev-0000 is a case of the development split, the one the thresholds were tuned on. The dossier shows what a dossier looks like and what the tool does on a case it was tuned on; it says nothing about other cases.
- `stored_path` and `crop` in the JSON are paths inside the case folder that a run writes (`data/cases/<case id>/`). That folder is not kept here, and the HTML does not need it.
- `python -m pytest tests/test_e2e_sample.py` checks that the files are unedited (the hash at the end of the page is the hash of the data in the JSON), that they are the dossier of dev-0000's documents, and that a new run of the case writes the same dossier apart from the case id, the times, the audit trail's hashes and timings and its signed checkpoint (the signing key is made for each data folder, so a run on another machine signs with another key). When a change to the tool changes what a dossier shows, that test fails until the dossier is made again: run the case as above, copy `dossier.html` and `dossier.json` from `data/cases/<case id>/` to these two names, and put the new case id, time and commit in this section.

A second pair, `dossier-dev-0000-llm.html` and `dossier-dev-0000-llm.json`, is the same case run with `--llm` (`python -m docforensics run sample_data/dev-0000 --llm`), which uses the model phi4-mini:3.8b through Ollama; the pair above used no model. Case C-20261107-191022-760e, created at 19:10:22 UTC on 7 November 2026 (00:40 IST on 8 November), tool as of commit 1f858e1. It is the first run made with this commit, kept as it came out; the model's reading and its headline wording came out word for word the same as in the run before it (commit 7067fa7), which this one replaces. The model's reading was kept, except for one relation that the checks dropped, and its wording of the group headline (F-003) was accepted; both are marked as inference on the page. The findings, values and places are the same as in the first pair, and a test checks that. The checks look at ids, figures, dates and verdict words, not at meaning: the accepted headline gives the two balances and one ordinary cause and does not mention the earlier saved revision (F-001), so read it against the first pair's wording. The test cannot make this pair again, because that needs the model; it checks that the files are unedited, that the audit trail records the model's calls, and that the findings are the same.

## The manifest

`manifest.json` holds what is true of each case: the documents with their type, sha256, values and boxes, and each planted change with its method, place and note. The tool never reads it. The evaluation's scorer and the tests do, to say whether a case was found. Read it after a run if you want to try without the answer first.

The six ext-dev cases are described by two manifests, one for each pack, `manifest-ext-dev-h.json` and `manifest-ext-dev-e.json`, in the shape the two packs write ([datagen/reuse_pack.py](../datagen/reuse_pack.py), [datagen/ela_pack.py](../datagen/ela_pack.py)). For a reused-signature case it lists the planted pair of signatures with the box of each (`reuse`, empty on a genuine case). For a compression-history case it gives the quality of the earlier save (`host_quality`) and of the last save (`final_quality`), what the check is meant to see (`expect`) and the pasted box (`box`). The tool never reads these either.

## Make them again

```
python -m datagen.sample sample_data
```

A case depends only on its number, so this writes the same cases and manifests, the six ext-dev cases and their two manifests included. The bytes of the files are the same only where the libraries and the system are the same as when these were written; the sha256 of every file in the manifest identifies exactly what was run.
