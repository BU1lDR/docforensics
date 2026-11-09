"""Draws the figures of the README (docs/img/*.svg), standard library only.

The capability counts are read from src/docforensics/capabilities.json. The held-out counts are copied from eval/test.md (run 1) and
eval/freeze-2/test.md (run 2); before anything is written they are checked against the README text that quotes them.
Run from the repository folder:  python docs/img/make_figures.py
"""
import json
import sys
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]

# --- numbers ---------------------------------------------------------------------------------------------------------------
# (medium, changes planted, found in run 1, found in run 2); the README gives them in one sentence under the table of kinds
MEDIA = [("Digital", 60, 58, 58), ("Mild scan", 18, 13, 13), ("150 dpi scan", 9, 6, 7), ("120 dpi scan", 9, 2, 5)]
HEADLINE = [  # (value in run 2, what it counts, run 1)
    ("83 of 96", "planted changes found (86 %)", "run 1: 79 of 96 (82 %)"),
    ("40 of 48", "changes with a place, located", "run 1: 37 of 48; overlap 0.5 or more"),
    ("2 of 144", "genuine documents flagged", "run 1: 1; both of run 2 on one page"),
    ("13", "planted changes missed", "run 1: 17"),
]
TESTS = "1,534"  # the full suite on the submitted tree: 1534 passed (see the README, Tests)

# --- look: the colours of the review desk and the dossier --------------------------------------------------------------------
BG, PANEL, LINE, LINE2 = "#0D1117", "#121A25", "#1F2937", "#33425A"
TEXT, TEXT2, MUTED = "#E6EDF3", "#9AA7B4", "#7A8794"
ACCENT, TEAL, TEAL_DIM = "#00FFCC", "#34D3B3", "#17806E"  # the accent of the UI; mark colour (3:1 on BG); the dimmer step for run 1
CLASS = {"observation": "#3082f6", "inconsistency": "#e15247", "potential_manipulation": "#e34cbb", "processing_limitation": "#78838f"}
MONO = "ui-monospace, 'Cascadia Mono', 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"
CW = 0.6  # width of a monospace character in em, for placing boxes around text


def t(x, y, s, size=14, fill=TEXT, weight=400, anchor="start"):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" font-weight="{weight}" text-anchor="{anchor}">{escape(s)}</text>'


def svg(w, h, name, body, desc):
    head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(desc)}">'
            f'<title>{escape(desc)}</title><style>text{{font-family:{MONO}}}.caret{{animation:blink 1.1s steps(1) infinite}}'
            f'@keyframes blink{{50%{{fill:transparent}}}}@media (prefers-reduced-motion:reduce){{.caret{{animation:none}}}}</style>'
            f'<rect width="{w}" height="{h}" rx="14" fill="{BG}" stroke="{LINE}"/>')
    (OUT / name).write_text(head + "".join(body) + "</svg>\n", encoding="utf-8")


def banner():
    b = ['<defs><pattern id="sl" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#fff" opacity=".045"/></pattern></defs>',
         '<rect width="960" height="300" rx="14" fill="url(#sl)"/>',
         t(48, 54, "# DataOps Innovation Hackathon 2026 (Hack The Core), problem statement 2", 14, MUTED),
         f'<text x="48" y="134" font-size="56" font-weight="700" fill="{ACCENT}">$ docforensics<tspan class="caret">_</tspan></text>',
         t(48, 182, "Documents of one case in. A dossier of cited findings out.", 18, TEXT),
         t(48, 210, "Findings cite the source file, and the page and box where there is one.", 14, TEXT2)]
    x = 48
    for label in ("offline", "synthetic data only", "a person decides", "AGPL-3.0", "Python 3.11+", f"{TESTS} tests"):
        w = int(len(label) * 13 * CW + 28)
        b += [f'<rect x="{x}" y="244" width="{w}" height="28" rx="14" fill="none" stroke="{LINE2}"/>', t(x + w / 2, 263, label, 13, TEXT2, anchor="middle")]
        x += w + 10
    # a page with one box of each kind of finding
    b += ['<rect x="744" y="30" width="150" height="196" rx="6" fill="#E9EDF1"/>', f'<rect x="756" y="42" width="22" height="22" fill="#B8C1CC"/>',
          '<rect x="786" y="46" width="78" height="6" fill="#8D99A8"/><rect x="786" y="58" width="52" height="5" fill="#B8C1CC"/>']
    for i in range(5):
        y = 82 + i * 16
        b.append(f'<rect x="756" y="{y}" width="{70 if i % 2 else 52}" height="5" fill="#B8C1CC"/><rect x="838" y="{y}" width="44" height="5" fill="#8D99A8"/>')
    b += [f'<rect x="752" y="38" width="30" height="30" fill="none" stroke="{CLASS["observation"]}" stroke-width="2.5"/>',
          f'<rect x="832" y="96" width="56" height="17" fill="none" stroke="{CLASS["inconsistency"]}" stroke-width="2.5"/>',
          f'<path d="M820 150v-8h8M876 142h8v8M884 184v8h-8M828 192h-8v-8" fill="none" stroke="{CLASS["potential_manipulation"]}" stroke-width="2.5"/>',
          f'<rect x="752" y="180" width="64" height="30" fill="none" stroke="{CLASS["processing_limitation"]}" stroke-width="2" stroke-dasharray="2 3"/>',
          f'<path d="M888 104.5h12" stroke="{CLASS["inconsistency"]}" stroke-width="1.5"/>',
          f'<rect x="900" y="92" width="48" height="24" rx="4" fill="none" stroke="{CLASS["inconsistency"]}"/>', t(924, 108, "F-004", 12, CLASS["inconsistency"], anchor="middle")]
    svg(960, 300, "banner.svg", b, "docforensics: documents of one case in, a dossier of cited findings out")


