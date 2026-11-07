# Learned patch detector: the confirm run (Task 29)

Run: 2026-11-07 13:37 India Standard Time, commit fc18fff, Windows 10, Python 3.11.9, 6 cores, CPU only.
Fixed before the run, from the design slices: ridge 10, positive weight 1, lift 0.5, threshold t* = 3.3555 (the smallest at which the out-of-fold unedited dev-design pages are flagged no more often than the baseline flags them, raised by 0.5 times its distance above the median unedited page: amendment 1 in the docstring). Weights trained on 525 design pages (46290 words, 319 positive).
The bar is in the docstring of evaluation/train_patches.py (commit 76c1f42, with amendment 1). "Higher" means by at least max(2, 10 % of the changed pages).

## Verdict

- (a) recall higher on dev-design (out of fold) and dev-confirm: **met**
- (b) false regions and falsely flagged unedited pages no higher, on dev-design, dev-confirm, xdev-confirm: **met**
- (c) recall higher on xdev-confirm: **met**
- All three met: the detector goes in.
- For information, not part of the bar: (b) with one more falsely flagged page allowed would be met.

## Every combination on every slice

A page is found when a region of a flag has IoU >= 0.1 with the edit box.

| slice | checks | changed pages found | unedited pages falsely flagged | false regions |
|---|---|---|---|---|
| dev-design | grain | 0 of 72 | 0 of 273 | 0 |
| dev-design | placement | 5 of 72 | 0 of 273 | 0 |
| dev-design | jpeg_history | 11 of 72 | 0 of 273 | 0 |
| dev-design | baseline (grain, placement) | 5 of 72 | 0 of 273 | 0 |
| dev-design | learned | 27 of 72 | 0 of 273 | 0 |
| dev-design | the three existing | 16 of 72 | 0 of 273 | 0 |
| dev-design | the three existing and learned | 29 of 72 | 0 of 273 | 0 |
| xdev-design | grain | 25 of 120 | 0 of 60 | 0 |
| xdev-design | placement | 4 of 120 | 0 of 60 | 0 |
| xdev-design | jpeg_history | 81 of 120 | 0 of 60 | 0 |
| xdev-design | baseline (grain, placement) | 28 of 120 | 0 of 60 | 0 |
| xdev-design | learned | 89 of 120 | 0 of 60 | 0 |
| xdev-design | the three existing | 89 of 120 | 0 of 60 | 0 |
| xdev-design | the three existing and learned | 107 of 120 | 0 of 60 | 0 |
| dev-confirm | grain | 0 of 36 | 0 of 159 | 0 |
| dev-confirm | placement | 3 of 36 | 0 of 159 | 0 |
| dev-confirm | jpeg_history | 6 of 36 | 0 of 159 | 0 |
| dev-confirm | baseline (grain, placement) | 3 of 36 | 0 of 159 | 0 |
| dev-confirm | learned | 16 of 36 | 0 of 159 | 0 |
| dev-confirm | the three existing | 9 of 36 | 0 of 159 | 0 |
| dev-confirm | the three existing and learned | 17 of 36 | 0 of 159 | 0 |
| xdev-confirm | grain | 18 of 72 | 0 of 36 | 0 |
| xdev-confirm | placement | 5 of 72 | 0 of 36 | 0 |
| xdev-confirm | jpeg_history | 49 of 72 | 0 of 36 | 0 |
| xdev-confirm | baseline (grain, placement) | 19 of 72 | 0 of 36 | 0 |
| xdev-confirm | learned | 59 of 72 | 0 of 36 | 0 |
| xdev-confirm | the three existing | 55 of 72 | 0 of 36 | 0 |
| xdev-confirm | the three existing and learned | 66 of 72 | 0 of 36 | 0 |

## What the learned detector adds to the three existing checks

| slice | changed pages only the learned detector finds | changed pages the three existing find that it does not | unedited pages only it flags |
|---|---|---|---|
| dev-design | 13 | 2 | 0 |
| xdev-design | 18 | 18 | 0 |
| dev-confirm | 8 | 1 | 0 |
| xdev-confirm | 11 | 7 | 0 |

## By kind

