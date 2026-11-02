"""Explain stage (design 7.6): every finding gets measured wording and next steps from the templates, never a verdict."""
from ..model import Case
from ..pipeline import Ctx
from .templates import explain_finding


def run_explain(case: Case, ctx: Ctx) -> None:
    for f in case.findings:
        f.explanation, f.next_steps = explain_finding(f, case)
        f.explanation_source = "template"
    ctx.audit.append("system", "findings_explained", {"findings": len(case.findings), "source": "template"})
