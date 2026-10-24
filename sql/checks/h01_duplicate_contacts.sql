-- H01 Duplicate contacts.
-- Contacts with a valid email are grouped by normalized email. The oldest contact in a
-- group is kept; every newer one is flagged with the record it should merge into.
-- Merges are never auto-fixed (auto_fixable = false): a person reviews each pair.
WITH contacts_with_email AS (
    SELECT contact_id, email, created_at, normalize_email(email) AS email_key
    FROM contacts
    WHERE is_valid_email(email)
),
ranked AS (
    SELECT
        *,
        row_number() OVER (PARTITION BY email_key ORDER BY created_at, contact_id) AS position,
        first_value(contact_id) OVER (PARTITION BY email_key ORDER BY created_at, contact_id)
            AS keep_contact_id
    FROM contacts_with_email
)
SELECT
    'contact' AS object,
    contact_id AS record_id,
    'email' AS field,
    email AS current_value,
    keep_contact_id AS suggested_value,
    false AS auto_fixable
FROM ranked
WHERE position > 1
ORDER BY record_id;
