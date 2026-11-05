"use strict";
/* Review desk (design 7.8). One page, no framework, no build step.
   Text that came from a document reaches the page only through textContent, append(string) or setAttribute, never as markup;
   the content security policy also forbids inline script and style. The wording of the labels is the dossier's. */

const CLASS_LABEL = {
  observation: "Observation",
  inconsistency: "Inconsistency",
  potential_manipulation: "Potential manipulation (for review)",
  processing_limitation: "Limitation of the analysis",
};
const SOURCE_LABEL = {template: "Template wording", llm: "AI-generated wording (inference)"};
const READING_LABEL = "AI reading of the case (inference)";
const MODEL_READ_LABEL = "model-read (inference)";
const STATUS_LABEL = {
  open: "Open",
  needs_verification: "Needs verification",
  confirmed_by_reviewer: "Confirmed by reviewer",
  dismissed: "Dismissed",
};
const REVIEW = [
  ["needs_verification", "Needs verification"],
  ["confirmed_by_reviewer", "Confirmed by reviewer"],
  ["dismissed", "Dismissed"],
  ["open", "Back to open"],
];
// Potential manipulation first, as in the dossier's summary; observations and limitations after the anomalies.
const CLASS_ORDER = ["potential_manipulation", "inconsistency", "observation", "processing_limitation"];
const STAGES = [
  ["read", "Reading pages (text layer or OCR)"],
  ["classify", "Classifying documents"],
  ["extract", "Extracting fields"],
  ["forensics", "Checking the files for changes"],
  ["checks", "Checking values within and across documents"],
  ["link", "Relating findings"],
  ["explain", "Writing explanations"],
  ["crops", "Cutting evidence crops"],
  ["dossier", "Building the dossier"],
];
const TABS = ["documents", "findings", "clusters", "relationships", "audit", "capabilities", "dossier"];
const SVGNS = "http://www.w3.org/2000/svg";

const state = {
  id: null,       // the case that is open
  info: null,     // the last answer for it: {status, stage, error, intake, low_conf, case}
  doc: null,      // the document in the viewer
  page: 1,
  zoom: null,     // null = fit the width
  show: {words: false, fields: true, findings: true},
  finding: null,  // the selected finding
  mark: null,     // a box picked from the fields table or an evidence item: {doc, page, box, label}
  tab: "documents",
  timer: null,
  audit: null,
  caps: null,
  rel: null,      // the relationship view of the open case, as the server worked it out
  relSel: null,   // the box picked in it: a document, entity or finding id
};

const $ = (id) => document.getElementById(id);
const enc = encodeURIComponent;
const cases = () => `/api/cases/${enc(state.id)}`;
const data = () => (state.info && state.info.case) || null;
const docsOf = () => (data() ? data().documents : []);
const findingsOf = () => (data() ? data().findings : []);
const docNow = () => docsOf().find((d) => d.id === state.doc) || null;
const pageNow = () => {
  const d = docNow();
  return (d && d.pages.find((p) => p.n === state.page)) || null;
};
const num = (v) => String(Math.round(v * 10) / 10);
const conf = (v) => Number(v).toFixed(2);
const shorten = (t, n) => (t.length > n ? `${t.slice(0, n - 3)}...` : t);
const lowConf = () => (state.info ? state.info.low_conf : 0.6);

// ---- building elements -------------------------------------------------------------------------------------------

/* h("tag", {attr: value, event: handler}, ...children). A function is an event listener, true is a bare attribute, and
   null or false is skipped. Strings in children become text nodes. */
function h(tag, props, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v == null || v === false) continue;
    if (typeof v === "function") el.addEventListener(k, v);
    else el.setAttribute(k, v === true ? "" : String(v));
  }
  el.append(...kids.flat().filter((k) => k != null && k !== false));
  return el;
}

function svgEl(tag, props, title) {
  const el = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(props)) el.setAttribute(k, String(v));
  if (title) {
    const t = document.createElementNS(SVGNS, "title");
    t.textContent = title;
    el.append(t);
  }
  return el;
}

const rect = (b, cls, title, extra) =>
  svgEl("rect", {x: b[0], y: b[1], width: b[2] - b[0], height: b[3] - b[1], class: cls, ...extra}, title);

function say(text, bad) {
  const m = $("message");
  m.textContent = text;
  m.className = bad ? "bad" : "";
}

