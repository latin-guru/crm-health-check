-- CRM closed-won ARR vs billing active-subscription ARR, one row per account.
--
-- The two systems don't share an ID, so an "account" is a normalized domain: the CRM
-- company domain on one side, the billing company_domain on the other. This is a
-- compromise (shared domains and subsidiaries break it); real stacks sync the CRM
-- company ID into billing so the join is exact.
--
-- Both sides are normalized to annual USD before comparing:
--   CRM:     amount x 12 / term_months           (annualize_deal in macros.sql)
--   Billing: price x 12 (monthly) or price (yearly) (annualize_billing)
--   Currency: converted with the fixed demo FX table in config/reconciliation.yml
--
-- Status is decided in this order:
--   Billing-only      -> billing has an active subscription, CRM has no closed-won deal
--   CRM-only          -> CRM has a closed-won deal, billing has no active subscription
--   Currency mismatch -> the two systems use different currencies for the account
--   Matched           -> annual USD values within $tolerance_usd
--   Term mismatch     -> one side is exactly 12x the other (monthly vs annual mix-up)
--   Amount mismatch   -> anything else
WITH crm_deals AS (
    SELECT
        normalize_domain(c.domain) AS domain,
        d.amount,
        upper(d.currency) AS currency,
        annualize_deal(d.amount, d.term_months) * fx.usd_rate AS arr_usd
    FROM deals AS d
    JOIN companies AS c ON c.company_id = d.company_id
    LEFT JOIN fx_rates AS fx ON fx.currency = upper(d.currency)
    WHERE d.stage = 'closedwon'
),
crm AS (
    SELECT
        domain,
        sum(coalesce(arr_usd, 0)) AS crm_arr,
        count(*) FILTER (WHERE amount IS NULL) AS missing_amounts,
        string_agg(DISTINCT currency, '/' ORDER BY currency) AS crm_currency
    FROM crm_deals
    GROUP BY domain
),
billing_rows AS (
    SELECT
        normalize_domain(b.company_domain) AS domain,
        lower(b.status) AS status,
        upper(b.currency) AS currency,
        b.canceled_at,
        annualize_billing(b.mrr, b.interval) * fx.usd_rate AS arr_usd
    FROM billing_subscriptions AS b
    LEFT JOIN fx_rates AS fx ON fx.currency = upper(b.currency)
),
billing AS (
    SELECT
        domain,
        sum(arr_usd) FILTER (WHERE status = 'active') AS billing_arr,
        count(*) FILTER (WHERE status = 'active') AS active_subscriptions,
        max(canceled_at) AS last_canceled_at,
        string_agg(DISTINCT currency, '/' ORDER BY currency) FILTER (WHERE status = 'active')
            AS billing_currency
    FROM billing_rows
    GROUP BY domain
),
crm_companies AS (
    -- The oldest company per domain represents the account (duplicates are H02's job).
    SELECT
        normalize_domain(domain) AS domain,
        arg_min(company_id, created_at) AS company_id,
        arg_min(name, created_at) AS company_name
    FROM companies
    GROUP BY 1
),
accounts AS (
    SELECT domain FROM crm
    UNION
    SELECT domain FROM billing WHERE active_subscriptions > 0
),
compared AS (
    SELECT
        a.domain,
        cc.company_id,
        cc.company_name,
        coalesce(crm.crm_arr, 0) AS crm_arr,
        coalesce(b.billing_arr, 0) AS billing_arr,
        coalesce(b.billing_arr, 0) - coalesce(crm.crm_arr, 0) AS delta,
        crm.crm_currency,
        b.billing_currency,
        coalesce(crm.missing_amounts, 0) AS missing_amounts,
        b.last_canceled_at,
        CASE
            WHEN crm.domain IS NULL THEN 'Billing-only'
            WHEN coalesce(b.active_subscriptions, 0) = 0 THEN 'CRM-only'
            WHEN crm.crm_currency <> b.billing_currency THEN 'Currency mismatch'
            WHEN abs(b.billing_arr - crm.crm_arr) <= $tolerance_usd THEN 'Matched'
            WHEN abs(crm.crm_arr * 12 - b.billing_arr) <= $tolerance_usd
              OR abs(crm.crm_arr - b.billing_arr * 12) <= $tolerance_usd THEN 'Term mismatch'
            ELSE 'Amount mismatch'
        END AS status
    FROM accounts AS a
    LEFT JOIN crm ON crm.domain = a.domain
    LEFT JOIN billing AS b ON b.domain = a.domain
    LEFT JOIN crm_companies AS cc ON cc.domain = a.domain
)
SELECT
    company_id,
    company_name,
    domain,
    round(crm_arr, 2) AS crm_arr,
    round(billing_arr, 2) AS billing_arr,
    round(delta, 2) AS delta,
    status,
    CASE
        WHEN status = 'Matched' THEN
            'CRM and billing agree after converting both to annual USD.'
        WHEN status = 'Billing-only' AND company_id IS NULL THEN
            'Billing has an active subscription for a domain that is not in the CRM at all, '
            || 'likely a self-serve signup that never synced.'
        WHEN status = 'Billing-only' THEN
            'Billing has an active subscription, but this company has no closed-won deal in '
            || 'the CRM, so the sale never reached the pipeline.'
        WHEN status = 'CRM-only' AND last_canceled_at IS NOT NULL THEN
            'Billing canceled the subscription on ' || CAST(last_canceled_at AS VARCHAR)
            || ', but the CRM still counts the closed-won deal, so CRM ARR is overstated.'
        WHEN status = 'CRM-only' THEN
            'The CRM counts a closed-won deal, but billing has no subscription for this '
            || 'domain: the customer may never have been invoiced, or was billed under another domain.'
        WHEN status = 'Currency mismatch' THEN
            'The CRM deal is in ' || crm_currency || ' but billing charges ' || billing_currency
            || '; after converting with the demo FX table the gap is $'
            || format('{:,.0f}', abs(delta)) || '.'
        WHEN status = 'Term mismatch' AND billing_arr > crm_arr THEN
            'CRM ARR is 1/12 of billing ARR: the deal amount looks like a monthly price '
            || 'entered as the full 12-month contract value.'
        WHEN status = 'Term mismatch' THEN
            'Billing ARR is 1/12 of CRM ARR: the subscription is set to a yearly interval '
            || 'but is priced like a monthly plan.'
        WHEN missing_amounts > 0 THEN
            'A closed-won deal has no amount (check H07), so CRM ARR is understated by $'
            || format('{:,.0f}', abs(delta)) || '.'
        ELSE
            'Same currency and term, but billing is ' || format('{:,.0f}', abs(delta))
            || CASE WHEN delta > 0 THEN ' higher' ELSE ' lower' END
            || ' (USD per year) than the CRM: look for a discount, an extra storefront or '
            || 'a price change that never reached the deal.'
    END AS explanation
FROM compared
ORDER BY
    CASE status WHEN 'Matched' THEN 1 ELSE 0 END,
    abs(delta) DESC,
    domain;
