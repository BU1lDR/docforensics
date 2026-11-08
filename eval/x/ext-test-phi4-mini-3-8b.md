# Template-free extraction by the local model: measured on the pack of invoices and electricity bills

Model: phi4-mini:3.8b (78fad5d182a7c33065e153a5f8ba210754207ba9d91973f57dffa7f487363753). Split ext-test, 8 cases, 208 printed facts in 16 documents. 2026-11-08 12:15 India Standard Time bb08c8e

Every value the model read is **inference** (10.4): the words come from the page, the name comes from the model, and nothing here feeds a check or a finding. The counting rules are in the docstring of `evaluation/score_x.py`; in short: a fact is *right* when a model-read field sits at its box (IoU 0.5 or more) under an acceptable name, *misnamed* when the name is not acceptable, *partial* when the field only touches the box (IoU 0.1 to 0.5), *rules* when only the rules' own reading is there, *missing* when nothing is near.

Of 208 printed facts: 114 right, 9 misnamed, 7 partial, 63 rules, 15 missing. Of the 114 right, 106 carry the value as printed.

| kind | facts | right | misnamed | partial | rules | missing |
|---|---|---|---|---|---|---|
| amount | 64 | 20 (31 %) | 0 (0 %) | 0 (0 %) | 43 (67 %) | 1 (2 %) |
| date | 32 | 7 (22 %) | 1 (3 %) | 1 (3 %) | 20 (62 %) | 3 (9 %) |
| id | 40 | 29 (72 %) | 3 (8 %) | 5 (12 %) | 0 (0 %) | 3 (8 %) |
| text | 72 | 58 (81 %) | 5 (7 %) | 1 (1 %) | 0 (0 %) | 8 (11 %) |

| medium | facts | right | misnamed | partial | rules | missing |
|---|---|---|---|---|---|---|
| 120dpi | 52 | 30 (58 %) | 3 (6 %) | 2 (4 %) | 7 (13 %) | 10 (19 %) |
| 150dpi | 52 | 22 (42 %) | 0 (0 %) | 5 (10 %) | 20 (38 %) | 5 (10 %) |
| digital | 52 | 30 (58 %) | 0 (0 %) | 0 (0 %) | 22 (42 %) | 0 (0 %) |
| mild | 52 | 32 (62 %) | 6 (12 %) | 0 (0 %) | 14 (27 %) | 0 (0 %) |

| document | facts | right | misnamed | partial | rules | missing |
|---|---|---|---|---|---|---|
| bill | 120 | 53 (44 %) | 2 (2 %) | 7 (6 %) | 47 (39 %) | 11 (9 %) |
| invoice | 88 | 61 (69 %) | 7 (8 %) | 0 (0 %) | 16 (18 %) | 4 (5 %) |

| layout | facts | right | misnamed | partial | rules | missing |
|---|---|---|---|---|---|---|
| A | 104 | 60 (58 %) | 0 (0 %) | 0 (0 %) | 44 (42 %) | 0 (0 %) |
| B | 104 | 54 (52 %) | 9 (9 %) | 7 (7 %) | 19 (18 %) | 15 (14 %) |

Calls: 16 pages considered, 16 replies accepted, 305 items given, 213 kept. Dropped: 58 already read by the rules, 15 source text not found on the page, 12 value not inside its source text, 6 same words as an earlier item, 1 label too long; 0 beyond the limit.
Seconds per page: mean 80.9, median 80.8, longest 110.1 (16 calls).

Extras (model-read fields at no listed fact): 28 unlisted, 58 table cell.

## Facts not read right

