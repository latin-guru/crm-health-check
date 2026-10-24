-- H09 Non-canonical UTM values on contacts.
-- A value is fine only if it exactly matches a canonical value in config/utm_governance.yml.
-- Known aliases ("FB", "facebook.com") get the canonical value as an auto-fix; unknown
-- values have no suggestion and go to marketing ops for review. Empty UTMs are allowed.
WITH utm_values AS (
    SELECT contact_id, 'source' AS kind, 'utm_source' AS field, utm_source AS value
    FROM contacts WHERE utm_source IS NOT NULL
    UNION ALL
    SELECT contact_id, 'medium', 'utm_medium', utm_medium
    FROM contacts WHERE utm_medium IS NOT NULL
)
SELECT
    'contact' AS object,
    v.contact_id AS record_id,
    v.field,
    v.value AS current_value,
    a.canonical AS suggested_value,
    a.canonical IS NOT NULL AS auto_fixable
FROM utm_values AS v
LEFT JOIN utm_canonical AS c ON c.kind = v.kind AND c.value = v.value
LEFT JOIN utm_aliases AS a ON a.kind = v.kind AND a.alias = lower(trim(v.value))
WHERE c.value IS NULL
ORDER BY record_id, field;
