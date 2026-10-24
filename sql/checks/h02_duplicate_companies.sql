-- H02 Duplicate companies.
-- Companies are grouped by normalized domain. The oldest company in a group is kept;
-- every newer one is flagged with the record it should merge into (human review only).
WITH companies_with_domain AS (
    SELECT company_id, domain, created_at, normalize_domain(domain) AS domain_key
    FROM companies
    WHERE nullif(trim(domain), '') IS NOT NULL
),
ranked AS (
    SELECT
        *,
        row_number() OVER (PARTITION BY domain_key ORDER BY created_at, company_id) AS position,
        first_value(company_id) OVER (PARTITION BY domain_key ORDER BY created_at, company_id)
            AS keep_company_id
    FROM companies_with_domain
)
SELECT
    'company' AS object,
    company_id AS record_id,
    'domain' AS field,
    domain AS current_value,
    keep_company_id AS suggested_value,
    false AS auto_fixable
FROM ranked
WHERE position > 1
ORDER BY record_id;
