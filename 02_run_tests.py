"""Run journal entry tests on the synthetic GL and score them against the seeded answer key.

Eight entry-level tests plus a Benford's law analysis. Outputs go to ../output.
Usage: python3 02_run_tests.py   (run from the scripts directory)
"""
import math

import matplotlib
import numpy as np
import pandas as pd
from scipy.stats import chi2

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HOLIDAYS = pd.to_datetime(["2025-01-01", "2025-01-20", "2025-02-17", "2025-05-26", "2025-06-19",
                           "2025-07-04", "2025-09-01", "2025-10-13", "2025-11-11", "2025-11-27", "2025-12-25"])
APPROVAL_LIMIT = 10_000
BAND_FLOOR = 0.95 * APPROVAL_LIMIT        # 9,500 to 9,999.99 counts as "just below"
ROUND_MIN = 5_000

gl = pd.read_csv("../data/gl_entries.csv", parse_dates=["posted_date", "effective_date"])
seeded = pd.read_csv("../data/seeded_anomalies.csv")
manual = gl[gl["source"] == "Manual"]
ap = gl[gl["source"] == "AP"]

tests = {}   # test name -> set of flagged je_ids

# T1: exact duplicate invoices (same vendor and invoice number). Flag the later posting.
ap_sorted = ap.sort_values(["posted_date", "je_id"])
dup = ap_sorted[ap_sorted.duplicated(["vendor", "invoice_no"], keep="first")]
tests["duplicate_invoice"] = set(dup["je_id"])

# T2: near duplicates (same vendor and amount, different invoice number, within 30 days).
near = set()
for (_, _), grp in ap_sorted.groupby(["vendor", "amount"]):
    if len(grp) < 2:
        continue
    rows = grp.to_dict("records")
    for i in range(1, len(rows)):
        for j in range(i):
            gap = (rows[i]["posted_date"] - rows[j]["posted_date"]).days
            if rows[i]["invoice_no"] != rows[j]["invoice_no"] and gap <= 30:
                near.add(rows[i]["je_id"])
tests["near_duplicate_invoice"] = near

# T3: round-dollar manual entries of $5,000 or more
tests["round_dollar"] = set(manual[(manual["amount"] >= ROUND_MIN) & (manual["amount"] % 1000 == 0)]["je_id"])

# T4: manual entries posted on a weekend or a holiday
off = manual["posted_date"].dt.weekday.ge(5) | manual["posted_date"].isin(HOLIDAYS)
tests["weekend_posting"] = set(manual[off]["je_id"])

# T5: manual entries just below the approval limit
band = manual[(manual["amount"] >= BAND_FLOOR) & (manual["amount"] < APPROVAL_LIMIT)]
tests["just_below_limit"] = set(band["je_id"])

# T6: self-approved manual entries
tests["self_approved"] = set(manual[manual["preparer"] == manual["approver"]]["je_id"])

# T7: manual entries posted after the period closed (close = 5th day of the following month)
eff = manual["effective_date"]
close = pd.to_datetime(dict(year=eff.dt.year + (eff.dt.month == 12), month=eff.dt.month % 12 + 1, day=5))
tests["late_posting"] = set(manual[manual["posted_date"] > close]["je_id"])

# T8: manual entries that debit revenue and credit cash
tests["revenue_to_cash"] = set(manual[(manual["debit_account"] == 4000) & (manual["credit_account"] == 1010)]["je_id"])

# ---- Validation against the answer key ---------------------------------------
labels = {
    "duplicate_invoice": "Exact duplicate invoices", "near_duplicate_invoice": "Near-duplicate invoices",
    "round_dollar": "Round-dollar manual entries", "weekend_posting": "Weekend or holiday postings",
    "just_below_limit": "Just below approval limit", "self_approved": "Self-approved entries",
    "late_posting": "Posted after period close", "revenue_to_cash": "Revenue debited, cash credited",
}
rows = []
for name, flagged in tests.items():
    truth = set(seeded[seeded["anomaly_type"] == name]["je_id"])
    tp, fp, fn = len(flagged & truth), len(flagged - truth), len(truth - flagged)
    rows.append(dict(test=labels[name], flagged=len(flagged), seeded=len(truth), true_positives=tp,
                     false_positives=fp, missed=fn,
                     precision=round(tp / len(flagged), 2) if flagged else None,
                     recall=round(tp / len(truth), 2) if truth else None))
