"""Fictional identities. Institutions carry TEST in their names; there are no real logos, ID documents or customers."""
import random
from dataclasses import dataclass
from datetime import date

FIRST = ["Meera", "Anil", "Priya", "Rohan", "Kavya", "Arjun", "Sneha", "Vikram", "Divya", "Nikhil", "Anjali", "Suresh"]
LAST = ["Varghese", "Rao", "Nair", "Menon", "Iyer", "Pillai", "Kulkarni", "Reddy", "Bhat", "Joshi", "Shetty", "Kurian"]
BANKS = ["Halcyon", "Meridian", "Lakeshore", "Bluepeak", "Cedarline", "Orchard"]
FIRMS = ["Northwind", "Brightfield", "Kestrel", "Ironwood", "Silverleaf", "Harborview"]
BUILDINGS = ["Orchid Residency", "Lotus Heights", "Palm Court", "Maple Terrace", "Jasmine Apartments", "Cedar Villas"]
ROADS = ["Lakeview Road", "Temple Street", "Station Road", "Garden Lane", "Market Road", "Canal Street"]
CITIES = [("Kochi", "682001"), ("Pune", "411001"), ("Mysuru", "570001"), ("Nagpur", "440001"), ("Indore", "452001"),
          ("Madurai", "625001")]
DESIGNATIONS = ["Analyst", "Engineer", "Accountant", "Coordinator", "Supervisor", "Technician"]


@dataclass(frozen=True)  # frozen so a scenario can change one field with dataclasses.replace
class Identity:
    name: str
    address: str  # one line
    employer: str
    designation: str
    employee_id: str
    bank: str
    account_no: str
    consumer_no: str
    monthly_gross: int
    deductions: int
    month: date  # first day of the month the statement and the payslip cover
    loan_amount: int
    tenure_months: int
    existing_emi: int
    hand: str = ""  # whose hand signs the documents drawn from this identity; empty is the person's own (manipulation C4 sets it)

    @property
    def net_pay(self) -> int:
        return self.monthly_gross - self.deductions


def identity(seed: int) -> Identity:
    r = random.Random(seed)
    first, last = r.choice(FIRST), r.choice(LAST)
    city, pin = r.choice(CITIES)
    gross = r.randrange(30, 121) * 1000
    return Identity(
        name=f"{first} {r.choice('ABCDEGHJKLMNPRSTV')}. {last}",
        address=f"Flat {r.randrange(1, 40)}, {r.choice(BUILDINGS)}, {r.choice(ROADS)}, {city} {pin}",
        employer=f"{r.choice(FIRMS)} Test Pvt Ltd",
        designation=r.choice(DESIGNATIONS),
        employee_id=f"EMP-{r.randrange(1000, 10000)}",
        bank=f"{r.choice(BANKS)} Test Bank",
        account_no=f"TST-{r.randrange(10**9, 10**10)}",
        consumer_no=str(r.randrange(10**9, 10**10)),
        monthly_gross=gross,
        deductions=round(gross * r.uniform(0.08, 0.14) / 100) * 100,
        month=date(2026, r.randrange(1, 10), 1),
        loan_amount=r.randrange(2, 21) * 50_000,
        tenure_months=r.choice((24, 36, 48, 60)),
        existing_emi=r.randrange(0, 11) * 1000,
    )
