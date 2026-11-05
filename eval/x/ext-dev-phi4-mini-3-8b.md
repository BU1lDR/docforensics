# Template-free extraction by the local model: measured on the pack of invoices and electricity bills

Model: phi4-mini:3.8b (78fad5d182a7c33065e153a5f8ba210754207ba9d91973f57dffa7f487363753). Split ext-dev, 7 cases, 182 printed facts in 14 documents. 2026-11-05 22:57 India Standard Time 74d2679

Every value the model read is **inference** (10.4): the words come from the page, the name comes from the model, and nothing here feeds a check or a finding. The counting rules are in the docstring of `evaluation/score_x.py`; in short: a fact is *right* when a model-read field sits at its box (IoU 0.5 or more) under an acceptable name, *misnamed* when the name is not acceptable, *partial* when the field only touches the box (IoU 0.1 to 0.5), *rules* when only the rules' own reading is there, *missing* when nothing is near.

Of 182 printed facts: 97 right, 1 misnamed, 8 partial, 60 rules, 16 missing. Of the 97 right, 92 carry the value as printed.

| kind | facts | right | misnamed | partial | rules | missing |
|---|---|---|---|---|---|---|
| amount | 56 | 13 (23 %) | 0 (0 %) | 0 (0 %) | 41 (73 %) | 2 (4 %) |
| date | 28 | 6 (21 %) | 0 (0 %) | 2 (7 %) | 19 (68 %) | 1 (4 %) |
| id | 35 | 28 (80 %) | 1 (3 %) | 4 (11 %) | 0 (0 %) | 2 (6 %) |
| text | 63 | 50 (79 %) | 0 (0 %) | 2 (3 %) | 0 (0 %) | 11 (17 %) |

| medium | facts | right | misnamed | partial | rules | missing |
|---|---|---|---|---|---|---|
| 120dpi | 26 | 12 (46 %) | 0 (0 %) | 0 (0 %) | 4 (15 %) | 10 (38 %) |
| 150dpi | 52 | 22 (42 %) | 0 (0 %) | 8 (15 %) | 20 (38 %) | 2 (4 %) |
| digital | 52 | 29 (56 %) | 0 (0 %) | 0 (0 %) | 22 (42 %) | 1 (2 %) |
| mild | 52 | 34 (65 %) | 1 (2 %) | 0 (0 %) | 14 (27 %) | 3 (6 %) |

| document | facts | right | misnamed | partial | rules | missing |
|---|---|---|---|---|---|---|
| bill | 105 | 42 (40 %) | 0 (0 %) | 8 (8 %) | 44 (42 %) | 11 (10 %) |
| invoice | 77 | 55 (71 %) | 1 (1 %) | 0 (0 %) | 16 (21 %) | 5 (6 %) |

| layout | facts | right | misnamed | partial | rules | missing |
|---|---|---|---|---|---|---|
| A | 104 | 59 (57 %) | 0 (0 %) | 0 (0 %) | 44 (42 %) | 1 (1 %) |
| B | 78 | 38 (49 %) | 1 (1 %) | 8 (10 %) | 16 (21 %) | 15 (19 %) |

Calls: 14 pages considered, 14 replies accepted, 256 items given, 178 kept. Dropped: 57 already read by the rules, 14 value not inside its source text, 4 same words as an earlier item, 2 source text not found on the page, 1 label too long; 0 beyond the limit.
Seconds per page: mean 87.7, median 84.8, longest 122.8 (14 calls).

Extras (model-read fields at no listed fact): 22 unlisted, 54 table cell.

## Facts not read right