async function api(url, opts) {
  let r;
  try {
    r = await fetch(url, opts);
  } catch (e) {
    throw new Error("the server did not answer; is it still running?");
  }
  if (!r.ok) {
    let why = r.statusText;
    try {
      const j = await r.json();
      why = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch (e) {
      // the reply was not JSON: the status text will do
    }
    throw new Error(`${r.status}: ${why}`);
  }
  return r.json();
}

// ---- loading a case ----------------------------------------------------------------------------------------------

async function openCase(id, finding) {
  clearTimeout(state.timer);
  Object.assign(state, {id, info: null, doc: null, page: 1, finding: finding || null, mark: null, audit: null, rel: null, relSel: null});
  history.replaceState(null, "", finding ? `#${id}/${finding}` : `#${id}`);
  say("");
  render();
  await refresh();
}

async function refresh() {
  const id = state.id;
  let info;
  try {
    info = await api(cases());
  } catch (e) {
    if (state.id === id) say(`Cannot read case ${id}: ${e.message}`, true);
    return;
  }
  if (state.id !== id) return; // another case was opened while this answer was on its way
  const before = state.info && state.info.status;
  state.info = info;
  if (info.status === "processing") state.timer = setTimeout(refresh, 1000);
  else if (before !== info.status) arrived(info);
  render();
}

// The analysis has ended (or the case was already finished when it was opened): choose what to show first.
function arrived(info) {
  const ds = docsOf();
  if (!state.doc && ds.length) state.doc = ds[0].id;
  if (info.status === "failed") say(`The analysis did not finish: ${info.error}`, true);
  else say(`Analysis finished: ${ds.length} document(s), ${findingsOf().length} finding(s).`);
  if (state.finding && !pick(state.finding)) {
    say(`This case has no finding ${state.finding}.`, true);
    state.finding = null;
  }
}

// Select a finding in the state only: show its first piece of evidence in the viewer. False if there is no such finding.
function pick(id) {
  const f = findingsOf().find((x) => x.id === id);
  state.finding = f ? id : null;
  state.mark = null;
  if (!f) return false;
  const e = f.evidence.find((x) => x.page > 0 && docsOf().some((d) => d.id === x.doc));
  if (e) {
    state.doc = e.doc;
    state.page = e.page;
  }
  state.tab = "findings";
  return true;
}

function selectFinding(id) {
  if (pick(id)) history.replaceState(null, "", `#${state.id}/${id}`);
  render();
}

function mark(d, page, box, label) {
  Object.assign(state, {doc: d.id, page, mark: {doc: d.id, page, box, label}});
  render();
}

function showDoc(id) {
  Object.assign(state, {doc: id, page: 1, mark: null});
  render();
  $("page").scrollTo(0, 0);
}

function turn(by) {
  const d = docNow();
  const n = state.page + by;
  if (!d || n < 1 || n > d.pages.length) return;
  Object.assign(state, {page: n, mark: null});
  render();
  $("page").scrollTo(0, 0);
}

function fromHash() {
  const m = /^#(C-\d{8}-\d{6}-[0-9a-f]{4})(?:\/(F-\d+))?$/.exec(location.hash);
  if (!m) return;
  if (m[1] !== state.id) openCase(m[1], m[2]);
  else if (m[2]) selectFinding(m[2]);
}

async function onUpload(ev) {
  ev.preventDefault();
  const input = $("files");
  if (!input.files.length) {
    say("Choose at least one PDF, PNG or JPEG file first.", true);
    return;
  }
  const form = new FormData();
  for (const f of input.files) form.append("files", f, f.name);
  $("go").disabled = true;
  say("Uploading...");
  try {
    const out = await api("/api/cases", {method: "POST", body: form});
    input.value = "";
    await openCase(out.case_id);
    say(`Case ${out.case_id} created; analysing.`);
  } catch (e) {
    say(`Upload failed: ${e.message}`, true);
  } finally {
    $("go").disabled = false;
  }
}

async function review(f, status) {
  const body = {};
  if (status) body.status = status;
  const note = $("note").value;
  if (note !== f.note) body.note = note;
  if (!Object.keys(body).length) {
    say("Nothing to save: the status and the note are unchanged.");
    return;
  }
  try {
    const out = await api(`${cases()}/findings/${enc(f.id)}/review`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body),
    });
    Object.assign(f, out); // the server's copy is the record
    state.audit = null;
    say(`${f.id} saved as "${STATUS_LABEL[f.status]}". The action is in the audit trail.`);
  } catch (e) {
    say(`Not saved: ${e.message}`, true);
  }
  render();
}

// ---- rendering ---------------------------------------------------------------------------------------------------

function render() {
  renderCaseLine();
  renderViewerBar();
  renderPage();
  renderDocuments();
  renderFields();
  renderFindings();
  renderClusters();
  renderDossier();
  showTab(state.tab);
}

function showTab(name) {
  state.tab = name;
  for (const b of document.querySelectorAll("[data-tab]")) b.setAttribute("aria-selected", String(b.dataset.tab === name));
  for (const t of TABS) $(`tab-${t}`).hidden = t !== name;
  if (name === "relationships") {
    if (state.rel) renderRelations();
    else loadRelations();
  }
  if (name === "audit") {
    if (state.audit) renderAudit();
    else loadAudit();
  }
  if (name === "capabilities") {
    if (state.caps) renderCaps();
    else loadCaps();
  }
}

function renderCaseLine() {
  const i = state.info;
  let text = "No case open. Choose documents on the Documents tab to start one.";
  if (state.id && !i) text = `Case ${state.id}: loading...`;
  else if (i && i.status === "processing") text = `Case ${state.id}: analysing...`;
  else if (i) {
    const end = i.status === "done" ? "analysis finished" : "analysis did not finish";
    text = `Case ${state.id}: ${end}; ${docsOf().length} document(s), ${findingsOf().length} finding(s).`;
  }
  $("caseline").textContent = text;
}

function renderLegend() {
  $("legend").replaceChildren(
    ...CLASS_ORDER.map((c) => h("span", {class: "legend-item"}, h("span", {class: `swatch ${c}`}), CLASS_LABEL[c])),
    h("span", {class: "legend-item"}, h("span", {class: "swatch fld"}), "Extracted field"),
    h("span", {class: "legend-item"}, h("span", {class: "swatch w"}), "Word"),
  );
}

function renderViewerBar() {
  const ds = docsOf();
  const d = docNow();
  const p = pageNow();
  const sel = $("doc-select");
  sel.replaceChildren(...ds.map((x) => h("option", {value: x.id, selected: x.id === state.doc}, `${x.id}: ${x.filename}`)));
  sel.disabled = !ds.length;
  $("prev").disabled = !p || state.page <= 1;
  $("next").disabled = !d || state.page >= d.pages.length;
  $("pageno").textContent = d && p ? `Page ${p.n} of ${d.pages.length}` : "No page";
}

