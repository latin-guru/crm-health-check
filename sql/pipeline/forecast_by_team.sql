-- Weighted forecast by sales team = sum(amount x stage probability) over open deals.
-- The team comes from the deal owner. Only as good as stage hygiene (see H06).
SELECT
    coalesce(o.team, 'Unassigned') AS team,
    count(*) AS deals,
    sum(d.amount * fx.usd_rate) AS amount_usd,
    sum(d.amount * fx.usd_rate * s.probability) AS weighted_usd
FROM deals AS d
JOIN stages AS s ON s.stage_id = d.stage
LEFT JOIN owners AS o ON o.owner_id = d.owner_id
LEFT JOIN fx_rates AS fx ON fx.currency = upper(d.currency)
WHERE NOT s.is_closed
GROUP BY ALL
ORDER BY weighted_usd DESC;
