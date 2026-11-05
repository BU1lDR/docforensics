# Template-free extraction by the local model: measured on the pack of invoices and electricity bills

Model: qwen3:4b-instruct-2507-q4_K_M (0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0). Split ext-dev, 6 cases, 156 printed facts in 12 documents. 2026-11-05 22:58 India Standard Time 74d2679

Every value the model read is **inference** (10.4): the words come from the page, the name comes from the model, and nothing here feeds a check or a finding. The counting rules are in the docstring of `evaluation/score_x.py`; in short: a fact is *right* when a model-read field sits at its box (IoU 0.5 or more) under an acceptable name, *misnamed* when the name is not acceptable, *partial* when the field only touches the box (IoU 0.1 to 0.5), *rules* when only the rules' own reading is there, *missing* when nothing is near.

Of 156 printed facts: 38 right, 5 misnamed, 34 partial, 54 rules, 25 missing. Of the 38 right, 33 carry the value as printed.

| kind | facts | right | misnamed | partial | rules | missing |
|---|---|---|---|---|---|---|
| amount | 48 | 4 (8 %) | 0 (0 %) | 5 (10 %) | 38 (79 %) | 1 (2 %) |
| date | 24 | 7 (29 %) | 0 (0 %) | 1 (4 %) | 16 (67 %) | 0 (0 %) |
| id | 30 | 9 (30 %) | 0 (0 %) | 9 (30 %) | 0 (0 %) | 12 (40 %) |
| text | 54 | 18 (33 %) | 5 (9 %) | 19 (35 %) | 0 (0 %) | 12 (22 %) |

| medium | facts | right | misnamed | partial | rules | missing |
|---|---|---|---|---|---|---|
| 120dpi | 26 | 12 (46 %) | 1 (4 %) | 7 (27 %) | 4 (15 %) | 2 (8 %) |
| 150dpi | 26 | 7 (27 %) | 1 (4 %) | 6 (23 %) | 10 (38 %) | 2 (8 %) |
| digital | 52 | 1 (2 %) | 1 (2 %) | 11 (21 %) | 22 (42 %) | 17 (33 %) |
| mild | 52 | 18 (35 %) | 2 (4 %) | 10 (19 %) | 18 (35 %) | 4 (8 %) |

| document | facts | right | misnamed | partial | rules | missing |
|---|---|---|---|---|---|---|
| bill | 90 | 17 (19 %) | 0 (0 %) | 17 (19 %) | 38 (42 %) | 18 (20 %) |
| invoice | 66 | 21 (32 %) | 5 (8 %) | 17 (26 %) | 16 (24 %) | 7 (11 %) |

| layout | facts | right | misnamed | partial | rules | missing |
|---|---|---|---|---|---|---|
| A | 93 | 3 (3 %) | 2 (2 %) | 27 (29 %) | 40 (43 %) | 21 (23 %) |
| B | 63 | 35 (56 %) | 3 (5 %) | 7 (11 %) | 14 (22 %) | 4 (6 %) |

Calls: 12 pages considered, 10 replies accepted, 195 items given, 174 kept. Dropped: 14 already read by the rules, 3 source text not found on the page, 2 value not inside its source text, 2 same words as an earlier item; 0 beyond the limit.
Seconds per page: mean 108.9, median 108.9, longest 152.7 (11 calls).

Extras (model-read fields at no listed fact): 61 unlisted, 38 table cell.

## Facts not read right

