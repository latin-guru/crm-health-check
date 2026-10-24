-- Open pipeline by stage: deal count, total amount and weighted amount, in USD.
-- weighted = amount x stage probability (config/pipeline.yml).
SELECT
    s.label AS stage,
    s.probability,
    count(d.deal_id) AS deals,
    coalesce(sum(d.amount * fx.usd_rate), 0) AS amount_usd,
    coalesce(sum(d.amount * fx.usd_rate * s.probability), 0) AS weighted_usd
FROM stages AS s
LEFT JOIN deals AS d ON d.stage = s.stage_id
LEFT JOIN fx_rates AS fx ON fx.currency = upper(d.currency)
WHERE NOT s.is_closed
GROUP BY s.label, s.probability, s.stage_order
ORDER BY s.stage_order;