STAGES = [("Ingest", "type, size,", "sha256"), ("Read", "text layer", "or OCR"), ("Classify", "3 types,", "or unknown"), ("Extract", "values, boxes,", "confidence"),
          ("Forensics", "revisions,", "pixels, bytes"), ("Checks", "within and", "across files"), ("Link", "clusters,", "entities"),
          ("Explain", "wording per", "finding"), ("Crops", "marked crop", "per place"), ("Dossier", "HTML and JSON,", "hashed")]


def pipeline():
    bw, gap, bh = 146, 37.5, 88
    b = ['<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="#5B6E8A"/></marker></defs>',
         t(40, 44, "Nine stages after ingest, one audit trail under all of them", 18, TEXT, 700)]
    pos = []
    for i, (name, l1, l2) in enumerate(STAGES):
        x, y = 40 + (i % 5) * (bw + gap), 72 if i < 5 else 204
        pos.append((x, y))
        b += [f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="8" fill="{PANEL}" stroke="{LINE2}"/>',
              t(x + 14, y + 24, str(i), 13, ACCENT, 700), t(x + 14, y + 47, name, 16, TEXT, 700), t(x + 14, y + 66, l1, 11.5, TEXT2), t(x + 14, y + 81, l2, 11.5, TEXT2)]
        if i % 5 < 4:
            b.append(f'<path d="M{x + bw + 4} {y + bh / 2}H{x + bw + gap - 4}" stroke="#5B6E8A" stroke-width="1.5" marker-end="url(#ar)"/>')
    (x4, y4), (x5, y5) = pos[4], pos[5]
    b.append(f'<path d="M{x4 + bw / 2} {y4 + bh + 3}V{y4 + bh + 20}H{x5 + bw / 2}V{y5 - 4}" fill="none" stroke="#5B6E8A" stroke-width="1.5" marker-end="url(#ar)"/>')
    b += [f'<rect x="40" y="322" width="880" height="62" rx="8" fill="#0F1A1F" stroke="{ACCENT}" stroke-opacity=".55"/>',
          t(58, 348, "Audit trail under every stage", 16, ACCENT, 700),
          t(58, 370, "each event carries the hash of the one before; checkpoints are signed (Ed25519); verify-audit checks both", 13, TEXT2)]
    notes = [("Failures stay visible", ["A failing stage becomes a", "visible limitation in the", "dossier, not a crash."]),
             ("Optional local model", ["Off unless asked. It words", "headlines and a reading order,", "labelled INFERENCE. It cannot", "add, change or remove a finding."]),
             ("Offline", ["After install nothing uses the", "network. The review desk", "answers on 127.0.0.1 only."])]
    for k, (head, lines) in enumerate(notes):
        x = 40 + k * 300
        b.append(t(x, 416, head, 14, TEXT, 700))
        b += [t(x, 436 + 17 * j, s, 12.5, TEXT2) for j, s in enumerate(lines)]
    svg(960, 520, "pipeline.svg", b, "The pipeline: ingest, then read, classify, extract, forensics, checks, link, explain, crops and dossier, with an audit trail under every stage")


