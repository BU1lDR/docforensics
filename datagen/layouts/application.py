"""Personal loan application: the lender, a labelled block of declared particulars, a declaration and a drawn signature. Layout A
is the one the spec files were written from; it prints the date with its weekday ('Mon 03 Nov 2025'), which is what the application
check reads. Layout B is another lender's form, drawn once the spec files were final: other wording for some labels, the date
without a weekday, other margins and spacing."""
import random
from datetime import datetime, time, timedelta

from .. import marks, signatures
from ..fictional import Identity
from . import DAYS, MONTHS, Drawn, Sheet, money, norm, text_width

# drawn top to bottom, in this order: field name -> kind
KIND = {"application_date": "date", "applicant_name": "text", "address": "text", "employer": "text", "account_no": "id",
        "declared_monthly_income": "amount", "existing_emi": "amount", "loan_amount": "amount", "tenure_months": "amount"}
STYLE = {
    "A": dict(x=40, name=(16, 62), logo_y=40, sub=("Personal Loan Application", 80), top=108, pitch=14, value_x=200, decl_y=262,
              labels=("Application Date", "Applicant Name", "Residential Address", "Employer", "Salary Account Number",
                      "Declared Monthly Income", "Existing EMI", "Loan Amount", "Tenure in Months"),
              dates=("%a %d %b %Y", "%d %b %Y"),  # with the weekday, and without it
              show=lambda d: f"{DAYS[d.weekday()]} {d.day:02d} {MONTHS[d.month - 1][:3]} {d.year}",
              sign=(400, 748, "Applicant Signature"), seal=(40, 748)),
    "B": dict(x=56, name=(15, 64), logo_y=42, sub=("Loan Application Form", 84), top=116, pitch=16, value_x=230, decl_y=284,
              labels=("Date of Application", "Full Name", "Present Address", "Employer Name", "Salary A/c No", "Gross Monthly Income",
                      "Existing EMI", "Amount of Loan", "Tenure in Months"),
              dates=("%d-%b-%Y",), show=lambda d: f"{d.day:02d}-{MONTHS[d.month - 1][:3]}-{d.year}",
              sign=(380, 740, "Signature of Applicant"), seal=(56, 740)),
}
DECLARATION = "I declare that the particulars given above are true and complete to the best of my knowledge."


def draw_application(ident: Identity, layout: str = "A", seed: int = 0, overrides: dict[str, str] | None = None) -> Drawn:
    """A genuine application, dated in the month after the identity's statement month. `overrides` replace one drawn text
    by field name without recomputing anything else. The truth holds what is drawn, normalised, and echoes the overrides."""
    if layout not in STYLE:
        raise ValueError(f"unknown layout {layout!r}")
    st = STYLE[layout]
    over = dict(overrides or {})
    for key in over:
        if key not in KIND:
            raise ValueError(f"unknown override {key!r}")
    rng = random.Random(f"application/{ident.account_no}/{seed}")
    day = (ident.month + timedelta(days=31)).replace(day=rng.randrange(10, 21))  # +31 days from the 1st is inside next month
    created = datetime.combine(day, time(rng.randrange(10, 18), rng.randrange(60)))

    fields = {"application_date": day.isoformat(), "applicant_name": ident.name, "address": ident.address,
              "employer": ident.employer, "account_no": ident.account_no,
              "declared_monthly_income": f"{ident.monthly_gross}.00", "existing_emi": f"{ident.existing_emi}.00",
              "loan_amount": f"{ident.loan_amount}.00", "tenure_months": f"{ident.tenure_months}.00"}
    shown = fields | {"application_date": st["show"](day),
                      "declared_monthly_income": money(ident.monthly_gross), "existing_emi": money(ident.existing_emi),
                      "loan_amount": money(ident.loan_amount), "tenure_months": str(ident.tenure_months)}
    for k in fields:
        if k in over:
            shown[k], fields[k] = over[k], norm(KIND[k], over[k], st["dates"])

    sheet = Sheet(f"{ident.bank.split()[0]} LoanDesk Forms 3.0", created)
    sheet.new_page()
    pressing = random.Random(f"application/{ident.account_no}/{seed}/marks")  # its own stream: the other draws do not move
    x0, (size, base) = st["x"], st["name"]
    sheet.text(x0, base, ident.bank, size, bold=True)
    marks.logo(sheet, ident.logo or ident.bank, pressing, x0 + text_width(ident.bank, size, True) + 14, st["logo_y"])
    sheet.text(x0, st["sub"][1], st["sub"][0], 11)
    for i, (name, label) in enumerate(zip(KIND, st["labels"])):
        y = st["top"] + st["pitch"] * i
        sheet.text(x0, y, label, 9)
        sheet.text(st["value_x"], y, shown[name], 9, bold=True, key=name)
    sheet.text(x0, st["decl_y"], DECLARATION, 8)
    sx, sy, caption = st["sign"]
    signatures.draw(sheet, ident.hand or ident.name, random.Random(f"application/{ident.account_no}/{seed}/signature"), sx, sy)
    sheet.text(sx, sy, caption, 8)
    marks.seal(sheet, ident.stamp or ident.bank, pressing, *st["seal"], "For Bank Use")
    truth = {"type": "loan_application", "layout": layout, "fields": fields, "rows": [], "boxes": sheet.boxes, "overridden": over}
    return Drawn(sheet.pdf(), truth)
