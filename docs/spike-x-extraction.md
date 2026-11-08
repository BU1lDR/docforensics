# Template-free extraction by the local model, measured on ext-dev (package X, 5 Nov 2026)

What was built: with `--llm`, a page whose type the tool has no spec for (type `unknown`) is shown to the local model as numbered lines of text, and the model lists the facts the page states, each as a label, a value and the words it took the value from. Code then looks for those words among the page's word boxes. A fact the page does not hold is dropped and logged. The value kept is the page's own words, with a box and a page. What the model read is marked as read by the model, sits below the doubt limit, is shown as inference in the dossier and on the page, feeds no check and raises no finding. The type is still decided by the keyword rules; the model never decides it. Off unless `--llm` is given.

What it is not: it does not find anything wrong with a page, it does not read a page it cannot get text for, and it was not measured on any page of the three supported types (those are read by the specs, as before).

Everything below was measured on the laptop (Ryzen 5 220, CPU only, Windows 11; the run files say "Windows 10" because Python reports it so), Ollama, temperature 0 and seed 0, one run per model. All numbers are on the **development** split of the new pack (`ext-dev`), except those named as held-out. The held-out `ext-test` split was read once, at the freeze, by phi4-mini:3.8b alone and on the frozen code (commit bb08c8e); no constant, prompt or rule was set on it, and its figures are under 'What this supports'.

## The pack

`datagen/unseen.py` draws a fictional invoice and a fictional electricity bill for one person, 26 printed facts per case (11 on the invoice, 15 on the bill), each in two layouts that word and place their labels differently, digital or as a simulated scan. Case n is digital, mild, 150 dpi, 120 dpi, in that order; the layout changes every two cases (A, A, B, B, A, A, B). The truth for every fact (label as printed, text, box, and the names a reviewer would accept for it as patterns) was written before any model read a page. Table rows are not listed as facts. Seeds start at 3 000 000. Names, firms and addresses are invented.

Counting rules (the docstring of `evaluation/score_x.py` has them in full): a fact is **right** when a model-read field sits at its box (IoU 0.5 or more) under an acceptable name, **misnamed** when it sits there under another name, **partial** when a field only touches the box (IoU 0.1 to 0.5), **rules** when only the rules' own reading is there (the model is not asked about words the rules read), **missing** when nothing is near. Fields at no listed fact are counted as extras and neither right nor wrong.

## Runs

| run | cases | facts | right | misnamed | partial | rules | missing | s per page (mean, longest) |
|---|---|---|---|---|---|---|---|---|
| phi4-mini 3.8B, live, before the grounding fix (9b269f4) | 7 | 182 | 18 | 0 | 8 | 64 | 92 | 87.7, 122.8 |
| the same replies, grounding fixed, first 20 items of a reply read (823e5df) | 7 | 182 | 94 | 1 | 8 | 60 | 19 | 87.7, 122.8 |
| the same replies, first 60 items read (74d2679, the final code) | 7 | 182 | 97 | 1 | 8 | 60 | 16 | 87.7, 122.8 |
| qwen3 4B instruct 2507 q4_K_M, live; the same counts with the grounding fix (9b269f4, 823e5df) | 6 | 156 | 36 | 5 | 31 | 54 | 30 | 108.9, 152.7 |
| qwen3, the same replies, first 60 items read (74d2679, the final code) | 6 | 156 | 38 | 5 | 34 | 54 | 25 | 108.9, 152.7 |

The runs took 21:47 to 22:31 IST with a budget of 19 minutes a model, so phi4-mini finished 7 cases and qwen3 6. The reports and the replies are in `eval/x/`; the reports of the middle scoring (first 20 items read) and of the first one are kept beside them under their own names. `tests/test_x_replay.py` scores the first two cases again from the saved replies and expects the written-down counts.

Both defects below were found by reading the list of facts not read right of this run, so they were found on development data; they are defects of the code that reads the model, not of the pack, and these numbers say how the code does on this pack. They do not predict a held-out one; the held-out run of the freeze is reported under 'What this supports'.

**The grounding defect.** The first phi4-mini run kept 22 of 256 items. The model copied the "5: " it had been shown in front of each line into the words it cited, so 190 items were dropped as "source text not found on the page". Fixed in db788f1 (the number is stripped as a fallback, after the text as given has been tried), with tests. The prompt did not change, so the saved replies are still what the model said, and scoring them again is valid: 171 items kept, 18 facts right become 94. The first report is kept as `eval/x/ext-dev-phi4-mini-3-8b-before-the-grounding-fix.md`.

**The item limit.** The prompt asks for up to 20 facts, and the code looked only at the first 20 items of a reply. phi4-mini does not count: on 4 of 14 pages it gave 21 to 25 items, and an invoice lists its totals last. The cut was silent: 13 of 256 items were lost without a trace, among them the tax amount or the total of three invoices. It showed as a tax amount "missing" on 5 of 7 invoices, while the saved replies held the amount for 3 of them. Fixed in 74d2679: up to 60 items (as many as the lines the model is shown) are looked at, and any beyond are counted in the audit event and said as a limitation in the dossier. The prompt did not change, so again the saved replies apply: 97 facts right instead of 94, 16 missing instead of 19; for qwen3, 38 right instead of 36, 25 missing instead of 30. The report of the middle scoring is `eval/x/ext-dev-phi4-mini-3-8b-with-the-item-limit-at-20.md` (and the same for qwen3).

**Model choice.** phi4-mini stays the default (`DEFAULT_MODEL`). On the six cases both models read: 86 right against 38, and phi4-mini failed no call. qwen3 returned the label inside the value ("Invoice No INV-2026-7688"), so its fields cover the label as well and 34 facts count as partial; its reply to the first page of case 4 was not JSON after 153 s, and the case's other page was then skipped by the rule that stops a case after one failed call, which left 15 facts missing. It also took longer. gemma3:4b was not tried.

