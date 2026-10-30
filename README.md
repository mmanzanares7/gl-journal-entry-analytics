# General Ledger Journal Entry Analytics

## Project Description

This project tests a full year of synthetic general ledger activity (5,096 journal entries, FY2025) for the kinds of anomalies auditors look for in journal entry testing: duplicate invoices, round-dollar manual entries, weekend postings, entries just under an approval limit, self-approval, late postings after period close, unusual account pairings, and a Benford's law digit analysis. Because I planted a known set of anomalies in the data, I could measure how well each test performs instead of only showing that it returns results. This reflects the data analytics work used in financial statement audits, internal audits and fraud risk assessments, where whole populations are tested instead of small samples.

## Files

| File | Purpose |
|---|---|
| [`scripts/01_generate_gl.py`](scripts/01_generate_gl.py) | Builds the synthetic ledger and plants the anomalies (seeded, so results are reproducible) |
| [`scripts/02_run_tests.py`](scripts/02_run_tests.py) | Runs the eight tests and the Benford analysis, scores them, writes the outputs |
| [`scripts/03_verify_sql.py`](scripts/03_verify_sql.py) | Runs the SQL versions of four tests in SQLite and confirms they match the Python results |
| [`sql/`](sql) | SQL for duplicate invoices, round-dollar entries, just-below-limit entries and self-approval |
| [`data/gl_entries.csv`](data/gl_entries.csv) | The synthetic ledger |
| [`data/seeded_anomalies.csv`](data/seeded_anomalies.csv) | The answer key used only to score the tests |
| [`output/`](output) | Test validation, flagged entries, Benford results, preparer concentration, chart |

Run with `python3 01_generate_gl.py`, then `02_run_tests.py`, then `03_verify_sql.py` from the `scripts` folder. Requires pandas, numpy, scipy and matplotlib.

## The ledger

Each entry has a posting date, effective date, accounting period, source (AP, AR, Payment or Manual), debit and credit account, amount, preparer, approver, and for AP entries a vendor and invoice number. Clean entries follow the rules a healthy process would: amounts are spread across $100 to $100,000 in a way that follows Benford's law, manual entries are posted on business days, the approver is never the preparer, and every entry is posted before its period closes (the 5th of the following month). The approval limit for manual entries is $10,000.

## Tests and results

| Test | Flagged | Planted | Missed | False positives |
|---|---|---|---|---|
| Exact duplicate invoices | 12 | 12 | 0 | 0 |
| Near-duplicate invoices (same vendor and amount, changed invoice number) | 6 | 6 | 0 | 0 |
| Round-dollar manual entries of $5,000 or more | 25 | 25 | 0 | 0 |
| Manual entries posted on a weekend or holiday | 15 | 15 | 0 | 0 |
| Manual entries just below the approval limit ($9,500 to $9,999.99) | 25 | 18 | 0 | 7 |
| Self-approved manual entries | 8 | 8 | 0 | 0 |
| Manual entries posted after period close | 10 | 10 | 0 | 0 |
| Manual entries debiting revenue and crediting cash | 7 | 7 | 0 | 0 |

Every planted anomaly was found. The only false positives came from the approval limit test: 7 legitimate entries happened to fall between $9,500 and $10,000, which is expected when amounts are spread over a wide range. That is why this test needs a second look at who prepared the entries, not just an amount filter.

## One preparer stands out in three separate tests

| Preparer | Manual entries | Just below limit | Share |
|---|---|---|---|
| akim | 173 | 0 | 0.0% |
| bpatel | 187 | 1 | 0.5% |
| cmorales | 185 | 0 | 0.0% |
| dlee | 183 | 2 | 1.1% |
| rjones | 170 | 1 | 0.6% |
| **tnguyen** | 180 | **21** | **11.7%** |

- **Threshold concentration:** tnguyen prepared 21 of the 25 entries just under the limit, about 11.7% of that preparer's manual entries against at most 1.1% for everyone else. This is the pattern of splitting or sizing amounts to avoid an approval.
- **Benford's law:** the full population conforms (MAD 0.0041, close conformity). Tested one preparer at a time, only tnguyen's manual entries deviate (chi-square 63.6, p below 0.001), with a spike of leading 9s that comes from the same near-$10,000 amounts.
- **Self-approval:** three of tnguyen's just-below-limit entries (JE-03610, JE-04375, JE-04635) were also approved by tnguyen, so they carry two flags each.

![Benford's law: all entries compared with tnguyen's manual entries](output/benford_chart.png)

## Entries flagged by more than one test

| Entry | Preparer | Amount | Flags |
|---|---|---|---|
| JE-00310 | dlee | $89,000.00 | Round-dollar; weekend or holiday posting |
| JE-02525 | cmorales | $47,000.00 | Round-dollar; weekend or holiday posting |
| JE-03610 | tnguyen | $9,797.96 | Just below limit; self-approved |
| JE-04375 | tnguyen | $9,930.65 | Just below limit; self-approved |
| JE-04635 | tnguyen | $9,600.15 | Just below limit; self-approved |

These five would go to the top of an auditor's review queue. The full list of 103 flagged entries, sorted by number of flags and then amount, is in [`output/flagged_entries.csv`](output/flagged_entries.csv).

## SQL verification

Four of the tests are also written in SQL and run against the same data in SQLite. All four return exactly the same entries as the Python versions (12, 25, 25 and 8 entries), which confirms the logic does not depend on the tool.

## Limitations

- The data is synthetic and the anomalies are planted, so recall in a real ledger would be lower and noise higher. The answer key shows the logic works; it does not predict real-world accuracy.
- Benford's law needs a reasonably large sample and amounts spread over several orders of magnitude. At around 180 entries per preparer, a 5% significance level would flag roughly 1 preparer in 20 by chance, so a Benford flag is a reason to look closer, not a conclusion.
- A flagged entry is not a finding. Each one needs support reviewed and an explanation from the preparer before anything is reported.

## Summary

I built a reproducible journal entry testing workflow, ran eight audit tests plus a Benford analysis on a 5,000 entry ledger, and measured the results against a known answer key: every planted anomaly was detected, with one test producing predictable false positives. Combining the tests pointed to a single preparer through three independent signals, which is how journal entry testing narrows a population of thousands down to a handful of entries worth an auditor's time.
