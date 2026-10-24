-- Shared helper functions (DuckDB macros) used by the checks and metrics.
-- Each one is small on purpose so its rule can be read in one line.

-- Email used to find duplicates: lowercase, no surrounding spaces, "+tag" removed
-- (ana+news@shop.example and Ana@Shop.example are the same inbox).
CREATE OR REPLACE MACRO normalize_email(email) AS
    regexp_replace(lower(trim(email)), '\+[^@]*@', '@');

-- A usable email has one "@", no spaces, and a dot in the domain part.
CREATE OR REPLACE MACRO is_valid_email(email) AS
    coalesce(regexp_full_match(trim(email), '[^@\s]+@[^@\s]+\.[A-Za-z]{2,}'), false);

-- Domain used to join records: lowercase, no http(s)://, no leading www., no path.
-- "https://www.Shop.example/" becomes "shop.example".
CREATE OR REPLACE MACRO normalize_domain(domain) AS
    regexp_replace(
        regexp_replace(lower(trim(domain)), '^https?://', ''),
        '^www\.|/.*$', '', 'g'
    );

-- CRM deal amount is the total contract value for term_months.
-- Annual value = amount * 12 / term. A missing term is treated as 12 months (H07 flags it).
CREATE OR REPLACE MACRO annualize_deal(amount, term_months) AS
    amount * 12.0 / coalesce(nullif(term_months, 0), 12);

-- Billing exports the price per billing interval (in a column named mrr, even for
-- yearly plans). Annual value = price * 12 for monthly plans, price for yearly plans.
CREATE OR REPLACE MACRO annualize_billing(price, billing_interval) AS
    CASE lower(billing_interval)
        WHEN 'month' THEN price * 12.0
        WHEN 'year' THEN price * 1.0
    END;