| case | document | fact | printed | outcome | the model's name and words |
|---|---|---|---|---|---|
| ext-dev-x-0000 | 01_invoice.pdf | seller | Brightfield Test Traders Pvt Ltd | misnamed | party: Brightfield Test Traders Pvt Ltd |
| ext-dev-x-0000 | 01_invoice.pdf | invoice_number | INV-2026-7688 | partial | invoice_number: Invoice No INV-2026-7688 |
| ext-dev-x-0000 | 01_invoice.pdf | po_number | PO-61846 | partial | po_reference: PO Reference PO-61846 |
| ext-dev-x-0000 | 01_invoice.pdf | buyer | Vikram D. Joshi | partial | bill_to: Bill To Vikram D. Joshi |
| ext-dev-x-0000 | 01_invoice.pdf | payment_terms | Net 30 days | partial | payment_terms: Payment Terms Net 30 days |
| ext-dev-x-0000 | 01_invoice.pdf | bank_account | TST-1698328893 | partial | pay_to_account: Pay to Account TST-1698328893 |
| ext-dev-x-0000 | 01_invoice.pdf | tax | 2,952.00 | partial | gst_amount: GST @ 18% 2,952.00 |
| ext-dev-x-0000 | 02_bill.pdf | consumer_no | 3599687351 | missing | -: - |
| ext-dev-x-0000 | 02_bill.pdf | bill_number | EB-2026-258556 | partial | bill_no: Bill No EB-2026-258556 |
| ext-dev-x-0000 | 02_bill.pdf | customer | Vikram D. Joshi | partial | customer_name: Customer Name Vikram D. Joshi |
| ext-dev-x-0000 | 02_bill.pdf | billing_period | 01/05/2026 to 31/05/2026 | partial | billing_period: Billing Period 01/05/2026 to 31/05/2026 |
| ext-dev-x-0000 | 02_bill.pdf | previous_reading | 17775 | partial | previous_reading: Previous Reading 17775 |
| ext-dev-x-0000 | 02_bill.pdf | current_reading | 18165 | partial | current_reading: Current Reading 18165 |
| ext-dev-x-0000 | 02_bill.pdf | units_consumed | 390 | missing | -: - |
| ext-dev-x-0001 | 01_invoice.jpg | seller | Silverleaf Test Traders Pvt Ltd | misnamed | party: Silverleaf Test Traders Pvt Ltd |
| ext-dev-x-0001 | 02_bill.jpg | consumer_no | 4500893747 | missing | -: - |
| ext-dev-x-0001 | 02_bill.jpg | bill_number | EB-2026-802751 | partial | bill_no: Bill No EB-2026-802751 |
| ext-dev-x-0001 | 02_bill.jpg | customer | Anil S. Reddy | partial | customer_name: Customer Name Anil S. Reddy |
| ext-dev-x-0001 | 02_bill.jpg | billing_period | 01/02/2026 to 28/02/2026 | partial | billing_period: Billing Period 01/02/2026 to 28/02/2026 |
| ext-dev-x-0001 | 02_bill.jpg | previous_reading | 52494 | partial | previous_reading: Previous Reading 52494 |
| ext-dev-x-0001 | 02_bill.jpg | current_reading | 52966 | partial | current_reading: Current Reading 52966 |
| ext-dev-x-0001 | 02_bill.jpg | units_consumed | 472 | missing | -: - |
| ext-dev-x-0002 | 01_invoice.jpg | seller | Northwind Test Traders Pvt Ltd | misnamed | party: Northwind Test Traders Pvt Ltd |
| ext-dev-x-0002 | 01_invoice.jpg | invoice_number | INV-2026-3190 | partial | invoice_number: Invoice No INV-2026-3190 |
| ext-dev-x-0002 | 01_invoice.jpg | po_number | PO-85250 | partial | po_reference: PO Reference PO-85250 |
| ext-dev-x-0002 | 01_invoice.jpg | buyer | Meera H. Menon | partial | bill_to: Bill To Meera H. Menon |
| ext-dev-x-0002 | 01_invoice.jpg | payment_terms | Net 30 days | partial | payment_terms: Payment Terms Net 30 days |
| ext-dev-x-0002 | 01_invoice.jpg | bank_account | TST-7939109314 | partial | pay_to_account: Pay to Account TST-7939109314 |
| ext-dev-x-0002 | 01_invoice.jpg | tax | 4,266.00 | partial | gst_amount: GST @ 18% 4,266.00 |
| ext-dev-x-0002 | 02_bill.jpg | consumer_no | 9854584182 | missing | -: - |
| ext-dev-x-0002 | 02_bill.jpg | bill_number | EB-2026-883312 | missing | -: - |
| ext-dev-x-0003 | 01_invoice.jpg | seller | Harborview Test Traders Pvt Ltd | misnamed | party: Harborview Test Traders Pvt Ltd |
| ext-dev-x-0003 | 01_invoice.jpg | buyer | Suresh T. Nair | partial | terms: Suresh T. Nair Net 30 days |
| ext-dev-x-0003 | 01_invoice.jpg | payment_terms | Net 30 days | partial | terms: Suresh T. Nair Net 30 days |
| ext-dev-x-0003 | 01_invoice.jpg | subtotal | Rs. 29,250.00 | partial | amount_before_tax: Amount before tax Rs. 29.250.00 |
| ext-dev-x-0003 | 01_invoice.jpg | tax | Rs. 5,265.00 | partial | tax_amount: Tax (18%) Rs. 5.265.00 |
| ext-dev-x-0003 | 01_invoice.jpg | total | Rs. 34,515.00 | partial | amount_payable: Amount Payable Rs. 34.515.00 |
| ext-dev-x-0003 | 02_bill.jpg | consumer_no | 7865163317 | missing | -: - |
| ext-dev-x-0003 | 02_bill.jpg | bill_number | EB-2026-902781 | missing | -: - |
| ext-dev-x-0003 | 02_bill.jpg | due_date | 19 Oct 2026 | partial | cycle_pay_by: 01p 6 - p 26 19 Oct 2026 |
| ext-dev-x-0003 | 02_bill.jpg | billing_period | 01 Sep 2026 - 30 Sep 2026 | partial | cycle_pay_by: 01p 6 - p 26 19 Oct 2026 |
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
| ext-dev-x-0005 | 01_invoice.jpg | seller | Ironwood Test Traders Pvt Ltd | misnamed | party: Ironwood Test Traders Pvt Ltd |
| ext-dev-x-0005 | 02_bill.jpg | consumer_no | 1589648881 | missing | -: - |
| ext-dev-x-0005 | 02_bill.jpg | bill_number | EB-2026-133555 | partial | bill_no: Bill No EB-2026-133555 |
| ext-dev-x-0005 | 02_bill.jpg | customer | Anil S. Reddy | partial | customer_name: Customer Name Anil S. Reddy |
| ext-dev-x-0005 | 02_bill.jpg | billing_period | 01/09/2026 to 30/09/2026 | partial | billing_period: Billing Period 01/09/2026 to 30/09/2026 |
| ext-dev-x-0005 | 02_bill.jpg | previous_reading | 80571 | partial | previous_reading: Previous Reading 80571 |
| ext-dev-x-0005 | 02_bill.jpg | current_reading | 80984 | partial | current_reading: Current Reading 80984 |
| ext-dev-x-0005 | 02_bill.jpg | units_consumed | 413 | missing | -: - |

