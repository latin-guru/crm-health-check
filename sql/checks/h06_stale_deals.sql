-- H06 Stale open deals.
-- An open deal is stale when its close date is before the audit date ($as_of), or when
-- its stage hasn't changed for more than $stale_days days (config/pipeline.yml).
SELECT
    'deal' AS object,
    d.deal_id AS record_id,
    CASE WHEN d.close_date < $as_of THEN 'close_date' ELSE 'last_stage_change_at' END AS field,
    CASE
        WHEN d.close_date < $as_of THEN CAST(d.close_date AS VARCHAR)
        ELSE CAST(CAST(d.last_stage_change_at AS DATE) AS VARCHAR)
    END AS current_value,
    NULL AS suggested_value,
    false AS auto_fixable
FROM deals AS d
JOIN stages AS s ON s.stage_id = d.stage
WHERE NOT s.is_closed
  AND (
      d.close_date < $as_of
      OR date_diff('day', d.last_stage_change_at, CAST($as_of AS TIMESTAMP)) > $stale_days
  )
ORDER BY record_id;
