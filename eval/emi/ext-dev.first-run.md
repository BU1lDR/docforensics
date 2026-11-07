# Declared-EMI check on the ext-dev pack (whole tool)

Run: 2026-11-07 16:31 India Standard Time, commit 97ed34c, Windows 10, Python 3.11.9, 6 cores, CPU only.
44 cases (seeds 3400000 to 3400043), 175 s in all, 4.0 s a case.

A case is a loan application and a bank statement of one month, as digital PDFs or as mild scans. Some rows of the statement are set by datagen/emi_pack.py, which also fixed, before the check was run on the pack, what each kind must show. The instalments are narrated with the words the check reads (EMI, instalment, loan), so this is a measurement by construction: it shows what the check does with those wordings on statements and applications made by this project's generator. It says nothing about how often a real instalment is narrated like that, and nothing about other layouts or other producers. The kind lender-only is a gap the check cannot read; it is counted apart.

## In short

- Cases with nothing to find (28): a finding on 0, which is a false flag.
- Cases with a gap the check reads (12): found on 6; missed: ext-dev-m-0018, ext-dev-m-0019, ext-dev-m-0020, ext-dev-m-0040, ext-dev-m-0041, ext-dev-m-0042.
- In the cases found, the finding named the instalments' total correctly on 6 of 6.
- Cases with a gap the check cannot read (4, kind lender-only): found on 0.
- Cases where the dossier says the check could not compare: 0.
- Possible extraction errors raised by the check (a difference read from a doubtful figure or page, shown as a limitation): 0.
- Findings of other checks on these cases: 5 (context_emi: Context rule: monthly obligations are 116% of declared income on ext-dev-m-0025; context_emi: Context rule: monthly obligations are 53% of declared income on ext-dev-m-0030; context_emi: Context rule: monthly obligations are 54% of declared income on ext-dev-m-0009; context_emi: Context rule: monthly obligations are 69% of declared income on ext-dev-m-0026; context_emi: Context rule: monthly obligations are 92% of declared income on ext-dev-m-0000).

## By kind

| kind | gap | cases | found | missed | false flags |
|---|---|---|---|---|---|
| none | no | 4 | 0 | 0 | 0 |
| match | no | 4 | 0 | 0 | 0 |
| rounded | no | 4 | 0 | 0 | 0 |
| two-loans | no | 4 | 0 | 0 | 0 |
| declared-higher | no | 4 | 0 | 0 | 0 |
| fee-not-emi | no | 4 | 0 | 0 | 0 |
| lookalike | no | 4 | 0 | 0 | 0 |
| under-zero | yes | 4 | 2 | 2 | 0 |
| under-part | yes | 4 | 2 | 2 | 0 |
| under-some | yes | 4 | 2 | 2 | 0 |
| lender-only | yes, not readable | 4 | 0 | 4 | 0 |

## By medium and layout

| medium | layout | cases | gaps read: found of planted | false flags |
|---|---|---|---|---|
| digital | A | 11 | 3 of 3 | 0 |
| digital | B | 11 | 0 of 3 | 0 |
| scan | A | 11 | 3 of 3 | 0 |
| scan | B | 11 | 0 of 3 | 0 |

## Every case

