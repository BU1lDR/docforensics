from datetime import date
from decimal import Decimal

from docforensics.understand.normalise import (amount_in_words, amount_side, fmt_amount, name_similarity, parse_amount,
                                               parse_date, text_similarity)

RUPEE, MINUS, NBSP = chr(0x20B9), chr(0x2212), chr(0xA0)


def arabic_indic(digits: str) -> str:
    return "".join(chr(0x660 + int(d)) for d in digits)


# strings with digits, spaces or marks from other scripts, a control character and an emoji
ODD = [arabic_indic("5") + "," + arabic_indic("000"), chr(0xFF15) + ",000", "5" + chr(0xB2), "5,000" + chr(0x301), chr(0),
       chr(0x1F4B0) + " 5,000", RUPEE, "   ", "()", "Rs.", arabic_indic("3") + "/" + arabic_indic("4") + "/" + arabic_indic("2026")]


def test_western_and_indian_grouping_agree():
    assert parse_amount("1,23,456.78") == parse_amount("123,456.78") == Decimal("123456.78")
    assert parse_amount("1,00,00,000") == Decimal("10000000")  # crore
    assert parse_amount("52000") == Decimal("52000") and parse_amount("0.50") == Decimal("0.50")
    assert parse_amount("1,2345.00") is None  # a misplaced comma is not repaired
    assert parse_amount("") is None and parse_amount("abc") is None and parse_amount("-") is None


def test_prefixes_and_negatives():
    assert parse_amount(RUPEE + " 5,000") == parse_amount("Rs." + NBSP + "5,000") == Decimal("5000")  # text layers use no-break spaces
    assert parse_amount("Rs. 5,000.00 Cr") == Decimal("5000.00") and amount_side("Rs. 5,000.00 Cr") == "cr"
    assert parse_amount("(1,200.00)") == Decimal("-1200.00")
    assert parse_amount("-1,200.00") == parse_amount("1,200.00-") == parse_amount(MINUS + "1,200.00") == Decimal("-1200.00")
    assert parse_amount("INR 1,200") == parse_amount("Rs.1,200/-") == Decimal("1200")
    assert parse_amount("4,125.50 DR") == Decimal("4125.50") and amount_side("4,125.50 DR") == "dr"
    assert amount_side("4,125.50") is None and amount_side("Descr") is None
    assert parse_amount("(1,200.00") is None  # an unclosed bracket is not a negative


def test_fmt_amount_keeps_the_cents_or_says_none():
    assert fmt_amount(Decimal("52000")) == "52000.00" and fmt_amount(Decimal("148034.5")) == "148034.50"
    assert fmt_amount(Decimal("-1200")) == "-1200.00" and fmt_amount(Decimal("-0.00")) == "0.00"
    assert fmt_amount(Decimal("1.500")) == "1.50" and fmt_amount(Decimal("1.005")) is None  # no rounding of what was read
    assert fmt_amount(parse_amount("9" * 39)) is None and fmt_amount(Decimal("1E+30")) is None  # too big to be money; no raise


def test_letters_in_digits_are_not_repaired():
    for bad in ("1O,000", "52,OOO.00", "5,000.0l", "Rs. 5,0OO", "5,000.00 Debit"):
        assert parse_amount(bad) is None


def test_absurd_input_is_none_not_an_error():
    assert parse_amount("9" * 5000) is None and parse_date("1" * 5000) == (None, False)
    assert amount_in_words("one " * 500) is None
    for odd in ODD:  # only ASCII digits and letters are read; nothing raises
        assert parse_amount(odd) is None and amount_side(odd) is None and amount_in_words(odd) is None
        assert parse_date(odd) == (None, False)
        assert 0.0 <= name_similarity(odd, "Meera") <= 1.0 and 0.0 <= text_similarity(odd, "x") <= 1.0


