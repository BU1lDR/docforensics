"""Dossier (design 7.9): the case as one document for a reviewer. Sections follow PS-2 7.1 to 7.6; the appendices hold the audit trail,
the capability matrix and the limitations. It is written twice from one dict: dossier.json for machines, and dossier.html, which is
self-contained (crops embedded, no scripts, no address to fetch). Text that came from a document is stripped of control and bidi
characters and escaped before it reaches the HTML. Observations, inconsistencies, potential-manipulation candidates and limitations
are kept in separate places, and each row says which it is."""
import base64
import hashlib
import json
import os
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from . import __version__
from .audit import GENESIS
from .capabilities import load_capabilities
from .findings import quote
from .ingest import sniff
from .model import Case, Document, Evidence, Finding
from .pipeline import Ctx
from .relations import build_relations
from .signing import checkpoint, signing_view
from .store import CaseDir

MAX_CROP_BYTES = 2_000_000  # a crop is a padded piece of one page: a bigger file is not one of ours
SHOWN = 2000  # characters of any one value shown in the HTML
ANOMALY = ("potential_manipulation", "inconsistency")  # in this order in the summary
NOTICE = ("Every item in this dossier is for a human reviewer to examine. Nothing in it is a conclusion about whether a document is "
          "genuine or about anyone's conduct. Values were read from the documents by software: OCR output is a reading, not ground "
          "truth, and each finding says how doubtful its weakest reading is. A status of 'confirmed by reviewer' appears only when a "
          "person set it.")
CLASS_LABEL = {"observation": "Observation", "inconsistency": "Inconsistency",
               "potential_manipulation": "Potential manipulation (for review)", "processing_limitation": "Limitation of the analysis"}
SOURCE_LABEL = {"template": "Template wording", "llm": "AI-generated wording (inference)"}
READING_LABEL = "AI reading of the case (inference)"
METHOD = "sha256 of this document without this block, as JSON with sorted keys, compact separators and ASCII escapes"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("ascii")


def _round(box) -> list[float]:
    return [round(v, 1) for v in box]


def _evidence_row(n: int, e: Evidence, docs: dict[str, Document]) -> dict:
    d = docs.get(e.doc)
    dpi = d.pages[e.page - 1].dpi if d and 0 < e.page <= len(d.pages) else 200
    return {"n": n, "document": e.doc, "file": d.filename if d else None, "sha256": d.sha256 if d else None, "page": e.page,
            "box": _round(e.box), "dpi": dpi, "box_pt": _round([v * 72 / dpi for v in e.box]), "note": e.note,
            "field": e.field_id, "value": e.value, "crop": e.crop_path}


def _finding_row(f: Finding, docs: dict[str, Document]) -> dict:
    return {"id": f.id, "class": f.fclass, "detector": f.detector, "family": f.family, "title": f.title, "detail": f.detail,
            "confidence": f.conf, "review_priority": f.review_priority, "status": f.status, "reviewer_note": f.note,
            "explanation": f.explanation, "explanation_source": f.explanation_source, "next_steps": f.next_steps,
            "related": f.related, "cluster": f.cluster, "evidence": [_evidence_row(i, e, docs) for i, e in enumerate(f.evidence, 1)]}


def _document(d: Document) -> dict:
    return {"id": d.id, "file": d.filename, "sha256": d.sha256, "size": d.size, "kind": d.kind, "type": d.doc_type,
            "type_confidence": d.type_conf, "meta": d.meta,
            "pages": [{"n": p.n, "width": p.width, "height": p.height, "dpi": p.dpi, "read_mode": p.read_mode,
                       "quality": p.quality_class, "sharpness": p.sharpness, "words": len(p.words)} for p in d.pages],
            "fields": [{"id": f.id, "name": f.name, "raw": f.raw, "value": f.value, "kind": f.kind, "confidence": f.conf,
                        "page": f.page, "box": _round(f.box), "row": f.row, "role": f.role, "note": f.note,
                        **({"model_read": True} if f.model_read else {})} for f in d.fields]}


def audit_view(ctx: Ctx) -> dict:
    """The trail as it stands now, whether its chain holds, and its length and last hash (the anchor). A missing or empty trail is a
    problem: every case starts with an event."""
    ok, bad = ctx.audit.verify()
    try:
        events = ctx.audit.events()
    except ValueError:  # a line that is not an event: verify() has already said where
        events = []
    problem = (None if events else "No audit trail: audit.jsonl is missing or empty.") if ok else \
        f"The hash chain breaks at event {bad}: the audit trail was changed after it was written."
    return {"events": [e.model_dump() for e in events], "anchor": {"events": len(events), "head": events[-1].hash if events else GENESIS},
            "chain_ok": problem is None, "problem": problem, "signing": signing_view(ctx.cd)}