summary = pd.DataFrame(rows)
summary.to_csv("../output/test_validation.csv", index=False)

# ---- Flagged entries and review queue ---------------------------------------
flag_map = {}
for name, ids in tests.items():
    for je in ids:
        flag_map.setdefault(je, []).append(labels[name])
flagged = gl[gl["je_id"].isin(flag_map)].copy()
flagged["flags"] = flagged["je_id"].map(lambda j: "; ".join(flag_map[j]))
flagged["flag_count"] = flagged["je_id"].map(lambda j: len(flag_map[j]))
flagged = flagged.sort_values(["flag_count", "amount"], ascending=[False, False])
flagged.to_csv("../output/flagged_entries.csv", index=False)

# ---- Just-below-limit concentration by preparer ----------------------------
conc = manual.groupby("preparer").agg(manual_entries=("je_id", "count"))
conc["just_below_limit"] = band.groupby("preparer")["je_id"].count()
conc = conc.fillna(0).astype(int)
conc["share_of_entries"] = (conc["just_below_limit"] / conc["manual_entries"]).round(3)
conc.to_csv("../output/threshold_concentration_by_preparer.csv")

# ---- Benford's law ---------------------------------------------------------
expected = np.array([math.log10(1 + 1 / d) for d in range(1, 10)])


def first_digit(series):
    return series.abs().astype(str).str.lstrip("0.").str[0].astype(int)


def benford(series):
    d = first_digit(series)
    n = len(d)
    obs = np.array([(d == k).sum() for k in range(1, 10)])
    share = obs / n
    mad = float(np.abs(share - expected).mean())
    stat = float(((obs - n * expected) ** 2 / (n * expected)).sum())
    return dict(n=n, mad=round(mad, 4), chi_square=round(stat, 1), p_value=float(chi2.sf(stat, 8))), share


def mad_label(m):   # Nigrini's first-digit thresholds (intended for large samples)
    return ("close conformity" if m < 0.006 else "acceptable" if m < 0.012 else
            "marginally acceptable" if m < 0.015 else "nonconformity")


b_all, share_all = benford(gl["amount"])
b_all["mad_reading"] = mad_label(b_all["mad"])
benford_rows = [dict(group="All entries", **b_all)]
shares = {"All entries": share_all}
for p, grp in manual.groupby("preparer"):
    res, sh = benford(grp["amount"])
    res["mad_reading"] = "n/a (small sample)"
    benford_rows.append(dict(group=f"Manual entries: {p}", **res))
    shares[p] = sh
bdf = pd.DataFrame(benford_rows)
bdf["flag_at_5pct"] = bdf["p_value"] < 0.05
bdf["p_value"] = bdf["p_value"].map(lambda x: f"{x:.2g}")
bdf.to_csv("../output/benford_results.csv", index=False)

# ---- Chart -----------------------------------------------------------------
digits = np.arange(1, 10)
fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
for ax, key, title in ((axes[0], "All entries", "All entries (n = %d)" % len(gl)),
                       (axes[1], "tnguyen", "Manual entries by tnguyen (n = %d)" % len(manual[manual.preparer == "tnguyen"]))):
    ax.bar(digits, shares[key], color="#2E75B6", width=0.7, label="Observed")
    ax.plot(digits, expected, color="#C00000", marker="o", lw=2, label="Benford expected")
    ax.set_xticks(digits)
    ax.set_xlabel("Leading digit")
    ax.set_title(title, loc="left", fontsize=11)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
axes[0].set_ylabel("Share of entries")
axes[0].yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
axes[0].legend(frameon=False)
plt.tight_layout()
plt.savefig("../output/benford_chart.png", dpi=130)

# ---- Console summary -------------------------------------------------------
pd.set_option("display.width", 200)
print(summary.to_string(index=False))
print()
print(conc)
print()
print(bdf.to_string(index=False))
print()
print("entries with 2+ flags:", int((flagged["flag_count"] >= 2).sum()))
print(flagged[flagged["flag_count"] >= 2][["je_id", "preparer", "amount", "flags"]].to_string(index=False))