| case | document | fact | printed | outcome | the model's name and words |
|---|---|---|---|---|---|
| ext-dev-x-0001 | 01_invoice.jpg | buyer | Anil S. Reddy | missing | -: - |
| ext-dev-x-0001 | 01_invoice.jpg | bank_account | TST-1008088288 | misnamed | invoice_number: TST-1008088288 |
| ext-dev-x-0002 | 02_bill.jpg | consumer_no | 9854584182 | partial | connection_id: 9854584182 EB-2026-883312 |
| ext-dev-x-0002 | 02_bill.jpg | bill_number | EB-2026-883312 | partial | connection_id: 9854584182 EB-2026-883312 |
| ext-dev-x-0002 | 02_bill.jpg | due_date | 21 Feb 2026 | partial | cycle_pay_by: 01 Jan 2026 - 31 Jan 2026 21 Feb 2026 |
| ext-dev-x-0002 | 02_bill.jpg | billing_period | 01 Jan 2026 - 31 Jan 2026 | partial | cycle_pay_by: 01 Jan 2026 - 31 Jan 2026 21 Feb 2026 |
| ext-dev-x-0002 | 02_bill.jpg | current_reading | 47432 | missing | -: - |
| ext-dev-x-0003 | 01_invoice.jpg | buyer | Suresh T. Nair | missing | -: - |
| ext-dev-x-0003 | 02_bill.jpg | consumer_no | 7865163317 | missing | -: - |
| ext-dev-x-0003 | 02_bill.jpg | bill_number | EB-2026-902781 | missing | -: - |
| ext-dev-x-0003 | 02_bill.jpg | customer | Suresh T. Nair | missing | -: - |
| ext-dev-x-0003 | 02_bill.jpg | service_address | Flat 20, Jasmine Apartments, Station Road, Nagpur 440001 | missing | -: - |
| ext-dev-x-0003 | 02_bill.jpg | due_date | 19 Oct 2026 | missing | -: - |
| ext-dev-x-0003 | 02_bill.jpg | billing_period | 01 Sep 2026 - 30 Sep 2026 | missing | -: - |
| ext-dev-x-0003 | 02_bill.jpg | previous_reading | 35288 | missing | -: - |
| ext-dev-x-0003 | 02_bill.jpg | current_reading | 35712 | missing | -: - |
| ext-dev-x-0003 | 02_bill.jpg | units_consumed | 424 | missing | -: - |
| ext-dev-x-0004 | 01_invoice.pdf | tax | 3,330.00 | missing | -: - |
| ext-dev-x-0005 | 01_invoice.jpg | payment_terms | Net 15 days | missing | -: - |
| ext-dev-x-0005 | 01_invoice.jpg | tax | Rs. 2,655.00 | missing | -: - |
| ext-dev-x-0006 | 02_bill.jpg | consumer_no | 5137235967 | partial | connection_id: 5137235967 EB-2026-716930 |
| ext-dev-x-0006 | 02_bill.jpg | bill_number | EB-2026-716930 | partial | connection_id: 5137235967 EB-2026-716930 |
| ext-dev-x-0006 | 02_bill.jpg | due_date | 22 Aug 2026 | partial | cycle_pay_by: 01 Jul 2026 - 31 Jul 2026 22 Aug 2026 |
| ext-dev-x-0006 | 02_bill.jpg | billing_period | 01 Jul 2026 - 31 Jul 2026 | partial | cycle_pay_by: 01 Jul 2026 - 31 Jul 2026 22 Aug 2026 |
| ext-dev-x-0006 | 02_bill.jpg | current_reading | 43661 | missing | -: - |

## Extras

