# docforensics

Offline document forensics for a human investigator. A case of scanned and digital documents goes in. An investigation dossier comes out, and every finding in it is traced to a box on a page of a stored source file.

It is a solo entry to the DataOps Innovation Hackathon 2026 (Hack The Core), for the problem statement on AI-powered document forensics and contextual intelligence.

The tool lists anomalies for a reviewer. It does not decide whether a document is authentic and it does not name intent. Observations, inconsistencies, candidates for closer review and limits of the analysis are kept apart, and what a finding means is the reviewer's decision. **Every document used to build and test it is synthetic:** read [docs/limitations.md](docs/limitations.md) before reading anything into a result.

## What it does

- **Several documents in one case.** PDF, PNG and JPEG, typed by their first bytes, limited in size, pages and number, hashed and stored read-only. A file that is refused or cannot be read becomes a visible limitation, not a crash.
- **Reading, offline.** The text layer of a digital PDF, or RapidOCR for a scan, gives every word a box. Scanned pages are classed by sharpness, because the recogniser's own confidence does not flag misread digits.
- **Understanding.** Each document is classified, and its fields and table cells are extracted with a confidence and a location. Bank statements, payslips and loan applications have a spec each (one drawn layout each). Document types are data, in TOML files; anything else is reported as `unknown`.
- **Visual and file forensics.** Digital PDFs: saved revisions, text covered by a shape or picture, hidden text, fonts of figures and dates, file metadata. Scans: image grain and the placement of words. Across documents: the shape of the signature, of the logo and of the stamp.
- **Contextual intelligence.** Within a document: balance chain, totals, net pay against its words, dates, weekday. Across documents: name, address, employer, account number, net pay against the bank credit, declared income against earnings, dates, duplicate files, the same producing software. Two context rules against a synthetic reference.
- **Relationships between findings.** Findings that cite the same field, the same place on a page or the same name, address, employer or account are grouped. A group is ranked by how many independent kinds of check fired in it.
- **An optional local model.** Off unless you ask for it. With `--llm`, a small model running on this computer words the headline of each group of findings and suggests relations, a summary and a reading order. A guard checks it first, it cannot add, change or remove a finding, and everything it says is labelled as inference. See [The language model](#the-language-model).
- **Evidence you can follow.** Each finding names its document, page and box, with a marked crop. `trace` follows it to the stored file and checks the file against its sha256.
- **A dossier.** One self-contained HTML file and one JSON file: overview, extracted information, contextual analysis, visual forensic findings, evidence and traceability, investigation summary, and appendices with the audit trail, the capability matrix and the limitations.
- **A review desk.** A page in the browser on this computer for upload, page images with word, field and finding boxes, evidence, reviewer actions and the dossier download.
- **An audit trail.** Every submission, step, failure, model use, dossier build and reviewer action is an event, each carrying the hash of the one before. `verify-audit` checks the chain.

How the pieces fit is in [docs/architecture.md](docs/architecture.md).

## Set up

Python 3.11 or newer. It was developed and tested on Windows 11 with Python 3.11.9; no other system has been tried.

```
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

Upload the documents on the Documents tab. The Findings tab lists what was found, with the evidence, the explanation and the reviewer actions; the Clusters tab shows related findings together; the Audit trail, Capabilities and Dossier tabs hold the rest. `--port` changes the port.

Follow a finding to its source, and check that the audit trail has not been changed:

```
python -m docforensics trace C-20261104-153000-ab12 F-003
python -m docforensics verify-audit C-20261104-153000-ab12
```

`trace` prints the document, the stored file and its sha256 (and whether the file still matches it), the page and the box in pixels and in PDF points, and the value read there.

### Tests

```
pip install -r requirements-dev.txt
python -m pytest
```

The suite takes several minutes because some tests load the OCR engine; `python -m pytest -m "not ocr"` leaves those out. The tests run with connections to public addresses blocked.

## Demonstration documents

The `datagen/` package draws fictional bank statements, payslips and loan applications as PDFs whose content is known, applies manipulations to them (each one records what was done and where, in the pixel frame the tool reports) and simulates scans at several quality levels. Institutions carry TEST in their names; no real logo, person or identity document is used. The tests use it to check each detector against known truth. The generator's font-substitution manipulation reads Arial from the Windows fonts folder and does not run elsewhere. The tool does not use the generator.

A ready-made dataset of genuine and manipulated documents, and an evaluation on cases held out from the tuning of the thresholds, are not in this repository yet. Until they are, **no accuracy figure is claimed**.

## Capability matrix

Each capability is marked Implemented, Partial, Planned or Unsupported. A status changes only when the evidence for it does, and Tests counts the automated tests that back the row. The table is written from [capabilities.json](src/docforensics/capabilities.json), the file the dossier and the review desk print. After that file changes, rebuild this table with `python -m docforensics.capabilities --update` from the repository folder.

<!-- capabilities:start -->
| Capability | Status | Tests | Note |
|---|---|---|---|
| Multi-document ingestion with file-type checks, limits and hashing | Implemented | 3 | PDF, PNG and JPEG by their first bytes. By default 10 MB, 20 pages and 10 documents per case. Files are stored under their sha256; a rejected file becomes a limitation with a reason. |
| Document classification | Partial | 3 | Rules over words and layout. Three types have a spec at this build (bank statement, payslip, loan application), written for one drawn layout each; anything else is 'unknown' and says so. Wording that differs from the specs' may also read as 'unknown'. A local-model fallback is not built. |
| Text-layer reading and OCR (offline) | Implemented | 4 | Every word has a box in page pixels. Scanned pages get a quality class from sharpness, not from the recogniser's score; numbers read from a degraded or poor page are flagged, not trusted. OCR output is a reading, not ground truth. |
| Structured extraction: fields and tables, each with a confidence and a location | Partial | 4 | Bank statements, payslips and loan applications, digital and scanned (scans are simulated at three levels), on the drawn layouts the specs were written for. A column or label that is not found is reported as missing, never filled in, and nothing repairs a misread digit or separator. How many values come out right, wrong or missing, by kind of value and scan level, is measured by the evaluation, not by the tests: at the lowest simulated level (120 dpi) most amounts are not read. A deduction beside an empty earnings cell is not read as a row. Other document types and layouts are not built. |
| Digital PDF forensics: comparison of saved revisions | Partial | 3 | Text that differs between a PDF's earlier saved version and a later one is reported as an observation, with the old and the new text. The other digital checks are in the next row. |
| Digital PDF forensics: covered and hidden text, pictures over text, fonts, file metadata | Partial | 7 | Reported as observations with the measured values: text still in the file but drawn under a filled rectangle or a picture that comes after it (the text written over a covering rectangle is cited too); a figure or date set in a different font, size or colour from the others in its column or on its line; text that is invisible, under 2 pt or off the page; a producer or creator that names PDF-editing software; a modification date later than the creation date. Built against synthetic manipulations D2 to D5 and not yet evaluated on a held-out set. Not built: text hidden by its colour, covers that are not rectangles, bold against regular. |
| Scan and image forensics | Partial | 9 | Two checks on scanned pages that are not of poor quality, both shown as observations: words whose image grain differs from the page median, and words set out of line after the page is straightened (a word against its row, a figure's right edge against its column, a figure's height against the page's other figures). How often these checks find a changed scan is measured by the evaluation, not by the tests. |
| Edits inside one picture: error-level analysis, cloned regions, reused signatures and stamps | Unsupported | 0 | Not built, and not planned before submission: the dataset has no such change, so a detector for it could not be measured. A changed part of a scan is looked for only through the grain and placement checks above. A region copied inside one page is not looked for, and a signature, logo or stamp reused unchanged on two documents is not flagged (they are compared for difference, not for sameness). Photographs are out of scope. |
| Signature comparison across documents | Partial | 4 | The drawn signature on each document that has a signature caption in its spec (loan application, payslip) is cut out above that caption, straightened by the page's turn if it is a scan, and compared with the signature on every other such document by shape. A pair that differs by more than the stated limit is an inconsistency with both signatures marked; every pair compared is written to the audit trail. A signature that cannot be found or read (no ink, no caption, a poor page, printed matter in the area) is a limitation, never a pass. Shapes only: it does not say who signed. Built and measured on synthetic signatures, not yet evaluated on a held-out set. |
| Checks within one document | Partial | 7 | Bank statement balance chain and dates; payslip totals, net pay against its words, and pay date against pay month; the weekday printed on a loan application. Each states its tolerance. A conflict resting on a doubtful reading is shown as a possible extraction error. |
| Cross-document conflict checks | Partial | 12 | Name, address and employer across documents, graded as passing, written differently (observation), Minor mismatch or Mismatch; account number, which matches or is a Mismatch; net pay against the credits on a statement; declared income against gross earnings; the application date against the dates of the other documents; a file submitted twice; the same producing software on different kinds of document made minutes apart. A comparison that cannot be made is reported as a limitation, never as a pass. Built for three document types with one drawn layout each, and not yet evaluated on a held-out set. Each finding prints its tolerance. |
| Context rules (income, obligations, date windows) | Partial | 2 | Two rules: monthly obligations (existing instalments plus the new loan over its tenure) as a share of declared income, and a document dated more than 90 days before the application. Both are observations for the reviewer, never conflicts. Their reference limits are synthetic values chosen for this prototype, not a lending standard, and the instalment sum ignores interest. Rules taken from a lender's own policy are not built. |
| Relationships between findings (clusters) | Partial | 8 | Findings are grouped when they cite the same extracted field, lie on the same place of a page (half of the smaller box inside the other), or concern the same name, address, employer or account number in different documents. A group is ranked by how many independent kinds of check fired in it (visual, arithmetic, cross-document, metadata): a count, not a probability. A group with two or more kinds gets a headline finding, classed as potential manipulation, that lists its members and cites each of their places once. Context rules are linked but count as no kind, and limitations are never grouped. Findings that share none of these stay apart even where a person would relate them. Not evaluated on a held-out set; the overlap limit is a starting value. |
| Plain-language explanations and next steps from fixed templates | Implemented | 2 | Fixed wording per detector and class. Without --llm nothing is written by a model; the next row covers the optional model. |
| Explanation wording from a local language model | Partial | 16 | Optional, and off unless a run is started with --llm. A small model (phi4-mini 3.8B, MIT) runs through Ollama on this computer, and the client refuses any other host. It words the headline of each group of findings and reads the case once for relations between findings, a short summary and a reading order. It sees structured findings (ids, kinds of check, titles, the values the checks used) and no page text, and it cannot add, change or remove a finding. Each part of what it writes is used only if the guard accepts it (ids, figures, dates, verdict words), and a relation only if its kind is true of what the two findings cite; the rest is dropped and logged. It is labelled as inference. Partial because it was measured only on development-set prompts, CPU only, one run each (the guard accepted 18 of 24 headline wordings), the guard does not check meaning, and nothing was run on a held-out set. |
| Evidence traceability: finding to file, sha256, page and box, with a marked crop | Implemented | 3 | Every piece of evidence names its document, page and box; the trace command prints them and checks the stored file's hash. |
| Investigation dossier: HTML (self-contained) and JSON, with its own hash | Implemented | 3 | Observations, inconsistencies, potential-manipulation candidates and limitations are kept in separate places. |
| Dossier export as PDF | Planned | 0 | Print the HTML dossier to PDF from a browser meanwhile. |
| Tamper-evident audit trail with a verify command | Implemented | 3 | Each event carries the hash of the one before it. The dossier records the trail's length and last hash. |
| Safe failure: rejected files, failed or stuck steps become visible limitations | Implemented | 3 | A step that fails or times out is listed as a limitation and the case goes on. A step stuck in native code is abandoned, not killed. |
| Offline operation | Implemented | 1 | The OCR models ship inside the package. The test suite runs with connections to public addresses blocked. |
| Review interface in the browser | Partial | 7 | Runs on this computer only. Upload, a background run with progress, page images with word, field and finding boxes, evidence crops, reviewer actions written to the audit trail, the audit trail, this list and the dossier download. The server side is tested; how the page behaves in a browser was checked by hand, not by an automated browser test. Findings that share evidence are grouped in the Clusters tab, each group under its headline. |
| Handwriting and multilingual OCR | Planned | 0 | Not built; text is read as printed English. |
| Real-world document layouts at scale | Unsupported | 0 | Only synthetic documents were used. Nothing is claimed about real ones. |
| Logo and stamp comparison across documents of one issuer | Partial | 5 | The logo (right of the issuer's name) and the stamp (above its caption) on each document whose type spec lists them (bank statement, loan application) are cut out, straightened by the page's turn if it is a scan, and compared by shape with those on every other document whose issuer line reads alike; a stamp is compared at its best turn within 8 degrees. A pair that differs by more than the stated limit is an inconsistency with both marks marked; every pair compared is written to the audit trail. A mark that cannot be found or read (no ink, no caption, a poor page, printed matter in the window) is a limitation, never a pass. Built and measured on synthetic marks only: six invented designs, two of which (the same motif in a circle and in an octagon) are not told apart, and a small change to a logo is not found. Not yet evaluated on a held-out set. |
| Verdicts on authenticity or intent; telling who signed; photographs and identity documents | Unsupported | 0 | Unsupported by design. The tool lists anomalies for a human reviewer and never concludes. Signatures, logos and stamps are compared by shape between documents, which does not say who signed or who issued them. Photographs and identity documents are not examined. |
<!-- capabilities:end -->

## Limitations

The full list of limitations and assumptions, and a table of the ordinary things that raise each finding, is in [docs/limitations.md](docs/limitations.md). In short:

- Nothing was evaluated on real documents, real scanners or real layouts.
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

The author chose the problem statement, set the requirements and constraints (offline, synthetic data only, findings for a reviewer and no verdicts) and is responsible for what is submitted.

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
