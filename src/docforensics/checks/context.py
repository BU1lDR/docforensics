"""Context rules (design 7.5): what the figures of one application say when set against a reference limit. A rule that applies
is an observation for the reviewer and never a conflict, because its limit is a synthetic, illustrative value chosen for this
prototype, not a lending standard, and the finding says so. A rule that cannot be applied because an input is unreadable or
doubtful is reported as a limitation of its own."""
from decimal import Decimal

from ..config import Thresholds
from ..findings import add_findings, field_evidence
from ..model import Case, Finding
from ..pipeline import Ctx
from . import collect, observation
from .cross import DATED, _of, _read, _who, fold, gap
from .within import _amount, _day, _inr

EMI, AGE = "context_emi", "context_age"
EMI_INPUTS = (("declared_monthly_income", "declared monthly income"), ("existing_emi", "existing instalments"),
              ("loan_amount", "loan amount"), ("tenure_months", "tenure in months"))


def context_emi(case: Case, th: Thresholds) -> list[Finding]:
    """Existing instalments plus the new loan over its tenure, as a share of declared income. Interest is ignored."""
    out: list[Finding] = []
    for app in _of(case, "loan_application"):
        gaps: list[Finding] = []
        got = [_read(case, app, name, label, gaps, _amount, th.low_conf) for name, label in EMI_INPUTS]
        if not gaps and (got[0][1] <= 0 or got[3][1] <= 0):
            gaps.append(gap(f"the declared income or the tenure in {_who(app)} is not a positive number", app.id))
        if gaps:
            out.append(fold(gaps, EMI, "Context rule not applied: an input could not be used",
                            "The rule on monthly obligations needs the declared income, the existing instalments, the loan amount and "
                            "the tenure, and could not be applied"))
            continue
        (income, inc), (_, emi), (_, loan), (_, months) = got
        ratio = (emi + loan / months) / inc
        if ratio <= Decimal(str(th.emi_ratio_max)):
            continue
        detail = (f"The declared monthly income in {_who(app)} is {_inr(inc)}. Existing instalments of {_inr(emi)} plus the new loan of "
                  f"{_inr(loan)} over {months} months ({_inr(loan / months)} a month, interest ignored) come to {ratio:.2f} of it. "
                  f"The reference limit of {th.emi_ratio_max:g} is a synthetic, illustrative value chosen for this prototype, not a "
                  "lending standard.")
        out.append(observation(EMI, "cross_document", f"Context rule: monthly obligations are {ratio:.0%} of declared income", detail,
                               [field_evidence(f, label) for (f, _), (_, label) in zip(got, EMI_INPUTS)],
                               conf=min(f.conf for f, _ in got)))
    return out


def context_age(case: Case, th: Thresholds) -> list[Finding]:
    """A document dated more than max_doc_age_days before the application it supports. Unreadable dates are not repeated here:
    cross_dates already reports them."""
    out: list[Finding] = []
    for app in _of(case, "loan_application"):
        when = _read(case, app, "application_date", "application date", [], _day)
        if not when:
            continue
        for t, (name, label) in DATED.items():
            for d in _of(case, t):
                got = _read(case, d, name, label, [], _day)
                days = (when[1] - got[1]).days if got else 0
                if days <= th.max_doc_age_days:
                    continue
                detail = (f"The application date in {_who(app)} is {when[1]:%d/%m/%Y} and the {label} in {_who(d)} is "
                          f"{got[1]:%d/%m/%Y}, {days} days earlier. The reference limit of {th.max_doc_age_days} days is a synthetic, "
                          "illustrative value chosen for this prototype, not a lending standard. A document can be older than that "
                          "for ordinary reasons.")
                out.append(observation(AGE, "cross_document",
                                       f"Context rule: {_who(d)} is dated more than {th.max_doc_age_days} days before the application",
                                       detail, [field_evidence(got[0], label), field_evidence(when[0], "application date")],
                                       conf=min(got[0].conf, when[0].conf)))
    return out


CONTEXT_RULES = [context_emi, context_age]


def run_context_rules(case: Case, ctx: Ctx) -> None:
    drafts = collect(case, ctx, CONTEXT_RULES)  # the module's list, read now
    ctx.audit.append("system", "context_checked", {"findings": len(drafts)})
    add_findings(case, ctx, drafts)
