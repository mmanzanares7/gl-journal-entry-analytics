"""Generate a synthetic general ledger (FY2025) with seeded anomalies.

Base entries are clean: amounts are log-uniform across $100 to $100,000 (which follows
Benford's law), manual entries are posted on business days by someone other than the
approver, and every entry is posted before its period closes.

On top of that, known anomalies are planted so the audit tests in 02_run_tests.py can be
scored against an answer key (data/seeded_anomalies.csv). Real audits have no answer key;
this exists to show whether the tests work.

Usage: python3 01_generate_gl.py   (run from the scripts directory)
"""
import csv
import random
from datetime import date, timedelta

random.seed(2025)

HOLIDAYS = {date(2025, 1, 1), date(2025, 1, 20), date(2025, 2, 17), date(2025, 5, 26),
            date(2025, 6, 19), date(2025, 7, 4), date(2025, 9, 1), date(2025, 10, 13),
            date(2025, 11, 11), date(2025, 11, 27), date(2025, 12, 25)}
START, END = date(2025, 1, 1), date(2025, 12, 31)

PREPARERS = ["akim", "bpatel", "cmorales", "dlee", "tnguyen", "rjones"]
APPROVERS = ["mgr_chen", "mgr_ortiz", "controller_walsh"]
VENDORS = ["Apex Medical Supply", "Harbor Linen Co", "Summit IT Services", "Pinecrest Staffing",
           "Lakeside Lab Partners", "Cardinal Office Products", "Northgate Security", "Brightpath Software",
           "Meridian Facilities", "Keystone Legal LLP", "Evergreen Utilities", "Atlas Courier",
           "Redwood Consulting", "Silverline Telecom", "Ironbridge Maintenance", "Bluewater Catering",
           "Crestview Printing", "Granite Equipment Leasing", "Orchard Pharma Wholesale", "Vantage Analytics",
           "Beacon Insurance Brokers", "Falcon Travel Group", "Harvest Food Service", "Juniper Cleaning",
           "Lighthouse Training Co", "Monarch Furniture", "Nimbus Cloud Hosting", "Oakmont Audit Partners",
           "Pioneer Waste Removal", "Quartz Imaging Supply"]

ACCT = {1010: "Cash", 1200: "Accounts Receivable", 1400: "Prepaid Expenses", 2000: "Accounts Payable",
        2100: "Accrued Liabilities", 4000: "Service Revenue", 5200: "Supplies Expense",
        5300: "Professional Fees", 5400: "Rent Expense", 5500: "IT and Software Expense"}
EXPENSES = [5200, 5300, 5400, 5500]


def is_bizday(d):
    return d.weekday() < 5 and d not in HOLIDAYS


BIZDAYS = [START + timedelta(days=i) for i in range((END - START).days + 1) if is_bizday(START + timedelta(days=i))]
NONBIZ = [START + timedelta(days=i) for i in range((END - START).days + 1) if not is_bizday(START + timedelta(days=i))]


def amount():
    return round(10 ** random.uniform(2, 5), 2)


def period_of(d):
    return f"{d.year}-{d.month:02d}"


entries, seeded, counter, by_key = [], {}, [0], {}


def add(posted, eff, source, dr, cr, amt, prep, appr, vendor="", inv="", desc="", seed=None):
    counter[0] += 1
    key = counter[0]
    by_key[key] = dict(key=key, posted_date=posted, effective_date=eff, source=source, debit_account=dr,
                        credit_account=cr, amount=amt, preparer=prep, approver=appr, vendor=vendor,
                        invoice_no=inv, description=desc)
    entries.append(by_key[key])
    if seed:
        seeded.setdefault(seed, set()).add(key)
    return key


def other_approver(prep):
    return random.choice([a for a in APPROVERS if a != prep])


def manual_entry(posted, amt, prep=None, appr=None, dr=None, cr=None, desc=None, eff=None, seed=None):
    prep = prep or random.choice(PREPARERS)
    appr = appr or other_approver(prep)
    if dr is None:
        kind = random.choice(["accrual", "prepaid", "amort"])
        if kind == "accrual":
            dr, cr, desc = random.choice(EXPENSES), 2100, desc or "Month-end accrual"
        elif kind == "prepaid":
            dr, cr, desc = 1400, 1010, desc or "Prepay annual contract"
        else:
            dr, cr, desc = random.choice(EXPENSES), 1400, desc or "Amortize prepaid"
    eff = eff or posted - timedelta(days=random.randint(0, 3))
    return add(posted, eff, "Manual", dr, cr, amt, prep, appr, desc=desc or "Manual adjustment", seed=seed)


# ---- Clean base population -------------------------------------------------
ap_keys = []
for _ in range(2000):                                   # AP invoices: Dr expense, Cr AP
    d = random.choice(BIZDAYS)
    v = random.choice(VENDORS)
    inv = f"INV-{VENDORS.index(v) + 1:02d}{random.randint(10000, 99999)}"
    ap_keys.append(add(d, d, "AP", random.choice(EXPENSES), 2000, amount(), "SYSTEM", "SYSTEM", v, inv, "Vendor invoice"))
