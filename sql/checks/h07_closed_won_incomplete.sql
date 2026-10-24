-- H07 Closed-won deal missing amount, close date or term.
-- One row per missing field, so a deal missing two fields shows up twice.
SELECT 'deal' AS object, deal_id AS record_id, 'amount' AS field,
       NULL AS current_value, NULL AS suggested_value, false AS auto_fixable
FROM deals WHERE stage = 'closedwon' AND amount IS NULL
UNION ALL
SELECT 'deal', deal_id, 'close_date', NULL, NULL, false
FROM deals WHERE stage = 'closedwon' AND close_date IS NULL
UNION ALL
SELECT 'deal', deal_id, 'term_months', NULL, NULL, false
FROM deals WHERE stage = 'closedwon' AND term_months IS NULL
ORDER BY record_id, field;