function renderPage() {
  const box = $("page");
  const d = docNow();
  const p = pageNow();
  const keep = [box.scrollLeft, box.scrollTop];
  box.replaceChildren();
  if (!d || !p) {
    const waiting = state.info && state.info.status === "processing";
    box.append(h("p", {class: "empty"}, waiting ? "Pages appear here when the analysis finishes." : "Nothing to show yet."));
    return;
  }
  if (!p.image_path) {
    box.append(h("p", {class: "empty"}, "This page was not rendered: the analysis stopped before it got here."));
    return;
  }
  const z = state.zoom || Math.min(1, Math.max(0.2, (box.clientWidth - 16) / p.width));
  $("zoom").value = Math.round(z * 100);
  const svg = svgEl("svg", {
    viewBox: `0 0 ${p.width} ${p.height}`,
    width: Math.round(p.width * z),
    height: Math.round(p.height * z),
    role: "img",
    "aria-label": `${d.filename}, page ${p.n}`,
  });
  svg.append(svgEl("image", {href: `${cases()}/pages/${enc(d.id)}/${p.n}.png`, x: 0, y: 0, width: p.width, height: p.height}));
  if (state.show.words) {
    const g = svgEl("g", {});
    for (const w of p.words) g.append(rect(w.box, "w"));
    svg.append(g);
  }
  if (state.show.fields) {
    const g = svgEl("g", {});
    for (const f of d.fields) {
      if (f.page !== p.n) continue;
      const shown = f.value != null ? f.value : f.raw;
      g.append(rect(f.box, f.conf < lowConf() ? "fld low" : "fld", `${f.name}: ${shown} (confidence ${conf(f.conf)})${f.model_read ? `; ${MODEL_READ_LABEL}` : ""}`));
    }
    svg.append(g);
  }
  let focus = null;
  const g = svgEl("g", {});
  for (const f of findingsOf()) {
    for (const e of f.evidence) {
      if (e.doc !== d.id || e.page !== p.n) continue;
      const chosen = f.id === state.finding;
      if (!state.show.findings && !chosen) continue; // the selected finding is always drawn
      const label = `${f.id}, ${CLASS_LABEL[f.fclass]}: ${f.title}`;
      const r = rect(e.box, `ev ${f.fclass}${chosen ? " sel" : ""}`, label, {tabindex: 0, role: "button", "aria-label": label});
      r.addEventListener("click", () => selectFinding(f.id));
      r.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          selectFinding(f.id);
        }
      });
      g.append(r);
      if (chosen && !focus) focus = e.box;
    }
  }
  svg.append(g);
  if (state.mark && state.mark.doc === d.id && state.mark.page === p.n) {
    svg.append(rect(state.mark.box, "hl", state.mark.label));
    focus = state.mark.box;
  }
  box.append(svg);
  if (focus) {
    box.scrollTo({
      left: Math.max(0, ((focus[0] + focus[2]) / 2) * z - box.clientWidth / 2),
      top: Math.max(0, ((focus[1] + focus[3]) / 2) * z - box.clientHeight / 2),
    });
  } else box.scrollTo(keep[0], keep[1]);
}

function progress(i) {
  const k = STAGES.findIndex((s) => s[0] === i.stage);
  const out = [
    h("p", {}, k < 0 ? "Waiting to start..." : `Step ${k + 1} of ${STAGES.length}: ${STAGES[k][1]}`),
    h("progress", {max: STAGES.length, value: k + 1}),
  ];
  if (i.intake) {
    out.push(
      h("h3", {}, "Received"),
      h("ul", {}, i.intake.accepted.map((a) => h("li", {}, `${a.id}: ${a.filename} (${a.size} bytes)`))),
    );
    if (i.intake.rejected.length) out.push(h("h3", {}, "Not accepted"), h("ul", {}, i.intake.rejected.map((r) => h("li", {}, r))));
  }
  return h("div", {}, ...out);
}

function reading(d) {
  const count = {};
  for (const p of d.pages) {
    const k = p.read_mode === "ocr" ? `OCR, ${p.quality_class}` : "text layer";
    count[k] = (count[k] || 0) + 1;
  }
  return Object.entries(count).map(([k, n]) => `${k} (${n} page${n === 1 ? "" : "s"})`).join("; ") || "no pages";
}

function docRow(d) {
  const mine = findingsOf().filter((f) => f.evidence.some((e) => e.doc === d.id)).length;
  const weak = d.pages.filter((p) => p.quality_class === "degraded" || p.quality_class === "poor").map((p) => p.n);
  const notes = [];
  if (d.doc_type === "unknown") notes.push(h("span", {class: "chip warn"}, "type not recognised"));
  if (weak.length) notes.push(h("span", {class: "chip warn"}, `unreliable reading, page ${weak.join(", ")}`));
  return h("tr", {class: d.id === state.doc ? "now" : ""},
    h("td", {}, d.id),
    h("td", {}, h("button", {type: "button", class: "link", click: () => showDoc(d.id)}, d.filename)),
    h("td", {}, d.doc_type === "unknown" ? "not recognised" : `${d.doc_type} (${conf(d.type_conf)})`),
    h("td", {}, d.kind),
    h("td", {}, reading(d)),
    h("td", {}, String(d.fields.length)),
    h("td", {}, String(mine)),
    h("td", {}, ...notes));
}

