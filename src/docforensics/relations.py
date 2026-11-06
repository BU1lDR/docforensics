"""Relationship view: which names, addresses, employers and account numbers in the documents are one thing, and which findings touch
them. A writing joins the first entity, in the order the documents mention them, in which every writing is graded by the cross-document
checks as the same as it (alike, or alike apart from form); otherwise it is an entity of its own. So two writings those checks grade as a
mismatch are never in one entity, and the finding that reports the mismatch touches both. An initial or a masked number matches several
writings that do not match each other and sits with the first. A finding touches an entity when it cites a field that holds it, or a
place that lies on one. The view is worked out from the case on request: the case is not changed, no model takes part, and nothing in
it says what a difference means."""
import re

from .checks.cross import FORM, ROLES, SAME
from .config import Thresholds
from .link import ENTITY_ROLES, _Fields
from .model import Case

LEFT_OUT = ("potential_manipulation", "processing_limitation")  # a headline repeats the places of its members; a limitation cites a whole document


def build_relations(case: Case, th: Thresholds | None = None) -> dict:
    """{"entities": [...], "findings": [...], "documents": [...]}. Entities are numbered E1.. in the order the documents first mention
    them; findings are listed as they were raised, those that touch an entity only."""
    th = th or Thresholds()
    entities: list[dict] = []
    held: dict[str, dict] = {}  # field id: the entity that holds it
    docs = []
    for d in case.documents:
        docs.append({"id": d.id, "file": d.filename, "type": d.doc_type, "entities": []})
        for f in d.fields:
            if f.role not in ENTITY_ROLES or not f.value or not re.search(r"\w", f.value):
                continue
            same = lambda m: ROLES[f.role][2](m["value"], f.value, th)[0] in (SAME, FORM)  # noqa: E731
            # every writing in the entity, not any: an initial or a masked number matches several that do not match each other
            e = next((e for e in entities if e["role"] == f.role and all(same(m) for m in e["mentions"])), None)
            if e is None:
                e = {"id": f"E{len(entities) + 1}", "role": f.role, "label": f.value, "writings": [], "mentions": [], "findings": []}
                entities.append(e)
            if f.value not in e["writings"]:
                e["writings"].append(f.value)
            e["mentions"].append({"doc": d.id, "file": d.filename, "field": f.id, "name": f.name, "page": f.page, "box": list(f.box),
                                  "conf": f.conf, "value": f.value})
            held[f.id] = e
            if e["id"] not in docs[-1]["entities"]:
                docs[-1]["entities"].append(e["id"])
    fields, nodes = _Fields(case, th), []
    for f in case.findings:
        if f.fclass in LEFT_OUT:
            continue
        touched = list(dict.fromkeys(held[x.id]["id"] for ev in f.evidence for x in fields.at(ev) if x.id in held))
        if touched:
            nodes.append({"id": f.id, "class": f.fclass, "title": f.title, "detector": f.detector, "cluster": f.cluster, "entities": touched})
            for e in entities:
                if e["id"] in touched:
                    e["findings"].append(f.id)
    return {"entities": entities, "findings": nodes, "documents": docs}