## phi4-mini, final code (7 cases, 182 facts)

97 right, 1 misnamed, 8 partial, 60 rules, 16 missing. Without the model the rules' own reading is at the box of 60 facts; with it, 157 of 182 are read at the right box (97 by the model, 60 by the rules). Of the 97 right, 92 carry the value as printed (on a scan this measures the OCR as well as the model). Items: 256 given, 178 kept; dropped: 57 already read by the rules, 14 value not inside its source text, 4 same words as an earlier item, 2 source text not found on the page, 1 label too long; none beyond the limit.

| kind | facts | right | misnamed | partial | rules | missing |
|---|---|---|---|---|---|---|
| amount | 56 | 13 | 0 | 0 | 41 | 2 |
| date | 28 | 6 | 0 | 2 | 19 | 1 |
| id | 35 | 28 | 1 | 4 | 0 | 2 |
| text | 63 | 50 | 0 | 2 | 0 | 11 |

| medium | facts | right | misnamed | partial | rules | missing |
|---|---|---|---|---|---|---|
| digital | 52 | 29 | 0 | 0 | 22 | 1 |
| mild | 52 | 34 | 1 | 0 | 14 | 3 |
| 150dpi | 52 | 22 | 0 | 8 | 20 | 2 |
| 120dpi | 26 | 12 | 0 | 0 | 4 | 10 |

| layout | facts | right | misnamed | partial | rules | missing |
|---|---|---|---|---|---|---|
| A | 104 | 59 | 0 | 0 | 44 | 1 |
| B | 78 | 38 | 1 | 8 | 16 | 15 |

Where it falls short, from the list of facts not read right:

- The tax amount of an invoice is missing on 2 of 7 invoices (cases 4 and 5): the model gave the rate ("18%") from that line and not the amount.
- Layout B puts two labels on one line and their two values on the next. The model joins what it reads: the consumer number and the bill number as one field, the billing period and the due date as one. Each pair counts as two partial facts (8 in all, on both 150 dpi cases).
- The closing meter reading is missing on all three layout B bills. On the 150 dpi ones the model cited "Closing Meter Reading" followed by the value as one phrase, which the page does not hold in that order, so the item was dropped as "source text not found on the page"; on the 120 dpi one see the next point.
- On the 120 dpi bill (case 3) 9 of the 15 facts are missing (and the invoice's buyer, which makes 10 of the 26 facts of the case). 8 of the model's items on that page were dropped because the value was not inside the words it cited: it cited the line of labels, the values being on the line below, and in one of them gave a period ("01p 6 - p 26") that is on no page. The OCR garbles that page too.
- The OCR's mistakes pass through: at 120 dpi a decimal comma was read as a point ("1.150.00"), and the model copies it. Nothing repairs it, and the field shows what the page says.
- One misnamed fact: a bank account named `invoice_number`. The name is the model's word; no check reads it.
- Extras: 22 fields at no listed fact and 54 at cells of the invoice table. They are real text from the page under the model's own names (document title, tax rate, line items); counting them as neither right nor wrong is the rule, and a reviewer sees them marked as model-read.

Time: a page takes 58 to 123 s (mean 88 s over the 14 calls), a case of two pages about three minutes, and the model is loaded for each call. A document is limited to its first two pages and a page to its first 60 lines; what is left out is a limitation in the dossier. The model sees page text only, never boxes or images.

## What this supports

Template-free reading is **Partial**. On synthetic invoices and bills in two layouts it names and finds, at the right place, 97 of the 122 facts that the rules do not read (the rules read the other 60 of the 182 themselves); layout B, 120 dpi scans and the tax line are where it falls short. It says nothing about real invoices, other document types, other languages, longer pages, or the other models; it was run once per model on `ext-dev` and once, by phi4-mini:3.8b alone, on the held-out `ext-test` split, and there is no repeat to show the spread. The names it gives are judged against patterns written by the author before the run, so "right" is the author's reading of what a reviewer would accept.

The held-out run: the `ext-test` split (8 cases, 208 printed facts; the same generator and the same two layouts as `ext-dev`, other draws) was read once, at the freeze, on the frozen code (commit bb08c8e), and no constant, prompt or rule was set on it. Of the facts, 114 were read at the right box under an acceptable name (106 of them with the value as printed), 63 more by the rules alone, 7 partly (the field touches the box without covering it), 9 under another name, 15 not read; on the development split, 97 of 182 were read right. By layout, read right: A 60 of 104, B 54 of 104. By medium: 120dpi 30 of 52, 150dpi 22 of 52, digital 30 of 52, mild 32 of 52. A page of that run took a median of 80.8 s, the longest 110.1 s (16 calls). These counts are not in-sample; the facts not read right are listed in `eval/x/ext-test-phi4-mini-3-8b.md`. The limits of the paragraph above hold for it too.

To repeat the scoring without the model: `python -m evaluation.run_x ext-dev --cases 7 --replay eval/x/ext-dev-phi4-mini-3-8b.json --out <folder>`. To repeat the run itself: `python -m evaluation.run_x ext-dev --model phi4-mini:3.8b --cases 8 --budget 19 --out <folder>` with Ollama running and the model pulled; it takes about 20 minutes. The held-out split is read with `python -m evaluation.run_x ext-test --once-at-freeze --model phi4-mini:3.8b --cases 8 --out <folder>` (the model calls of that run added up to 22 minutes): the flag is required (a replay of that split needs it too), and a run in which the model answered nothing exits 1 and writes no report.
