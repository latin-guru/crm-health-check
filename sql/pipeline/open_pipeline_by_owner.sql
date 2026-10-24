-- Open pipeline by owner. Deals with no owner, or an owner that doesn't exist, show as
-- "Unassigned"; inactive owners are kept and marked so their deals can be reassigned.
SELECT
    coalesce(o.name, 'Unassigned') AS owner,
    coalesce(o.team, 'Unassigned') AS team,
    coalesce(o.active, false) AS active,
    count(*) AS deals,
    sum(d.amount * fx.usd_rate) AS amount_usd,
    sum(d.amount * fx.usd_rate * s.probability) AS weighted_usd
FROM deals AS d
JOIN stages AS s ON s.stage_id = d.stage
LEFT JOIN owners AS o ON o.owner_id = d.owner_id
LEFT JOIN fx_rates AS fx ON fx.currency = upper(d.currency)
WHERE NOT s.is_closed
GROUP BY ALL
ORDER BY weighted_usd DESC, owner;
