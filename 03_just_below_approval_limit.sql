-- Test 5: manual entries from 95% up to (not including) the $10,000 approval limit.
SELECT je_id, posted_date, preparer, approver, amount
FROM gl_entries
WHERE source = 'Manual'
  AND amount >= 9500
  AND amount < 10000
ORDER BY je_id;