def _tool_order(case: Case) -> list[str]:
    """The order the tool itself reads the findings in: highest review priority first, clusters and limitations left out."""
    return [f.id for f in sorted((f for f in case.findings if f.detector != "link" and f.fclass != "processing_limitation"),
                                 key=lambda f: (-f.review_priority, f.id))]


def ai_reading(case: Case, events: list[dict]) -> dict:
    """What a local model made of the whole case, or why there is none. It is inference, kept apart from the findings, and it changes
    none of them. The model's order is given only where it differs from the tool's."""
    r = case.reasoning
    if r is None:
        asked = [e["data"] for e in events if e["event"] == "llm_reasoning"]
        if not asked:
            return {"status": "none", "note": "No language model was used for this case."}
        why, model = asked[-1].get("reason") or "nothing it said passed the checks", asked[-1].get("model", "")
        if why.startswith("skipped"):  # the stage ran out of time before it made the call
            return {"status": "none", "note": f"A local language model ({model}) was turned on for this case but did not read it ({why})."}
        return {"status": "none", "note": f"A local language model ({model}) was asked to read this case and none of its reading was kept: {why}."}
    return {"status": "kept", "source": r.source, "model": r.model, "summary": r.summary, "relations": [x.model_dump() for x in r.relations],
            "order": r.order if r.order != _tool_order(case) else [], "rejected": [{"part": p, "reason": why} for p, why in r.rejected]}


def dossier_dict(case: Case, ctx: Ctx) -> dict:
    docs = {d.id: d for d in case.documents}
    rows = [_finding_row(f, docs) for f in case.findings]
    trail = audit_view(ctx)

    def of(*classes: str) -> list[dict]:
        return [r for r in rows if r["class"] in classes]

    anomalies = sorted(of(*ANOMALY), key=lambda r: (ANOMALY.index(r["class"]), -r["review_priority"]))
    steps: dict[str, list[str]] = {}
    for r in rows:
        for s in r["next_steps"]:
            steps.setdefault(s, []).append(r["id"])
    caps = load_capabilities()
    d = {
        "overview": {
            "case": case.id, "created": case.created, "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "tool": {"name": "docforensics", "version": __version__}, "notice": NOTICE, "thresholds": ctx.th.as_dict(),
            "documents": [{"id": x.id, "file": x.filename, "sha256": x.sha256, "size": x.size, "type": x.doc_type, "pages": len(x.pages)}
                          for x in case.documents],
            "counts": {"documents": len(case.documents), "findings": len(rows), "observations": len(of("observation")),
                       "inconsistencies": len(of("inconsistency")), "potential_manipulation": len(of("potential_manipulation")),
                       "limitations": len(of("processing_limitation"))}},
        "extracted_information": {"documents": [_document(x) for x in case.documents]},
        "contextual_analysis": {"inconsistencies": of("inconsistency"), "potential_manipulation": of("potential_manipulation"),
                                "relationships": build_relations(case, ctx.th)},
        "visual_forensic_findings": {"observations": of("observation")},
        "evidence_and_traceability": {
            "documents": [{"id": x.id, "file": x.filename, "sha256": x.sha256, "stored_path": x.stored_path, "size": x.size}
                          for x in case.documents],
            "trace": [{"finding": r["id"], **e} for r in rows for e in r["evidence"]]},
        "investigation_summary": {
            "anomalies": [{k: r[k] for k in ("id", "class", "title", "confidence", "status")} for r in anomalies],
            "evidence": [{"finding": r["id"], "places": [{k: e[k] for k in ("n", "file", "page", "box", "note")} for e in r["evidence"]]}
                         for r in anomalies],
            "explanations": [{"finding": r["id"], "explanation": r["explanation"], "source": r["explanation_source"]} for r in anomalies],
            "further_verification": [{"step": s, "findings": ids} for s, ids in steps.items()],
            "limitations": of("processing_limitation"), "ai_reading": ai_reading(case, trail["events"])},
        "appendices": {"audit_trail": trail, "capabilities": caps["capabilities"],
                       "limitations": {"limitations": caps["limitations"], "assumptions": caps["assumptions"]}},
    }
    d["integrity"] = {"json_sha256": _sha(_canon(d)), "method": METHOD}
    return d


