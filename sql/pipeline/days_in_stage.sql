-- Average days a deal spent in each open stage, from deal_stage_history.
-- Time in a stage = when the deal left it minus when it entered it. A deal still sitting
-- in its current stage isn't counted yet (we don't know how long it will stay).
WITH visits AS (
    SELECT
        deal_id,
        to_stage AS stage_id,
        changed_at AS entered_at,
        lead(changed_at) OVER (PARTITION BY deal_id ORDER BY changed_at) AS left_at
    FROM deal_stage_history
)
SELECT
    s.label AS stage,
    count(v.left_at) AS completed_visits,
    round(avg(date_diff('hour', v.entered_at, v.left_at)) / 24.0, 1) AS avg_days
FROM stages AS s
LEFT JOIN visits AS v ON v.stage_id = s.stage_id AND v.left_at IS NOT NULL
WHERE NOT s.is_closed
GROUP BY s.label, s.stage_order
ORDER BY s.stage_order;