function renderDocuments() {
  const box = $("docs");
  box.replaceChildren();
  const i = state.info;
  if (!i) {
    box.append(h("p", {class: "empty"}, state.id ? "Loading..." : "No case open."));
    return;
  }
  if (i.status === "processing") box.append(progress(i));
  if (i.status === "failed") box.append(h("p", {class: "bad"}, `The analysis did not finish: ${i.error}`));
  if (!i.case) return;
  const ds = docsOf();
  const refused = findingsOf().filter((f) => f.fclass === "processing_limitation" && f.title.startsWith("File not ingested"));
  if (ds.length) {
    box.append(h("div", {class: "scroll"}, h("table", {},
      h("thead", {}, h("tr", {}, ["ID", "File", "Type", "Kind", "Reading", "Fields", "Findings", "Notes"].map((t) => h("th", {scope: "col"}, t)))),
      h("tbody", {}, ds.map(docRow)))));
  } else box.append(h("p", {class: "empty"}, "No document was accepted."));
  if (refused.length) {
    box.append(h("h3", {}, "Not analysed"), h("ul", {}, refused.map((f) => h("li", {}, f.detail || f.title))));
  }
}

function cellButton(d, f) {
  const shown = f.value != null ? f.value : f.raw;
  return h("button", {
    type: "button",
    class: "cell",
    title: `Read as "${f.raw}"; confidence ${conf(f.conf)}; page ${f.page}`,
    click: () => mark(d, f.page, f.box, `${f.name}: ${shown}`),
  }, shown === "" ? "(empty)" : shown);
}

function renderFields() {
  const box = $("fields");
  box.replaceChildren();
  const d = docNow();
  if (!d) return;
  box.append(h("h3", {}, `Extracted fields: ${d.filename}`));
  if (!d.fields.length) {
    const why = d.doc_type === "unknown"
      ? "Nothing was extracted: the type of this document is not recognised, and only recognised types have a field specification."
      : "No fields were extracted from this document.";
    box.append(h("p", {class: "empty"}, why));
    return;
  }
  box.append(h("p", {class: "hint"}, "Select a field to see where it was read on the page. A confidence below the threshold is marked low."));
  const head = d.fields.filter((f) => f.row == null);
  const cells = d.fields.filter((f) => f.row != null);
  if (head.length) {
    const low = (f) => (f.conf < lowConf() ? h("span", {class: "chip warn"}, "low") : null);
    box.append(h("div", {class: "scroll"}, h("table", {},
      h("thead", {}, h("tr", {}, ["Field", "Value", "As read", "Confidence", "Page"].map((t) => h("th", {scope: "col"}, t)))),
      h("tbody", {}, head.map((f) => h("tr", {},
        h("td", {}, h("button", {type: "button", class: "link", click: () => mark(d, f.page, f.box, f.name)}, f.name),
          f.model_read ? h("span", {class: "chip warn"}, MODEL_READ_LABEL) : null),
        h("td", {}, f.value != null ? f.value : "(not parsed)"),
        h("td", {}, f.raw),
        h("td", {class: f.conf < lowConf() ? "low" : ""}, conf(f.conf), " ", low(f)),
        h("td", {}, String(f.page))))))));
  }
  if (cells.length) {
    const cols = [...new Set(cells.map((f) => f.name))];
    const rows = [...new Set(cells.map((f) => f.row))].sort((a, b) => a - b);
    const at = new Map(cells.map((f) => [`${f.row}/${f.name}`, f]));
    const cell = (f) => (f
      ? h("td", {class: f.conf < lowConf() ? "low" : ""}, cellButton(d, f))
      : h("td", {}, "\u2014"));
    box.append(h("h4", {}, `Table cells (${rows.length} rows)`), h("div", {class: "scroll"}, h("table", {},
      h("thead", {}, h("tr", {}, h("th", {scope: "col"}, "Row"), cols.map((c) => h("th", {scope: "col"}, c)))),
      h("tbody", {}, rows.map((r) => h("tr", {}, h("th", {scope: "row"}, String(r)), cols.map((c) => cell(at.get(`${r}/${c}`)))))))));
  }
}

function findingButton(f) {
  return h("button", {
    type: "button",
    class: `finding ${f.fclass}`,
    "aria-pressed": String(f.id === state.finding),
    click: () => selectFinding(f.id),
  },
  h("strong", {}, f.id), ` ${f.title}`,
  h("span", {class: "meta"}, `${STATUS_LABEL[f.status]} \u00b7 confidence ${conf(f.conf)} \u00b7 priority ${f.review_priority}`));
}

function renderFindings() {
  const box = $("findings");
  box.replaceChildren();
  if (!data()) {
    box.append(h("p", {class: "empty"}, state.info ? "Findings appear when the analysis finishes." : "No case open."));
    $("detail").replaceChildren();
    return;
  }
  const all = findingsOf();
  if (!all.length) {
    box.append(h("p", {class: "empty"}, "No findings. That does not mean the documents are in order: only the checks that exist were run (see Capabilities)."));
  }
  for (const c of CLASS_ORDER) {
    const group = all.filter((f) => f.fclass === c).sort((a, b) => b.review_priority - a.review_priority);
    box.append(h("section", {},
      h("h3", {}, `${CLASS_LABEL[c]} (${group.length})`),
      group.length
        ? h("ul", {class: "plain"}, group.map((f) => h("li", {}, findingButton(f))))
        : h("p", {class: "empty"}, "None reported.")));
  }
  renderDetail();
}

