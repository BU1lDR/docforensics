# Sample data

Five small cases to run the tool on. A case is one folder: a bank statement, a payslip and a loan application of one fictional applicant. Everything in them is synthetic: the institutions carry TEST in their names, the people, account numbers and amounts are made up, and no real logo or identity document is used. The generator that drew them is [datagen/](../datagen/).

## What they are, and what they are not

The five cases come from the **development split** of the generator, the split on which the tool's thresholds were tuned. Running them shows the tool working from files to dossier, with each finding traced to its place in a file. It is a demonstration, not evidence of how well the tool detects.

- On the whole development split the tool finds 50 of 54 planted changes and raises no flag on 78 genuine documents ([eval/dev.md](../eval/dev.md)). Those are figures on the data the thresholds were tuned on.
- The figures that count are from the held-out test split, run once and reported whole in [eval/test.md](../eval/test.md): 79 of 96 changes found (82 %), 37 of the 48 that have a place on a page located, and 1 flag on 144 genuine documents (a 120 dpi scan). By medium, changes found: digital 58 of 60, mild scan 13 of 18, 150 dpi scan 6 of 9, 120 dpi scan 2 of 9.
- All five cases use the first of the generator's two page layouts. On the second layout, which only the test split has, extraction is weak: about half of its labels are wordings the spec files do not list, and a value under one of them is reported as missing, not guessed (on digital documents none of the ids and 34 % of the text values are read).
- One generator drew everything, and its scans are simulated. The figures say little about documents drawn in other styles or scanned on other devices.

## Run one

From the repository folder, after the set-up in the main README:

```
python -m docforensics run sample_data/dev-0000
```

It prints the case id, the documents it recognised and the findings, and writes the case, with `dossier.html` and `dossier.json`, to `data/cases/<case id>/`. The last line shows how to follow a finding to its source (`trace`); `verify-audit` checks the audit trail. Run another case the same way, with its folder. A scanned case takes longer, because OCR reads its pages (0.53 s per digital page and 4.39 s per scanned page in the held-out run on a CPU-only laptop; the same split run again took 0.35 s and 2.33 s).

The date and time in a case id, in the audit trail and in the dossier are UTC. IST is UTC+05:30, so a run at 16:00 IST has 10:30 in its id.

`python -m pytest tests/test_e2e_sample.py` runs all five cases through the whole pipeline, with connections to public addresses blocked, and checks that what comes out is what is written below.

## The five cases

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

## Why these five

Four are the first case of their kind in the split, so their position picked them and not their result: the first case (a PDF edited in a later saved revision), the first genuine case, the first spliced scan and the first changed name. The fifth, dev-0043, was picked because the development report lists it as a miss. They are not the best cases of the split, and they are not its worst: the other three development misses are spliced scans (dev-0021, dev-0036, dev-0051) and are not here.

## A sample dossier

`dossier-dev-0000.html` and `dossier-dev-0000.json` are the dossier of dev-0000 as the tool wrote it, copied without editing. The HTML is one file with the images of the changed places inside it; open it in a browser after cloning (GitHub shows its source, not the page). The JSON holds the same data for programs.

- Sections 3 to 5 hold the three findings and where each sits in the statement. Appendices B and C hold the capability matrix and the limitations, which say what the tool does not do.
- Made by `python -m docforensics run sample_data/dev-0000`, without `--llm`. No language model was used, so the explanations are the tool's fixed texts (marked `template`), and section 6 says so.
- The case is C-20261105-081924-a120, created at 08:19:24 UTC on 5 November 2026 (13:49 IST). Every time in the files is UTC.
- Made with the tool as of commit 1eca670.
- dev-0000 is a case of the development split, the one the thresholds were tuned on. The dossier shows what a dossier looks like and what the tool does on a case it was tuned on; it says nothing about other cases.
- `stored_path` and `crop` in the JSON are paths inside the case folder that a run writes (`data/cases/<case id>/`). That folder is not kept here, and the HTML does not need it.
- `python -m pytest tests/test_e2e_sample.py` checks that the files are unedited (the hash at the end of the page is the hash of the data in the JSON), that they are the dossier of dev-0000's documents, and that a new run of the case writes the same dossier apart from the case id, the times and the audit trail's hashes and timings. When a change to the tool changes what a dossier shows, that test fails until the dossier is made again: run the case as above, copy `dossier.html` and `dossier.json` from `data/cases/<case id>/` to these two names, and put the new case id, time and commit in this section.

A second pair, `dossier-dev-0000-llm.html` and `dossier-dev-0000-llm.json`, is the same case run with `--llm` (`python -m docforensics run sample_data/dev-0000 --llm`), which uses the model phi4-mini:3.8b through Ollama; the pair above used no model. Case C-20261105-083750-82b1, created at 08:37:50 UTC on 5 November 2026 (14:07 IST), tool as of commit d098858. It is the first run that was made, kept as it came out. The model's reading was kept, except for one relation that the checks dropped, and its wording of the group headline (F-003) was accepted; both are marked as inference on the page. The findings, values and places are the same as in the first pair, and a test checks that. The checks look at ids, figures, dates and verdict words, not at meaning: the accepted headline gives the two balances and one ordinary cause and does not mention the earlier saved revision (F-001), so read it against the first pair's wording. The test cannot make this pair again, because that needs the model; it checks that the files are unedited, that the audit trail records the model's calls, and that the findings are the same.

## The manifest

`manifest.json` holds what is true of each case: the documents with their type, sha256, values and boxes, and each planted change with its method, place and note. The tool never reads it. The evaluation's scorer and the tests do, to say whether a case was found. Read it after a run if you want to try without the answer first.

## Make them again

```
python -m datagen.sample sample_data
```

A case depends only on its number, so this writes the same cases and manifest. The bytes of the files are the same only where the libraries and the system are the same as when these were written; the sha256 of every file in the manifest identifies exactly what was run.
