"""Classification reads the wordings the extraction already knows: a payslip that says 'Total Earnings' and 'Emp. Code', or an application
that calls the income a 'Monthly Salary', is still of its type; a letter that mentions a salary is not made one."""
from tests.helpers import lines_pdf
from tests.test_statement_extraction import run


def page(*lines: str) -> bytes:
    return lines_pdf([(50, 60 + 18 * i, text, 11) for i, text in enumerate(lines)])


def doc_type(tmp_path, *lines: str) -> str:
    return run(tmp_path, page(*lines))[0].documents[0].doc_type


def test_a_payslip_that_says_total_earnings_and_employee_code_is_a_payslip(tmp_path):
    assert doc_type(tmp_path, "Fabrikam Systems Pvt Ltd", "Earnings Statement", "Employee Code: E10442", "Pay Date: 31 Oct 2026",
                    "Total Earnings 95,000.00", "Total Deductions 12,000.00", "Net Amount 83,000.00") == "payslip"


def test_an_application_that_calls_the_income_monthly_salary_is_an_application(tmp_path):
    assert doc_type(tmp_path, "Halcyon Bank", "Loan Request Form", "Borrower Name: Asha Verma", "Loan Amount: 5,00,000.00",
                    "Repayment Period: 48 months", "Monthly Salary: 95,000.00", "Existing EMI: 8,000.00", "Company: Fabrikam Systems") == "loan_application"


def test_a_letter_that_mentions_a_salary_and_a_date_stays_unknown(tmp_path):
    assert doc_type(tmp_path, "Employment verification letter", "Date: 02 Nov 2026", "This is to certify that Mr Rohan Mehta is employed with",
                    "Fabrikam Systems Pvt Ltd since 01 Apr 2021 with a gross monthly salary of 95,000.00.", "Payment date: 31 Oct 2026") == "unknown"
