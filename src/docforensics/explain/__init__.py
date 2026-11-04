"""Explain stage (design 7.6, 7.7): every finding gets measured wording and next steps from the templates, never a verdict. When a
local language model is given (ctx.llm), the headline of each cluster is worded by it instead, if the guard accepts what it says."""
from ..model import Case
from ..pipeline import Ctx
from .llm import explain_cluster
from .templates import explain_finding


def run_explain(case: Case, ctx: Ctx) -> None:
    for f in case.findings:
        f.explanation, f.next_steps = explain_finding(f, case)
        f.explanation_source = "template"
    ctx.audit.append("system", "findings_explained", {"findings": len(case.findings), "source": "template"})
    if ctx.llm is not None:  # the template wording above stays unless the guard accepts the model's
        for f in [f for f in case.findings if f.detector == "link"]:
            text, source = explain_cluster(f, case, ctx, ctx.llm)
            if source == "llm":
                f.explanation, f.explanation_source = text, source
