# Spike results, 2 Nov 2026

The throwaway code of the spike is not in the repo. Everything below was measured on the laptop (Ryzen 5 220, CPU only, 2.0 to 2.5 GB of RAM free during the runs), Python 3.11.9, rapidocr 3.10.0 with onnxruntime 1.31.1, PyMuPDF 1.28.2.

**Status.** OCR and PDF checks are done (2 Nov), and so is the CPU-only measurement of two small language models (4 to 5 Nov, section "Local language model"). The language-model tests were on hold at the author's request until 4 Nov. Vulkan and a vision-language model were not measured. Ollama 0.40.13 was installed on 2 Nov (winget, installer hash verified) and idles at about 170 MB (server 38 MB, tray app 128 MB); the model runs used 0.40.14.

## Test material and its limits

- Two fictional pages drawn with PyMuPDF in Helvetica and rendered at 200 DPI: a bank statement (130 words) and a payslip (61 words). Ground truth is the PDF text layer.
- Scans are simulated from the render: resolution loss, blur, noise, uneven lighting, JPEG. One seed, one run, no repeats.
- The typography is easy (clean vector fonts). No stamps, handwriting, photographs or real scans. Numbers below describe this material only; real scans will be worse.
- Degradation ladder (the name is the effective resolution after the loss; scale, blur px, noise sigma, lighting falloff, JPEG quality):

| Level | Scale | Blur | Noise | Falloff | JPEG |
|---|---|---|---|---|---|
| clean | 1.0 | 0 | 0 | 0 | 95 |
| mild | 1.0 | 0.6 | 5 | 0.06 | 85 |
| 150dpi | 0.75 | 1.0 | 15 | 0.15 | 50 |
| 120dpi | 0.6 | 1.3 | 25 | 0.25 | 35 |
| 100dpi | 0.5 | 1.6 | 30 | 0.30 | 25 |
| 75dpi | 0.375 | 2.0 | 40 | 0.35 | 15 |

## PyMuPDF (design 7.5)

- Draw order is available. `get_texttrace()` and `get_drawings()` share one `seqno` sequence: original text 0, white rectangle 1, retyped text 2.
- Revisions can be read. After an incremental save the file has two `%%EOF` markers; truncating at each opens as a valid document. Revision 1 reads `Net Pay 52,000.00`, revision 2 reads `Net Pay` and `82,000.00` (the redaction removed the old number).

## OCR: RapidOCR (PP-OCRv6 small, ONNX, CPU)

- Models ship inside the wheel (det 9.9 MB, rec 21.2 MB, cls 0.6 MB per the package RECORD), so there is no run-time download. Model licences are in the package's `licenses/MODEL_LICENSES.md`; they go into the README credits.
- Speed: 1.1 to 2.1 s per A4 page at 200 DPI, including word boxes. The first call also loads the models (about 1.6 s). Peak working set about 660 MB.
- Word boxes work with `return_word_box=True`: per word `(text, score, 4-point box)`.

| Level | Token recall, exact | Fuzzy | Digit tokens, exact | Digit tokens, fuzzy | Mean IoU | Words with IoU 0.5 or more | Score, correct words | Score, misread words | Misread words |
|---|---|---|---|---|---|---|---|---|---|
| clean | 1.00 | 1.00 | 1.00 | 1.00 | 0.82 | 1.00 | 0.999 | n/a | 0 |
| mild | 1.00 | 1.00 | 1.00 | 1.00 | 0.81 | 1.00 | 0.997 | n/a | 0 |
| 150dpi | 0.99 | 1.00 | 1.00 | 1.00 | 0.84 | 1.00 | 0.997 | 0.999 | 2 |
| 120dpi | 0.86 | 0.99 | 0.68 | 0.99 | 0.86 | 0.99 | 0.998 | 0.983 | 28 |
| 100dpi | 0.79 | 0.98 | 0.57 | 0.99 | 0.85 | 0.97 | 0.992 | 0.994 | 41 |
| 75dpi | 0.45 | 0.57 | 0.47 | 0.62 | 0.68 | 0.47 | 0.893 | 0.847 | 126 |

"Fuzzy" counts a token as found at difflib similarity 0.85 or more, so a one-character misread still counts. "Misread" means an OCR word that is not in the page's token set (a wrong character or a different split). The IoU is against PyMuPDF's word boxes, which probably span the font's line box while OCR boxes hug the glyphs (not checked), so 0.82 on clean text is a convention gap, not an error.

Findings:

1. Reading is exact down to the 150dpi level and falls apart below it. At 120dpi about a third of the digit tokens are wrong by a character or two (68% exact, 99% fuzzy), which is exactly the kind of error that changes an amount.
2. **The recogniser's score does not flag these errors.** Misread words scored 0.983 against 0.998 at 120dpi and 0.994 against 0.992 at 100dpi. Only at the 75dpi collapse do scores drop (0.893 against 0.847), and even there they overlap.
3. **A second read does not flag them either.** Re-reading each digit word's crop at 2x (digit words only, 72 to 73 per level):

| Level | Misread digit words | Caught by score below 0.99 | Caught by 2x disagreement | Correct words falsely flagged by disagreement |
|---|---|---|---|---|
| 150dpi | 0 of 72 | n/a | n/a | 1 of 72 |
| 120dpi | 24 of 72 | 1 | 2 | 0 of 48 |
| 100dpi | 33 of 73 | 2 | 8 | 2 of 40 |

   The recogniser makes the same mistake on the enlarged crop. Self-agreement is not a usable confidence signal.
