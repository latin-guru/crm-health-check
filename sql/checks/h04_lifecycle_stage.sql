-- H04 Lifecycle stage missing, or "customer" with no closed-won deal at the company.
-- A missing stage is auto-filled from the company's deals:
--   any closed-won deal -> customer, any open deal -> opportunity, otherwise -> lead.
-- A "customer" with no won deal is NOT auto-fixed: either a won deal is missing from the
-- CRM or the stage is wrong, and HubSpot doesn't move lifecycle stages backwards by default.
WITH won_companies AS (
    SELECT DISTINCT company_id
    FROM deals
    WHERE stage = 'closedwon' AND company_id IS NOT NULL
),
open_companies AS (
    SELECT DISTINCT d.company_id
    FROM deals AS d
    JOIN stages AS s ON s.stage_id = d.stage
    WHERE NOT s.is_closed AND d.company_id IS NOT NULL
)
SELECT
    'contact' AS object,
    c.contact_id AS record_id,
    'lifecycle_stage' AS field,
    c.lifecycle_stage AS current_value,
    CASE
        WHEN c.lifecycle_stage IS NOT NULL THEN NULL
        WHEN w.company_id IS NOT NULL THEN 'customer'
        WHEN o.company_id IS NOT NULL THEN 'opportunity'
        ELSE 'lead'
    END AS suggested_value,
    c.lifecycle_stage IS NULL AS auto_fixable
FROM contacts AS c
LEFT JOIN won_companies AS w ON w.company_id = c.company_id
LEFT JOIN open_companies AS o ON o.company_id = c.company_id
WHERE c.lifecycle_stage IS NULL
   OR (c.lifecycle_stage = 'customer' AND w.company_id IS NULL)
ORDER BY record_id;
