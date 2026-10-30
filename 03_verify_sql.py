"""Run the four SQL tests in SQLite and confirm they flag the same entries as the pandas tests.
Usage: python3 03_verify_sql.py   (run from the scripts directory)
"""
import sqlite3
import pandas as pd

gl = pd.read_csv("../data/gl_entries.csv")
flagged = pd.read_csv("../output/flagged_entries.csv")
con = sqlite3.connect(":memory:")
gl.to_sql("gl_entries", con, index=False)

checks = {
    "01_duplicate_invoices.sql": "Exact duplicate invoices",
    "02_round_dollar_entries.sql": "Round-dollar manual entries",
    "03_just_below_approval_limit.sql": "Just below approval limit",
    "04_self_approved_entries.sql": "Self-approved entries",
}
ok = True
for fname, label in checks.items():
    sql_ids = set(pd.read_sql(open(f"../sql/{fname}").read(), con)["je_id"])
    py_ids = set(flagged[flagged["flags"].str.contains(label, regex=False)]["je_id"])
    match = sql_ids == py_ids
    ok &= match
    print(f"{fname:38s} SQL {len(sql_ids):3d}  pandas {len(py_ids):3d}  {'MATCH' if match else 'MISMATCH'}")
raise SystemExit(0 if ok else 1)