| case | kind | layout | medium | declared | instalments | expected | shown | total named | limitations | not compared | other findings | s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ext-dev-m-0000 | none | A | digital | 4000.00 | - | - | - | - | - | - | context_emi: Context rule: monthly obligations are 92% of declared income | 1.0 |
| ext-dev-m-0001 | match | A | digital | 11500.00 | - | - | - | - | - | - | - | 0.9 |
| ext-dev-m-0002 | rounded | A | digital | 8000.00 | - | - | - | - | - | - | - | 0.9 |
| ext-dev-m-0003 | two-loans | A | digital | 37000.00 | - | - | - | - | - | - | - | 0.9 |
| ext-dev-m-0004 | declared-higher | A | digital | 17000.00 | - | - | - | - | - | - | - | 0.9 |
| ext-dev-m-0005 | fee-not-emi | A | digital | 3000.00 | - | - | - | - | - | - | - | 0.9 |
| ext-dev-m-0006 | lookalike | A | digital | 2000.00 | - | - | - | - | - | - | - | 1.0 |
| ext-dev-m-0007 | under-zero | A | digital | 0.00 | 18000.00 | yes | yes | yes | - | - | - | 1.0 |
| ext-dev-m-0008 | under-part | A | digital | 3000.00 | 8000.00 | yes | yes | yes | - | - | - | 1.0 |
| ext-dev-m-0009 | under-some | A | digital | 8000.00 | 12000.00 | yes | yes | yes | - | - | context_emi: Context rule: monthly obligations are 54% of declared income | 1.1 |
| ext-dev-m-0010 | lender-only | A | digital | 0.00 | 2500.00 | yes | - | - | - | - | - | 0.9 |
| ext-dev-m-0011 | none | B | digital | 6000.00 | - | - | - | - | - | - | - | 1.0 |
| ext-dev-m-0012 | match | B | digital | 5000.00 | - | - | - | - | - | - | - | 0.9 |
| ext-dev-m-0013 | rounded | B | digital | 7000.00 | - | - | - | - | - | - | - | 0.9 |
| ext-dev-m-0014 | two-loans | B | digital | 36000.00 | - | - | - | - | - | - | - | 1.0 |
| ext-dev-m-0015 | declared-higher | B | digital | 15500.00 | - | - | - | - | - | - | - | 0.9 |
| ext-dev-m-0016 | fee-not-emi | B | digital | 0.00 | - | - | - | - | - | - | - | 1.0 |
| ext-dev-m-0017 | lookalike | B | digital | 10000.00 | - | - | - | - | - | - | - | 0.9 |
| ext-dev-m-0018 | under-zero | B | digital | 0.00 | 3000.00 | yes | - | - | - | - | - | 0.9 |
| ext-dev-m-0019 | under-part | B | digital | 2000.00 | 21500.00 | yes | - | - | - | - | - | 0.9 |
| ext-dev-m-0020 | under-some | B | digital | 4000.00 | 7000.00 | yes | - | - | - | - | - | 1.0 |
| ext-dev-m-0021 | lender-only | B | digital | 0.00 | 17000.00 | yes | - | - | - | - | - | 1.0 |
| ext-dev-m-0022 | none | A | scan | 9000.00 | - | - | - | - | - | - | - | 7.6 |
| ext-dev-m-0023 | match | A | scan | 3500.00 | - | - | - | - | - | - | - | 6.8 |
| ext-dev-m-0024 | rounded | A | scan | 7000.00 | - | - | - | - | - | - | - | 7.0 |
| ext-dev-m-0025 | two-loans | A | scan | 30500.00 | - | - | - | - | - | - | context_emi: Context rule: monthly obligations are 116% of declared income | 6.8 |
| ext-dev-m-0026 | declared-higher | A | scan | 15500.00 | - | - | - | - | - | - | context_emi: Context rule: monthly obligations are 69% of declared income | 7.0 |
| ext-dev-m-0027 | fee-not-emi | A | scan | 2000.00 | - | - | - | - | - | - | - | 6.7 |
| ext-dev-m-0028 | lookalike | A | scan | 5000.00 | - | - | - | - | - | - | - | 6.7 |
| ext-dev-m-0029 | under-zero | A | scan | 0.00 | 10000.00 | yes | yes | yes | - | - | - | 7.2 |
| ext-dev-m-0030 | under-part | A | scan | 17000.00 | 26500.00 | yes | yes | yes | - | - | context_emi: Context rule: monthly obligations are 53% of declared income | 7.1 |
| ext-dev-m-0031 | under-some | A | scan | 9000.00 | 13000.00 | yes | yes | yes | - | - | - | 6.9 |
| ext-dev-m-0032 | lender-only | A | scan | 0.00 | 5500.00 | yes | - | - | - | - | - | 6.8 |
| ext-dev-m-0033 | none | B | scan | 6000.00 | - | - | - | - | - | - | - | 7.0 |
| ext-dev-m-0034 | match | B | scan | 18000.00 | - | - | - | - | - | - | - | 6.8 |
| ext-dev-m-0035 | rounded | B | scan | 10000.00 | - | - | - | - | - | - | - | 6.9 |
| ext-dev-m-0036 | two-loans | B | scan | 32500.00 | - | - | - | - | - | - | - | 6.9 |
| ext-dev-m-0037 | declared-higher | B | scan | 24000.00 | - | - | - | - | - | - | - | 6.7 |
| ext-dev-m-0038 | fee-not-emi | B | scan | 10000.00 | - | - | - | - | - | - | - | 6.9 |
| ext-dev-m-0039 | lookalike | B | scan | 0.00 | - | - | - | - | - | - | - | 6.9 |
| ext-dev-m-0040 | under-zero | B | scan | 0.00 | 9000.00 | yes | - | - | - | - | - | 7.3 |
| ext-dev-m-0041 | under-part | B | scan | 18500.00 | 36500.00 | yes | - | - | - | - | - | 7.2 |
| ext-dev-m-0042 | under-some | B | scan | 13000.00 | 19000.00 | yes | - | - | - | - | - | 7.3 |
| ext-dev-m-0043 | lender-only | B | scan | 0.00 | 3000.00 | yes | - | - | - | - | - | 7.2 |
