# Template-free extraction by the local model: measured on the pack of invoices and electricity bills

Model: phi4-mini:3.8b (78fad5d182a7c33065e153a5f8ba210754207ba9d91973f57dffa7f487363753). Split ext-dev, 7 cases, 182 printed facts in 14 documents. 2026-11-05 22:09 India Standard Time 9b269f4

Every value the model read is **inference** (10.4): the words come from the page, the name comes from the model, and nothing here feeds a check or a finding. The counting rules are in the docstring of `evaluation/score_x.py`; in short: a fact is *right* when a model-read field sits at its box (IoU 0.5 or more) under an acceptable name, *misnamed* when the name is not acceptable, *partial* when the field only touches the box (IoU 0.1 to 0.5), *rules* when only the rules' own reading is there, *missing* when nothing is near.

Of 182 printed facts: 18 right, 0 misnamed, 8 partial, 64 rules, 92 missing. Of the 18 right, 16 carry the value as printed.

| kind | facts | right | misnamed | partial | rules | missing |
|---|---|---|---|---|---|---|
| amount | 56 | 2 (4 %) | 0 (0 %) | 0 (0 %) | 45 (80 %) | 9 (16 %) |
| date | 28 | 0 (0 %) | 0 (0 %) | 2 (7 %) | 19 (68 %) | 7 (25 %) |
| id | 35 | 2 (6 %) | 0 (0 %) | 4 (11 %) | 0 (0 %) | 29 (83 %) |
| text | 63 | 14 (22 %) | 0 (0 %) | 2 (3 %) | 0 (0 %) | 47 (75 %) |

| medium | facts | right | misnamed | partial | rules | missing |
|---|---|---|---|---|---|---|
| 120dpi | 26 | 2 (8 %) | 0 (0 %) | 0 (0 %) | 4 (15 %) | 20 (77 %) |
| 150dpi | 52 | 8 (15 %) | 0 (0 %) | 8 (15 %) | 20 (38 %) | 16 (31 %) |
| digital | 52 | 8 (15 %) | 0 (0 %) | 0 (0 %) | 22 (42 %) | 22 (42 %) |
| mild | 52 | 0 (0 %) | 0 (0 %) | 0 (0 %) | 18 (35 %) | 34 (65 %) |

| document | facts | right | misnamed | partial | rules | missing |
|---|---|---|---|---|---|---|
| bill | 105 | 18 (17 %) | 0 (0 %) | 8 (8 %) | 44 (42 %) | 35 (33 %) |
| invoice | 77 | 0 (0 %) | 0 (0 %) | 0 (0 %) | 20 (26 %) | 57 (74 %) |

| layout | facts | right | misnamed | partial | rules | missing |
|---|---|---|---|---|---|---|
| A | 104 | 8 (8 %) | 0 (0 %) | 0 (0 %) | 44 (42 %) | 52 (50 %) |
| B | 78 | 10 (13 %) | 0 (0 %) | 8 (10 %) | 20 (26 %) | 40 (51 %) |

Calls: 14 pages considered, 14 replies accepted, 256 items given, 22 kept. Dropped: 190 source text not found on the page, 20 already read by the rules, 9 value not inside its source text, 1 label too long, 1 same words as an earlier item.
Seconds per page: mean 87.7, median 84.8, longest 122.8 (14 calls).

Extras (model-read fields at no listed fact): none.

## Facts not read right