4. Consequence for the design: field confidence for scans cannot be built on the recogniser's score. See 7.2 of the design (page-quality class plus arithmetic validators, with demotion to "possible extraction error").

## Page quality without OCR

Two statistics on the same ladder, two pages each (stmt, slip):

| Level | Edge sharpness (stmt, slip) | Noise estimate (stmt, slip) |
|---|---|---|
| clean | 0.395, 0.393 | 0.00, 0.00 |
| mild | 0.354, 0.351 | 1.52, 1.48 |
| 150dpi | 0.268, 0.265 | 3.11, 2.99 |
| 120dpi | 0.220, 0.215 | 6.64, 6.44 |
| 100dpi | 0.189, 0.183 | 5.99, 5.80 |
| 75dpi | 0.173, 0.169 | 5.36, 5.18 |

- Edge sharpness (99.5th percentile gradient on a lightly smoothed copy, divided by ink-paper contrast) falls steadily and agrees across the two pages. A threshold near 0.24 would split 150dpi (reads fine) from 120dpi (digits break) on this ladder.
- The noise estimate is not usable: JPEG smoothing hides most injected noise (injected sigma 15 to 40, estimated 3 to 7) and the values stop rising after 120dpi. Drop it.
- This is circular: thresholds fitted on the generator that made the degradation. They must be re-checked on degradations the fit never saw (motion blur, other fonts, textured paper) before anything is claimed about real scans.

## Layout of words on a scan (Task 17, 4 Nov)

42 genuine simulated statements (levels mild, 150dpi, 120dpi x seeds 1 to 14, layout A, 100 words each), read with RapidOCR; the scan detector `scan_layout` run on each.

- The reader's word boxes follow the slant of a turned page (centres track the line slope). The turn of the page is estimated by maximising the sharpness of the deskewed word-centre histogram over +-3 degrees in 0.05 steps (widened to +-10 in Task 25, see "Turn of the page" below). It matched the turn the simulation applied within 0.05 degrees on all 42 scans (statements of 100 words; pages with fewer words are less exact, see below).
- Largest difference between a genuine word and the text around it, after straightening (px at 200 dpi):

| Measure | Pages not degraded (28) | Degraded pages (14) |
|---|---|---|
| position across the row (centre) | 3.3 | 3.5 |
| height of a figure against the page's figures | 7.0 (mild seed 3; next 5.5 and 5.1) | 3.2 (figures read on 1 to 5 per page, often too few to compare) |
| right edge of a figure against its column | 6.1 (mild seed 13) | not measurable: no column of four figures found on any |

- Comparing the height of every word against its own row failed: genuine words reached 8.6 px, because the height of a box depends on the letters (descenders) and on the slant of the whole detected line. Only figures (single-word boxes) are compared for height.
- Floors on the usual spread are 1.5, 2.5 and 2.5 px (x1.5 on degraded pages), so with layout_k = 4 a difference must be 6, 10 and 10 px. With them, 0 observations on all 42 genuine scans. The largest genuine differences reach 55%, 70% and 61% of the three thresholds; the largest right-edge difference rose from 5.6 px (seeds 1 to 6) to 6.1 px (seeds 7 to 14), so the maximum had not settled.
- Circular, as the quality gate is: the floors are fitted on scans from the generator that rotates about the page centre by 0.5 to 2 degrees, with no creases, curl, perspective or scanner skew. They must be re-checked on the held-out split (Task 19), and nothing is claimed about real scans.

## Signatures (Task 25, 4 Nov)