function evidenceItem(e) {
  const d = docsOf().find((x) => x.id === e.doc);
  const pg = d && d.pages[e.page - 1];
  const dpi = (pg && pg.dpi) || 200;
  const where = e.page === 0
    ? "the document as a whole"
    : `page ${e.page}, box ${e.box.map(num).join(", ")} px at ${dpi} dpi (${e.box.map((v) => num((v * 72) / dpi)).join(", ")} pt)`;
  const crop = e.crop_path ? e.crop_path.split(/[\\/]/).pop() : null;
  return h("li", {},
    h("p", {}, h("strong", {}, d ? d.filename : e.doc), ` (${e.doc}), ${where}`),
    e.note ? h("p", {}, e.note) : null,
    e.value != null ? h("p", {}, "Value: ", h("code", {}, e.value)) : null,
    d && e.page > 0 ? h("button", {type: "button", click: () => mark(d, e.page, e.box, e.note || "Evidence")}, "Show on page") : null,
    crop ? h("img", {class: "crop", src: `${cases()}/crops/${enc(crop)}`, alt: `Crop of the evidence in ${d ? d.filename : e.doc}, page ${e.page}`}) : null);
}

function renderDetail() {
  const box = $("detail");
  box.replaceChildren();
  const f = findingsOf().find((x) => x.id === state.finding);
  if (!f) {
    box.append(h("p", {class: "empty"}, "Select a finding to see its evidence, its explanation and the reviewer actions."));
    return;
  }
  const byId = new Map(findingsOf().map((x) => [x.id, x]));
  const note = h("textarea", {id: "note", rows: 3, maxlength: 2000});
  note.value = f.note;
  const link = (id) => (byId.has(id)
    ? h("button", {type: "button", class: "chip", click: () => selectFinding(id)}, `${id}: ${byId.get(id).title}`)
    : h("span", {class: "chip"}, id));
  box.append(h("div", {}, // h() drops the null children; a bare append() would print them as the word "null"
    h("h3", {}, `${f.id}: ${f.title}`),
    h("p", {},
      h("span", {class: `tag ${f.fclass}`}, CLASS_LABEL[f.fclass]),
      h("span", {class: "tag"}, `${f.family} / ${f.detector}`),
      h("span", {class: "tag"}, `confidence ${conf(f.conf)}`),
      h("span", {class: "tag"}, `review priority ${f.review_priority}`),
      f.conf < lowConf() ? h("span", {class: "chip warn"}, "weak reading") : null),
    f.detail ? h("p", {}, f.detail) : null,
    h("h4", {}, "Explanation"),
    h("p", {class: "label"}, SOURCE_LABEL[f.explanation_source] || f.explanation_source),
    h("p", {}, f.explanation || "No explanation was recorded."),
    f.next_steps.length ? h("h4", {}, "Further verification") : null,
    f.next_steps.length ? h("ul", {}, f.next_steps.map((t) => h("li", {}, t))) : null,
    h("h4", {}, `Evidence (${f.evidence.length})`),
    f.evidence.length
      ? h("ol", {class: "evidence"}, f.evidence.map(evidenceItem))
      : h("p", {class: "empty"}, "No evidence is recorded for this finding."),
    f.related.length ? h("h4", {}, "Related findings") : null,
    f.related.length ? h("p", {}, f.related.map(link)) : null,
    f.cluster
      ? h("p", {}, "Cluster: ", h("button", {type: "button", class: "link", click: () => { state.tab = "clusters"; render(); }}, f.cluster))
      : null,
    h("h4", {}, "Reviewer"),
    h("p", {}, `Status: ${STATUS_LABEL[f.status]}. Only a person sets "Confirmed by reviewer" or "Dismissed", and every action is written to the audit trail.`),
    h("div", {class: "actions"}, REVIEW.map(([status, label]) =>
      h("button", {type: "button", "aria-pressed": String(f.status === status), click: () => review(f, status)}, label))),
    h("label", {for: "note"}, "Reviewer note (saved with the next status change, or on its own)"),
    note,
    h("button", {type: "button", click: () => review(f, null)}, "Save note"),
    h("p", {class: "hint"}, "The same trace on the command line: ", h("code", {}, `docforensics trace ${state.id} ${f.id}`),
      " (add --data FOLDER if the app was started with one).")));
}

function renderClusters() {
  const box = $("clusters");
  box.replaceChildren();
  if (!data()) {
    box.append(h("p", {class: "empty"}, state.info ? "Clusters appear when the analysis finishes." : "No case open."));
    return;
  }
  const groups = new Map();
  for (const f of findingsOf()) if (f.cluster) groups.set(f.cluster, [...(groups.get(f.cluster) || []), f]);
  if (!groups.size) {
    box.append(h("p", {class: "empty"}, "No findings in this case are grouped into clusters. Grouping findings by shared evidence is listed on the Capabilities tab, with its status."));
  }
  const byId = new Map(findingsOf().map((x) => [x.id, x]));
  for (const [id, members] of groups) {
    const head = byId.get(id);
    box.append(h("section", {},
      h("h3", {}, head ? `${id}: ${head.title}` : id),
      head && head.detail ? h("p", {}, head.detail) : null,
      head && head.explanation ? h("p", {}, head.explanation) : null,
      h("ul", {class: "plain"}, members.map((f) => h("li", {}, findingButton(f))))));
  }
  box.append(aiReading(byId));
}

