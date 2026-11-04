"""Linking (design 7.6). Findings that cite the same extracted field, lie on the same place of a page, or concern the same name,
address, employer or account number are grouped. No probabilities are computed: the review priority of a group is the number of
independent kinds of check that fired in it (visual, arithmetic, cross-document, metadata). The same kind twice on one box is one
kind, and a context rule is none, because it rests on a synthetic reference. A group with two or more kinds is a candidate for
potential manipulation and gets a headline finding that lists its members and cites each of their places once.

Limitations, evidence that points at a whole document and boxes with no area link nothing. Everything is worked out before the
case is changed, so a failure cannot leave a member pointing at a headline that was never made."""
import re
from collections import Counter, defaultdict
from itertools import combinations
from typing import TYPE_CHECKING

from .checks.within import SHOWN
from .config import Thresholds
from .findings import add_findings, quote
from .model import Box, Case, Evidence, Field, Finding

if TYPE_CHECKING:  # the stage runner imports this module lazily; the type is only needed for annotations
    from .pipeline import Ctx

ENTITY_ROLES = {"name", "address", "employer", "account"}  # Field.role values that stand for one thing in different documents
KINDS = {"visual": "visual", "arithmetic": "arithmetic", "cross_document": "cross-document", "metadata": "metadata"}  # family: as a headline says it


def _area(b: Box) -> float:
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def overlap(a: Box, b: Box) -> float:
    """The share of the smaller box that lies inside the other: a shape over a field, or a mark inside one, is 1. 0 when the boxes do
    not meet or one has no area."""
    w, h = min(a[2], b[2]) - max(a[0], b[0]), min(a[3], b[3]) - max(a[1], b[1])
    smaller = min(_area(a), _area(b))
    return w * h / smaller if w > 0 and h > 0 and smaller > 0 else 0.0


def _meets(a: Box, b: Box, limit: float) -> bool:
    share = overlap(a, b)
    return share > 0 and share >= limit


def _counts(f: Finding) -> bool:
    return f.family in KINDS and not f.detector.startswith("context_")


def _key(value: str) -> tuple[str, ...]:
    """A name, address, employer or account number with case, order, spacing and punctuation ignored."""
    return tuple(sorted(re.findall(r"\w+", value.casefold())))


class _Fields:
    """The case's extracted fields, found by id or by the place a piece of evidence points at."""

    def __init__(self, case: Case, th: Thresholds):
        self.limit = th.link_overlap
        self.by_id = {f.id: f for d in case.documents for f in d.fields}
        self.by_page: dict[tuple[str, int], list[Field]] = defaultdict(list)
        for f in self.by_id.values():
            self.by_page[(f.doc, f.page)].append(f)

    def at(self, e: Evidence) -> list[Field]:
        if e.field_id in self.by_id:
            return [self.by_id[e.field_id]]
        return [f for f in self.by_page.get((e.doc, e.page), ()) if _meets(e.box, f.box, self.limit)]  # page 0 holds no field