for _ in range(1000):                                   # AR billing: Dr AR, Cr revenue
    d = random.choice(BIZDAYS)
    add(d, d, "AR", 1200, 4000, amount(), "SYSTEM", "SYSTEM", desc="Customer billing")
for _ in range(1000):                                   # Payments: Dr AP, Cr cash
    d = random.choice(BIZDAYS)
    add(d, d, "Payment", 2000, 1010, amount(), "SYSTEM", "SYSTEM", desc="Vendor payment")
for _ in range(1000):                                   # Manual journal entries
    manual_entry(random.choice(BIZDAYS), amount())

# ---- Seeded anomalies ------------------------------------------------------
# A1: exact duplicate invoices (same vendor, invoice number and amount posted again)
early_ap = [k for k in ap_keys if by_key[k]["posted_date"] < date(2025, 11, 1)]
dup_originals = random.sample(early_ap, 12)
for k in dup_originals:
    b = by_key[k]
    later = b["posted_date"] + timedelta(days=random.randint(3, 25))
    while not is_bizday(later):
        later += timedelta(days=1)
    add(later, later, "AP", b["debit_account"], 2000, b["amount"], "SYSTEM", "SYSTEM", b["vendor"],
        b["invoice_no"], "Vendor invoice", seed="duplicate_invoice")

# A2: near duplicates (same vendor and amount, invoice number altered)
for k in random.sample([x for x in early_ap if x not in dup_originals], 6):
    b = by_key[k]
    later = b["posted_date"] + timedelta(days=random.randint(2, 20))
    while not is_bizday(later):
        later += timedelta(days=1)
    add(later, later, "AP", b["debit_account"], 2000, b["amount"], "SYSTEM", "SYSTEM", b["vendor"],
        b["invoice_no"] + "A", "Vendor invoice", seed="near_duplicate_invoice")

# A3: just below the $10,000 approval limit, concentrated with one preparer (tnguyen)
threshold_keys = []
for _ in range(18):
    threshold_keys.append(manual_entry(random.choice(BIZDAYS), round(random.uniform(9500, 9999.99), 2),
                                       prep="tnguyen", seed="just_below_limit"))

# A4: self-approved entries (3 of them by the same tnguyen entries above, 5 elsewhere)
for k in threshold_keys[:3]:
    by_key[k]["approver"] = "tnguyen"
    seeded.setdefault("self_approved", set()).add(k)
for _ in range(5):
    p = random.choice([x for x in PREPARERS if x != "tnguyen"])
    manual_entry(random.choice(BIZDAYS), amount(), prep=p, appr=p, seed="self_approved")

# A5: manual entries posted on weekends or holidays
weekend_keys = []
for _ in range(15):
    weekend_keys.append(manual_entry(random.choice(NONBIZ), amount(), seed="weekend_posting"))

# A6: round-dollar manual entries (2 overlap with weekend postings, 23 new)
for k in weekend_keys[:2]:
    by_key[k]["amount"] = float(random.choice(range(5000, 90001, 1000)))
    seeded.setdefault("round_dollar", set()).add(k)
for _ in range(23):
    manual_entry(random.choice(BIZDAYS), float(random.choice(range(5000, 90001, 1000))), seed="round_dollar")

# A7: entries posted well after the period closed (close = 5th of the following month)
for _ in range(10):
    eff = random.choice([d for d in BIZDAYS if date(2025, 1, 1) <= d <= date(2025, 8, 31)])
    month_end = date(eff.year + (eff.month == 12), eff.month % 12 + 1, 1) - timedelta(days=1)
    posted = month_end + timedelta(days=random.randint(20, 70))
    while not is_bizday(posted):
        posted += timedelta(days=1)
    manual_entry(posted, amount(), eff=eff, seed="late_posting")

# A8: manual entries that debit revenue and credit cash
for _ in range(7):
    p = random.choice(PREPARERS)
    manual_entry(random.choice(BIZDAYS), amount(), prep=p, dr=4000, cr=1010,
                 desc="Revenue adjustment", seed="revenue_to_cash")

# ---- Finalize: sort, assign IDs, write files -------------------------------
entries.sort(key=lambda e: (e["posted_date"], e["key"]))
key_to_id = {}
for i, e in enumerate(entries, 1):
    e["je_id"] = f"JE-{i:05d}"
    key_to_id[e["key"]] = e["je_id"]
    e["period"] = period_of(e["effective_date"])

cols = ["je_id", "posted_date", "effective_date", "period", "source", "debit_account", "credit_account",
        "amount", "preparer", "approver", "vendor", "invoice_no", "description"]
with open("../data/gl_entries.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(entries)

with open("../data/seeded_anomalies.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["anomaly_type", "je_id"])
    for t, keys in sorted(seeded.items()):
        for k in sorted(keys, key=lambda x: key_to_id[x]):
            w.writerow([t, key_to_id[k]])

with open("../data/chart_of_accounts.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["account", "name"])
    for a, n in ACCT.items():
        w.writerow([a, n])

print(f"{len(entries)} entries written")
for t, keys in sorted(seeded.items()):
    print(f"  seeded {t}: {len(keys)}")