class Raw(str):
    """Markup this module wrote itself. Every other string is escaped."""


def esc(v) -> str:
    return str(v) if isinstance(v, Raw) else escape(quote("" if v is None else str(v), SHOWN), quote=True)


def _num(v, nd: int = 2) -> str:
    return "" if v is None else f"{v:.{nd}f}"


def _table(head: list[str], rows: list[list]) -> Raw:
    if not rows:
        return Raw('<p class="none">None.</p>')
    th = "".join(f"<th>{esc(h)}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>" for row in rows)
    return Raw(f"<table><tr>{th}</tr>{body}</table>")


def _link(fid: str) -> Raw:
    return Raw(f'<a href="#{esc(fid)}">{esc(fid)}</a>')


def _crop_uri(cd: CaseDir, rel: str) -> str | None:
    """The crop as a data: address, or None when it is not a PNG of ours inside the case's crops folder."""
    try:
        path = (cd.root / rel).resolve()
        if not path.is_relative_to(cd.crops.resolve()) or path.stat().st_size > MAX_CROP_BYTES:
            return None
        data = path.read_bytes()
    except (OSError, ValueError):
        return None
    return ("data:image/png;base64," + base64.b64encode(data).decode("ascii")) if sniff(data) == "png" else None


def _where(e: dict, full: bool = False) -> str:
    """'the document as a whole', or the page and box (with dpi and points when `full`)."""
    if e["page"] == 0:
        return "the document as a whole"
    px = f"page {e['page']}, box {' '.join(map(str, e['box']))} px"
    return f"{px} at {e['dpi']} dpi ({' '.join(map(str, e['box_pt']))} pt)" if full else px


def _evidence_item(rid: str, e: dict, cd: CaseDir) -> str:
    said = [esc(e["note"])] if e["note"] else []
    if e["value"] is not None:
        said.append(f"value read: <code>{esc(e['value'])}</code>")
    uri = _crop_uri(cd, e["crop"]) if e["crop"] else None
    crop = f'<br><img alt="Crop of evidence {e["n"]} of {esc(rid)}" src="{uri}">' if uri else \
        (' <span class="warn">crop not available</span>' if e["crop"] else "")
    return (f'<li>{esc(e["file"] or "(document not in this case)")} <span class="sha">sha256 {esc(e["sha256"])}</span>, '
            f'{esc(_where(e, True))}' + "".join(f"; {s}" for s in said) + f".{crop}</li>")


def _card(r: dict, cd: CaseDir) -> str:
    own = f"<p>{esc(r['detail'])}</p>" if r["detail"] else ""
    why = f'<p><b>{esc(SOURCE_LABEL[r["explanation_source"]])}:</b> {esc(r["explanation"])}</p>' if r["explanation"] else ""
    steps = "<ul>" + "".join(f"<li>{esc(s)}</li>" for s in r["next_steps"]) + "</ul>" if r["next_steps"] else ""
    note = f"<p>Reviewer note: {esc(r['reviewer_note'])}</p>" if r["reviewer_note"] else ""
    rel = f"<p>Related: {', '.join(_link(x) for x in r['related'])}</p>" if r["related"] else ""
    rel += f"<p>Grouped under {_link(r['cluster'])}.</p>" if r["cluster"] else ""
    ev = "<ol>" + "".join(_evidence_item(r["id"], e, cd) for e in r["evidence"]) + "</ol>" if r["evidence"] else \
        '<p class="none">No evidence location is recorded.</p>'
    return (f'<article class="{esc(r["class"])}" id="{esc(r["id"])}"><h4><span class="tag">{esc(CLASS_LABEL[r["class"]])}</span> '
            f'{esc(r["id"])}: {esc(r["title"])}</h4><p class="meta">detector {esc(r["detector"])}; family {esc(r["family"])}; '
            f'weakest-reading confidence {_num(r["confidence"])}; review priority {esc(r["review_priority"])}; '
            f'status {esc(r["status"])}</p>{own}{why}{steps}{note}{rel}<h5>Evidence</h5>{ev}</article>')


def _cards(rows: list[dict], cd: CaseDir) -> str:
    return "".join(_card(r, cd) for r in rows) or '<p class="none">None.</p>'