| slice | kind | changed: baseline | changed: learned | unedited falsely flagged: baseline | learned |
|---|---|---|---|---|---|
| dev-design | S1 | 5 of 72 | 27 of 72 | 0 of 144 | 0 of 144 |
| dev-design | genuine | 0 of 0 | 0 of 0 | 0 of 129 | 0 of 129 |
| xdev-design | aligned | 0 of 30 | 18 of 30 | 0 of 0 | 0 of 0 |
| xdev-design | genuine | 0 of 0 | 0 of 0 | 0 of 30 | 0 of 30 |
| xdev-design | pasted-block | 0 of 30 | 27 of 30 | 0 of 0 | 0 of 0 |
| xdev-design | pasted-field | 1 of 30 | 22 of 30 | 0 of 0 | 0 of 0 |
| xdev-design | resaved | 0 of 0 | 0 of 0 | 0 of 30 | 0 of 30 |
| xdev-design | retyped | 27 of 30 | 22 of 30 | 0 of 0 | 0 of 0 |
| dev-confirm | S1 | 3 of 36 | 16 of 36 | 0 of 72 | 0 of 72 |
| dev-confirm | genuine | 0 of 0 | 0 of 0 | 0 of 87 | 0 of 87 |
| xdev-confirm | aligned | 0 of 18 | 12 of 18 | 0 of 0 | 0 of 0 |
| xdev-confirm | genuine | 0 of 0 | 0 of 0 | 0 of 18 | 0 of 18 |
| xdev-confirm | pasted-block | 1 of 18 | 18 of 18 | 0 of 0 | 0 of 0 |
| xdev-confirm | pasted-field | 0 of 18 | 17 of 18 | 0 of 0 | 0 of 0 |
| xdev-confirm | resaved | 0 of 0 | 0 of 0 | 0 of 18 | 0 of 18 |
| xdev-confirm | retyped | 18 of 18 | 12 of 18 | 0 of 0 | 0 of 0 |

## Every changed page