| case | document | fact | printed | outcome | the model's name and words |
|---|---|---|---|---|---|
| ext-test-x-0001 | 01_invoice.jpg | buyer | Anjali V. Bhat | misnamed | billing_address: Anjali V. Bhat |
| ext-test-x-0001 | 01_invoice.jpg | payment_terms | Net 45 days | misnamed | billing_address: Net 45 days |
| ext-test-x-0001 | 01_invoice.jpg | bank_account | TST-1044560999 | misnamed | invoice_reference: TST-1044560999 |
| ext-test-x-0002 | 02_bill.jpg | consumer_no | 9603153890 | partial | connection_id: 9603153890 EB-2026-356579 |
| ext-test-x-0002 | 02_bill.jpg | bill_number | EB-2026-356579 | partial | connection_id: 9603153890 EB-2026-356579 |
| ext-test-x-0002 | 02_bill.jpg | due_date | 17 Oct 2026 | partial | cycle_pay_by: 01 Sep 2026 - 30 Sep 2026 17 Oct 2026 |
| ext-test-x-0002 | 02_bill.jpg | billing_period | 01 Sep 2026 - 30 Sep 2026 | partial | cycle_pay_by: 01 Sep 2026 - 30 Sep 2026 17 Oct 2026 |
| ext-test-x-0002 | 02_bill.jpg | current_reading | 70025 | missing | -: - |
| ext-test-x-0003 | 01_invoice.jpg | invoice_date | 18 Aug 2026 | missing | -: - |
| ext-test-x-0003 | 01_invoice.jpg | buyer | Rohan M. Rao | missing | -: - |
| ext-test-x-0003 | 01_invoice.jpg | bank_account | TST-7365292901 | misnamed | invoice_number: TST-7365292901 |
| ext-test-x-0003 | 01_invoice.jpg | tax | Rs. 4,518.00 | missing | -: - |
| ext-test-x-0003 | 02_bill.jpg | consumer_no | 3486936376 | partial | connection_id: 3486936376 EB-2026-227386 |
| ext-test-x-0003 | 02_bill.jpg | bill_number | EB-2026-227386 | partial | connection_id: 3486936376 EB-2026-227386 |
| ext-test-x-0003 | 02_bill.jpg | due_date | 18 Sep 2026 | missing | -: - |
| ext-test-x-0003 | 02_bill.jpg | previous_reading | 7226 | missing | -: - |
| ext-test-x-0003 | 02_bill.jpg | current_reading | 7835 | missing | -: - |
| ext-test-x-0003 | 02_bill.jpg | units_consumed | 609 | missing | -: - |
| ext-test-x-0005 | 01_invoice.jpg | buyer | Anjali J. Reddy | misnamed | billing_address: Anjali J. Reddy |
| ext-test-x-0005 | 01_invoice.jpg | payment_terms | Net 30 days | misnamed | billing_address: Net 30 days |
| ext-test-x-0005 | 01_invoice.jpg | bank_account | TST-7175255341 | misnamed | invoice_reference: TST-7175255341 |
| ext-test-x-0006 | 02_bill.jpg | consumer_no | 6112902486 | missing | -: - |
| ext-test-x-0006 | 02_bill.jpg | bill_number | EB-2026-997239 | partial | connection_id: 6112902486 EB-2026-997239 |
| ext-test-x-0006 | 02_bill.jpg | due_date | 20 Apr 2026 | missing | -: - |
| ext-test-x-0006 | 02_bill.jpg | previous_reading | 8885 | missing | -: - |
| ext-test-x-0006 | 02_bill.jpg | current_reading | 9207 | missing | -: - |
| ext-test-x-0007 | 01_invoice.jpg | buyer | Nikhil D. Shetty | missing | -: - |
| ext-test-x-0007 | 02_bill.jpg | consumer_no | 1928778951 | missing | -: - |
| ext-test-x-0007 | 02_bill.jpg | bill_number | EB-2026-125735 | missing | -: - |
| ext-test-x-0007 | 02_bill.jpg | customer | Nikhil D. Shetty | misnamed | party: Nikhil D. Shetty |
| ext-test-x-0007 | 02_bill.jpg | due_date | 22 Mar 2026 | misnamed | date: 22 Mar 2026 |

## Extras