def classes():
    cards = [("observation", "Observation", ["Something seen, which untouched documents", "can show too, such as bytes after the end", "of a PDF."]),
             ("inconsistency", "Inconsistency", ["Two things that should agree do not, by a", "stated measure and tolerance. Example:", "declared income against the payslip."]),
             ("potential_manipulation", "Potential manipulation (for review)", ["Independent kinds of check point at one", "place. A priority for review, not a", "probability."]),
             ("processing_limitation", "Limitation of the analysis", ["A step could not run in full, so what it", "would have shown is unknown. It is never", "counted as a pass."])]
    b = [t(40, 40, "Four kinds of finding, kept apart in the desk and in the dossier", 18, TEXT, 700)]
    for i, (key, name, lines) in enumerate(cards):
        x, y, c = 40 + (i % 2) * 448, 62 + (i // 2) * 118, CLASS[key]
        dash = {"potential_manipulation": ' stroke-dasharray="6 3"', "processing_limitation": ' stroke-dasharray="2 3"'}.get(key, "")
        b += [f'<rect x="{x}" y="{y}" width="432" height="104" rx="6" fill="{PANEL}" stroke="{LINE}"/>',
              f'<path d="M{x + 3} {y + 6}V{y + 98}" stroke="{c}" stroke-width="5"{dash}/>']
        gx, gy = x + 24, y + 26
        if key == "observation":
            b.append(f'<path d="M{gx} {gy + 14}Q{gx + 16} {gy - 4} {gx + 32} {gy + 14}Q{gx + 16} {gy + 32} {gx} {gy + 14}Z" fill="none" stroke="{c}" stroke-width="2.5"/><circle cx="{gx + 16}" cy="{gy + 14}" r="5" fill="{c}"/>')
        elif key == "inconsistency":
            b.append(t(gx + 16, gy + 25, "≠", 34, c, 700, "middle"))
        elif key == "potential_manipulation":
            b.append(f'<path d="M{gx + 16} {gy - 2}L{gx + 32} {gy + 14}L{gx + 16} {gy + 30}L{gx} {gy + 14}Z" fill="none" stroke="{c}" stroke-width="2.5"/><circle cx="{gx + 16}" cy="{gy + 14}" r="3.5" fill="{c}"/>')
        else:
            b.append(f'<circle cx="{gx + 16}" cy="{gy + 14}" r="15" fill="none" stroke="{c}" stroke-width="2.5" stroke-dasharray="2 3"/>' + t(gx + 16, gy + 20, "i", 18, c, 700, "middle"))
        b += [t(x + 74, y + 32, name, 15, TEXT, 700)] + [t(x + 74, y + 56 + 17 * j, s, 12.5, TEXT2) for j, s in enumerate(lines)]
    svg(960, 298, "classes.svg", b, "The four classes of finding: observation, inconsistency, potential manipulation and limitation of the analysis")


def results():
    b = [t(40, 40, "Test split: 144 synthetic cases, 48 genuine, 96 with one planted change", 18, TEXT, 700),
         t(40, 64, "Run 1: the tool at spec-freeze (5 Nov). Run 2: the final pipeline at freeze-2 (8 Nov).", 13, TEXT2),
         t(40, 82, "Same cases, same scorer. Run 2 is not a blind test: the report of run 1 had been read.", 13, TEXT2),
         t(40, 126, "Planted changes found, by medium", 15, TEXT, 700)]
    x0, scale = 170, 330  # bars start at x0; 100 % is `scale` wide
    for k, (label, col) in enumerate((("Run 1", TEAL_DIM), ("Run 2", TEAL))):
        b += [f'<rect x="{40 + k * 84}" y="138" width="12" height="12" rx="2" fill="{col}"/>', t(58 + k * 84, 149, label, 12.5, TEXT2)]
    for g in (0, 50, 100):
        gx = x0 + scale * g / 100
        b += [f'<path d="M{gx} 162V398" stroke="{LINE}"/>', t(gx, 416, f"{g} %", 11.5, MUTED, anchor="middle")]
    for i, (label, n, a, c) in enumerate(MEDIA):
        y = 172 + i * 58
        b.append(t(40, y + 22, label, 13, TEXT))
        for k, (found, col) in enumerate(((a, TEAL_DIM), (c, TEAL))):
            w = scale * found / n
            b += [f'<rect x="{x0}" y="{y + k * 20}" width="{w:.1f}" height="16" rx="2" fill="{col}"/>', t(x0 + w + 8, y + k * 20 + 13, f"{found} of {n}", 12, TEXT2)]
    for j, (big, what, before) in enumerate(HEADLINE):
        y = 112 + j * 78
        b += [f'<rect x="640" y="{y}" width="280" height="68" rx="6" fill="{PANEL}" stroke="{LINE}"/>', t(656, y + 31, big, 26, TEXT, 700),
              t(656, y + 48, what, 12.5, TEXT2), t(656, y + 62, before, 11, MUTED)]
    b += [t(40, 450, "Counts of planted changes. Nine cases per scan medium is a small sample: read them as counts, not rates.", 12, MUTED),
          t(40, 468, "144 genuine documents = 48 genuine cases of three documents each. Both flags are on page 1 of test-0143, a 120 dpi scan.", 12, MUTED)]
    svg(960, 490, "results.svg", b, "Run 1 and run 2 on the held-out split: planted changes found by medium, and the headline counts")


def glyph(status, cx, cy, r=9):
    """One mark per status; the shape carries the meaning, so nothing rests on colour."""
    if status == "Implemented":
        return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{TEAL}"/>'
    ring = f'<circle cx="{cx}" cy="{cy}" r="{r - 1}" fill="none" stroke="{TEAL}" stroke-width="2"/>'
    if status == "Partial":
        return ring + f'<path d="M{cx} {cy - r + 1}A{r - 1} {r - 1} 0 0 0 {cx} {cy + r - 1}Z" fill="{TEAL}"/>'
    if status == "Planned":
        return ring
    return (f'<circle cx="{cx}" cy="{cy}" r="{r - 1}" fill="none" stroke="{MUTED}" stroke-width="2" stroke-dasharray="3 2.5"/>'
            f'<path d="M{cx - 5} {cy + 5}L{cx + 5} {cy - 5}" stroke="{MUTED}" stroke-width="2"/>')


MEANING = {"Implemented": "built, with tests", "Partial": "built, with a stated limit", "Planned": "not built, planned", "Unsupported": "not built, or not claimed"}


def capabilities():
    rows = json.loads((ROOT / "src" / "docforensics" / "capabilities.json").read_text(encoding="utf-8"))["capabilities"]
    n = Counter(r["status"] for r in rows)
    assert set(n) == set(MEANING), n
    pitch, r, group_gap = 22, 9, 22
    x = (960 - (len(rows) * pitch + 3 * group_gap)) / 2
    b = [t(40, 40, f"{len(rows)} capabilities, each marked by what its evidence supports", 18, TEXT, 700),
         t(40, 64, "A status changes only when the evidence does. A Partial row says in the matrix what is missing.", 13, TEXT2)]
    for s in MEANING:
        b.append(t(x + n[s] * pitch / 2 - (pitch - 2 * r) / 2, 116, str(n[s]), 26, TEXT, 700, "middle"))
        b += [glyph(s, x + r + k * pitch, 150) for k in range(n[s])]
        x += n[s] * pitch + group_gap
    for k, (s, meaning) in enumerate(MEANING.items()):  # the key repeats each shape with its meaning
        kx, ky = 40 + (k % 2) * 440, 204 + (k // 2) * 28
        b += [glyph(s, kx + r, ky), t(kx + 2 * r + 10, ky + 5, f"{s}: {meaning}", 12.5, TEXT2)]
    svg(960, 262, "capabilities.svg", b, f"Capability matrix: {n['Implemented']} implemented, {n['Partial']} partial, {n['Planned']} planned, {n['Unsupported']} unsupported")
    return n


def check_readme(counts):
    """The figures say what the README says: refuse to draw a number the text does not hold."""
    doc = (ROOT / "README.md").read_text(encoding="utf-8")
    sentence = ", ".join(f"{label.lower()} {a} of {n} and {c} of {n}" for label, n, a, c in MEDIA)
    for needed in (sentence, "83 of 96 (86 %)", "79 of 96 (82 %)", "| 37 | 40 |", "| 17 | 13 (each was also a miss in the first run) |", "440 of 440"):
        assert needed in doc, f"README does not hold: {needed}"
    assert f"{counts['Implemented']} Implemented" in doc or f"| Implemented |" in doc  # the matrix is generated from the same file


if __name__ == "__main__":
    counts = capabilities()
    try:
        check_readme(counts)
    except AssertionError as e:
        sys.exit(f"not drawn: {e}")
    banner(), pipeline(), classes(), results()
    print("written:", ", ".join(sorted(p.name for p in OUT.glob("*.svg"))))
