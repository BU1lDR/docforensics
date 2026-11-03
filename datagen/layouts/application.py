"""Personal loan application, layout A: the lender, a labelled block of declared particulars, a declaration and a drawn
signature. The date is printed with its weekday ('Mon 03 Nov 2025'), which is what the application check reads."""
import random
from datetime import datetime, time, timedelta

from ..fictional import Identity
from . import DAYS, MONTHS, Drawn, Sheet, money, norm

# drawn top to bottom from y = 108 in steps of 14: field name -> (label, kind); values start at x = 200
FIELDS = {"application_date": ("Application Date", "date"), "applicant_name": ("Applicant Name", "text"),
          "address": ("Residential Address", "text"), "employer": ("Employer", "text"),
          "account_no": ("Salary Account Number", "id"), "declared_monthly_income": ("Declared Monthly Income", "amount"),
          "existing_emi": ("Existing EMI", "amount"), "loan_amount": ("Loan Amount", "amount"),
          "tenure_months": ("Tenure in Months", "amount")}
DATE_FORMATS = ("%a %d %b %Y", "%d %b %Y")  # with the weekday, and without it
DECLARATION = "I declare that the particulars given above are true and complete to the best of my knowledge."


def _signature(sheet: Sheet, rng: random.Random) -> None:
    """A signature as strokes: a seeded scrawl and an underline. No text, so nothing can sit beneath it."""
    x, pts = 400.0, []
    for _ in range(9):
        pts.append((x, 710 + rng.uniform(-18, 14)))
        x += rng.uniform(9, 15)
    under = [(pts[0][0], 726.0), (pts[-1][0], 722.0)]
    ink = (0.1, 0.1, 0.5)
    sheet.page.draw_polyline(pts, color=ink, width=1.1)
    sheet.page.draw_line(*under, color=ink, width=0.8)
    xs, ys = zip(*pts, *under)
    sheet.region("signature", min(xs) - 1, min(ys) - 1, max(xs) + 1, max(ys) + 1)


def draw_application(ident: Identity, layout: str = "A", seed: int = 0, overrides: dict[str, str] | None = None) -> Drawn:
    """A genuine application, dated in the month after the identity's statement month. `overrides` replace one drawn text
    by field name without recomputing anything else. The truth holds what is drawn, normalised, and echoes the overrides."""
    if layout != "A":
        raise ValueError(f"unknown layout {layout!r}")
    over = dict(overrides or {})
    for key in over:
        if key not in FIELDS:
            raise ValueError(f"unknown override {key!r}")
    rng = random.Random(f"application/{ident.account_no}/{seed}")
    day = (ident.month + timedelta(days=31)).replace(day=rng.randrange(10, 21))  # +31 days from the 1st is inside next month
    created = datetime.combine(day, time(rng.randrange(10, 18), rng.randrange(60)))

    fields = {"application_date": day.isoformat(), "applicant_name": ident.name, "address": ident.address,
              "employer": ident.employer, "account_no": ident.account_no,
              "declared_monthly_income": f"{ident.monthly_gross}.00", "existing_emi": f"{ident.existing_emi}.00",
              "loan_amount": f"{ident.loan_amount}.00", "tenure_months": f"{ident.tenure_months}.00"}
    shown = fields | {"application_date": f"{DAYS[day.weekday()]} {day.day:02d} {MONTHS[day.month - 1][:3]} {day.year}",
                      "declared_monthly_income": money(ident.monthly_gross), "existing_emi": money(ident.existing_emi),
                      "loan_amount": money(ident.loan_amount), "tenure_months": str(ident.tenure_months)}
    for k in fields:
        if k in over:
            shown[k], fields[k] = over[k], norm(FIELDS[k][1], over[k], DATE_FORMATS)

    sheet = Sheet(f"{ident.bank.split()[0]} LoanDesk Forms 3.0", created)
    sheet.new_page()
    sheet.text(40, 62, ident.bank, 16, bold=True)
    sheet.text(40, 80, "Personal Loan Application", 11)
    for y, (name, (label, _)) in zip(range(108, 108 + 14 * len(FIELDS), 14), FIELDS.items()):
        sheet.text(40, y, label, 9)
        sheet.text(200, y, shown[name], 9, bold=True, key=name)
    sheet.text(40, 262, DECLARATION, 8)
    _signature(sheet, rng)
    sheet.text(400, 748, "Applicant Signature", 8)
    truth = {"type": "loan_application", "layout": layout, "fields": fields, "rows": [], "boxes": sheet.boxes, "overridden": over}
    return Drawn(sheet.pdf(), truth)