| case | document | name | words | where |
|---|---|---|---|---|
| ext-test-x-0000 | 01_invoice.pdf | invoice_type | Tax Invoice | unlisted |
| ext-test-x-0000 | 01_invoice.pdf | item_description | Wireless access point 2 | table cell |
| ext-test-x-0000 | 01_invoice.pdf | item_rate | 6,900.00 | table cell |
| ext-test-x-0000 | 01_invoice.pdf | item_description | Laptop stand 3 | table cell |
| ext-test-x-0000 | 01_invoice.pdf | item_rate | 1,150.00 | table cell |
| ext-test-x-0000 | 01_invoice.pdf | item_description | Annual maintenance contract 1 | table cell |
| ext-test-x-0000 | 01_invoice.pdf | item_rate | 12,000.00 | table cell |
| ext-test-x-0000 | 01_invoice.pdf | gst_rate | 18% | unlisted |
| ext-test-x-0000 | 02_bill.pdf | payment_options | Pay at any authorised collection centre or online. | unlisted |
| ext-test-x-0001 | 01_invoice.jpg | billing_address | A/c | unlisted |
| ext-test-x-0001 | 01_invoice.jpg | item_quantity | 1 | table cell |
| ext-test-x-0001 | 01_invoice.jpg | unit_price | 4,800.00 | table cell |
| ext-test-x-0001 | 01_invoice.jpg | item_quantity | 1 | unlisted |
| ext-test-x-0001 | 01_invoice.jpg | unit_price | 5,400.00 | table cell |
| ext-test-x-0001 | 01_invoice.jpg | line_total | 10,800.00 | table cell |
| ext-test-x-0001 | 01_invoice.jpg | item_quantity | 1 | table cell |
| ext-test-x-0001 | 01_invoice.jpg | unit_price | 12,000.00 | table cell |
| ext-test-x-0001 | 01_invoice.jpg | tax_rate | (18%) | unlisted |
| ext-test-x-0002 | 01_invoice.jpg | document_type | Tax Invoice | unlisted |
| ext-test-x-0002 | 01_invoice.jpg | description | Cloud hosting, monthly | table cell |
| ext-test-x-0002 | 01_invoice.jpg | quantity | 1 | table cell |
| ext-test-x-0002 | 01_invoice.jpg | rate | 4,800.00 | table cell |
| ext-test-x-0002 | 01_invoice.jpg | description | Backup storage, 1 TB | table cell |
| ext-test-x-0002 | 01_invoice.jpg | quantity | 2 | table cell |
| ext-test-x-0002 | 01_invoice.jpg | rate | 5,400.00 | table cell |
| ext-test-x-0002 | 01_invoice.jpg | amount | 10,800.00 | table cell |
| ext-test-x-0002 | 01_invoice.jpg | description | Router replacement kit 2 | table cell |
| ext-test-x-0002 | 01_invoice.jpg | quantity | 2 | table cell |
| ext-test-x-0002 | 01_invoice.jpg | rate | 3,250.00 | table cell |
| ext-test-x-0002 | 01_invoice.jpg | amount | 6,500.00 | table cell |
| ext-test-x-0002 | 01_invoice.jpg | gst_rate | 18% | unlisted |
| ext-test-x-0003 | 01_invoice.jpg | billed_to | Temms | unlisted |
| ext-test-x-0003 | 01_invoice.jpg | item_quantity | 2 | table cell |
| ext-test-x-0003 | 01_invoice.jpg | unit_price | 6.900.00 | table cell |
| ext-test-x-0003 | 01_invoice.jpg | line_total | 13.800.00 | table cell |
| ext-test-x-0003 | 01_invoice.jpg | item_quantity | 1 | table cell |
| ext-test-x-0003 | 01_invoice.jpg | unit_price | 4,800.00 | table cell |
| ext-test-x-0003 | 01_invoice.jpg | item_quantity | 2 | table cell |
| ext-test-x-0003 | 01_invoice.jpg | unit_price | 3.250.00 | table cell |
| ext-test-x-0003 | 01_invoice.jpg | line_total | 6.500.00 | table cell |
| ext-test-x-0003 | 01_invoice.jpg | tax_percentage | (18%) | unlisted |
| ext-test-x-0003 | 02_bill.jpg | organization | Kestrel Test Electricity Board | unlisted |
| ext-test-x-0003 | 02_bill.jpg | document_type | Monthly Power Bill | unlisted |
| ext-test-x-0003 | 02_bill.jpg | late_payment_surcharge | Late payment attracts a surcharge. | unlisted |
| ext-test-x-0004 | 01_invoice.pdf | invoice_type | Tax Invoice | unlisted |
| ext-test-x-0004 | 01_invoice.pdf | item_description | Network cabling, 40 m | table cell |
| ext-test-x-0004 | 01_invoice.pdf | item_description | Router replacement kit | table cell |
| ext-test-x-0004 | 01_invoice.pdf | item_description | Wireless access point | table cell |
| ext-test-x-0004 | 01_invoice.pdf | gst_rate | 18% | unlisted |
| ext-test-x-0004 | 02_bill.pdf | company_name | Northwind Test Electricity Board | unlisted |
| ext-test-x-0004 | 02_bill.pdf | bill_type | Electricity Bill | unlisted |
| ext-test-x-0004 | 02_bill.pdf | payment_instructions | Pay at any authorised collection centre or online. | unlisted |
| ext-test-x-0005 | 01_invoice.jpg | item_quantity | 3 | table cell |
| ext-test-x-0005 | 01_invoice.jpg | unit_price | 1,150.00 | table cell |
| ext-test-x-0005 | 01_invoice.jpg | line_total | 3,450.00 | table cell |
| ext-test-x-0005 | 01_invoice.jpg | item_quantity | 40 | unlisted |
| ext-test-x-0005 | 01_invoice.jpg | unit_price | 2,600.00 | table cell |
| ext-test-x-0005 | 01_invoice.jpg | item_quantity | 2 | table cell |
| ext-test-x-0005 | 01_invoice.jpg | unit_price | 6,900.00 | table cell |
| ext-test-x-0005 | 01_invoice.jpg | line_total | 13,800.00 | table cell |
| ext-test-x-0005 | 01_invoice.jpg | tax_rate | (18%) | unlisted |
| ext-test-x-0005 | 02_bill.jpg | payment_options | Pay at any authorised collection centre or online. | unlisted |
| ext-test-x-0006 | 01_invoice.jpg | invoice_type | Tax Invoice | unlisted |
| ext-test-x-0006 | 01_invoice.jpg | quantity | 6 | table cell |
| ext-test-x-0006 | 01_invoice.jpg | rate | 850.00 | table cell |
| ext-test-x-0006 | 01_invoice.jpg | item_description | Laptop stand | table cell |
| ext-test-x-0006 | 01_invoice.jpg | quantity | 3 | table cell |
| ext-test-x-0006 | 01_invoice.jpg | rate | 1,150.00 | table cell |
| ext-test-x-0006 | 01_invoice.jpg | item_description | Router replacement kit | table cell |
| ext-test-x-0006 | 01_invoice.jpg | quantity | 2 | table cell |
| ext-test-x-0006 | 01_invoice.jpg | rate | 3,250.00 | table cell |
| ext-test-x-0006 | 01_invoice.jpg | gst_rate | 18% | unlisted |
| ext-test-x-0006 | 01_invoice.jpg | invoice_type | computer generated | unlisted |
| ext-test-x-0007 | 01_invoice.jpg | item_quantity | 6 | table cell |
| ext-test-x-0007 | 01_invoice.jpg | unit_price | 850.00 | table cell |
| ext-test-x-0007 | 01_invoice.jpg | line_total | 5.100.00 | table cell |
| ext-test-x-0007 | 01_invoice.jpg | item_quantity | 1 | table cell |
| ext-test-x-0007 | 01_invoice.jpg | unit_price | 12,000.00 | table cell |
| ext-test-x-0007 | 01_invoice.jpg | line_total | 12.000.00 | table cell |
| ext-test-x-0007 | 01_invoice.jpg | item_quantity | 2 | table cell |
| ext-test-x-0007 | 01_invoice.jpg | unit_price | 3,250.00 | table cell |
| ext-test-x-0007 | 01_invoice.jpg | line_total | 6,500.00 | table cell |
| ext-test-x-0007 | 01_invoice.jpg | tax_rate | (18%) | unlisted |
| ext-test-x-0007 | 01_invoice.jpg | signature_requirement | Computer generated; no signature required. | unlisted |
| ext-test-x-0007 | 02_bill.jpg | party | Harborview Test Electricity Board | unlisted |
| ext-test-x-0007 | 02_bill.jpg | late_payment_surcharge | Late payment attracts a surcharge | unlisted |
