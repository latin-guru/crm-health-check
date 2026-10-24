-- H05 Deal missing its company or primary contact association.
-- One row per deal; field lists which association(s) are missing.
SELECT
    'deal' AS object,
    deal_id AS record_id,
    CASE
        WHEN company_id IS NULL AND primary_contact_id IS NULL THEN 'company_id, primary_contact_id'
        WHEN company_id IS NULL THEN 'company_id'
        ELSE 'primary_contact_id'
    END AS field,
    NULL AS current_value,
    NULL AS suggested_value,
    false AS auto_fixable
FROM deals
WHERE company_id IS NULL OR primary_contact_id IS NULL
ORDER BY record_id;