| case | document | name | words | where |
|---|---|---|---|---|
| ext-dev-x-0000 | 01_invoice.pdf | document_type | Tax Invoice | unlisted |
| ext-dev-x-0000 | 01_invoice.pdf | quantity | 2 | table cell |
| ext-dev-x-0000 | 01_invoice.pdf | rate | 3,250.00 | table cell |
| ext-dev-x-0000 | 01_invoice.pdf | item_description | Support hours | table cell |
| ext-dev-x-0000 | 01_invoice.pdf | quantity | 6 | table cell |
| ext-dev-x-0000 | 01_invoice.pdf | rate | 850.00 | table cell |
| ext-dev-x-0000 | 01_invoice.pdf | item_description | Cloud hosting, monthly | table cell |
| ext-dev-x-0000 | 01_invoice.pdf | quantity | 1 | table cell |
| ext-dev-x-0000 | 01_invoice.pdf | rate | 4,800.00 | table cell |
| ext-dev-x-0000 | 01_invoice.pdf | gst_rate | 18% | unlisted |
| ext-dev-x-0001 | 01_invoice.jpg | item_quantity | 6 | table cell |
| ext-dev-x-0001 | 01_invoice.jpg | unit_price | 850.00 | table cell |
| ext-dev-x-0001 | 01_invoice.jpg | line_total | 5,100.00 | table cell |
| ext-dev-x-0001 | 01_invoice.jpg | item_quantity | 1 | unlisted |
| ext-dev-x-0001 | 01_invoice.jpg | unit_price | 5,400.00 | table cell |
| ext-dev-x-0001 | 01_invoice.jpg | line_total | 10,800.00 | table cell |
| ext-dev-x-0001 | 01_invoice.jpg | item_quantity | 2 | table cell |
| ext-dev-x-0001 | 01_invoice.jpg | unit_price | 3,250.00 | table cell |
| ext-dev-x-0001 | 01_invoice.jpg | line_total | 6,500.00 | table cell |
| ext-dev-x-0001 | 01_invoice.jpg | tax_rate | (18%) | unlisted |
| ext-dev-x-0001 | 01_invoice.jpg | signature | Computer generated; no signature required. | unlisted |
| ext-dev-x-0001 | 02_bill.jpg | company | Ironwood Test Electricity Board | unlisted |
| ext-dev-x-0001 | 02_bill.jpg | bill_type | Electricity Bill | unlisted |
| ext-dev-x-0001 | 02_bill.jpg | payment_instructions | Pay at any authorised collection centre or online. | unlisted |
| ext-dev-x-0002 | 01_invoice.jpg | invoice_type | Tax Invoice | unlisted |
| ext-dev-x-0002 | 01_invoice.jpg | item_description | Wireless access point 2 | table cell |
| ext-dev-x-0002 | 01_invoice.jpg | item_rate | 6,900.00 | table cell |
| ext-dev-x-0002 | 01_invoice.jpg | item_amount | 13,800.00 | table cell |
| ext-dev-x-0002 | 01_invoice.jpg | item_description | Cloud hosting, monthly | table cell |
| ext-dev-x-0002 | 01_invoice.jpg | item_rate | 4,800.00 | table cell |
| ext-dev-x-0002 | 01_invoice.jpg | item_description | Support hours 6 | table cell |
| ext-dev-x-0002 | 01_invoice.jpg | item_rate | 850.00 | table cell |
| ext-dev-x-0002 | 01_invoice.jpg | gst_rate | 18% | unlisted |
| ext-dev-x-0003 | 01_invoice.jpg | item_quantity | 3 | table cell |
| ext-dev-x-0003 | 01_invoice.jpg | unit_price | 1.150.00 | table cell |
| ext-dev-x-0003 | 01_invoice.jpg | line_total | 3.450.00 | table cell |
| ext-dev-x-0003 | 01_invoice.jpg | item_quantity | 2 | table cell |
| ext-dev-x-0003 | 01_invoice.jpg | unit_price | 6,900.00 | table cell |
| ext-dev-x-0003 | 01_invoice.jpg | line_total | 13.800.00 | table cell |
| ext-dev-x-0003 | 01_invoice.jpg | item_quantity | 1 | table cell |
| ext-dev-x-0003 | 01_invoice.jpg | unit_price | 12,000.00 | table cell |
| ext-dev-x-0003 | 01_invoice.jpg | line_total | 12.000.00 | table cell |
| ext-dev-x-0003 | 01_invoice.jpg | tax_rate | (18%) | unlisted |
| ext-dev-x-0004 | 01_invoice.pdf | invoice_type | Tax Invoice | unlisted |
| ext-dev-x-0004 | 01_invoice.pdf | item_description | Network cabling, 40 m | table cell |
| ext-dev-x-0004 | 01_invoice.pdf | item_description | Support hours | table cell |
| ext-dev-x-0004 | 01_invoice.pdf | gst_rate | 18% | unlisted |
| ext-dev-x-0004 | 02_bill.pdf | company | Kestrel Test Electricity Board | unlisted |
| ext-dev-x-0004 | 02_bill.pdf | bill_type | Electricity Bill | unlisted |
| ext-dev-x-0004 | 02_bill.pdf | payment_instructions | Pay at any authorised collection centre or online. | unlisted |
| ext-dev-x-0005 | 01_invoice.jpg | item_quantity | 2 | table cell |
| ext-dev-x-0005 | 01_invoice.jpg | unit_price | 3,250.00 | table cell |
| ext-dev-x-0005 | 01_invoice.jpg | line_total | 6,500.00 | table cell |
| ext-dev-x-0005 | 01_invoice.jpg | item_quantity | 3 | table cell |
| ext-dev-x-0005 | 01_invoice.jpg | unit_price | 1,150.00 | table cell |
| ext-dev-x-0005 | 01_invoice.jpg | line_total | 3,450.00 | table cell |
| ext-dev-x-0005 | 01_invoice.jpg | item_quantity | 1 | table cell |
| ext-dev-x-0005 | 01_invoice.jpg | unit_price | 4,800.00 | table cell |
| ext-dev-x-0005 | 01_invoice.jpg | tax_percentage | (18%) | unlisted |
| ext-dev-x-0005 | 02_bill.jpg | party | Northwind Test Electricity Board | unlisted |
| ext-dev-x-0005 | 02_bill.jpg | bill_type | Electricity Bill | unlisted |
| ext-dev-x-0005 | 02_bill.jpg | payment_instructions | Pay at any authorised collection centre or online. | unlisted |
| ext-dev-x-0006 | 01_invoice.jpg | invoice_type | Tax Invoice | unlisted |
| ext-dev-x-0006 | 01_invoice.jpg | item_description | Laptop stand | table cell |
| ext-dev-x-0006 | 01_invoice.jpg | item_quantity | 3 | table cell |
| ext-dev-x-0006 | 01_invoice.jpg | item_rate | 1,150.00 | table cell |
| ext-dev-x-0006 | 01_invoice.jpg | item_amount | 3,450.00 | table cell |
| ext-dev-x-0006 | 01_invoice.jpg | item_description | Wireless access point | table cell |
| ext-dev-x-0006 | 01_invoice.jpg | item_quantity | 2 | table cell |
| ext-dev-x-0006 | 01_invoice.jpg | item_rate | 6,900.00 | table cell |
| ext-dev-x-0006 | 01_invoice.jpg | item_amount | 13,800.00 | table cell |
| ext-dev-x-0006 | 01_invoice.jpg | item_description | Support hours | table cell |
| ext-dev-x-0006 | 01_invoice.jpg | item_quantity | 6 | table cell |
| ext-dev-x-0006 | 01_invoice.jpg | item_rate | 850.00 | table cell |
| ext-dev-x-0006 | 01_invoice.jpg | item_amount | 5,100.00 | table cell |
| ext-dev-x-0006 | 01_invoice.jpg | gst_rate | 18% | unlisted |
