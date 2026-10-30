-- Test 1: exact duplicate invoices. Same vendor and invoice number posted more than once
-- in the AP subledger. Returns the later posting of each pair.
SELECT g.je_id, g.vendor, g.invoice_no, g.amount, g.posted_date
FROM gl_entries g
WHERE g.source = 'AP'
  AND EXISTS (
        SELECT 1 FROM gl_entries p
        WHERE p.source = 'AP'
          AND p.vendor = g.vendor
          AND p.invoice_no = g.invoice_no
          AND (p.posted_date < g.posted_date
               OR (p.posted_date = g.posted_date AND p.je_id < g.je_id)))
ORDER BY g.je_id;