// What a local model made of the whole case: inference, shown apart from the clusters the checks formed. It changes no finding.
function aiReading(byId) {
  const r = data().reasoning;
  if (!r) {
    return h("section", {}, h("h3", {}, READING_LABEL),
      h("p", {class: "empty"}, "No language-model reading is part of this case: none was asked for, or nothing it said passed the checks. The audit trail (event llm_reasoning) says which."));
  }
  const chip = (id) => (byId.has(id)
    ? h("button", {type: "button", class: "chip", click: () => selectFinding(id)}, `${id}: ${byId.get(id).title}`)
    : h("span", {class: "chip"}, id));
  return h("section", {}, h("h3", {}, READING_LABEL),
    h("p", {class: "label"}, `Written by the local model ${r.model} from the findings. It does not change, add or remove a finding, and it is not evidence.`),
    h("p", {}, r.summary || "The model gave no summary that passed the checks."),
    h("h4", {}, `Relations the model suggests (${r.relations.length})`),
    r.relations.length
      ? h("ul", {class: "plain"}, r.relations.map((x) => h("li", {}, chip(x.a), chip(x.b), h("span", {class: "tag"}, x.kind), ` ${x.reason}`)))
      : h("p", {class: "empty"}, "None."),
    r.rejected.length
      ? h("details", {}, h("summary", {}, `Dropped by the checks (${r.rejected.length})`),
        h("ul", {}, r.rejected.map(([part, why]) => h("li", {}, `${part}: ${why}`))))
      : null);
}

function renderDossier() {
  const box = $("dossier");
  box.replaceChildren();
  if (!data()) {
    box.append(h("p", {class: "empty"}, "Open a finished case to download its dossier."));
    return;
  }
  const stale = () => { state.audit = null; };
  box.append(
    h("p", {}, "The dossier is built when you click, so it holds the reviewer actions made so far. Each build is recorded in the audit trail."),
    h("ul", {},
      h("li", {}, h("a", {href: `${cases()}/dossier`, download: `dossier-${state.id}.html`, click: stale}, "Dossier as a self-contained HTML file")),
      h("li", {}, h("a", {href: `${cases()}/dossier.json`, download: `dossier-${state.id}.json`, click: stale}, "Dossier as JSON, with its own hash"))));
}

async function loadAudit() {
  if (!data()) {
    renderAudit();
    return;
  }
  const id = state.id;
  try {
    const a = await api(`${cases()}/audit`);
    if (state.id === id) {
      state.audit = a;
      renderAudit();
    }
  } catch (e) {
    say(`The audit trail could not be loaded: ${e.message}`, true);
  }
}

function signingLine(s) {
  if (s.status === "broken") return h("p", {class: "bad"}, s.problem);
  if (s.status === "unsigned") return h("p", {class: "hint"}, "No signed checkpoint: a cut at the end of the trail, or a rewrite with a new chain, would not be seen.");
  const late = s.uncovered ? ` ${s.uncovered} later event(s) are not covered.` : "";
  return h("div", {},
    h("p", {class: "ok"}, `Signed: ${s.checkpoints} checkpoint(s) by key ${s.key_id.slice(0, 16)}..., the last covers events 1-${s.last.events}.${late}`),
    h("p", {class: "hint"}, "The key is a file on this computer. A signature shows the trail unchanged since it was signed, as far as the key stayed private and the checkpoint is still in the file; it does not show who signed or when."));
}

function renderAudit() {
  const box = $("audit");
  box.replaceChildren();
  const a = state.audit;
  if (!a) {
    box.append(h("p", {class: "empty"}, data() ? "Loading the audit trail..." : "Open a finished case to see its audit trail."));
    return;
  }
  box.append(
    h("p", {class: a.chain_ok ? "ok" : "bad"},
      a.chain_ok ? `Hash chain intact: ${a.anchor.events} events, last hash ${a.anchor.head.slice(0, 16)}...` : a.problem),
    signingLine(a.signing),
    h("div", {class: "scroll"}, h("table", {},
      h("thead", {}, h("tr", {}, ["#", "Time (UTC)", "Actor", "Event", "Data"].map((t) => h("th", {scope: "col"}, t)))),
      h("tbody", {}, a.events.map((e) => h("tr", {},
        h("td", {}, String(e.seq)),
        h("td", {}, e.ts),
        h("td", {}, e.actor),
        h("td", {}, e.event),
        h("td", {class: "data"}, shorten(JSON.stringify(e.data), 240))))))));
}

async function loadCaps() {
  try {
    state.caps = await api("/api/capabilities");
    renderCaps();
  } catch (e) {
    say(`The capability list could not be loaded: ${e.message}`, true);
  }
}

function renderCaps() {
  const box = $("caps");
  box.replaceChildren();
  const c = state.caps;
  if (!c) return;
  const row = (x) => h("tr", {},
    h("td", {}, x.name),
    h("td", {}, h("span", {class: `chip status-${x.status.toLowerCase()}`}, x.status)),
    h("td", {}, x.note || ""),
    h("td", {}, x.evidence.length
      ? h("details", {}, h("summary", {}, `${x.evidence.length} test(s)`), h("ul", {}, x.evidence.map((t) => h("li", {}, h("code", {}, t)))))
      : "none yet"));
  box.append(
    h("p", {}, "What this build does, partly does, plans and declines. A recorded demo does not establish a capability; the tests listed here do."),
    h("div", {class: "scroll"}, h("table", {},
      h("thead", {}, h("tr", {}, ["Capability", "Status", "Note", "Tests"].map((t) => h("th", {scope: "col"}, t)))),
      h("tbody", {}, c.capabilities.map(row)))),
    h("h3", {}, "Limitations"),
    h("ul", {}, c.limitations.map((t) => h("li", {}, t))),
    h("h3", {}, "Assumptions"),
    h("ul", {}, c.assumptions.map((t) => h("li", {}, t))));
}

