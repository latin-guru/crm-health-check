-- First-touch vs last-touch source for closed-won deals, before and after UTM normalization.
-- Touches counted: the deal's primary contact's touchpoints up to the moment the deal was
-- created. First touch = the earliest one, last touch = the latest one.
-- "before" uses utm_source exactly as tracked; "after" maps aliases to canonical values
-- with config/utm_governance.yml. Unknown values stay visible as "(unmapped) value".
WITH won_deals AS (
    SELECT deal_id, primary_contact_id, created_at
    FROM deals
    WHERE stage = 'closedwon' AND primary_contact_id IS NOT NULL
),
touches AS (
    SELECT
        w.deal_id,
        coalesce(t.utm_source, '(no UTM)') AS source_raw,
        CASE
            WHEN t.utm_source IS NULL THEN '(no UTM)'
            ELSE coalesce(a.canonical, '(unmapped) ' || t.utm_source)
        END AS source_clean,
        row_number() OVER (PARTITION BY w.deal_id ORDER BY t.occurred_at, t.touchpoint_id)
            AS first_rank,
        row_number() OVER (
            PARTITION BY w.deal_id ORDER BY t.occurred_at DESC, t.touchpoint_id DESC
        ) AS last_rank
    FROM won_deals AS w
    JOIN touchpoints AS t
        ON t.contact_id = w.primary_contact_id AND t.occurred_at <= w.created_at
    LEFT JOIN utm_aliases AS a ON a.kind = 'source' AND a.alias = lower(trim(t.utm_source))
),
labeled AS (
    SELECT 'before' AS view, source_raw AS source, first_rank, last_rank FROM touches
    UNION ALL
    SELECT 'after', source_clean, first_rank, last_rank FROM touches
)
SELECT
    view,
    source,
    count(*) FILTER (WHERE first_rank = 1) AS first_touch_deals,
    count(*) FILTER (WHERE last_rank = 1) AS last_touch_deals
FROM labeled
GROUP BY view, source
HAVING count(*) FILTER (WHERE first_rank = 1 OR last_rank = 1) > 0
ORDER BY view DESC, first_touch_deals DESC, last_touch_deals DESC, source;