| slice | case | kind | level | baseline | jpeg_history | learned |
|---|---|---|---|---|---|---|
| dev-design | dev-0006 | S1 | mild | missed | missed | missed |
| dev-design | dev-0021 | S1 | 150dpi | missed | found | found |
| dev-design | dev-0036 | S1 | mild | missed | missed | found |
| dev-design | dev-0051 | S1 | 120dpi | missed | missed | missed |
| dev-design | dev-0066 | S1 | mild | found | missed | found |
| dev-design | dev-0081 | S1 | 150dpi | missed | missed | missed |
| dev-design | dev-0096 | S1 | mild | missed | missed | missed |
| dev-design | dev-0111 | S1 | 120dpi | missed | found | found |
| dev-design | dev-0126 | S1 | mild | missed | missed | missed |
| dev-design | dev-0141 | S1 | 150dpi | missed | found | found |
| dev-design | dev-0156 | S1 | mild | missed | missed | missed |
| dev-design | dev-0171 | S1 | 120dpi | missed | found | found |
| dev-design | dev-0186 | S1 | mild | found | missed | missed |
| dev-design | dev-0201 | S1 | 150dpi | missed | missed | missed |
| dev-design | dev-0216 | S1 | mild | missed | missed | missed |
| dev-design | dev-0231 | S1 | 120dpi | missed | missed | found |
| dev-design | dev-0246 | S1 | mild | missed | missed | missed |
| dev-design | dev-0261 | S1 | 150dpi | missed | found | found |
| dev-design | dev-0276 | S1 | mild | missed | missed | missed |
| dev-design | dev-0291 | S1 | 120dpi | missed | missed | missed |
| dev-design | dev-0306 | S1 | mild | missed | missed | missed |
| dev-design | dev-0321 | S1 | 150dpi | missed | missed | missed |
| dev-design | dev-0336 | S1 | mild | missed | missed | missed |
| dev-design | dev-0351 | S1 | 120dpi | missed | missed | missed |
| dev-design | dev-0366 | S1 | mild | missed | missed | found |
| dev-design | dev-0381 | S1 | 150dpi | missed | missed | found |
| dev-design | dev-0396 | S1 | mild | missed | missed | found |
| dev-design | dev-0411 | S1 | 120dpi | missed | found | found |
| dev-design | dev-0426 | S1 | mild | missed | missed | missed |
| dev-design | dev-0441 | S1 | 150dpi | missed | missed | missed |
| dev-design | dev-0456 | S1 | mild | missed | missed | missed |
| dev-design | dev-0471 | S1 | 120dpi | missed | missed | missed |
| dev-design | dev-0486 | S1 | mild | missed | missed | found |
| dev-design | dev-0501 | S1 | 150dpi | missed | missed | missed |
| dev-design | dev-0516 | S1 | mild | missed | missed | found |
| dev-design | dev-0531 | S1 | 120dpi | missed | missed | missed |
| dev-design | dev-0546 | S1 | mild | missed | missed | found |
| dev-design | dev-0561 | S1 | 150dpi | missed | missed | missed |
| dev-design | dev-0576 | S1 | mild | found | missed | missed |
| dev-design | dev-0591 | S1 | 120dpi | missed | missed | missed |
| dev-design | dev-0606 | S1 | mild | missed | missed | missed |
| dev-design | dev-0621 | S1 | 150dpi | missed | found | found |
| dev-design | dev-0636 | S1 | mild | missed | missed | missed |
| dev-design | dev-0651 | S1 | 120dpi | missed | found | found |
| dev-design | dev-0666 | S1 | mild | found | missed | found |
| dev-design | dev-0681 | S1 | 150dpi | missed | missed | missed |
| dev-design | dev-0696 | S1 | mild | missed | missed | missed |
| dev-design | dev-0711 | S1 | 120dpi | missed | found | found |
| dev-design | dev-0726 | S1 | mild | missed | missed | found |
| dev-design | dev-0741 | S1 | 150dpi | missed | missed | missed |
| dev-design | dev-0756 | S1 | mild | missed | missed | found |
| dev-design | dev-0771 | S1 | 120dpi | missed | missed | missed |
| dev-design | dev-0786 | S1 | mild | missed | missed | missed |
| dev-design | dev-0801 | S1 | 150dpi | missed | missed | missed |
| dev-design | dev-0816 | S1 | mild | found | missed | found |
| dev-design | dev-0831 | S1 | 120dpi | missed | missed | missed |
| dev-design | dev-0846 | S1 | mild | missed | missed | found |
| dev-design | dev-0861 | S1 | 150dpi | missed | missed | missed |
| dev-design | dev-0876 | S1 | mild | missed | missed | found |
| dev-design | dev-0891 | S1 | 120dpi | missed | found | found |
| dev-design | dev-0906 | S1 | mild | missed | missed | missed |
| dev-design | dev-0921 | S1 | 150dpi | missed | missed | missed |
| dev-design | dev-0936 | S1 | mild | missed | missed | missed |
| dev-design | dev-0951 | S1 | 120dpi | missed | missed | missed |
| dev-design | dev-0966 | S1 | mild | missed | missed | missed |
| dev-design | dev-0981 | S1 | 150dpi | missed | missed | missed |
| dev-design | dev-0996 | S1 | mild | missed | missed | found |
| dev-design | dev-1011 | S1 | 120dpi | missed | found | found |
| dev-design | dev-1026 | S1 | mild | missed | missed | missed |
| dev-design | dev-1041 | S1 | 150dpi | missed | missed | missed |
| dev-design | dev-1056 | S1 | mild | missed | missed | missed |
| dev-design | dev-1071 | S1 | 120dpi | missed | missed | missed |
| xdev-design | ext-dev-e-0002 | pasted-field | mild | missed | found | found |
| xdev-design | ext-dev-e-0003 | pasted-block | mild | missed | found | found |
| xdev-design | ext-dev-e-0004 | retyped | mild | missed | missed | found |
| xdev-design | ext-dev-e-0005 | aligned | mild | missed | missed | found |
| xdev-design | ext-dev-e-0008 | pasted-field | 150dpi | missed | found | found |
| xdev-design | ext-dev-e-0009 | pasted-block | 150dpi | missed | found | found |
| xdev-design | ext-dev-e-0010 | retyped | 150dpi | found | found | found |
| xdev-design | ext-dev-e-0011 | aligned | 150dpi | missed | missed | found |
| xdev-design | ext-dev-e-0014 | pasted-field | 120dpi | missed | found | missed |
| xdev-design | ext-dev-e-0015 | pasted-block | 120dpi | missed | found | missed |
| xdev-design | ext-dev-e-0016 | retyped | 120dpi | found | found | missed |
| xdev-design | ext-dev-e-0017 | aligned | 120dpi | missed | missed | found |
| xdev-design | ext-dev-e-0020 | pasted-field | mild | missed | found | missed |
| xdev-design | ext-dev-e-0021 | pasted-block | mild | missed | found | found |
| xdev-design | ext-dev-e-0022 | retyped | mild | found | missed | found |
| xdev-design | ext-dev-e-0023 | aligned | mild | missed | missed | missed |
| xdev-design | ext-dev-e-0026 | pasted-field | 150dpi | missed | found | found |
| xdev-design | ext-dev-e-0027 | pasted-block | 150dpi | missed | found | found |
| xdev-design | ext-dev-e-0028 | retyped | 150dpi | found | found | found |
| xdev-design | ext-dev-e-0029 | aligned | 150dpi | missed | missed | found |
| xdev-design | ext-dev-e-0032 | pasted-field | 120dpi | missed | found | found |
| xdev-design | ext-dev-e-0033 | pasted-block | 120dpi | missed | found | found |
| xdev-design | ext-dev-e-0034 | retyped | 120dpi | found | found | found |
| xdev-design | ext-dev-e-0035 | aligned | 120dpi | missed | missed | found |
| xdev-design | ext-dev-e-0038 | pasted-field | mild | missed | found | found |
| xdev-design | ext-dev-e-0039 | pasted-block | mild | missed | found | found |
| xdev-design | ext-dev-e-0040 | retyped | mild | found | missed | found |
| xdev-design | ext-dev-e-0041 | aligned | mild | missed | missed | found |
| xdev-design | ext-dev-e-0044 | pasted-field | 150dpi | missed | found | found |
| xdev-design | ext-dev-e-0045 | pasted-block | 150dpi | missed | found | found |
| xdev-design | ext-dev-e-0046 | retyped | 150dpi | found | found | missed |
| xdev-design | ext-dev-e-0047 | aligned | 150dpi | missed | missed | missed |
| xdev-design | ext-dev-e-0050 | pasted-field | 120dpi | found | found | found |
| xdev-design | ext-dev-e-0051 | pasted-block | 120dpi | missed | found | found |
| xdev-design | ext-dev-e-0052 | retyped | 120dpi | found | found | found |
| xdev-design | ext-dev-e-0053 | aligned | 120dpi | missed | missed | found |
| xdev-design | ext-dev-e-0056 | pasted-field | mild | missed | found | found |
| xdev-design | ext-dev-e-0057 | pasted-block | mild | missed | found | found |
| xdev-design | ext-dev-e-0058 | retyped | mild | found | missed | missed |
| xdev-design | ext-dev-e-0059 | aligned | mild | missed | missed | missed |
| xdev-design | ext-dev-e-0062 | pasted-field | 150dpi | missed | found | found |
| xdev-design | ext-dev-e-0063 | pasted-block | 150dpi | missed | found | found |
| xdev-design | ext-dev-e-0064 | retyped | 150dpi | found | found | found |
| xdev-design | ext-dev-e-0065 | aligned | 150dpi | missed | missed | missed |
| xdev-design | ext-dev-e-0068 | pasted-field | 120dpi | missed | found | found |
| xdev-design | ext-dev-e-0069 | pasted-block | 120dpi | missed | found | found |
| xdev-design | ext-dev-e-0070 | retyped | 120dpi | found | found | found |
| xdev-design | ext-dev-e-0071 | aligned | 120dpi | missed | missed | found |
| xdev-design | ext-dev-e-0074 | pasted-field | mild | missed | found | missed |
| xdev-design | ext-dev-e-0075 | pasted-block | mild | missed | found | found |
| xdev-design | ext-dev-e-0076 | retyped | mild | found | missed | missed |
| xdev-design | ext-dev-e-0077 | aligned | mild | missed | missed | missed |
| xdev-design | ext-dev-e-0080 | pasted-field | 150dpi | missed | found | found |
| xdev-design | ext-dev-e-0081 | pasted-block | 150dpi | missed | found | found |
| xdev-design | ext-dev-e-0082 | retyped | 150dpi | missed | found | found |
| xdev-design | ext-dev-e-0083 | aligned | 150dpi | missed | missed | missed |
| xdev-design | ext-dev-e-0086 | pasted-field | 120dpi | missed | found | found |
| xdev-design | ext-dev-e-0087 | pasted-block | 120dpi | missed | found | found |
| xdev-design | ext-dev-e-0088 | retyped | 120dpi | found | found | found |
| xdev-design | ext-dev-e-0089 | aligned | 120dpi | missed | missed | found |
| xdev-design | ext-dev-e-0092 | pasted-field | mild | missed | found | found |
| xdev-design | ext-dev-e-0093 | pasted-block | mild | missed | found | found |
| xdev-design | ext-dev-e-0094 | retyped | mild | found | missed | missed |
| xdev-design | ext-dev-e-0095 | aligned | mild | missed | missed | missed |
| xdev-design | ext-dev-e-0098 | pasted-field | 150dpi | missed | found | found |
| xdev-design | ext-dev-e-0099 | pasted-block | 150dpi | missed | found | found |
| xdev-design | ext-dev-e-0100 | retyped | 150dpi | found | found | found |
| xdev-design | ext-dev-e-0101 | aligned | 150dpi | missed | missed | missed |
| xdev-design | ext-dev-e-0104 | pasted-field | 120dpi | missed | found | missed |
| xdev-design | ext-dev-e-0105 | pasted-block | 120dpi | missed | found | found |
| xdev-design | ext-dev-e-0106 | retyped | 120dpi | found | found | found |
| xdev-design | ext-dev-e-0107 | aligned | 120dpi | missed | missed | missed |
| xdev-design | ext-dev-e-0110 | pasted-field | mild | missed | found | missed |
| xdev-design | ext-dev-e-0111 | pasted-block | mild | missed | found | found |
| xdev-design | ext-dev-e-0112 | retyped | mild | missed | missed | missed |
| xdev-design | ext-dev-e-0113 | aligned | mild | missed | missed | found |
| xdev-design | ext-dev-e-0116 | pasted-field | 150dpi | missed | found | found |
| xdev-design | ext-dev-e-0117 | pasted-block | 150dpi | missed | found | found |
| xdev-design | ext-dev-e-0118 | retyped | 150dpi | found | found | found |
| xdev-design | ext-dev-e-0119 | aligned | 150dpi | missed | missed | found |
| xdev-design | ext-dev-e-0122 | pasted-field | 120dpi | missed | found | missed |
| xdev-design | ext-dev-e-0123 | pasted-block | 120dpi | missed | found | found |
| xdev-design | ext-dev-e-0124 | retyped | 120dpi | found | found | missed |
| xdev-design | ext-dev-e-0125 | aligned | 120dpi | missed | missed | found |
| xdev-design | ext-dev-e-0128 | pasted-field | mild | missed | found | found |
| xdev-design | ext-dev-e-0129 | pasted-block | mild | missed | found | found |
| xdev-design | ext-dev-e-0130 | retyped | mild | found | missed | found |
| xdev-design | ext-dev-e-0131 | aligned | mild | missed | missed | found |
| xdev-design | ext-dev-e-0134 | pasted-field | 150dpi | missed | found | found |
| xdev-design | ext-dev-e-0135 | pasted-block | 150dpi | missed | found | found |
| xdev-design | ext-dev-e-0136 | retyped | 150dpi | found | found | missed |
| xdev-design | ext-dev-e-0137 | aligned | 150dpi | missed | missed | found |
| xdev-design | ext-dev-e-0140 | pasted-field | 120dpi | missed | found | found |
| xdev-design | ext-dev-e-0141 | pasted-block | 120dpi | missed | found | found |
| xdev-design | ext-dev-e-0142 | retyped | 120dpi | found | found | found |
| xdev-design | ext-dev-e-0143 | aligned | 120dpi | missed | missed | found |
| xdev-design | ext-dev-e-0146 | pasted-field | mild | missed | found | missed |
| xdev-design | ext-dev-e-0147 | pasted-block | mild | missed | found | missed |
| xdev-design | ext-dev-e-0148 | retyped | mild | found | missed | found |
| xdev-design | ext-dev-e-0149 | aligned | mild | missed | missed | missed |
| xdev-design | ext-dev-e-0152 | pasted-field | 150dpi | missed | found | found |
| xdev-design | ext-dev-e-0153 | pasted-block | 150dpi | missed | found | found |
| xdev-design | ext-dev-e-0154 | retyped | 150dpi | found | found | found |
| xdev-design | ext-dev-e-0155 | aligned | 150dpi | missed | found | found |
| xdev-design | ext-dev-e-0158 | pasted-field | 120dpi | missed | found | found |
| xdev-design | ext-dev-e-0159 | pasted-block | 120dpi | missed | found | found |
| xdev-design | ext-dev-e-0160 | retyped | 120dpi | found | found | found |
| xdev-design | ext-dev-e-0161 | aligned | 120dpi | missed | missed | missed |
| xdev-design | ext-dev-e-0164 | pasted-field | mild | missed | found | missed |
| xdev-design | ext-dev-e-0165 | pasted-block | mild | missed | found | found |
| xdev-design | ext-dev-e-0166 | retyped | mild | found | missed | found |
| xdev-design | ext-dev-e-0167 | aligned | mild | missed | missed | missed |
| xdev-design | ext-dev-e-0170 | pasted-field | 150dpi | missed | found | found |
| xdev-design | ext-dev-e-0171 | pasted-block | 150dpi | missed | found | missed |
| xdev-design | ext-dev-e-0172 | retyped | 150dpi | found | found | found |
| xdev-design | ext-dev-e-0173 | aligned | 150dpi | missed | missed | found |
| xdev-design | ext-dev-e-0176 | pasted-field | 120dpi | missed | found | found |
| xdev-design | ext-dev-e-0177 | pasted-block | 120dpi | missed | found | found |
| xdev-design | ext-dev-e-0178 | retyped | 120dpi | found | found | found |
| xdev-design | ext-dev-e-0179 | aligned | 120dpi | missed | missed | found |
| dev-confirm | dev-3006 | S1 | mild | missed | missed | found |
| dev-confirm | dev-3021 | S1 | 150dpi | missed | missed | missed |
| dev-confirm | dev-3036 | S1 | mild | missed | missed | missed |
| dev-confirm | dev-3051 | S1 | 120dpi | missed | missed | found |
| dev-confirm | dev-3066 | S1 | mild | found | missed | found |
| dev-confirm | dev-3081 | S1 | 150dpi | missed | missed | missed |
| dev-confirm | dev-3096 | S1 | mild | found | missed | found |
| dev-confirm | dev-3111 | S1 | 120dpi | missed | missed | missed |
| dev-confirm | dev-3126 | S1 | mild | missed | missed | found |
| dev-confirm | dev-3141 | S1 | 150dpi | missed | found | found |
| dev-confirm | dev-3156 | S1 | mild | missed | missed | missed |
| dev-confirm | dev-3171 | S1 | 120dpi | missed | missed | missed |
| dev-confirm | dev-3186 | S1 | mild | missed | missed | missed |
| dev-confirm | dev-3201 | S1 | 150dpi | missed | missed | missed |
| dev-confirm | dev-3216 | S1 | mild | missed | missed | missed |
| dev-confirm | dev-3231 | S1 | 120dpi | missed | found | found |
| dev-confirm | dev-3246 | S1 | mild | missed | missed | found |
| dev-confirm | dev-3261 | S1 | 150dpi | missed | found | found |
| dev-confirm | dev-3276 | S1 | mild | missed | missed | found |
| dev-confirm | dev-3291 | S1 | 120dpi | missed | missed | missed |
| dev-confirm | dev-3306 | S1 | mild | missed | missed | missed |
| dev-confirm | dev-3321 | S1 | 150dpi | missed | missed | missed |
| dev-confirm | dev-3336 | S1 | mild | missed | missed | missed |
| dev-confirm | dev-3351 | S1 | 120dpi | missed | found | found |
| dev-confirm | dev-3366 | S1 | mild | missed | missed | found |
| dev-confirm | dev-3381 | S1 | 150dpi | missed | missed | missed |
| dev-confirm | dev-3396 | S1 | mild | missed | missed | found |
| dev-confirm | dev-3411 | S1 | 120dpi | missed | missed | missed |
| dev-confirm | dev-3426 | S1 | mild | missed | missed | missed |
| dev-confirm | dev-3441 | S1 | 150dpi | missed | missed | missed |
| dev-confirm | dev-3456 | S1 | mild | found | missed | missed |
| dev-confirm | dev-3471 | S1 | 120dpi | missed | found | found |
| dev-confirm | dev-3486 | S1 | mild | missed | missed | found |
| dev-confirm | dev-3501 | S1 | 150dpi | missed | found | found |
| dev-confirm | dev-3516 | S1 | mild | missed | missed | missed |
| dev-confirm | dev-3531 | S1 | 120dpi | missed | missed | missed |
| xdev-confirm | ext-dev-e-5006 | pasted-field | mild | missed | found | found |
| xdev-confirm | ext-dev-e-5007 | pasted-block | mild | missed | found | found |
| xdev-confirm | ext-dev-e-5008 | retyped | mild | found | missed | missed |
| xdev-confirm | ext-dev-e-5009 | aligned | mild | missed | missed | missed |
| xdev-confirm | ext-dev-e-5012 | pasted-field | 150dpi | missed | found | found |
| xdev-confirm | ext-dev-e-5013 | pasted-block | 150dpi | missed | found | found |
| xdev-confirm | ext-dev-e-5014 | retyped | 150dpi | found | found | found |
| xdev-confirm | ext-dev-e-5015 | aligned | 150dpi | missed | missed | found |
| xdev-confirm | ext-dev-e-5018 | pasted-field | 120dpi | missed | found | missed |
| xdev-confirm | ext-dev-e-5019 | pasted-block | 120dpi | missed | found | found |
| xdev-confirm | ext-dev-e-5020 | retyped | 120dpi | found | found | found |
| xdev-confirm | ext-dev-e-5021 | aligned | 120dpi | missed | missed | found |
| xdev-confirm | ext-dev-e-5024 | pasted-field | mild | missed | found | found |
| xdev-confirm | ext-dev-e-5025 | pasted-block | mild | missed | found | found |
| xdev-confirm | ext-dev-e-5026 | retyped | mild | found | missed | missed |
| xdev-confirm | ext-dev-e-5027 | aligned | mild | missed | missed | missed |
| xdev-confirm | ext-dev-e-5030 | pasted-field | 150dpi | missed | found | found |
| xdev-confirm | ext-dev-e-5031 | pasted-block | 150dpi | missed | found | found |
| xdev-confirm | ext-dev-e-5032 | retyped | 150dpi | found | found | found |
| xdev-confirm | ext-dev-e-5033 | aligned | 150dpi | missed | missed | missed |
| xdev-confirm | ext-dev-e-5036 | pasted-field | 120dpi | missed | found | found |
| xdev-confirm | ext-dev-e-5037 | pasted-block | 120dpi | missed | found | found |
| xdev-confirm | ext-dev-e-5038 | retyped | 120dpi | found | found | found |
| xdev-confirm | ext-dev-e-5039 | aligned | 120dpi | missed | missed | found |
| xdev-confirm | ext-dev-e-5042 | pasted-field | mild | missed | found | found |
| xdev-confirm | ext-dev-e-5043 | pasted-block | mild | missed | found | found |
| xdev-confirm | ext-dev-e-5044 | retyped | mild | found | missed | missed |
| xdev-confirm | ext-dev-e-5045 | aligned | mild | missed | missed | found |
| xdev-confirm | ext-dev-e-5048 | pasted-field | 150dpi | missed | found | found |
| xdev-confirm | ext-dev-e-5049 | pasted-block | 150dpi | missed | found | found |
| xdev-confirm | ext-dev-e-5050 | retyped | 150dpi | found | found | found |
| xdev-confirm | ext-dev-e-5051 | aligned | 150dpi | missed | missed | found |
| xdev-confirm | ext-dev-e-5054 | pasted-field | 120dpi | missed | found | found |
| xdev-confirm | ext-dev-e-5055 | pasted-block | 120dpi | missed | found | found |
| xdev-confirm | ext-dev-e-5056 | retyped | 120dpi | found | found | found |
| xdev-confirm | ext-dev-e-5057 | aligned | 120dpi | missed | missed | found |
| xdev-confirm | ext-dev-e-5060 | pasted-field | mild | missed | found | found |
| xdev-confirm | ext-dev-e-5061 | pasted-block | mild | missed | found | found |
| xdev-confirm | ext-dev-e-5062 | retyped | mild | found | missed | missed |
| xdev-confirm | ext-dev-e-5063 | aligned | mild | missed | missed | found |
| xdev-confirm | ext-dev-e-5066 | pasted-field | 150dpi | missed | found | found |
| xdev-confirm | ext-dev-e-5067 | pasted-block | 150dpi | missed | found | found |
| xdev-confirm | ext-dev-e-5068 | retyped | 150dpi | found | found | found |
| xdev-confirm | ext-dev-e-5069 | aligned | 150dpi | missed | missed | found |
| xdev-confirm | ext-dev-e-5072 | pasted-field | 120dpi | missed | found | found |
| xdev-confirm | ext-dev-e-5073 | pasted-block | 120dpi | missed | found | found |
| xdev-confirm | ext-dev-e-5074 | retyped | 120dpi | found | found | found |
| xdev-confirm | ext-dev-e-5075 | aligned | 120dpi | missed | missed | found |
| xdev-confirm | ext-dev-e-5078 | pasted-field | mild | missed | found | found |
| xdev-confirm | ext-dev-e-5079 | pasted-block | mild | missed | found | found |
| xdev-confirm | ext-dev-e-5080 | retyped | mild | found | missed | found |
| xdev-confirm | ext-dev-e-5081 | aligned | mild | missed | missed | found |
| xdev-confirm | ext-dev-e-5084 | pasted-field | 150dpi | missed | found | found |
| xdev-confirm | ext-dev-e-5085 | pasted-block | 150dpi | missed | found | found |
| xdev-confirm | ext-dev-e-5086 | retyped | 150dpi | found | found | found |
| xdev-confirm | ext-dev-e-5087 | aligned | 150dpi | missed | missed | found |
| xdev-confirm | ext-dev-e-5090 | pasted-field | 120dpi | missed | found | found |
| xdev-confirm | ext-dev-e-5091 | pasted-block | 120dpi | found | found | found |
| xdev-confirm | ext-dev-e-5092 | retyped | 120dpi | found | found | missed |
| xdev-confirm | ext-dev-e-5093 | aligned | 120dpi | missed | found | found |
| xdev-confirm | ext-dev-e-5096 | pasted-field | mild | missed | found | found |
| xdev-confirm | ext-dev-e-5097 | pasted-block | mild | missed | found | found |
| xdev-confirm | ext-dev-e-5098 | retyped | mild | found | missed | missed |
| xdev-confirm | ext-dev-e-5099 | aligned | mild | missed | missed | missed |
| xdev-confirm | ext-dev-e-5102 | pasted-field | 150dpi | missed | found | found |
| xdev-confirm | ext-dev-e-5103 | pasted-block | 150dpi | missed | found | found |
| xdev-confirm | ext-dev-e-5104 | retyped | 150dpi | found | found | found |
| xdev-confirm | ext-dev-e-5105 | aligned | 150dpi | missed | missed | missed |
| xdev-confirm | ext-dev-e-5108 | pasted-field | 120dpi | missed | found | found |
| xdev-confirm | ext-dev-e-5109 | pasted-block | 120dpi | missed | found | found |
| xdev-confirm | ext-dev-e-5110 | retyped | 120dpi | found | found | found |
| xdev-confirm | ext-dev-e-5111 | aligned | 120dpi | missed | missed | missed |

## Every false region on an unedited page

| slice | case | file | page | by | regions |
|---|---|---|---|---|---|