// ---- relationships -----------------------------------------------------------------------------------------------

/* Three columns of boxes: the documents, the entities (names, addresses, employers, account numbers) they write, and the findings
   that touch an entity. A line joins a document to an entity it writes, and an entity to a finding that touches it. The server works
   the view out (/relations); nothing here decides what counts as the same thing, or what a difference means. */
const REL = {colw: 150, xs: [5, 230, 455], width: 610, top: 24, node: 40, pitch: 52};

async function loadRelations() {
  if (!data()) {
    renderRelations();
    return;
  }
  const id = state.id;
  try {
    const r = await api(`${cases()}/relations`);
    if (state.id === id) {
      state.rel = r;
      renderRelations();
    }
  } catch (e) {
    say(`The relationship view could not be loaded: ${e.message}`, true);
  }
}

// Pick a box (or none), draw again, and give the focus back to a box, because drawing replaces them all.
function relSelect(id, focus) {
  state.relSel = id;
  renderRelations();
  const want = focus === undefined ? id : focus;
  const n = [...$("relations").querySelectorAll("[data-node]")].find((x) => x.dataset.node === want);
  if (n) n.focus();
}

function svgText(x, y, text, cls) {
  const t = svgEl("text", {x, y, class: cls});
  t.textContent = text;
  return t;
}

function relNode(kind, item, at, lines, name, cls) {
  const on = state.relSel === item.id;
  const g = svgEl("g", {
    class: `node n-${kind}${cls ? ` ${cls}` : ""}`,
    "data-node": item.id,
    tabindex: 0,
    role: "button",
    "aria-pressed": String(on),
    "aria-label": name,
  }, name);
  g.append(
    svgEl("rect", {x: at.x, y: at.y, width: REL.colw, height: REL.node, rx: 5}),
    svgText(at.x + 8, at.y + 16, shorten(lines[0], 22), "l1"),
    svgText(at.x + 8, at.y + 32, shorten(lines[1], 27), "l2"),
  );
  const toggle = () => relSelect(on ? null : item.id, item.id);
  g.addEventListener("click", toggle);
  g.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" || ev.key === " ") {
      ev.preventDefault();
      toggle();
    }
  });
  return g;
}

function relGraph(r) {
  const sel = state.relSel;
  const rows = Math.max(r.documents.length, r.entities.length, r.findings.length);
  const high = rows * REL.pitch;
  // each column is spread over the same height, so the lines between neighbouring columns stay shallow
  const place = (items, c) => items.map((x, i) => [x.id, {x: REL.xs[c], y: REL.top + (i + 0.5) * (high / items.length) - REL.node / 2}]);
  const pos = new Map([...place(r.documents, 0), ...place(r.entities, 1), ...place(r.findings, 2)]);
  const edges = [
    ...r.documents.flatMap((d) => d.entities.map((e) => [d.id, e])).filter(([a, b]) => pos.has(a) && pos.has(b)),
    ...r.findings.flatMap((f) => f.entities.map((e) => [e, f.id])).filter(([a, b]) => pos.has(a) && pos.has(b)),
  ];
  const near = new Set(edges.flatMap(([a, b]) => (a === sel ? [b] : b === sel ? [a] : [])));
  const svg = svgEl("svg", {
    viewBox: `0 0 ${REL.width} ${REL.top + high}`,
    class: `relmap${sel ? " picked" : ""}`,
    role: "group",
    "aria-label": "Relationship graph: documents, the entities they write, and the findings that touch an entity. Each box can be selected.",
  });
  ["Documents", "Entities", "Findings"].forEach((t, i) => svg.append(svgText(REL.xs[i], 14, t, "colhead")));
  for (const [a, b] of edges) {
    const p = pos.get(a);
    const q = pos.get(b);
    const x1 = p.x + REL.colw;
    const y1 = p.y + REL.node / 2;
    const x2 = q.x;
    const y2 = q.y + REL.node / 2;
    const mid = (x1 + x2) / 2;
    svg.append(svgEl("path", {d: `M${x1} ${y1} C${mid} ${y1} ${mid} ${y2} ${x2} ${y2}`, class: `edge${a === sel || b === sel ? " on" : ""}`}));
  }
  const look = (id) => `${id === sel ? " sel" : ""}${near.has(id) ? " near" : ""}`;
  for (const d of r.documents) {
    const type = d.type === "unknown" ? "not recognised" : d.type;
    svg.append(relNode("document", d, pos.get(d.id), [`${d.id} ${d.file}`, type], `Document ${d.id}, ${d.file}`, look(d.id).trim()));
  }
  for (const e of r.entities) {
    const docs = new Set(e.mentions.map((m) => m.doc)).size;
    const cls = `${e.findings.length ? "touched" : ""}${look(e.id)}`.trim();
    svg.append(relNode("entity", e, pos.get(e.id), [`${e.id} ${e.label}`, `${e.role}, in ${docs} document${docs === 1 ? "" : "s"}`],
      `Entity ${e.id}, ${e.role}, ${e.label}`, cls));
  }
  for (const f of r.findings) {
    svg.append(relNode("finding", f, pos.get(f.id), [`${f.id} ${CLASS_LABEL[f.class]}`, f.title],
      `Finding ${f.id}, ${CLASS_LABEL[f.class]}: ${f.title}`, `${f.class}${look(f.id)}`));
  }
  return h("div", {class: "scroll"}, svg);
}