def _group(nodes: list[Finding], case: Case, th: Thresholds) -> list[list[Finding]]:
    """The findings joined by a shared field, by boxes that overlap on one page, or by an entity value; each group in the order
    the findings were raised, the groups in the order of their first finding."""
    fields = _Fields(case, th)
    parent = list(range(len(nodes)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def join(i: int, j: int) -> None:
        parent[find(i)] = find(j)

    first: dict[tuple, int] = {}  # a field or an entity value, to the first finding that reached it
    placed: dict[tuple[str, int], list[tuple[Box, int]]] = defaultdict(list)
    for i, f in enumerate(nodes):
        for e in f.evidence:
            placed[(e.doc, e.page)].append((e.box, i))  # a whole document (page 0, no area) meets nothing, whatever it is compared with
            for fl in fields.at(e):
                join(i, first.setdefault(("field", fl.id), i))
                if fl.role in ENTITY_ROLES and fl.value and (key := _key(fl.value)):
                    join(i, first.setdefault(("entity", fl.role, key), i))
    for boxes in placed.values():
        for (a, i), (b, j) in combinations(boxes, 2):
            if i != j and _meets(a, b, th.link_overlap):
                join(i, j)
    groups: dict[int, list[Finding]] = {}
    for i, f in enumerate(nodes):
        groups.setdefault(find(i), []).append(f)
    return list(groups.values())


def _ordered(members: list[Finding]) -> list[Finding]:
    """Conflicts first, then observations, each in the order the findings were raised."""
    return sorted(members, key=lambda f: (f.fclass != "inconsistency", f.id))


def _join(names: list[str]) -> str:
    return " and ".join([", ".join(names[:-1]), names[-1]] if len(names) > 1 else names)


def _place(members: list[Finding], case: Case, th: Thresholds) -> str:
    """Where a group meets: the field that most of its findings cite, else the first page they cite, else the documents."""
    docs = {d.id: quote(d.filename) for d in case.documents}
    fields, cited = _Fields(case, th), Counter()
    for m in members:
        cited.update(list(dict.fromkeys(fl.id for e in m.evidence for fl in fields.at(e))))  # one count per finding
    if cited:
        top = fields.by_id[max(cited, key=cited.get)]  # the first of those cited most often
        label = top.name.rpartition(".")[2].replace("_", " ").capitalize()  # "txn.credit" is a credit; "net_pay" is a net pay
        return f"{label}{'' if top.row is None else f' in row {top.row}'} on {docs.get(top.doc, top.doc)}"
    for m in members:
        for e in m.evidence:
            if e.page > 0 and _area(e.box) > 0:
                return f"Page {e.page} of {docs.get(e.doc, e.doc)}"
    return _join(list(dict.fromkeys(docs.get(e.doc, e.doc) for m in members for e in m.evidence))) or "The case"


def cluster_headline(members: list[Finding], case: Case, th: Thresholds | None = None) -> str:
    """The group in one sentence: where it meets, then each finding with the kind of check that raised it, conflicts first."""
    ordered = _ordered(members)
    listed = "; ".join(f"{m.title} ({KINDS.get(m.family, m.family)} {m.fclass})" for m in ordered[:SHOWN])
    more = f"; and {len(ordered) - SHOWN} more" if len(ordered) > SHOWN else ""
    return f"{_place(ordered, case, th or Thresholds())}: {listed}{more}."


def _places(members: list[Finding]) -> list[Evidence]:
    """Each place the members cite, once. Copies: the crop stage writes a crop path into every evidence it is given."""
    seen: dict[tuple, Evidence] = {}
    for m in _ordered(members):
        for e in m.evidence:
            seen.setdefault((e.doc, e.page, e.box), e.model_copy())
    return list(seen.values())


def link_findings(case: Case, ctx: "Ctx") -> None:
    """Set each finding's related ids and review priority, and add a headline finding for each group in which two or more kinds
    of check fired, pointing its members at it."""
    th = ctx.th
    nodes = [f for f in case.findings if f.fclass in ("observation", "inconsistency")]
    ranked = [(g, len({m.family for m in g if _counts(m)})) for g in _group(nodes, case, th)]
    clusters = [(g, k) for g, k in ranked if k >= 2]
    drafts = [Finding(fclass="potential_manipulation", detector="link", family="cluster", conf=min(m.conf for m in g), review_priority=k,
                      title=f"{_place(_ordered(g), case, th)}: {len(g)} findings from {k} kinds of check",
                      detail=cluster_headline(g, case, th), evidence=_places(g), related=[m.id for m in g]) for g, k in clusters]
    for g, k in ranked:  # nothing above has changed the case
        for m in g:
            m.review_priority = k
            m.related = [o.id for o in g if o is not m]
    for head, (g, _) in zip(add_findings(case, ctx, drafts), clusters):
        for m in g:
            m.cluster = head.id
    ctx.audit.append("system", "findings_linked", {"findings": len(nodes), "linked": sum(len(g) for g, _ in ranked if len(g) > 1),
                                                   "clusters": len(clusters)})
