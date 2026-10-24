-- Stage-to-stage conversion from deal_stage_history.
-- reached = deals that ever entered the stage. Conversion to the next stage (closed won
-- after the last open stage) = reached(next) / reached(this).
WITH reached AS (
    SELECT s.stage_id, s.label, s.stage_order, count(DISTINCT h.deal_id) AS deals_reached
    FROM stages AS s
    LEFT JOIN deal_stage_history AS h ON h.to_stage = s.stage_id
    WHERE s.stage_id <> 'closedlost'
    GROUP BY ALL
)
SELECT
    label AS stage,
    deals_reached,
    lead(label) OVER (ORDER BY stage_order) AS next_stage,
    lead(deals_reached) OVER (ORDER BY stage_order) AS next_reached,
    round(100.0 * lead(deals_reached) OVER (ORDER BY stage_order) / nullif(deals_reached, 0), 1)
        AS conversion_pct
FROM reached
ORDER BY stage_order;
