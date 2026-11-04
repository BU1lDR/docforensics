"""Explain stage (design 7.6, 7.7): every finding gets measured wording and next steps from the templates, never a verdict. When a
local language model is given (ctx.llm), it reads the whole case once (relations and a summary, kept on the case as inference in
case.reasoning) and then words the headline of each cluster instead of the template, if the guard accepts what it says. It is asked
only while a call, at its longest, can still end inside the time the stage has."""
import time

from ..model import Case
from ..pipeline import Ctx
from .llm import explain_cluster
from .reason import reason_case
from .templates import explain_finding

SKIPPED = "skipped: time budget"


def run_explain(case: Case, ctx: Ctx) -> None:
    for f in case.findings:
        f.explanation, f.next_steps = explain_finding(f, case)
        f.explanation_source = "template"
    ctx.audit.append("system", "findings_explained", {"findings": len(case.findings), "source": "template"})
    case.reasoning = None  # a reading is this run's or there is none: not what an earlier run with a model left on the case
    llm = ctx.llm
    if llm is None:  # the template wording above stays unless the guard accepts the model's
        return
    # run_case gives this stage stage_timeout_s for each document and one more. A call that is not finished by then would be left running.
    end = time.monotonic() + ctx.th.stage_timeout_s * (len(case.documents) + 1)

    def room() -> bool:
        return time.monotonic() + llm.timeout <= end

    if room():
        case.reasoning = reason_case(case, ctx, llm)
    else:
        ctx.audit.append("system", "llm_reasoning", {"model": llm.model, "accepted": False, "reason": SKIPPED})
    for f in [f for f in case.findings if f.detector == "link"]:
        if not room():
            ctx.audit.append("system", "llm_wording", {"finding": f.id, "model": llm.model, "accepted": False, "reason": SKIPPED})
            continue
        text, source = explain_cluster(f, case, ctx, llm)
        if source == "llm":
            f.explanation, f.explanation_source = text, source