def test_ambiguous_date_is_flagged_not_guessed():
    assert parse_date("04/05/2026") == (date(2026, 5, 4), True)
    assert parse_date("31/03/2026") == (date(2026, 3, 31), False)
    assert parse_date("03/13/2026") == (None, False)
    assert parse_date("05/05/2026") == (date(2026, 5, 5), False)  # both readings give the same day
    assert parse_date("31/04/2026") == (None, False) and parse_date("29/02/2026") == (None, False)
    assert parse_date("29/02/2028") == (date(2028, 2, 29), False)
    assert parse_date("12-03-26") == (date(2026, 3, 12), True) and parse_date("13.03.2026") == (date(2026, 3, 13), False)
    assert parse_date("2026-03-12") == (date(2026, 3, 12), False) and parse_date("2026-13-01") == (None, False)
    assert parse_date("2O26-03-12") == (None, False) and parse_date("") == (None, False)


def test_month_name_dates():
    want = (date(2026, 1, 12), False)
    for s in ("12 Jan 2026", "12-Jan-26", "12/JAN/2026", "12th January 2026", "January 12, 2026", "Jan 12 2026"):
        assert parse_date(s) == want, s
    assert parse_date("5 Sept 2026") == (date(2026, 9, 5), False) and parse_date("05-Sep-2026") == (date(2026, 9, 5), False)
    assert parse_date("12 Foo 2026") == (None, False) and parse_date("12 Ja 2026") == (None, False)


def test_two_digit_year_pivot():
    assert parse_date("01/02/68")[0] == date(2068, 2, 1) and parse_date("01/02/69")[0] == date(1969, 2, 1)


def test_amount_in_words():
    assert amount_in_words("Rupees Fifty Five Thousand Only") == Decimal(55000)
    assert amount_in_words("One Lakh Twenty Thousand") == Decimal(120000)
    assert amount_in_words("Two Crore") == Decimal(20000000)
    assert amount_in_words("RUPEES ONE LAKH TWENTY-FIVE THOUSAND SIX HUNDRED AND FIFTY ONLY") == Decimal(125650)
    assert amount_in_words("Rs. Twelve Thousand Five Hundred Only") == Decimal(12500)
    assert amount_in_words("Rupees Five Thousand and Fifty Paise Only") == Decimal("5000.50")
    assert amount_in_words("Fourty Thousand") == Decimal(40000) and amount_in_words("Five Lakhs") == Decimal(500000)
    for bad in ("", "Rupees Only", "Fifty Five Thousand Banana", "Thousand", "Rupees Fifty Paise Only", "Five and Hundred Paise",
                "Five Thousand and", "Thousand Five Lakh", "Five Five", "Five Thousand and One Hundred Paise Only"):
        assert amount_in_words(bad) is None, bad


def test_name_similarity_tolerates_order_title_initial():
    assert name_similarity("Meera K. Varghese", "VARGHESE MEERA K") >= 0.85
    assert name_similarity("Meera K. Varghese", "Mrs Meera Varghese") >= 0.85
    assert name_similarity("M. K. Varghese", "Meera Kumar Varghese") >= 0.85
    assert name_similarity("Meera Varghese", "Anil Rao") < 0.5
    assert name_similarity("Anil Rao", "Arun Rao") < 0.85
    assert name_similarity("Dr. Meera Varghese", "meera varghese") == 1.0
    assert name_similarity("", "Meera") == 0.0 and name_similarity("Mrs", "Mr") == 0.0
    assert name_similarity("Meera Varghese", "Anil Rao") == name_similarity("Anil Rao", "Meera Varghese")


def test_text_similarity_ignores_case_and_spacing():
    assert text_similarity("12  MG Road,\n Kochi", "12 mg road, kochi") == 1.0
    assert text_similarity("12 MG Road, Kochi", "45 Park Street, Pune") < 0.5
    assert 0.85 < text_similarity("12 MG Road, Kochi 682001", "12 MG Rd, Kochi 682001") < 1.0
    assert text_similarity("", "") == 0.0
