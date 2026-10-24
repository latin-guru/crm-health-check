-- H08 Record owned by nobody, by an inactive owner, or by an owner that doesn't exist.
-- Contacts and deals can be auto-reassigned to their company's owner when that owner is
-- active. Companies (or records whose company owner is also inactive) need a manager.
WITH active_owners AS (
    SELECT owner_id FROM owners WHERE active
),
owned_records AS (
    SELECT 'contact' AS object, contact_id AS record_id, owner_id, company_id FROM contacts
    UNION ALL
    SELECT 'company', company_id, owner_id, NULL FROM companies
    UNION ALL
    SELECT 'deal', deal_id, owner_id, company_id FROM deals
)
SELECT
    r.object,
    r.record_id,
    'owner_id' AS field,
    r.owner_id AS current_value,
    company_owner.owner_id AS suggested_value,
    company_owner.owner_id IS NOT NULL AS auto_fixable
FROM owned_records AS r
LEFT JOIN active_owners AS record_owner ON record_owner.owner_id = r.owner_id
LEFT JOIN companies AS co ON co.company_id = r.company_id
LEFT JOIN active_owners AS company_owner ON company_owner.owner_id = co.owner_id
WHERE record_owner.owner_id IS NULL
ORDER BY r.object, r.record_id;
