-- Test 3: round-dollar manual entries of $5,000 or more (exact multiples of $1,000).
SELECT je_id, posted_date, preparer, approver, amount
FROM gl_entries
WHERE source = 'Manual'
  AND amount >= 5000
  AND (CAST(ROUND(amount * 100) AS INTEGER) % 100000) = 0
ORDER BY je_id;