def _overview(d: dict) -> str:
    o = d["overview"]
    docs = _table(["Id", "File", "sha256", "Bytes", "Type", "Pages"],
                  [[x["id"], x["file"], x["sha256"], x["size"], x["type"], x["pages"]] for x in o["documents"]])
    th = _table(["Threshold", "Value"], [[k, v] for k, v in o["thresholds"].items()])
    return (f'<p class="notice">{esc(o["notice"])}</p><p>Case {esc(o["case"])}, created {esc(o["created"])}, dossier generated '
            f'{esc(o["generated"])} by {esc(o["tool"]["name"])} {esc(o["tool"]["version"])}.</p>'
            f'{_table(list(o["counts"]), [list(o["counts"].values())])}<h3>Documents</h3>{docs}'
            f'<details><summary>Thresholds used for this case</summary>{th}</details>')


def _extracted(d: dict) -> str:
    docs = d["extracted_information"]["documents"]
    if not docs:
        return '<p class="none">No document was accepted, so nothing was read.</p>'
    out = []
    for x in docs:
        out.append(f'<h3>{esc(x["id"])}: {esc(x["file"])} <span class="meta">({esc(x["type"])}, classification confidence '
                   f'{_num(x["type_confidence"])})</span></h3>')
        out.append(_table(["Page", "Width", "Height", "dpi", "Read by", "Quality", "Sharpness", "Words"],
                          [[p["n"], p["width"], p["height"], p["dpi"], p["read_mode"], p["quality"], _num(p["sharpness"], 3), p["words"]]
                           for p in x["pages"]]))
        out.append(_table(["Id", "Field", "As read", "Value", "Kind", "Confidence", "Page", "Box (px)", "Row", "Role", "Note"],
                          [[f["id"], f["name"], f["raw"], f["value"], f["kind"], _num(f["confidence"]), f["page"],
                            " ".join(map(str, f["box"])), f["row"], f["role"], f["note"]] for f in x["fields"]]))
        if x["meta"]:
            out.append("<h4>File metadata</h4>" + _table(["Key", "Value"], [[k, v] for k, v in x["meta"].items()]))
    return "".join(out)


def _entities(d: dict) -> str:
    """Which names, addresses, employers and account numbers the documents write, and which findings touch each."""
    rows = []
    for e in d["contextual_analysis"]["relationships"]["entities"]:
        where = Raw("<br>".join(f"{esc(m['file'])}, page {esc(m['page'])}, {esc(m['name'])}: {esc(m['value'])}" for m in e["mentions"]))
        rows.append([e["id"], e["role"], where, Raw(", ".join(_link(f) for f in e["findings"])) if e["findings"] else "none"])
    return ("<p>Entities are numbered in the order the documents mention them. Two writings share a row when the cross-document checks "
            "grade them the same, or the same apart from form. A writing those checks grade as a mismatch has a row of its own, and the "
            "finding that reports the mismatch is listed against both. It is a listing of what was read, not a conclusion.</p>"
            + _table(["Entity", "Role", "Where it is written", "Findings that touch it"], rows))


def _traceability(d: dict) -> str:
    t = d["evidence_and_traceability"]
    docs = _table(["Id", "File", "sha256", "Stored as", "Bytes"], [[x["id"], x["file"], x["sha256"], x["stored_path"], x["size"]] for x in t["documents"]])
    trace = _table(["Finding", "#", "File", "sha256", "Page", "Box (px)", "Box (pt)", "Note", "Value", "Crop file"],
                   [[_link(e["finding"]), e["n"], e["file"], e["sha256"], "whole document" if e["page"] == 0 else e["page"],
                     " ".join(map(str, e["box"])), " ".join(map(str, e["box_pt"])), e["note"], e["value"], e["crop"]] for e in t["trace"]])
    return ('<p>Each row is one place a finding cites. Page 0 is the document as a whole. Points are pixels x 72 / dpi.</p>'
            f'<h3>Documents</h3>{docs}<h3>Places cited</h3>{trace}')


def _reading(d: dict) -> str:
    a = d["investigation_summary"]["ai_reading"]
    head = f"<h3>{esc(READING_LABEL)}</h3>"
    if a["status"] != "kept":
        return f'{head}<p class="none">{esc(a["note"])}</p>'
    rel = _table(["Finding", "Finding", "Kind", "Reason"], [[_link(x["a"]), _link(x["b"]), x["kind"], x["reason"]] for x in a["relations"]])
    order = f'<h4>Reading order the model suggests</h4><p>{", ".join(_link(i) for i in a["order"])}</p>' if a["order"] else ""
    dropped = ("<details><summary>Dropped by the checks</summary><ul>" + "".join(f"<li>{esc(x['part'] + ': ' + x['reason'])}</li>" for x in a["rejected"])
               + "</ul></details>") if a["rejected"] else ""
    return (f'{head}<p class="meta">Written by the local model {esc(a["model"])} from the findings. It is a reading, not a finding: it does not '
            f'change, add or remove any finding, and it is not evidence.</p>'
            f'<p>{esc(a["summary"]) if a["summary"] else "The model gave no summary that passed the checks."}</p>'
            f'<h4>Relations the model suggests</h4>{rel}{order}{dropped}')