## Extras

| case | document | name | words | where |
|---|---|---|---|---|
| ext-dev-x-0000 | 01_invoice.pdf | document_type | Tax Invoice | unlisted |
| ext-dev-x-0000 | 01_invoice.pdf | invoice_date | Invoice Date 05/05/2026 | unlisted |
| ext-dev-x-0000 | 01_invoice.pdf | due_date | Due Date 04/06/2026 | unlisted |
| ext-dev-x-0000 | 01_invoice.pdf | description | Description Qty Rate Amount | unlisted |
| ext-dev-x-0000 | 01_invoice.pdf | item_description_1 | Router replacement kit 2 3,250.00 6,500.00 | table cell |
| ext-dev-x-0000 | 01_invoice.pdf | item_description_2 | Support hours 6 850.00 5,100.00 | table cell |
| ext-dev-x-0000 | 01_invoice.pdf | item_description_3 | Cloud hosting, monthly 1 4,800.00 4,800.00 | table cell |
| ext-dev-x-0000 | 01_invoice.pdf | subtotal | Subtotal 16,400.00 | unlisted |
| ext-dev-x-0000 | 01_invoice.pdf | total_amount | Total 19,352.00 | unlisted |
| ext-dev-x-0000 | 01_invoice.pdf | invoice_note | This is a computer generated invoice. | unlisted |
| ext-dev-x-0000 | 02_bill.pdf | party | Silverleaf Test Electricity Board | unlisted |
| ext-dev-x-0000 | 02_bill.pdf | document_type | Electricity Bill | unlisted |
| ext-dev-x-0000 | 02_bill.pdf | bill_date | Bill Date 03/06/2026 | unlisted |
| ext-dev-x-0000 | 02_bill.pdf | due_date | Due Date 18/06/2026 | unlisted |
| ext-dev-x-0000 | 02_bill.pdf | units_consumed_kwh | Units Consumed (kWh) 390 | unlisted |
| ext-dev-x-0000 | 02_bill.pdf | energy_charges | Energy Charges 2,437.50 | unlisted |
| ext-dev-x-0000 | 02_bill.pdf | fixed_charges | Fixed Charges 120.00 | unlisted |
| ext-dev-x-0000 | 02_bill.pdf | electricity_duty | Electricity Duty 146.25 | unlisted |
| ext-dev-x-0000 | 02_bill.pdf | net_amount_payable | Net Amount Payable 2,703.75 | unlisted |
| ext-dev-x-0000 | 02_bill.pdf | amount_payable_after_due_date | Amount Payable After Due Date 2,757.83 | unlisted |
| ext-dev-x-0000 | 02_bill.pdf | payment_method | Pay at any authorised collection centre or online. | unlisted |
| ext-dev-x-0001 | 01_invoice.jpg | document_type | Invoice | unlisted |
| ext-dev-x-0001 | 01_invoice.jpg | item | Support hours | table cell |
| ext-dev-x-0001 | 01_invoice.jpg | quantity_support_hours | 6 | table cell |
| ext-dev-x-0001 | 01_invoice.jpg | unit_price_support_hours | 850.00 | table cell |
| ext-dev-x-0001 | 01_invoice.jpg | line_total_support_hours | 5,100.00 | table cell |
| ext-dev-x-0001 | 01_invoice.jpg | item_2 | Backup storage, 1 TB | table cell |
| ext-dev-x-0001 | 01_invoice.jpg | quantity_backup_storage | 2 | table cell |
| ext-dev-x-0001 | 01_invoice.jpg | unit_price_backup_storage | 5,400.00 | table cell |
| ext-dev-x-0001 | 01_invoice.jpg | line_total_backup_storage | 10,800.00 | table cell |
| ext-dev-x-0001 | 01_invoice.jpg | item_3 | Router replacement kit | table cell |
| ext-dev-x-0001 | 01_invoice.jpg | unit_price_router_replacement_kit | 3,250.00 | table cell |
| ext-dev-x-0001 | 01_invoice.jpg | line_total_router_replacement_kit | 6,500.00 | table cell |
| ext-dev-x-0001 | 01_invoice.jpg | tax_percentage | (18%) | unlisted |
| ext-dev-x-0001 | 02_bill.jpg | party | Ironwood Test Electricity Board | unlisted |
| ext-dev-x-0001 | 02_bill.jpg | document_type | Electricity Bill | unlisted |
| ext-dev-x-0001 | 02_bill.jpg | bill_date | Bill Date 04/03/2026 | unlisted |
| ext-dev-x-0001 | 02_bill.jpg | due_date | Due Date 19/03/2026 | unlisted |
| ext-dev-x-0001 | 02_bill.jpg | units_consumed_kwh | Units Consumed (kWh) 472 | unlisted |
| ext-dev-x-0001 | 02_bill.jpg | energy_charges | Energy Charges 2,950.00 | unlisted |
| ext-dev-x-0001 | 02_bill.jpg | fixed_charges | Fixed Charges 210.00 | unlisted |
| ext-dev-x-0001 | 02_bill.jpg | electricity_duty | Electricity Duty 177.00 | unlisted |
| ext-dev-x-0001 | 02_bill.jpg | net_amount_payable | Net Amount Payable 3,337.00 | unlisted |
| ext-dev-x-0001 | 02_bill.jpg | amount_payable_after_due_date | Amount Payable After Due Date 3,403.74 | unlisted |
| ext-dev-x-0001 | 02_bill.jpg | payment_method | Pay at any authorised collection centre or online. | unlisted |
| ext-dev-x-0002 | 01_invoice.jpg | document_type | Tax Invoice | unlisted |
| ext-dev-x-0002 | 01_invoice.jpg | invoice_date | Invoice Date 23/01/2026 | unlisted |
| ext-dev-x-0002 | 01_invoice.jpg | due_date | Due Date 22/02/2026 | unlisted |
| ext-dev-x-0002 | 01_invoice.jpg | description | Description Qty Rate Amount | unlisted |
| ext-dev-x-0002 | 01_invoice.jpg | item_description | Wireless access point 2 6,900.00 13,800.00 | unlisted |
| ext-dev-x-0002 | 01_invoice.jpg | item_description | Cloud hosting, monthly 1 4,800.00 4,800.00 | table cell |
| ext-dev-x-0002 | 01_invoice.jpg | item_description | Support hours 6 850.00 5,100.00 | unlisted |
| ext-dev-x-0002 | 01_invoice.jpg | subtotal | Subtotal 23,700.00 | unlisted |
| ext-dev-x-0002 | 01_invoice.jpg | total_amount | Total 27,966.00 | unlisted |
| ext-dev-x-0002 | 01_invoice.jpg | invoice_note | This is a computer generated invoice. | unlisted |
| ext-dev-x-0002 | 02_bill.jpg | organization | Harborview Test Electricity Board | unlisted |
| ext-dev-x-0002 | 02_bill.jpg | document_type | Monthly Power Bill | unlisted |
| ext-dev-x-0002 | 02_bill.jpg | late_payment_surchage | Late payment attracts a surcharge. | unlisted |
| ext-dev-x-0003 | 01_invoice.jpg | document_type | Invoice | unlisted |
| ext-dev-x-0003 | 01_invoice.jpg | item | Laptop stand | table cell |
| ext-dev-x-0003 | 01_invoice.jpg | quantity_laptop_stand | 3 | table cell |
| ext-dev-x-0003 | 01_invoice.jpg | unit_price_laptop_stand | 1.150.00 | table cell |
| ext-dev-x-0003 | 01_invoice.jpg | line_total_laptop_stand | 3.450.00 | table cell |
| ext-dev-x-0003 | 01_invoice.jpg | item_2 | Wres sae ss sa eoint | table cell |
| ext-dev-x-0003 | 01_invoice.jpg | quantity_item_2 | 2 | table cell |
| ext-dev-x-0003 | 01_invoice.jpg | unit_price_item_2 | 6,900.00 | table cell |
| ext-dev-x-0003 | 01_invoice.jpg | line_total_item_2 | 13.800.00 | table cell |
| ext-dev-x-0003 | 01_invoice.jpg | item_3 | Annual maintenance contract | table cell |
| ext-dev-x-0003 | 01_invoice.jpg | quantity_item_3 | 1 | table cell |
| ext-dev-x-0003 | 01_invoice.jpg | unit_price_item_3 | 12,000.00 | table cell |
| ext-dev-x-0003 | 01_invoice.jpg | line_total_item_3 | 12.000.00 | table cell |
| ext-dev-x-0003 | 01_invoice.jpg | signature_required | signature required | unlisted |
| ext-dev-x-0003 | 02_bill.jpg | party | Harborview Test Electricity Board | unlisted |
| ext-dev-x-0003 | 02_bill.jpg | document_type | Monthly Power Bill | unlisted |
| ext-dev-x-0003 | 02_bill.jpg | late_payment_term | Late payment attracts a surcharge | unlisted |
| ext-dev-x-0005 | 01_invoice.jpg | document_type | Invoice | unlisted |
| ext-dev-x-0005 | 01_invoice.jpg | item | Router replacement kit | table cell |
| ext-dev-x-0005 | 01_invoice.jpg | quantity | 2 | table cell |
| ext-dev-x-0005 | 01_invoice.jpg | unit_price | 3,250.00 | table cell |
| ext-dev-x-0005 | 01_invoice.jpg | line_total | 6,500.00 | table cell |
| ext-dev-x-0005 | 01_invoice.jpg | item | Laptop stand | table cell |
| ext-dev-x-0005 | 01_invoice.jpg | quantity | 3 | table cell |
| ext-dev-x-0005 | 01_invoice.jpg | unit_price | 1,150.00 | table cell |
| ext-dev-x-0005 | 01_invoice.jpg | line_total | 3,450.00 | table cell |
| ext-dev-x-0005 | 01_invoice.jpg | item | Cloud hosting, monthly | table cell |
| ext-dev-x-0005 | 01_invoice.jpg | quantity | 1 | table cell |
| ext-dev-x-0005 | 01_invoice.jpg | unit_price | 4,800.00 | table cell |
| ext-dev-x-0005 | 01_invoice.jpg | tax_percentage | 18 | unlisted |
| ext-dev-x-0005 | 02_bill.jpg | party | Northwind Test Electricity Board | unlisted |
| ext-dev-x-0005 | 02_bill.jpg | document_type | Electricity Bill | unlisted |
| ext-dev-x-0005 | 02_bill.jpg | bill_date | Bill Date 07/10/2026 | unlisted |
| ext-dev-x-0005 | 02_bill.jpg | due_date | Due Date 22/10/2026 | unlisted |
| ext-dev-x-0005 | 02_bill.jpg | units_consumed_kwh | Units Consumed (kWh) 413 | unlisted |
| ext-dev-x-0005 | 02_bill.jpg | energy_charges | Energy Charges 2,271.50 | unlisted |
| ext-dev-x-0005 | 02_bill.jpg | fixed_charges | Fixed Charges 120.00 | unlisted |
| ext-dev-x-0005 | 02_bill.jpg | electricity_duty | Electricity Duty 136.29 | unlisted |
| ext-dev-x-0005 | 02_bill.jpg | net_amount_payable | Net Amount Payable 2,527.79 | unlisted |
| ext-dev-x-0005 | 02_bill.jpg | amount_payable_after_due_date | Amount Payable After Due Date 2,578.35 | unlisted |
| ext-dev-x-0005 | 02_bill.jpg | payment_method | Pay at any authorised collection centre or online. | unlisted |