// What the picked box connects to, in words: the same information as the lines, for a reader who cannot follow them.
function relPicked(r) {
  const id = state.relSel;
  const e = r.entities.find((x) => x.id === id);
  const d = r.documents.find((x) => x.id === id);
  const f = r.findings.find((x) => x.id === id);
  const entity = (eid) => {
    const x = r.entities.find((y) => y.id === eid);
    return h("button", {type: "button", class: "chip", click: () => relSelect(eid)}, `${eid}: ${x.role}, ${x.label}`);
  };
  const finding = (fid) => {
    const x = findingsOf().find((y) => y.id === fid);
    return x ? h("li", {}, findingButton(x)) : null;
  };
  if (e) {
    return h("div", {},
      h("h3", {}, `${e.id}: ${e.role}, ${e.label}`),
      h("p", {class: "hint"}, e.writings.length > 1
        ? `Written ${e.writings.length} ways: ${e.writings.join(" | ")}. The cross-document checks grade these as the same, or the same apart from form.`
        : e.mentions.length > 1 ? "Written the same way in every place." : "Read in one place only."),
      h("div", {class: "scroll"}, h("table", {},
        h("thead", {}, h("tr", {}, ["File", "Page", "Field", "As written", "Confidence", ""].map((t) => h("th", {scope: "col"}, t)))),
        h("tbody", {}, e.mentions.map((m) => {
          const doc = docsOf().find((x) => x.id === m.doc);
          return h("tr", {},
            h("td", {}, m.file),
            h("td", {}, String(m.page)),
            h("td", {}, m.name),
            h("td", {}, m.value),
            h("td", {class: m.conf < lowConf() ? "low" : ""}, conf(m.conf)),
            h("td", {}, doc ? h("button", {type: "button", click: () => mark(doc, m.page, m.box, `${m.name}: ${m.value}`)}, "Show on page") : null));
        })))),
      h("h4", {}, `Findings that touch it (${e.findings.length})`),
      e.findings.length ? h("ul", {class: "plain"}, e.findings.map(finding)) : h("p", {class: "empty"}, "None."));
  }
  if (d) {
    return h("div", {},
      h("h3", {}, `${d.id}: ${d.file}`),
      h("p", {}, `Type: ${d.type === "unknown" ? "not recognised" : d.type}.`),
      h("h4", {}, `Entities it writes (${d.entities.length})`),
      d.entities.length ? h("p", {}, d.entities.map(entity)) : h("p", {class: "empty"}, "None were read from this document."),
      h("button", {type: "button", click: () => showDoc(d.id)}, "Show in the viewer"));
  }
  if (f) {
    return h("div", {},
      h("h3", {}, `${f.id}: ${f.title}`),
      h("p", {}, h("span", {class: `tag ${f.class}`}, CLASS_LABEL[f.class]), h("span", {class: "tag"}, `detector ${f.detector}`)),
      f.cluster ? h("p", {class: "hint"}, `Grouped under ${f.cluster}.`) : null,
      h("h4", {}, `Entities it touches (${f.entities.length})`),
      h("p", {}, f.entities.map(entity)),
      h("button", {type: "button", click: () => selectFinding(f.id)}, "Open the finding"));
  }
  return h("p", {class: "empty"}, "Select a document, an entity or a finding to see what it connects to.");
}

function renderRelations() {
  const box = $("relations");
  box.replaceChildren();
  const r = state.rel;
  if (!r) {
    const wait = data() ? "Loading the relationship view..." : state.info ? "The relationship view appears when the analysis finishes." : "No case open.";
    box.append(h("p", {class: "empty"}, wait));
    return;
  }
  box.append(h("p", {class: "hint"},
    "Which names, addresses, employers and account numbers the documents write, and which findings touch them. Two writings are one entity when "
    + "the cross-document checks grade them the same, or the same apart from form. A writing those checks grade as a mismatch is an entity of "
    + "its own, and the finding that reports the mismatch touches both. This is a map of what was read, not a conclusion."));
  if (!r.entities.length) {
    box.append(h("p", {class: "empty"}, "No name, address, employer or account number was read from these documents, so there is nothing to relate."));
    return;
  }
  box.append(relGraph(r));
  if (!r.findings.length) box.append(h("p", {class: "hint"}, "No finding in this case touches one of these entities. Findings about amounts, dates or the files themselves are on the Findings tab."));
  box.append(h("div", {id: "relpick"}, relPicked(r)));
}

// ---- start -------------------------------------------------------------------------------------------------------

function boot() {
  renderLegend();
  for (const b of document.querySelectorAll("[data-tab]")) b.addEventListener("click", () => showTab(b.dataset.tab));
  $("upload").addEventListener("submit", onUpload);
  $("doc-select").addEventListener("change", (ev) => showDoc(ev.target.value));
  $("prev").addEventListener("click", () => turn(-1));
  $("next").addEventListener("click", () => turn(1));
  $("zoom").addEventListener("input", (ev) => {
    state.zoom = Number(ev.target.value) / 100;
    renderPage();
  });
  $("fit").addEventListener("click", () => {
    state.zoom = null;
    renderPage();
  });
  for (const k of Object.keys(state.show)) {
    $(`layer-${k}`).addEventListener("change", (ev) => {
      state.show[k] = ev.target.checked;
      renderPage();
    });
  }
  window.addEventListener("hashchange", fromHash);
  render();
  fromHash();
}

boot();