def _summary(d: dict, cd: CaseDir) -> str:
    s = d["investigation_summary"]
    anomalies = _table(["Finding", "Class", "Title", "Weakest-reading confidence", "Status"],
                       [[_link(a["id"]), CLASS_LABEL[a["class"]], a["title"], _num(a["confidence"]), a["status"]] for a in s["anomalies"]])
    evidence = ""
    for e in s["evidence"]:
        places = "".join(f'<li>{esc(p["file"])}, {esc(_where(p))}. {esc(p["note"])}</li>' for p in e["places"])
        evidence += f'<h4>{esc(e["finding"])}</h4><ul>{places}</ul>'
    why = "".join(f'<p><b>{esc(e["finding"])}</b> ({esc(SOURCE_LABEL[e["source"]])}): {esc(e["explanation"])}</p>'
                  for e in s["explanations"])
    verify = _table(["Step", "Findings"], [[v["step"], Raw(", ".join(_link(i) for i in v["findings"]))] for v in s["further_verification"]])
    none = '<p class="none">None.</p>'
    return (f'<h3>Anomalies for review</h3>{anomalies}<h3>Evidence</h3>{evidence or none}<h3>Explanations</h3>{why or none}'
            f'<h3>Further verification</h3>{verify}<h3>Limitations of this analysis</h3>{_cards(s["limitations"], cd)}{_reading(d)}')


def _signing_paragraph(s: dict) -> str:
    """What the signed checkpoints say about the trail, and what they cannot say (signing.py)."""
    if s["status"] == "broken":
        return f'<p class="warn">{esc(s["problem"])}</p>'
    if s["status"] == "unsigned":
        return ("<p>No signed checkpoint covers this trail, so a change made together with a new hash chain, or a cut at the end of the trail, "
                "would not show.</p>")
    last = s["last"]
    later = f' {esc(s["uncovered"])} later event(s) are not covered.' if s["uncovered"] else ""
    return (f'<p>Signed: {esc(s["checkpoints"])} checkpoint(s) by the {esc(s["algorithm"])} key {esc(s["key_id"][:16])}. The last, made {esc(last["ts"])}, '
            f'covers events 1 to {esc(last["events"])}, ending in hash {esc(last["head"][:16])}, signature {esc(last["sig"][:16])}.{later} A checkpoint shows '
            'that the events it covers were not changed or cut off after it was signed, as far as the key stayed private and the checkpoint is still in the file. '
            'It does not show who signed or when: the time is the clock of the machine that signed. The signatures are in checkpoints.jsonl in the case folder; '
            'verify-audit checks them, and its --pubkey option checks them against a key you know from elsewhere. The last checkpoints could be deleted '
            'together with the events they cover, and the events after the last checkpoint could be replaced and then signed by a later action; a copy of the head, '
            'kept outside the case folder, would show either.</p>')


def _audit_section(d: dict) -> str:
    a = d["appendices"]["audit_trail"]
    warn = f'<p class="warn">{esc(a["problem"])}</p>' if a["problem"] else "<p>The hash chain verifies.</p>"
    warn += _signing_paragraph(a["signing"])
    events = _table(["#", "Time (UTC)", "Actor", "Event", "Data", "Hash"],
                    [[e["seq"], e["ts"], e["actor"], e["event"], json.dumps(e["data"]), e["hash"][:16]] for e in a["events"]])
    return (f'{warn}<p>The trail below ends at event {esc(a["anchor"]["events"])}, hash {esc(a["anchor"]["head"])}. Events written after '
            f'this dossier was made are in audit.jsonl.</p>{events}')


def _capabilities_section(d: dict) -> str:
    return _table(["Capability", "Status", "Evidence", "Note"],
                  [[c["name"], c["status"], Raw("<br>".join(esc(x) for x in c["evidence"])), c.get("note", "")]
                   for c in d["appendices"]["capabilities"]])


def _limits_section(d: dict) -> str:
    x = d["appendices"]["limitations"]

    def items(xs: list[str]) -> str:
        return "<ul>" + "".join(f"<li>{esc(i)}</li>" for i in xs) + "</ul>"

    return f'<h3>Limitations</h3>{items(x["limitations"])}<h3>Assumptions</h3>{items(x["assumptions"])}'