| case | document | fact | printed | outcome | the model's name and words |
|---|---|---|---|---|---|
| ext-dev-x-0000 | 01_invoice.pdf | seller | Brightfield Test Traders Pvt Ltd | missing | -: - |
| ext-dev-x-0000 | 01_invoice.pdf | invoice_number | INV-2026-7688 | missing | -: - |
| ext-dev-x-0000 | 01_invoice.pdf | po_number | PO-61846 | missing | -: - |
| ext-dev-x-0000 | 01_invoice.pdf | buyer | Vikram D. Joshi | missing | -: - |
| ext-dev-x-0000 | 01_invoice.pdf | payment_terms | Net 30 days | missing | -: - |
| ext-dev-x-0000 | 01_invoice.pdf | bank_account | TST-1698328893 | missing | -: - |
| ext-dev-x-0000 | 01_invoice.pdf | tax | 2,952.00 | missing | -: - |
| ext-dev-x-0001 | 01_invoice.jpg | seller | Silverleaf Test Traders Pvt Ltd | missing | -: - |
| ext-dev-x-0001 | 01_invoice.jpg | invoice_number | INV-2026-7350 | missing | -: - |
| ext-dev-x-0001 | 01_invoice.jpg | invoice_date | 24 Feb 2026 | missing | -: - |
| ext-dev-x-0001 | 01_invoice.jpg | due_date | 11 Mar 2026 | missing | -: - |
| ext-dev-x-0001 | 01_invoice.jpg | po_number | PO-29755 | missing | -: - |
| ext-dev-x-0001 | 01_invoice.jpg | buyer | Anil S. Reddy | missing | -: - |
| ext-dev-x-0001 | 01_invoice.jpg | payment_terms | Net 15 days | missing | -: - |
| ext-dev-x-0001 | 01_invoice.jpg | bank_account | TST-1008088288 | missing | -: - |
| ext-dev-x-0001 | 01_invoice.jpg | tax | Rs. 4,032.00 | missing | -: - |
| ext-dev-x-0001 | 02_bill.jpg | consumer_no | 4500893747 | missing | -: - |
| ext-dev-x-0001 | 02_bill.jpg | bill_number | EB-2026-802751 | missing | -: - |
| ext-dev-x-0001 | 02_bill.jpg | customer | Anil S. Reddy | missing | -: - |
| ext-dev-x-0001 | 02_bill.jpg | service_address | Flat 5, Cedar Villas, Station Road, Indore 452001 | missing | -: - |
| ext-dev-x-0001 | 02_bill.jpg | billing_period | 01/02/2026 to 28/02/2026 | missing | -: - |
| ext-dev-x-0001 | 02_bill.jpg | previous_reading | 52494 | missing | -: - |
| ext-dev-x-0001 | 02_bill.jpg | current_reading | 52966 | missing | -: - |
| ext-dev-x-0001 | 02_bill.jpg | units_consumed | 472 | missing | -: - |
| ext-dev-x-0002 | 01_invoice.jpg | seller | Northwind Test Traders Pvt Ltd | missing | -: - |
| ext-dev-x-0002 | 01_invoice.jpg | invoice_number | INV-2026-3190 | missing | -: - |
| ext-dev-x-0002 | 01_invoice.jpg | po_number | PO-85250 | missing | -: - |
| ext-dev-x-0002 | 01_invoice.jpg | buyer | Meera H. Menon | missing | -: - |
| ext-dev-x-0002 | 01_invoice.jpg | payment_terms | Net 30 days | missing | -: - |
| ext-dev-x-0002 | 01_invoice.jpg | bank_account | TST-7939109314 | missing | -: - |
| ext-dev-x-0002 | 01_invoice.jpg | tax | 4,266.00 | missing | -: - |
| ext-dev-x-0002 | 02_bill.jpg | consumer_no | 9854584182 | partial | connection_id: 9854584182 EB-2026-883312 |
| ext-dev-x-0002 | 02_bill.jpg | bill_number | EB-2026-883312 | partial | connection_id: 9854584182 EB-2026-883312 |
| ext-dev-x-0002 | 02_bill.jpg | due_date | 21 Feb 2026 | partial | cycle_pay_by: 01 Jan 2026 - 31 Jan 2026 21 Feb 2026 |
| ext-dev-x-0002 | 02_bill.jpg | billing_period | 01 Jan 2026 - 31 Jan 2026 | partial | cycle_pay_by: 01 Jan 2026 - 31 Jan 2026 21 Feb 2026 |
| ext-dev-x-0002 | 02_bill.jpg | current_reading | 47432 | missing | -: - |
| ext-dev-x-0003 | 01_invoice.jpg | seller | Harborview Test Traders Pvt Ltd | missing | -: - |
| ext-dev-x-0003 | 01_invoice.jpg | invoice_number | INV-2026-4559 | missing | -: - |
| ext-dev-x-0003 | 01_invoice.jpg | invoice_date | 25 Sep 2026 | missing | -: - |
| ext-dev-x-0003 | 01_invoice.jpg | due_date | 25 Oct 2026 | missing | -: - |
| ext-dev-x-0003 | 01_invoice.jpg | po_number | PO-11792 | missing | -: - |
| ext-dev-x-0003 | 01_invoice.jpg | buyer | Suresh T. Nair | missing | -: - |
| ext-dev-x-0003 | 01_invoice.jpg | payment_terms | Net 30 days | missing | -: - |
| ext-dev-x-0003 | 01_invoice.jpg | bank_account | TST-7498588932 | missing | -: - |
| ext-dev-x-0003 | 01_invoice.jpg | subtotal | Rs. 29,250.00 | missing | -: - |
| ext-dev-x-0003 | 01_invoice.jpg | tax | Rs. 5,265.00 | missing | -: - |
| ext-dev-x-0003 | 01_invoice.jpg | total | Rs. 34,515.00 | missing | -: - |
| ext-dev-x-0003 | 02_bill.jpg | consumer_no | 7865163317 | missing | -: - |
| ext-dev-x-0003 | 02_bill.jpg | bill_number | EB-2026-902781 | missing | -: - |
| ext-dev-x-0003 | 02_bill.jpg | customer | Suresh T. Nair | missing | -: - |
| ext-dev-x-0003 | 02_bill.jpg | service_address | Flat 20, Jasmine Apartments, Station Road, Nagpur 440001 | missing | -: - |
| ext-dev-x-0003 | 02_bill.jpg | due_date | 19 Oct 2026 | missing | -: - |
| ext-dev-x-0003 | 02_bill.jpg | billing_period | 01 Sep 2026 - 30 Sep 2026 | missing | -: - |
| ext-dev-x-0003 | 02_bill.jpg | previous_reading | 35288 | missing | -: - |
| ext-dev-x-0003 | 02_bill.jpg | current_reading | 35712 | missing | -: - |
| ext-dev-x-0003 | 02_bill.jpg | units_consumed | 424 | missing | -: - |
| ext-dev-x-0004 | 01_invoice.pdf | seller | Harborview Test Traders Pvt Ltd | missing | -: - |
| ext-dev-x-0004 | 01_invoice.pdf | invoice_number | INV-2026-6670 | missing | -: - |
| ext-dev-x-0004 | 01_invoice.pdf | po_number | PO-32263 | missing | -: - |
| ext-dev-x-0004 | 01_invoice.pdf | buyer | Meera D. Joshi | missing | -: - |
| ext-dev-x-0004 | 01_invoice.pdf | payment_terms | Net 30 days | missing | -: - |
| ext-dev-x-0004 | 01_invoice.pdf | bank_account | TST-3482137197 | missing | -: - |
| ext-dev-x-0004 | 01_invoice.pdf | tax | 3,330.00 | missing | -: - |
| ext-dev-x-0004 | 02_bill.pdf | consumer_no | 6000163217 | missing | -: - |
| ext-dev-x-0004 | 02_bill.pdf | bill_number | EB-2026-873610 | missing | -: - |
| ext-dev-x-0004 | 02_bill.pdf | customer | Meera D. Joshi | missing | -: - |
| ext-dev-x-0004 | 02_bill.pdf | service_address | Flat 9, Palm Court, Station Road, Pune 411001 | missing | -: - |
| ext-dev-x-0004 | 02_bill.pdf | billing_period | 01/04/2026 to 30/04/2026 | missing | -: - |
| ext-dev-x-0004 | 02_bill.pdf | previous_reading | 76305 | missing | -: - |
| ext-dev-x-0004 | 02_bill.pdf | current_reading | 76473 | missing | -: - |
| ext-dev-x-0004 | 02_bill.pdf | units_consumed | 168 | missing | -: - |
| ext-dev-x-0005 | 01_invoice.jpg | seller | Ironwood Test Traders Pvt Ltd | missing | -: - |
| ext-dev-x-0005 | 01_invoice.jpg | invoice_number | INV-2026-2263 | missing | -: - |
| ext-dev-x-0005 | 01_invoice.jpg | invoice_date | 18 Sep 2026 | missing | -: - |
| ext-dev-x-0005 | 01_invoice.jpg | due_date | 03 Oct 2026 | missing | -: - |
| ext-dev-x-0005 | 01_invoice.jpg | po_number | PO-19007 | missing | -: - |
| ext-dev-x-0005 | 01_invoice.jpg | buyer | Anil S. Reddy | missing | -: - |
| ext-dev-x-0005 | 01_invoice.jpg | payment_terms | Net 15 days | missing | -: - |
| ext-dev-x-0005 | 01_invoice.jpg | bank_account | TST-9598771862 | missing | -: - |
| ext-dev-x-0005 | 01_invoice.jpg | tax | Rs. 2,655.00 | missing | -: - |
| ext-dev-x-0005 | 02_bill.jpg | consumer_no | 1589648881 | missing | -: - |
| ext-dev-x-0005 | 02_bill.jpg | bill_number | EB-2026-133555 | missing | -: - |
| ext-dev-x-0005 | 02_bill.jpg | customer | Anil S. Reddy | missing | -: - |
| ext-dev-x-0005 | 02_bill.jpg | service_address | Flat 3, Jasmine Apartments, Temple Street, Kochi 682001 | missing | -: - |
| ext-dev-x-0005 | 02_bill.jpg | billing_period | 01/09/2026 to 30/09/2026 | missing | -: - |
| ext-dev-x-0005 | 02_bill.jpg | previous_reading | 80571 | missing | -: - |
| ext-dev-x-0005 | 02_bill.jpg | current_reading | 80984 | missing | -: - |
| ext-dev-x-0005 | 02_bill.jpg | units_consumed | 413 | missing | -: - |
| ext-dev-x-0006 | 01_invoice.jpg | seller | Northwind Test Traders Pvt Ltd | missing | -: - |
| ext-dev-x-0006 | 01_invoice.jpg | invoice_number | INV-2026-4144 | missing | -: - |
| ext-dev-x-0006 | 01_invoice.jpg | po_number | PO-36068 | missing | -: - |
| ext-dev-x-0006 | 01_invoice.jpg | buyer | Nikhil M. Pillai | missing | -: - |
| ext-dev-x-0006 | 01_invoice.jpg | payment_terms | Net 45 days | missing | -: - |
| ext-dev-x-0006 | 01_invoice.jpg | bank_account | TST-3201045588 | missing | -: - |
| ext-dev-x-0006 | 01_invoice.jpg | tax | 4,023.00 | missing | -: - |
| ext-dev-x-0006 | 02_bill.jpg | consumer_no | 5137235967 | partial | connection_id: 5137235967 EB-2026-716930 |
| ext-dev-x-0006 | 02_bill.jpg | bill_number | EB-2026-716930 | partial | connection_id: 5137235967 EB-2026-716930 |
| ext-dev-x-0006 | 02_bill.jpg | due_date | 22 Aug 2026 | partial | cycle_pay_by: 01 Jul 2026 - 31 Jul 2026 22 Aug 2026 |
| ext-dev-x-0006 | 02_bill.jpg | billing_period | 01 Jul 2026 - 31 Jul 2026 | partial | cycle_pay_by: 01 Jul 2026 - 31 Jul 2026 22 Aug 2026 |
| ext-dev-x-0006 | 02_bill.jpg | current_reading | 43661 | missing | -: - |