Setup: 14 invented people (identity seeds 1 to 14, layout A), each with 2 applications and 3 payslips drawn in their own hand, the signing jittered (the control points of the strokes move by up to 0.12 of the box) by a random generator of its own. Every document as a digital PDF and as a scan at mild, 150dpi and 120dpi, read by the real pipeline (RapidOCR finds the caption, the turn of the page is estimated, the window above the caption is sized by the caption's word height). All 70 signed documents of each of the four levels were located (0 not located).

Measure: share of the ink of the one signature (cut to its box, scaled to 192 x 64 px) that lies farther than 6 px from the ink of the other, the larger of the two directions, at the best slide within 4 px. Pairs per level pair: 84 of one hand (2 applications x 3 payslips x 14 people) and 1092 of two hands. Eleven level pairs:

| Level of application : payslip | Same hand, largest | Same hand, median / 90th percentile | Two hands, smallest |
|---|---|---|---|
| digital : digital | 5.95 | 0.00 / 1.2 | 17.11 |
| mild : mild | 5.90 | 0.00 / 1.3 | 15.38 |
| 150dpi : 150dpi | 5.71 | 0.00 / 1.4 | 15.29 |
| 120dpi : 120dpi | 5.15 | 0.00 / 1.7 | 14.52 |
| digital : mild | 6.03 | 0.00 / 1.2 | 16.26 |
| mild : digital | 5.81 | 0.00 / 1.4 | 16.31 |
| mild : 150dpi | 6.07 | 0.00 / 1.4 | 15.71 |
| 150dpi : 120dpi | 5.21 | 0.00 / 1.5 | 14.59 |
| 120dpi : 150dpi | 5.77 | 0.00 / 1.5 | 15.29 |
| digital : 120dpi | 5.75 | 0.00 / 1.4 | 15.79 |
| 120dpi : digital | 5.59 | 0.00 / 1.6 | 15.86 |

- The distances of two hands have a median of about 40 (digits: 40.0 to 42.3 per level pair).
- The largest same-hand distance is the same pair at every level pair (person 9, application seed 50 against payslip seed 40), digital included, so it comes from how those two signings were jittered and not from the scan. The next largest same-hand distances are 2.9 to 3.0 (the five largest at digital : digital are 2.58, 2.64, 2.87, 2.95 and 5.95). One outlier in 84 pairs, so the tail of the same-hand distances is heavier than the bulk shows.
- Limit `signature_dist` = 9.4, the geometric mean of 6.1 (the largest same-hand distance on any level pair) and 14.5 (the smallest two-hands distance). Nothing in the dev split falls on the wrong side: 0 of 84 same-hand pairs over the limit and 0 of 1092 two-hands pairs under it, at all eleven level pairs. The first fit (8.0) came from 42 same-hand pairs per level (largest 3.24, from an oracle that read the signatures straight from the generator's ink) and was moved once the larger set showed 6.1.
- Dropped measure: the mean distance from each ink pixel to the other's ink (a chamfer distance). On scans it overlapped (same hand up to about 1.9, two hands from about 1.5), because speckle and thickened strokes of a scan raise it more than a different shape does. Without straightening by the page's turn (slide of 4 px only) the ratio of the smallest two-hands distance to the largest same-hand distance fell from 5.5 to 9.1 (oracle, before the larger set) to 2.9 or more, so the turn matters even for the best measure.
- Circular, like the quality gate and the layout floors: the hands are drawn by one generator from a few strokes; the jitter is small and every signing uses the same pen on white paper. Real signatures vary far more, and a person signs a payslip differently from a loan form. The limit says nothing about real signatures, and a signature copied onto another document gives a distance near 0 and passes.
- Window: left edge 0.8, right edge 17.0 and top 6.6 caption word heights from the caption's left edge and top; the bottom is the caption's top. Caption word height is about 30.5 px on a text layer and 35 to 37.5 px in OCR boxes. No printed word lies in that area on either layout (the nearest ends 1668 px above the application caption and 1166 px above the payslip caption), so the area holds the signature only.

## Turn of the page, searched wider (found in Task 25, 4 Nov)

- Task 17 searched the turn of a page over +-3 degrees. A page turned further was not reported as such: the search ended at some angle inside its range. With +-3, a scan turned by +6.27 degrees was estimated at +1.00, one turned by +9.27 at -1.55, and a synthetic grid tilted by 4.5 degrees at 0.4. Such a page was compared at the wrong angle, and on the grid a tilt of 3.5 degrees gave a spurious observation. The Task 17 rule "a page turned by 2.9 degrees or more is not compared" held only inside the search range.
- Fix: the search runs over +-10 degrees (`_SEARCH_DEG`) and the limit for comparing is a constant of its own, `MAX_TURN` = 2.9 (the layout floors were fitted on turns of 0.5 to 2 degrees). On the probe pages the wider search found the true turn within about 0.07 degrees. Beyond 10 degrees the estimate is arbitrary again; the capability text says so.
- Nothing in range moved. 84 documents per level (14 identities x 2 applications, 3 payslips and 1 statement); the estimated turn against the turn the simulation applied, for searches of +-3 (before), +-10 (shipped) and +-15:

| Level | Largest error (degrees) | Over 0.10 | Over 0.15 | Worst page |
|---|---|---|---|---|
| mild | 0.20 | 13 | 7 | application, 69 words |
| 150dpi | 0.23 | 18 | 6 | application, 64 words |
| 120dpi | 0.31 | 15 | 9 | application, 69 words |

  The three searches gave the same largest error and the same counts at every level. The larger errors are on applications of 64 to 69 words; the statements of the Task 17 study (100 words) were within 0.05. With errors up to 0.31, a page whose true turn lies within about 0.3 degrees of the 2.9 limit can fall on either side of it.
- Circular: the simulation turns pages by 0.5 to 2 degrees about the page centre, and the grid is synthetic. The search has not been tried on a page with perspective, curl or a scanner that skews unevenly.

## Logos and stamps (Task 26, 4 Nov)

Setup: six invented banks, each with a logo (a box of 34 pt) and a stamp (60 pt) drawn from strokes by `datagen/marks.py`: one to three rings in the shape of a circle, an octagon or a square, around a star, spokes, bars or a wave. Each pressing is moved by up to 0.03 box widths, scaled by up to 4 % and turned by up to 1 degree (logo) or 4 degrees (stamp), so two genuine marks are close but never equal. Identity seeds 1 to 12 (two per bank, layout A), each as a statement and an application: 24 documents, as digital PDF and as scan at mild, 150dpi and 120dpi, read by the real pipeline. All 96 documents had both marks located (0 not located). Two variants of each application, with only its mark replaced: the small edit (the bank's own design with one point of the logo's motif moved 0.1 box widths toward the middle, or the stamp's innermost ring left out) and the large edit (the design of another bank).

Measure: the share of the ink of one mark (cut from its window, straightened by the turn of its page, cut to its box and scaled to 128 x 128 px) that lies farther than 3 px from the ink of the other, the larger of the two directions, at the best slide within 3 px; for stamps also at the best turn of the second mark within 8 degrees (steps of 2). Genuine pairs: any two documents of one bank at any two levels (576). Other-design pairs: any two documents of two banks (3,840). Edits: each application's variant against the statement of the same seed at all 16 level pairs (192 each), and against the unedited application at equal levels (48).

Logo (percent of the ink):

| Pairs | n | Smallest | Median | 90th percentile | Largest |
|---|---|---|---|---|---|
| genuine | 576 | 0.0 | 0.0 | 0.9 | 8.5 |
| other design | 3840 | 0.3 | 35.1 | 51.8 | 58.7 |
| small edit | 192 | 0.6 | 1.8 | 4.7 | 14.0 |
| large edit | 192 | 0.5 | 26.0 | 48.3 | 55.6 |
| small edit against the unedited application | 48 | 0.6 | 1.1 | 2.7 | 3.5 |

Stamp:

| Pairs | n | Smallest | Median | 90th percentile | Largest |
|---|---|---|---|---|---|
| genuine | 576 | 0.0 | 0.0 | 0.1 | 1.6 |
| other design | 3840 | 5.8 | 23.2 | 40.8 | 48.9 |
| small edit | 192 | 21.2 | 24.1 | 36.4 | 41.0 |
| large edit | 192 | 7.6 | 17.9 | 41.1 | 42.3 |
| small edit against the unedited application | 48 | 20.5 | 23.8 | 35.3 | 39.7 |

- Limits (`config.py`): `logo_dist` = 10.5, the geometric mean of 8.5 (the largest genuine pair) and 13.1 (the nearest pair of designs after the one pair that cannot be told apart, Bluepeak and Meridian); `stamp_dist` = 3.0, the geometric mean of 1.6 and 5.8 (Lakeshore and Orchard). The logo margin is thin: 2.0 above the largest genuine distance and 2.6 below the nearest pair. The largest genuine logo distances (8.5, 7.4, 6.5) compare a digital page with a 120dpi scan; the largest genuine stamp distances (1.6) sit at the 120dpi level.
- At the limits: 0 of 576 genuine pairs over, for logos and for stamps. **Stamps: no miss anywhere** (other design 0 of 3,840, small edit 0 of 192, large edit 0 of 192, small edit against the unedited application 0 of 48). **Logos: two measured misses.** (1) Two of the six designs, Halcyon and Orchard, are the same motif in a circle and in an octagon; their distances run from 0.3 to 8.0 (median 1.7), inside the genuine spread, so no limit separates them: 256 of the 3,840 other-design pairs, and 32 of the 192 large edits (the two seeds whose "other bank" is that one), are under the limit. (2) The small logo edit is not found: 191 of 192 are under the limit (the largest is 14.0), and against the unedited application 48 of 48. A moved point is 0.1 of a box width; at the canvas used it changes few pixels.
- Window (`forensics/marks.py`), in word heights u: the logo window runs 0.2 to 4.5 u right of the right end of the issuer line (the tallest line of page 1 that holds three letters or digits), 1.5 u above and below the middle of the line; the stamp window runs from 1.2 u left of the caption's left edge to 10.0 u right of it and from 10.5 u to 0.1 u above the caption's top (u = median word height of the caption). A window clipped to under half its nominal width or height is not compared. Ink: darker than the paper (median-blur estimate) by more than 50 grey levels, specks under 12 px removed, as for signatures. Genuine windows hold 0.63 to 1.55 u squared of logo ink and 3.2 to 11.1 u squared of stamp ink, and up to 12.0 % (logo) and 9.5 % (stamp) of the window; none touches the window's edge. A window with under 0.25 u squared of ink is "no mark found", with more than 30 % of its area "printed matter", and with ink at its edge "may be cut off": each is a limitation and never a pass.
- Tried and dropped: a canvas of 64 x 64 px (the measure saturated; 128 shipped), anchoring the logo window at the first cell of the issuer line instead of its right end (both were calibrated; the end of the line shipped), and blanking the words that OCR reads inside the window (the plan said to; the words read there are the mark itself read as characters, and genuine windows hold no printed words). The turn search for stamps is needed: the generator turns each stamp by up to 4 degrees, and without the search the largest genuine stamp distance is 19.7 (90th percentile 6.7), with 113 of 576 genuine pairs over 3.0.
- A side finding: OCR reads a logo or stamp as a stray character, which can be the tallest line of page 1 and so become the `bank` field. `issuer_line` now takes the tallest line with three letters or digits at least; `tests/test_marks.py` has the case.
- Circular, like the quality gate and the signatures: the six designs are drawn by one generator from a few shapes in one colour on white paper, and the development and the held-out splits share them. The held-out split (Task 19) tests new seeds and new scans, not new designs. The limits say nothing about real logos or stamps, which vary in colour, pressure and ink. The comparison covers shape only: a mark copied from another document gives a distance near 0 and passes. A document with no mark of its own is not found by this check; it is found only when other documents of the same issuer carry one.

### Fixes to the mark and signature comparators (28de085 and 7184281, 4 Nov)

Found while the dev split was being run and from injected cases; fitted on generated dev marks and injected inputs only, and no test-split output was read. No limit moved: `signature_dist` 9.4, `logo_dist` 10.5, `stamp_dist` 3.0. What changed: (1) a piece of ink under a tenth of the largest piece that sticks out of the box of the bigger pieces is dropped before a signature or mark is cut and scaled, because it stretched the box (the speck limit of 12 px is unchanged); (2) where the 31 px median lies inside a mark wider than 15 px, the paper level is the median of the whole area, so a filled logo (a solid disc, a wide ring) is no longer read as hollow, and the "mostly ink" check now runs before the stray step; (3) the words of other lines are erased from the logo window (their boxes padded by 0.1 of a word height), and a line of text that ends inside the logo is a limitation, not a comparison, so a short issuer name no longer lets the line beneath it run into the window; (4) when two or more documents carry a kind of mark and none shares its issuer line with another, the existing limitation "Issuer marks only partly compared" now names each of them (before, that case left no trace and a comparison that never happened looked like a pass); (5) the issuer line is the topmost line that reads as a name among those at least 85 % as tall as the tallest (below).

Marks: 12 statements and 12 applications over the six banks (two per bank), each digital, mild, 150dpi and 120dpi (96 documents), re-read on the reader of 9e8d2d8. The "before" column is the code of 1268b1b on the same documents; it is not the first Task 26 table above, which was read on the reader of the day (there the largest genuine stamp pair was 1.6, here 2.54: the stamp margin to 3.0 was thinner than that table showed).

| | Logo (limit 10.5) | Stamp (limit 3.0) |
|---|---|---|
| Pairs located (genuine + different) | 4,416 (576 + 3,840) | 4,324 (564 + 3,760) |
| Largest genuine pair, before then after | 6.52 then 6.52 | 2.54 then 0.27 |
| 99th percentile of genuine pairs | 3.55 then 3.53 | 1.36 then 0.14 |
| Nearest different pair | 0.23 then 0.22 (Halcyon and Orchard) | 5.80 then 5.80 |
| Nearest different pair, without the closest pair of banks | 13.79 then 13.79 | 6.86 then 6.86 (Lakeshore and Orchard) |
| Genuine pairs that rose by more than 0.5 | 0 | 0 |

The Halcyon and Orchard logos differ in outline only and are not told apart at any limit (documented). The stamp of one application at 120dpi is not located before or after (the OCR misses the caption).

Short issuer names (one genuine statement and application per name, digital, mild, 150dpi, 120dpi; logo distance in percent, "!" = reported as different, "limit" = not compared, a limitation):

| Issuer line | Before | After |
|---|---|---|
| SBI | limit, limit, limit, limit | 0.00, 0.38, 2.21, 2.67 |
| ICICI | 27.67!, limit, 39.25!, limit | 0.03, 0.87, 1.66, 1.95 |
| Canara | 42.11!, limit, limit, limit | 0.02, 1.39, 0.45, 0.65 |
| Merid | 26.86!, limit, limit, limit | 0.00, 1.50, 3.35, 3.17 |
| Meridian Test Bank | 0.00, 0.00, 0.00, 0.05 | unchanged |
| Axis Bank, Meridian Te | limit at all four | limit at all four, now with the true reason ("text of another line ends inside the logo ... cannot be told apart") |

Four genuine pairs that were reported as different are now compared and pass (3.35 at most against 10.5). Two that cannot be compared say so and are not counted as a pass.

Signatures (14 people, 2 applications and 3 payslips each: 280 documents, 11 level pairs; measured on the 1268b1b reader and generator, not rebuilt on 9e8d2d8): largest genuine pair 7.30 then 7.30 (limit 9.4); nearest different pair 15.34 then 15.62. Nine genuine pairs rose by more than 0.5 (by 1.90 at most, all from one person's application at 120dpi; none above 7.30 afterwards): dropping strays removes the end of one real stroke there. Accepted and documented as a ceiling.

Issuer line: the topmost line that reads as a name (three letters or digits at least) among the lines at least 85 % as tall as the tallest, so a subtitle that a scan made as tall as the employer's name ("Payslip") no longer takes its place. Evidence, height of the topmost line over the tallest line on 168 payslips (14 people, 3 each, 4 levels): digital 1.000, mild at least 0.941, 150dpi at least 0.909, 120dpi at least 0.963; applications and statements 1.000. A tolerance of 10 % would clear the worst case by 0.009, 15 % by 0.091. On the marks set 0 of 96 documents change line; on the signature set 19 of 280 (all scanned payslips) change from "Payslip" to the employer, all correct.

Ceilings that stay (in the limitations and the Partial capability row): a stray larger than the speck threshold, or inside the mark's own box, counts as part of the mark; a solid logo filling more than 30 % of its window is reported as "mostly ink" and not compared; text printed over a logo erases part of that logo in the one document that has it, so the two differ; a page title shared by documents of different issuers and more than 15 % taller than the issuer line groups them as one issuer; dropping strays can remove the end of a real stroke.

## Dev split, first runs (Task 19, 4 Nov)

Setup: `python -m evaluation.run_eval --split dev`. 80 cases of layout A (seeds 1,000,000 to 1,000,079): 26 genuine (every third) and 54 with one change each. The PDF edits (D1, D2, D4, D5) are digital; the splices (S1) are scans at mild, 150dpi or 120dpi; the other changes and the genuine cases alternate between digital and the three scan levels. D3 and S2 appear only in the held-out test split. The dev split is the only one anything was fitted or fixed against; the test split is run once, after the specs and detectors are frozen. Counting rules are printed in every report.

**First run (commit 1268b1b).** Detection: 50 of 54 changes found, 19 of 23 with a place on a page located. Genuine documents: 12 flags on 78 documents (5 of 26 genuine cases flagged), 46 limitations. Extraction on documents nobody changed, by medium:

| Kind of value | digital | mild | 150dpi | 120dpi |
|---|---|---|---|---|
| amounts | 100 % | 25.1 % | 26.2 % | 16.5 % |
| dates | 100 % | 44.1 % | 100 % | 52.7 % |
| text | 100 % | 52.5 % | 88.9 % | 40.5 % |

On mild scans 689 of 922 amounts were missing and 2 wrong: the pipeline said "not found", it did not guess. The cause was not the OCR (the same words were on the page): `lines_of` put a word on a line when its vertical centre lay within 0.4 word heights of the line's mean, which holds for level rows only. A scan is turned by 0.5 to 2 degrees, so along a wide row the centres drift by tens of pixels, rows broke apart, and a transaction row no longer read as one with a date in its first column.

**Fix (9e8d2d8).** Extraction reads each OCR page as it would stand upright: the turn comes from the same estimate the scan detectors use (`page_turn`, within 10 degrees), words are placed on the straightened page, and the boxes of the extracted fields are mapped back to the page as given, so an evidence box still lies on the original image. A page with fewer than 12 words, or read from a text layer, is not turned. The gap that starts a new cell (`CELL_GAP`) went from 0.5 to 0.8 word heights: drawn text keeps its words within 0.2 of a word height and its columns 1.2 or more apart, but OCR boxes put the words of a name up to 0.6 apart, and at 0.5 an employer name split into two cells and the value was its first half.

**Rerun (22:47).** Detection did not move (50 of 54, 19 of 23 located); genuine documents: 2 flags on 78 documents, 1 of 26 genuine cases flagged, 20 limitations. Extraction on scans, layout A:

| Kind of value | mild | 150dpi | 120dpi |
|---|---|---|---|
| amounts | 922 of 922 (100 %) | 352 of 400 (88.0 %): 48 unreadable, 0 wrong | 77 of 382 (20.2 %): 291 unreadable, 14 wrong |
| dates | 100 % | 100 % | 100 % |
| ids | 62 of 63 | 28 of 28 | 28 of 28 |
| text | 614 of 617 (99.5 %) | 262 of 270 (97.0 %): 8 wrong | 166 of 262 (63.4 %): 72 wrong, 24 missing |

- Digital documents: 100 % on all four kinds (2,570 amounts, 1,108 dates, 175 ids, 1,717 texts).
- What is left on amounts is the OCR (see the OCR section: at 120dpi about a third of the digit tokens are off by a character). `parse_amount` accepts only well-grouped numbers, so a misread digit usually makes an unreadable amount (reported missing) and sometimes a different valid amount (wrong: 14 of 382 at 120dpi). Nothing repairs a digit or a separator.
- What is left on text: names and descriptions the OCR misreads (UPI read as UP, a name read with an l for an I, "Transter" for "Transfer"). The remaining flagged genuine documents trace to one reader defect, not to the OCR: on a payslip scan the line under the employer's name (the word "Payslip", about as tall as the name) can be taller than the name and be taken for the employer. Fixed on the Task 26 branch (the issuer line is the topmost among the lines within 15 % of the tallest height); the rerun after the merge is the next paragraph.

**Rerun on the merged tree (e85fd73, 23:27, clean tree).** Detection did not move: 50 of 54 changes found, 19 of 23 located, the same four misses (dev-0021, dev-0036 and dev-0051 are spliced scans, dev-0043 is the small logo). Genuine documents: **0 flags on 78 documents** (12 in the first run, 2 in the 22:47 rerun), 0 of 26 genuine cases flagged, 20 limitations raised apart from those, no flag in a changed case that cites no changed document. The two flags left at 22:47 (dev-0029 at 150dpi: cross_employer and cross_payer) and the three off-target flags (dev-0027, dev-0057, dev-0066) are gone: they were all the same defect, the word "Payslip" taken for the employer, which the 15 % rule removes. On scans, text went from 614 of 617 to 617 of 617 at mild and from 262 of 270 to 263 of 270 at 150dpi; nothing else in the extraction table moved. Time: 2.40 s per scanned page and 0.36 s per digital page for the whole pipeline, peak memory of the process 812 MB; the run took 5.5 minutes for 80 cases.

**Wrong values that nothing warned of.** The extraction table has a column for wrong values read at a confidence at or above the 0.6 limit under which the pipeline doubts a value: a wrong value that is doubted reaches the reviewer as a limitation, one that is not is a silent error. On the dev scans (layout A) 8 of the 94 wrong values were not doubted: 1 id at mild (1 wrong) and 7 texts at 150dpi (7 wrong). At 120dpi none of the 14 wrong amounts and none of the 72 wrong texts was trusted, because the confidence of a value is capped by the quality class of its page (good 0.95, degraded 0.5, poor 0.2) and every 120dpi page of the dev split is degraded, so nothing read there reaches 0.6. The 8 trusted values all sit on good pages, where the OCR engine's own confidence gave no warning; they are the residual risk of scans the gate calls good, and nothing repairs them. Amounts on good pages: 0 wrong of 1,322 read, 48 unreadable (reported missing, not guessed). Digital documents: 0 wrong of 5,570 values.

**Page quality classes on the dev scans (no OCR, 4 Nov).** Sharpness of the 95 scanned pages of the dev split, one page per document: mild 0.332 to 0.340 (51 pages, all good); 150dpi 0.249 to 0.258 (22 pages, all good); 120dpi 0.202 to 0.211 (22 pages, all degraded); none poor. Each medium spans 0.008 to 0.009. The dev pages read lower than the pages of the same medium in the ladder above (150dpi: 0.249 to 0.258 against 0.265 and 0.268; 120dpi: 0.202 to 0.211 against 0.215 and 0.220), so the content of a page moves its sharpness by about as much as the 0.009 between the lowest 150dpi page and the `sharp_good` limit of 0.24. The limits stay at 0.24 and 0.18: any good limit from 0.211 to 0.249 sorts the dev pages the same way, so the dev split cannot place it more exactly, and `sharp_poor` has no dev evidence at all (no dev page is near it; the ladder puts 100dpi at 0.189 and 0.183, 75dpi at 0.173 and 0.169). The two possible errors are not equal. A 120dpi-like page called good would have its digits trusted (at 120dpi only 20.2 % of the amounts were read and 14 were wrong), which is the costly error. A 150dpi page called degraded loses its text-based flags to limitations, which the reviewer still sees, which is the cheap one. The 0.24 limit sits on the side of the cheap error. The report of the test split lists the quality classes of its own scanned pages by medium, so a flag lost to the gate shows up there; the limits are not tuned against it.

**Layout B (the second layout of the test split).** Drawn after the spec files were final. About half of its labels, column headings and captions are wordings the spec files do not list (a value under one is reported missing, never guessed), and its dates carry no weekday (03-Nov-2026); `tests/test_layout_b.py` fails if a synonym for one of them is later added to a spec file. It was read once, on digital drawings, before the test split was built. That read found one defect: a label that is the start of a longer listed one ("Employer" in "Employer Name") left the rest of the label as the value. Taking the longer of two equal matches fixed it; nothing else was changed for B. Layout B on scans, and the test-only changes D3 and S2, have not been run: they are for the single test run.

**Spliced scans (S1): 2 of 5 found.** What the dev cases show:

| Case | Medium | What was pasted | On a line of 4+ words? | Found |
|---|---|---|---|---|
| dev-0006 | mild | payslip, gross earnings | no | by the payslip's own sums, not by position |
| dev-0021 | 150dpi | statement, closing balance | no | no (a limitation only) |
| dev-0036 | mild | application, loan amount | no | no (a limitation only) |
| dev-0051 | 120dpi | application, declared income | no | no (the page is degraded: the income mismatch is demoted to a limitation) |
| dev-0066 | mild | statement, credit in row 2 | yes | yes, by `scan_layout`: the pasted amount stands 12.1 px off the row (8.1 times the spread) |

- A paste is seen if it differs from the page around it in position, size or grain. `scan_layout` measures a word only against a row of four words or more (and a figure's height and right edge only against four or more figures in a column). A label and its value are two or three words on a line, so the four header-field pastes could not be measured at all: their offsets are undefined, not small. Only the paste in a table row was.
- In the simulation donor and host scans share one grain: the per-word grain ratios in the pasted boxes are 0.99 to 1.20 against the page median (limits 0.5 and 2.0), so `scan_noise` has nothing to see. The pasted digits are in the same font and size.
- Position differs only by the difference of the two pages' turns times the distance from the page centre. A donor turned almost like the host leaves little: 0.1 degrees of difference, 800 px from the centre, is 1.4 px against the 6 px the detector needs, so such a splice is invisible to position as well.
- Decision: no new splice cue was added. With five dev cases, any new threshold would be fitted to them and cost false flags on genuine scans; the miss is reported with its cause. A header-field splice is found only when an arithmetic or cross-document check disagrees (dev-0006), and on degraded pages that finding is demoted to a limitation.

**What the dev figures cannot say.** One generator drew all documents and all scans; the specs, the reader, the thresholds and the detectors were fixed against these 80 cases. The dev figures are the ceiling of what the pipeline does on documents like these, not a forecast for the test split, and not for real scans.

## Local language model (Task 22, 4 to 5 Nov)

Measured on the laptop, CPU only (the Radeon 740M was not used), Ollama 0.40.14, temperature 0, seed 0, context 4096, on AC power with the usual apps open. The prompts are the real ones of the explain stage, built from dev-set cases: 24 cluster headlines, and 10 case readings with the shipped prompts. One run per prompt on a few synthetic cases, so the rates are rough and the order of the two models could change on other documents. The model sees structured findings only (ids, kinds of check, titles, the values the checks used), never page text.

Models: phi4-mini 3.8B (MIT) and qwen3-4b-instruct-2507 q4_K_M (Apache-2.0, read with `ollama show --license`). gemma3:4b (Gemma Terms of Use, not a permissive licence) was pulled and not run.

**Wording of a cluster headline** (24 headlines, shipped prompts). "Accepted" means the guard let it through; the guard checks ids, figures, dates and verdict words, not meaning.

| Model | JSON valid | Accepted | Refused for | Tokens/s | Seconds per call (max) | Peak model memory | Lowest free RAM |
|---|---|---|---|---|---|---|---|
| qwen3-4b-instruct-2507 | 24/24 | 13/24 | 7 figure not in the evidence, 4 verdict wording | 7.8 | 25.6 (38.7) | 3.45 GiB | 2.00 GiB |
| phi4-mini 3.8B | 24/24 | 18/24 | 6 figure not in the evidence (all computed sums) | 8.7 | 16.7 (35.1) | 3.41 GiB | 1.99 GiB |

With the first prompts the guard accepted 14 of 24 for qwen3 (refused: 5 verdict wording, 5 calculated sums) and 21 of 24 for phi4-mini (refused: 3 figures). A cold first call costs 3.8 to 5.6 s of loading, and the product loads the model for every call (`keep_alive` 0).

**Reading a whole case** (a summary, relations between findings, a reading order).

| Model | Readings | JSON valid | Summary kept | Relations kept | Order changed | Seconds per call (max) | Peak model memory |
|---|---|---|---|---|---|---|---|
| qwen3-4b-instruct-2507 | 10 | 10/10 | 6 | 19 of 23 offered | 5 | 40.5 (112) | 4.40 GiB |
| phi4-mini 3.8B, arrays bounded | 5 | 5/5 | 3 | 9 of 26 offered | 1 | 48 (62.8; cold 70) | 3.56 GiB |

- qwen3: 4 summaries were dropped for a calculated figure; of the 4 relations dropped, 2 named same_field though the evidence did not support it and 2 repeated a pair; the order always changed the same way (the arithmetic finding ahead of the revision diff); 7.0 tokens/s; lowest free RAM 2.12 GiB.
- phi4-mini: of its 26 relations, 9 repeated a pair and 8 named a kind the evidence did not support; 6.9 tokens/s; lowest free RAM 2.17 GiB. These five readings and the end-to-end run below ran while a full test run used the CPU, so they are slower than on a free machine.
- phi4-mini wrote on without end in 2 of 16 readings, both before the reply schema bounded its arrays: one ran 600 s with no answer (before there was a token limit), one ran to the 1024-token limit (140 s) and was lost. After the bound: 0 of 5, the longest 435 tokens. qwen3 did not in 34 readings.
- With the first prompts, qwen3 left the order unchanged in 24 of 24 readings and ran the machine down to 1.00 GiB free (peak 5.45 GiB). The shipped prompts changed the order in 5 of 10, so the model's order is not settled.
- A relation's kind is checked against what its two findings cite (a figure, a field id or a document), because phi4-mini named same_field wrongly in 10 of 16 attempts and qwen3 in 2 of 5.

**Default.** phi4-mini. It is faster at the part every case uses (about 17 s against 26 s a call), the guard accepted more of its wording (18 of 24 against 13 of 24), it needs less memory, and its licence is MIT. It is the weaker reader of a whole case (9 of 26 relations kept against 19 of 23) and the only one seen to run on without end. qwen3 stays available with `--llm-model`.

**End to end** (`docforensics run --llm`, 3 documents: payslip, bank statement, loan application; 3 findings): exit 0 after 67 s. The headline was worded by the model and accepted. The reading kept 1 relation, dropped the summary (a figure not in the evidence) and one relation (kind not supported), and left the order as it was. The audit trail holds one `llm_reasoning` and one `llm_wording` event, each with the model, its digest, the prompt and output hashes and the verdict.

**What the guard does not catch.** Accepted wording was seen wrong in meaning: a headline called the revision text-change finding "the debit amount of 723.26"; "$" was written for rupees; an amount in words was given as another figure; a revision text change was called "the transactions listed". The free-text reason of a relation can name the wrong document or field though its kind is checked. A model's reading is inference and is labelled so.

**For a demo.** A case with the model takes a minute or more and free RAM drops to about 2 GiB, so other apps should be closed. The explain stage has 120 s per document plus 120 s, and a call starts only if the client timeout (180 s) fits in what is left. Use 3 or more documents: a 1-document case (240 s) has its wording calls skipped ("skipped: time budget") once the reading took over 60 s.

**Not measured:** Vulkan on the Radeon 740M (Ollama 0.40.14 drops an integrated GPU unless the server starts with `OLLAMA_IGPU_ENABLE=1`; the server was not restarted), a vision-language model on page images, and any model on the held-out split.

## Implementation gotchas

- **RapidOCR call flags persist across calls.** After one `use_det=False` call, later full-page calls ran recognition-only and returned a single garbage line. Pass `use_det`, `use_cls`, `use_rec` explicitly on every call, or keep separate engine instances.
- A line can come back without word tuples (a raw `WordInfo` object, empty text). The reader must tolerate it and fall back to the line box.
- The recogniser is multilingual: on a whole-page crop it emitted CJK characters. Constrain or validate the character set on amount and date fields.
- The default Windows console encoding (cp1252) crashes on non-Latin OCR output. The CLI must reconfigure stdout to UTF-8.
- Git Bash rewrites `/FI`-style arguments into paths; use `MSYS_NO_PATHCONV=1` or PowerShell for Windows tools.

## Not done

- Tesseract was not benchmarked. RapidOCR was adopted because it was good enough on this material and installs from pip with its models inside; Tesseract stays a candidate second engine, and the only untested idea for flagging misreads by disagreement.
- Language model: Vulkan on the Radeon 740M and any model on the held-out split were not measured; the figures in "Local language model" are CPU only, one run each, a small sample.
- VLM: not tried (gemma3:4b was pulled and not run); default off.
- Skewed pages: the first run checked recall only (0.8 and -1.8 degrees, all tokens found) and did not measure IoU. Task 19 measured field extraction on scans turned by 0.5 to 2 degrees (see "Dev split, first runs"). Pages with perspective, curl or an uneven skew, and turns beyond 10 degrees, are untried.
- Models measured: phi4-mini (3.8B, MIT) and qwen3-4b-instruct-2507 (Apache-2.0). Other candidates seen on the Ollama library page (a summarised web page, tags and licences unverified, none measured): qwen3.5 (0.8B, 2B, 4B), gemma4 (E2B, E4B), granite4.2 (3B, Apache 2.0 stated), llama3.2 (1B, 3B), smollm2 (1.7B). Check the tag and licence at pull time.
