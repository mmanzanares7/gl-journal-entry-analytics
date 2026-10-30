-- Test 6: manual entries where the preparer and approver are the same person.
SELECT je_id, posted_date, preparer, approver, amount
FROM gl_entries
WHERE source = 'Manual'
  AND preparer = approver
ORDER BY je_id;
