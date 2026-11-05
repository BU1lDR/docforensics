# Compression history of a scan (error-level analysis), measured on ext-dev (package E, 5 and 6 Nov 2026)

What was built: for a scanned page that is a JPEG picture, the tool saves the page again at qualities 25 to 95 in steps of 5 and measures how much that changes its ink. The quality at which it changes the ink least is the page's last save. If, at a quality at least 10 below that, saving again changes the ink clearly less than at the qualities beside it, the page was saved earlier at about that quality and most of its ink still carries the trace. Compact regions of ink that do not carry the trace are reported as one observation a page, with their boxes, the two qualities and the ordinary causes. A page saved once, or saved again with nothing changed, gives nothing. A picture the check cannot read as the JPEG that was saved (a PNG, the rendered page of a scanned PDF, a picture the reader scaled or turned upright) gives a limitation, "not examined", never a pass. It runs on every page read by OCR, whatever its quality class, and needs no model.

What it is not: it does not say that anything was changed. It says that a part of a page has a different compression history from the rest. A page put together from more than one scan, a stamp, date or page number added later by a scanner or a program, and a sticker leave the same mark. It sees nothing when the page was saved once, when the last save is less than 10 quality points above the earlier one, when the changed part has the page's own JPEG grid and quality, or when the earlier save was written with other quantisation tables than libjpeg's. It does not look inside a scanned PDF (the embedded picture is not taken out; the page is rendered, so the limitation is given). The idea is not new: it is the JPEG ghost of the literature (H. Farid, IEEE Transactions on Information Forensics and Security, 2009) with the quality searched for, and, with one assumed quality, what is called error-level analysis. The code is written for this project on numpy, OpenCV and Pillow (the same JPEG writer, libjpeg through Pillow, that saves the pack's scans); no other component, no model, no new dependency.

Everything below was measured on the laptop (Ryzen 5 220, CPU only, Windows 11; the run files say "Windows 10" because Python reports it so). All numbers are on development material: the `ext-dev` split of the pack made for this check, and the `dev` split for the guard. The `ext-test` split has not been run by the author of the check; it is run once, at the freeze (`--once-at-freeze`).

## The pack

`datagen/ela_pack.py` draws one fictional payslip a case and writes it as a 200-dpi JPEG scan at one of the three levels of `datagen/scan.py` (saved once, at the level's quality: 85 mild, 50 at 150 dpi, 35 at 120 dpi). Case n has a kind and a level; the kind cycles through six, the level through three every six cases. The kinds and what the check can do on each were written down before the check existed (the module's docstring, `tests/test_ela_pack.py`):

- `genuine`: the scan as the scanner saved it. `resaved`: the same, opened and saved again at quality 95. Nothing to find in either.
- `pasted-field`, `pasted-block`: the net pay, or the block of gross earnings, deductions and net pay, cut from another payslip's scan of the same level and pasted over, taken 3 px right and 5 px down of where it lies so that its JPEG blocks do not fall on the host's, then the page saved at 95.
- `retyped`: the net pay erased and another amount typed in (stock S2 of `datagen/manipulate.py`), saved at 85.
- `aligned`: the same place of another payslip's scan pasted in (stock S1), saved at 85. The pasted part has the host's own grid and quality.

`expect` follows one rule: `none` for the first two kinds; `seen` for a pasted or retyped part when the last save is at least 10 above the level's quality (two steps of the grid the check tries); otherwise `blind`, and always `blind` for `aligned`. A `blind` case is a miss the check is not claimed to cover; the reports list those cases apart and count them nowhere else. The truth is the manifest's box for the edit. Seeds are 3 100 000 and up (`ext-dev`) and 4 100 000 and up (`ext-test`). Names are invented.

Counting: a **region** is a box the check returns; **located** is a region with IoU above 0.3 against the edit's box; **stray** is a region that does not touch the edit's box; **touching** is a region that touches it (reported for the `blind` cases so that nothing is hidden). A **false flag** is a region on a scan with no edit.

## How the check works, and its constants

`forensics/ela.py`, constants at its top. Ink is a pixel more than `INK` (60) grey levels darker than the median of its neighbourhood, widened by one pixel; fewer than `MIN_INK` (24) ink pixels gives nothing.

1. The page curve: the mean change of the ink on saving the page again at each of `QUALITIES` (25 to 95, step 5). The quality with the smallest change is the **last save**.
2. The **earlier save**: for each quality at least `GAP` (10) below the last save, the dip is the geometric mean of the changes at the qualities 5 above and below it divided by the change at it. The largest dip, if it is at least `MIN_DIP` (1.3), names the earlier quality. If there is none, the page gets nothing.
3. The page is cut into cells of `BLOCK` (16) px, two JPEG blocks. A cell with at least `MIN_INK` ink pixels is measured at the earlier quality and at the two beside it.
4. A cell is a **hit** when its change at the earlier quality is more than `Z` (6) robust standard deviations (median and MAD) above the page's median cell, at least `MIN_RATIO` (2) times that median, and its own dip is under `MAX_DIP` (1.3). The last condition matters: large bold type alone has a larger change than small type, but it keeps the page's dip; a piece without the earlier save is flat across the qualities beside it.
5. Hits are closed with a 3 x 3 window and joined (8 neighbours). A component with at least `MIN_CELLS` (4) hit cells is a **region**; the observation lists at most `LISTED` (6).

Cost: the check takes 0.5 to 0.9 s a page on this CPU (the pixel runs in `eval/e/`: 0.9 s a case in the first, 0.5 to 0.6 s in the others); the whole tool on a one-page upload takes 3.4 s (OCR included; the run of `ext-dev-tool` took 122 s for its 36 cases).

The constants were set on the 36 cases of `ext-dev` that the first row below reports, by looking at the cell statistics of that pack with throwaway scripts (not kept), so those figures are **in-sample**. The pack's page-wide dips (the largest dip over the qualities at least 10 below the last save) are 1.02 to 1.03 on every page without an earlier save (genuine pages, retyped pages at the level where both saves are 85, `aligned` pages at mild) and 1.82 and above on every page that has one (retyped 1.82 to 2.55; `aligned` at 150 and 120 dpi 1.88 to 2.61; pasted 3.30 to 5.35; resaved 4.34 to 6.95). `MIN_DIP` of 1.3 is a choice inside that empty gap; a real page with a weak trace, a dip between 1.3 and 1.8, is not covered by any measurement here. Where a constant sits has not been varied to see how the figures move.

## Runs

All with the constants above, on the code of the commit named in each report. The scans are the same for the first five rows; cases 36 to 107 were not used to set anything.

| run | cases | unchanged scans with a region (false flags) | edits it is meant to see, found at the edit | stray regions | edits it cannot see: a region at all (at the edit) | last, earlier save named right |
|---|---|---|---|---|---|---|
| `ext-dev`, the check on pixels (the set the constants were set on) | 36 | 0 of 12 | 16 of 16 | 0 | 3 of 8 (0) | 16 of 16, 16 of 16 |
| the same, the whole tool on each uploaded picture | 36 | 0 of 12 | 16 of 16 | 0 | 3 of 8 (0) | not recorded in this mode |
| `ext-dev` cases 36 to 107, pixels | 72 | 0 of 24 | 32 of 32 | 0 | 2 of 16 (0) | 32 of 32, 32 of 32 |
| hosts saved between the steps of 5 (quality 82, 47, 33 instead of 85, 50, 35) | 36 | 0 of 12 | 16 of 16 | 0 | 3 of 8 (0) | 16 of 16, **0 of 16** |
| hosts written with other quantisation tables (Photoshop-family presets) | 36 | 0 of 12 | **0 of 18** | 0 | 0 of 6 (0) | 18 of 18, **0 of 18** |
| guard: the picture files of 80 `dev` cases | 95 scans | 0 of 90 | see below | 0 | see below | |

The reports are in `eval/e/`: `ext-dev-pixels`, `ext-dev-tool`, `ext-dev-36-107-pixels`, `ext-dev-off-grid-pixels`, `ext-dev-other-tables-pixels` and `dev-guard`, each as `.md` with every case listed (misses, false regions, the blind cases apart) and `.json` with the rows. The reports name the commit they were run at, with a clean working tree. The two robustness rows (hosts between the steps, other tables) were made after the constants were fixed, to see what the check cannot do; nothing was tuned on them. In the 8 and 16 `blind` cases the numbers in brackets mean: none of the regions found there sits at the edit (IoU above 0.3); the regions touched the edge of the pasted box, where the blocks of an off-grid box are a mixture. That is not claimed as a find.

## Where it falls short

- **An earlier save written with other tables is not seen at all.** The check saves with libjpeg's tables, so it can only find the dip of an earlier save written with those. With the Photoshop-family presets (`web_medium`, `web_low`) it found 0 of 18 edits and named the earlier quality on 0 of 18, though the last save was named right on all 18, and it raised nothing on the 12 unchanged scans. A scan whose first save came from a program with its own tables is silent. How common that is for real scanners and programs is not known here; the pack's scanner is the Pillow writer.
- **The quality it names for the earlier save is where the trace shows.** With hosts at 82, 47 and 33 it found the edits on all 16 cases but named 80 for the first, and 75 or 45 for the second and 75 for the third; the dip also shows at a quality that is a related step of the quantiser. The finding says so ("where the trace shows, which is not always the quality of the earlier save").
- **A change on the page's own grid and quality is invisible by construction** (`aligned`: 18 of the 108 cases of the two slices). Together with the `retyped` cases at the mild level, whose two saves are both at 85, that makes 24 cases the pack lists as `blind`. A region appeared on 5 of the 24: each one touches the edge of the pasted box, none sits at the edit.
- **A last save close to the earlier one**: 12 cases of `retyped` and `aligned` at mild, where both saves are 85, give a page-wide dip of 1.03 and nothing.
- **Single-save pages are silent**, which is the intended behaviour and also means that an unchanged-looking result says little: a scan saved once and then edited by a program that saves it once more is a double save and is covered; a scan edited and saved only once from a lossless source is not.
- **Scanned PDFs are not examined.** The tool renders the page; the embedded JPEG is not taken out of the PDF. The dossier says so as a limitation whenever the page's picture is not the saved JPEG (about 2 s of extra work would not change that).
- **Two quality classes of the other detectors do not apply**: the check runs on poor pages too, since it needs no word boxes; on the 120-dpi level of the pack it gave no false region, but a very degraded page from another scanner may.
- **Thresholds are in-sample** on the 36 cases (above). The second slice shows that they do not depend on those 36 draws, not that they hold on other generators or on real scans. Every scan here is synthetic, made by one generator and one JPEG writer.

## The guard on the `dev` split

`python -m evaluation.run_e dev` looks at the picture files (the `.jpg` scans) of the first 80 cases of the `dev` split, the cases of `eval/dev.md`, which nobody tuned the check on: 95 scans. In that split every scan is saved once at its level's quality (85, 50, 35), and a changed scan ends with one more save at 85.

- 45 scans of genuine cases: no region. 45 scans of changed cases that were not themselves changed as a picture: no region. No false flag on the 90.
- 5 scans changed by pasting a part of another scan (S1): a region on 1, at the splice (dev-0021, 150 dpi, last save found 85, earlier 50, IoU about 0.53 against the splice box). The other four: three at mild, where both saves are 85, which the check cannot tell apart; and dev-0051 at 120 dpi, where it found the history (85 over 35) and no region, so that one is a miss. This split has no S2 scan among these cases. Its S1 splice takes the same place of a scan of the same level, which is the pack's `aligned` kind, and the pack lists that kind as blind; why a region appeared on dev-0021 was not examined, so it is not claimed as a find.

The guard was run after the constants were fixed, and no constant was changed after it. It is a guard against false regions on scans nobody changed, not a measure of how many changes the check finds.

## What this supports

Compression-history analysis is **Partial**. On synthetic payslip scans saved with libjpeg, a part that was pasted in, or typed in, after an earlier save at least 10 quality points below the last was found at its place in 48 of 48 cases of the two slices (16 and 32), with no region on the 36 unchanged scans of those slices and none on 90 unchanged scans of the `dev` split. It finds nothing in the cases it cannot see by construction, in scans whose earlier save used other quantisation tables, and in scans saved once; it names the earlier save only approximately; it does not look inside scanned PDFs. What it reports is an observation with ordinary causes (a page assembled from several scans, a stamp or date added later), never a verdict. The figures are for one generator and one JPEG writer and do not predict real scans.

To repeat the reports (from the repository folder; times on this laptop): `python -m evaluation.run_e ext-dev --out <folder>` (the check on pixels, 36 cases, about 25 s); with `--pipeline` (the whole tool, about 2 min); `--start 36 --cases 72` (cases 36 to 107, about 45 s); `--hosts off-grid` and `--hosts other-tables` (about 25 s each); `python -m evaluation.run_e dev --out <folder>` (about 2 min). `--out` is relative to the repository folder; give an absolute path to write elsewhere. The pack itself: `python -m datagen.ela_pack ext-dev <folder>`.
