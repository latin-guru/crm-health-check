-- H03 Missing or invalid email.
-- Not auto-fixable: only the record owner can find the real address.
SELECT
    'contact' AS object,
    contact_id AS record_id,
    'email' AS field,
    email AS current_value,
    NULL AS suggested_value,
    false AS auto_fixable
FROM contacts
WHERE NOT is_valid_email(email)
ORDER BY record_id;