CSS = ("body{font:14px/1.45 system-ui,sans-serif;max-width:1100px;margin:1.5em auto;padding:0 1em;color:#111}"
       "table{border-collapse:collapse;width:100%;margin:.5em 0;font-size:12px}"
       "td,th{border:1px solid #bbb;padding:3px 6px;text-align:left;vertical-align:top;overflow-wrap:break-word}th{background:#eee}"
       "article{border:1px solid #bbb;border-left-width:6px;padding:.3em .9em;margin:.8em 0;break-inside:avoid}"
       ".observation{border-left-color:#2b6cb0}.inconsistency{border-left-color:#c05621}"
       ".potential_manipulation{border-left-color:#b83280}.processing_limitation{border-left-color:#718096}"
       ".tag{font-weight:600}.meta,.sha{color:#555;font-size:12px}.warn{color:#b00020;font-weight:600}.notice{background:#f6f6f0;padding:.5em}"
       "img{max-width:100%;border:1px solid #888}@media print{nav{display:none}}")


def _page(d: dict, ctx: Ctx) -> str:
    cd = ctx.cd
    ca = d["contextual_analysis"]
    parts = [
        ("overview", "1. Overview", _overview(d)),
        ("extracted_information", "2. Extracted information", _extracted(d)),
        ("contextual_analysis", "3. Contextual analysis",
         "<p>Where documents, or parts of one, disagree. A candidate for manipulation appears only where independent kinds of check "
         f"point at the same place.</p><h3>Potential manipulation</h3>{_cards(ca['potential_manipulation'], cd)}"
         f"<h3>Inconsistencies</h3>{_cards(ca['inconsistencies'], cd)}<h3>Entities across documents</h3>{_entities(d)}"),
        ("visual_forensic_findings", "4. Visual forensic findings",
         "<p>Measured properties of the files and pages. An observation is not a problem: unaltered documents can show the same.</p>"
         + _cards(d["visual_forensic_findings"]["observations"], cd)),
        ("evidence_and_traceability", "5. Evidence and traceability", _traceability(d)),
        ("investigation_summary", "6. Investigation summary", _summary(d, cd)),
        ("appendix_audit_trail", "Appendix A. Audit trail", _audit_section(d)),
        ("appendix_capabilities", "Appendix B. Capability matrix", _capabilities_section(d)),
        ("appendix_limitations", "Appendix C. Limitations and assumptions", _limits_section(d)),
    ]
    nav = " | ".join(f'<a href="#{i}">{esc(t)}</a>' for i, t, _ in parts)
    body = "".join(f'<section id="{i}"><h2>{esc(t)}</h2>{b}</section>' for i, t, b in parts)
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Investigation dossier {esc(d["overview"]["case"])}</title>'
            f'<style>{CSS}</style></head><body><h1>Investigation dossier</h1><nav>{nav}</nav>{body}'
            f'<p class="meta">Content hash of the data in dossier.json (sha256): {esc(d["integrity"]["json_sha256"])}</p></body></html>')


def _write(path: Path, data: bytes) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def build_dossier(case: Case, ctx: Ctx) -> tuple[Path, Path]:
    """Write dossier.html and dossier.json into the case folder and audit both files' hashes. Returns (html path, json path). Where the case
    already has signed checkpoints the trail is signed first, so the dossier carries a signed anchor, and again after `dossier_generated`,
    so that event is covered too. Asking for a dossier never begins a chain: only a run does (signing.checkpoint)."""
    checkpoint(ctx.cd)
    d = dossier_dict(case, ctx)
    js, page = json.dumps(d, indent=1).encode("ascii"), _page(d, ctx).encode("utf-8")
    _write(ctx.cd.dossier_json, js)
    _write(ctx.cd.dossier_html, page)
    ctx.audit.append("system", "dossier_generated", {"html_sha256": _sha(page), "json_sha256": _sha(js), "content_sha256": d["integrity"]["json_sha256"],
                                                     "documents": len(case.documents), "findings": len(case.findings)})
    checkpoint(ctx.cd)
    return ctx.cd.dossier_html, ctx.cd.dossier_json


def dossier_stage(case: Case, ctx: Ctx) -> None:
    checkpoint(ctx.cd, start=True)  # the stage of a run: it begins the chain, so the dossier it writes carries a signed anchor
    build_dossier(case, ctx)
