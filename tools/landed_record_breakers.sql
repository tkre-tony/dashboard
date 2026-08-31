-- ============================================================================
-- LANDED RECORD BREAKER SCANNER - 4-GRAIN MATRIX WITH VERDICT LAYER
-- PropertyAtlas | tools/landed_record_breakers.sql | v2.0 | 30 Aug 2026
-- ============================================================================
-- THE ONLY SCANNER. Do not create W1/W2/W3_patched.sql, a _4grain_production
-- variant, or a dated _wm<NNNNN> snapshot. Four such files accumulated in
-- Project Knowledge, where the session-open sequence cannot fetch them, and the
-- weekly runbook pointed at a tools/ path that did not exist (L-DEPLOY-13).
-- Only prev_max_id changes week to week. Change it in params, nowhere else.
--
-- USAGE
--   1. Set prev_max_id below = MAX(id) captured BEFORE this week's ingest.
--   2. Paste the ENTIRE file into a FRESH Supabase SQL tab.
--   3. Set the row dropdown to "No limit".
--   4. Run, export CSV, triage by verdict.
--
-- GRAINS - a record is only a record at a stated grain.
--   DISTRICT  postal_district + property_type + tenure + area_type
--   SECTOR    postal_sector (2-digit) + property_type + tenure + area_type
--   ENCLAVE   project_name + property_type + tenure + area_type (named estates)
--   STREET    street + district + property_type + tenure + area_type
--   type_of_area is a GROUPING KEY, not a filter, so Land and Strata are each
--   compared against their own baseline within every grain.
--
-- VERDICT is a COLUMN, NOT A FILTER. Every flagged row returns, labelled. A
-- scanner that silently drops rows hides its own behaviour.
--   PUBLISHABLE            claim stands against a sufficient baseline
--   SUPPRESS_NO_PRIOR      no prior comparable at this grain at all
--   SUPPRESS_THIN_PRIOR    HIGH claim, fewer than min_n_all_high priors
--   SUPPRESS_THIN_RECENT   LOW claim, fewer than min_n20_low since 2020
--   REVIEW_STALE_BASELINE  baseline predates 2020; read prev_last_year first
-- The thin-prior test applies ONLY to HIGH claims and thin-recent ONLY to LOW.
-- Conflating them wrongly suppresses valid LOW flags (S345: Dalla Vale).
--
-- PROVENANCE COLUMNS prev_hi_psf_year, prev_hi_px_year, prev_last_year turn
-- "this looks like a 65% record" into "the baseline was set in 2019 and nothing
-- has traded since", visible on the row rather than requiring a second query.
--
-- EXCLUSIONS
--   'LANDED HOUSING DEVELOPMENT' and 'N.A.' excluded from ENCLAVE grain only
--   (generic URA labels, no estate assignment). Both remain covered by
--   DISTRICT, SECTOR and STREET.
--   number_of_units > 1 (bulk deals) excluded from all grains.
--   tenure that parses to neither Freehold nor Leasehold is excluded.
--
-- KNOWN CALIBRATION, LEFT DELIBERATELY
--   min_n_all_high = 30 passes 26 Yuk Tong Avenue (n_all exactly 30), which
--   S345 rejected by hand. Left at 30: moving to 31 to win one case is fitting
--   the rule to a single data point. prev_hi_px_year surfaces the stale
--   baseline there anyway.
--
-- TRAP A real P&L gain is not a record. 25 Jalan Nira's +64.9% (S347) is a
--   holding-period gain, not a record break. Do not conflate the two.
--
-- PROVENANCE
--   S348. Merge of two forked lineages, neither ever committed:
--     landed_record_breakers_4grain_production.sql v1.0 (25 Jul 2026) gave the
--       four grains, the type_of_area dimension and the exclusions;
--     W1/W2/W3_patched.sql (S345, watermark 80433) gave the verdict layer and
--       the three provenance columns, regression-tested on that week's ten real
--       flags: 7 PUBLISHABLE, 2 SUPPRESS_THIN_PRIOR (Verandah n_all 3, Chuan
--       Vale n_all 12), 1 SUPPRESS_THIN_RECENT (D'Manor n_20 1).
--   Superseded and safe to delete: W1_patched.sql, W2_patched.sql,
--   W3_patched.sql, landed_record_breakers.sql (3-grain, no verdict),
--   landed_record_breakers_4grain_production.sql,
--   landed_record_breakers_20260822_wm80395.sql.
--
-- WATERMARK LOG
--   20 Jul 2026  prev_max_id 80194   47 new rows, 49 flags
--   22 Aug 2026  prev_max_id 80395   38 new rows
--   29 Aug 2026  prev_max_id 80433   35 new rows, 10 flags (S345 triage above)
--   next run     prev_max_id 80468   <- current MAX(id); confirm before running
-- ============================================================================

WITH params AS (
  SELECT
    80468 AS prev_max_id,      -- <- UPDATE EACH WEEK. MAX(id) BEFORE the ingest.
    30    AS min_n_all_high,   -- HIGH claims need this many prior comparables
    10    AS min_n20_low       -- LOW claims need this many since 2020
),
base AS (
  SELECT
    t.id,
    COALESCE(t.project_name, 'N.A.') AS project_name,
    t.transacted_price,
    t.area_sqft,
    t.unit_price_psf,
    t.sale_date::date AS sd,
    EXTRACT(YEAR FROM t.sale_date::date)::int AS yr,
    t.address,
    t.property_type,
    t.type_of_area,
    t.postal_district::text AS postal_district,
    t.postal_code,
    LEFT(t.postal_code, 2) AS postal_sector,
    REGEXP_REPLACE(t.address, '^\d+[A-Z]?\s+', '') AS street_name,
    CASE
      WHEN t.tenure ILIKE '%freehold%' THEN 'Freehold'
      WHEN t.tenure ~ '\d' AND (regexp_match(t.tenure, '(\d+)'))[1]::int > 937 THEN 'Freehold'
      WHEN t.tenure ~ '\d' AND (regexp_match(t.tenure, '(\d+)'))[1]::int <= 103 THEN 'Leasehold'
    END AS tenure_class
  FROM public.landed_transactions t
  WHERE t.unit_price_psf IS NOT NULL
    AND t.unit_price_psf > 0
    AND t.transacted_price > 0
    AND COALESCE(t.number_of_units, 1) = 1
),
eligible AS (
  SELECT * FROM base WHERE tenure_class IS NOT NULL
),
g1_prior AS (
  SELECT
    postal_district, property_type, tenure_class, type_of_area,
    COUNT(*) AS n_all,
    COUNT(*) FILTER (WHERE yr >= 2020) AS n_20,
    MAX(unit_price_psf) AS hi_psf,
    MIN(unit_price_psf) FILTER (WHERE yr >= 2020) AS lo_psf_20,
    MAX(transacted_price) AS hi_px,
    MIN(transacted_price) FILTER (WHERE yr >= 2020) AS lo_px_20,
    (array_agg(yr ORDER BY unit_price_psf DESC, yr DESC))[1] AS prev_hi_psf_year,
    (array_agg(yr ORDER BY transacted_price DESC, yr DESC))[1] AS prev_hi_px_year,
    MAX(yr) AS prev_last_year
  FROM eligible, params
  WHERE id <= params.prev_max_id
  GROUP BY postal_district, property_type, tenure_class, type_of_area
),
g1_new AS (
  SELECT e.* FROM eligible e, params WHERE e.id > params.prev_max_id
),
g1 AS (
  SELECT
    'DISTRICT' AS grain,
    'D' || n.postal_district AS group_key,
    n.id, n.address, n.project_name, n.property_type, n.tenure_class,
    n.type_of_area, n.postal_district, n.postal_sector, n.street_name,
    n.transacted_price, n.area_sqft, n.unit_price_psf, n.sd AS sale_date,
    CASE WHEN n.unit_price_psf > COALESCE(p.hi_psf, 0) THEN 'HIGH_PSF' END AS psf_flag,
    CASE WHEN n.yr >= 2020 AND p.lo_psf_20 IS NOT NULL
              AND n.unit_price_psf < p.lo_psf_20 THEN 'LOW_PSF' END AS psf_lo_flag,
    CASE WHEN n.transacted_price > COALESCE(p.hi_px, 0) THEN 'HIGH_PX' END AS px_flag,
    CASE WHEN n.yr >= 2020 AND p.lo_px_20 IS NOT NULL
              AND n.transacted_price < p.lo_px_20 THEN 'LOW_PX' END AS px_lo_flag,
    p.hi_psf AS prev_hi_psf, p.lo_psf_20 AS prev_lo_psf_20,
    p.hi_px AS prev_hi_px, p.lo_px_20 AS prev_lo_px_20,
    p.prev_hi_psf_year, p.prev_hi_px_year, p.prev_last_year,
    p.n_all, p.n_20,
    CASE
      WHEN p.n_all IS NULL THEN 'SUPPRESS_NO_PRIOR'
      WHEN (n.unit_price_psf > COALESCE(p.hi_psf, 0)
            OR n.transacted_price > COALESCE(p.hi_px, 0))
           AND p.n_all < params.min_n_all_high THEN 'SUPPRESS_THIN_PRIOR'
      WHEN NOT (n.unit_price_psf > COALESCE(p.hi_psf, 0)
            OR n.transacted_price > COALESCE(p.hi_px, 0))
           AND p.n_20 < params.min_n20_low THEN 'SUPPRESS_THIN_RECENT'
      WHEN p.prev_last_year < 2020 THEN 'REVIEW_STALE_BASELINE'
      ELSE 'PUBLISHABLE'
    END AS verdict
  FROM g1_new n
  CROSS JOIN params
  LEFT JOIN g1_prior p
    ON  p.postal_district = n.postal_district
    AND p.property_type   = n.property_type
    AND p.tenure_class    = n.tenure_class
    AND p.type_of_area    = n.type_of_area
  WHERE n.unit_price_psf > COALESCE(p.hi_psf, 0)
     OR (n.yr >= 2020 AND p.lo_psf_20 IS NOT NULL AND n.unit_price_psf < p.lo_psf_20)
     OR n.transacted_price > COALESCE(p.hi_px, 0)
     OR (n.yr >= 2020 AND p.lo_px_20 IS NOT NULL AND n.transacted_price < p.lo_px_20)
),
g2_prior AS (
  SELECT
    LEFT(postal_code, 2) AS postal_sector, property_type, tenure_class, type_of_area,
    COUNT(*) AS n_all,
    COUNT(*) FILTER (WHERE yr >= 2020) AS n_20,
    MAX(unit_price_psf) AS hi_psf,
    MIN(unit_price_psf) FILTER (WHERE yr >= 2020) AS lo_psf_20,
    MAX(transacted_price) AS hi_px,
    MIN(transacted_price) FILTER (WHERE yr >= 2020) AS lo_px_20,
    (array_agg(yr ORDER BY unit_price_psf DESC, yr DESC))[1] AS prev_hi_psf_year,
    (array_agg(yr ORDER BY transacted_price DESC, yr DESC))[1] AS prev_hi_px_year,
    MAX(yr) AS prev_last_year
  FROM eligible, params
  WHERE id <= params.prev_max_id
    AND postal_code IS NOT NULL
  GROUP BY LEFT(postal_code, 2), property_type, tenure_class, type_of_area
),
g2_new AS (
  SELECT e.* FROM eligible e, params
  WHERE e.id > params.prev_max_id
    AND e.postal_code IS NOT NULL
),
g2 AS (
  SELECT
    'SECTOR' AS grain,
    'S' || n.postal_sector AS group_key,
    n.id, n.address, n.project_name, n.property_type, n.tenure_class,
    n.type_of_area, n.postal_district, n.postal_sector, n.street_name,
    n.transacted_price, n.area_sqft, n.unit_price_psf, n.sd AS sale_date,
    CASE WHEN n.unit_price_psf > COALESCE(p.hi_psf, 0) THEN 'HIGH_PSF' END AS psf_flag,
    CASE WHEN n.yr >= 2020 AND p.lo_psf_20 IS NOT NULL
              AND n.unit_price_psf < p.lo_psf_20 THEN 'LOW_PSF' END AS psf_lo_flag,
    CASE WHEN n.transacted_price > COALESCE(p.hi_px, 0) THEN 'HIGH_PX' END AS px_flag,
    CASE WHEN n.yr >= 2020 AND p.lo_px_20 IS NOT NULL
              AND n.transacted_price < p.lo_px_20 THEN 'LOW_PX' END AS px_lo_flag,
    p.hi_psf AS prev_hi_psf, p.lo_psf_20 AS prev_lo_psf_20,
    p.hi_px AS prev_hi_px, p.lo_px_20 AS prev_lo_px_20,
    p.prev_hi_psf_year, p.prev_hi_px_year, p.prev_last_year,
    p.n_all, p.n_20,
    CASE
      WHEN p.n_all IS NULL THEN 'SUPPRESS_NO_PRIOR'
      WHEN (n.unit_price_psf > COALESCE(p.hi_psf, 0)
            OR n.transacted_price > COALESCE(p.hi_px, 0))
           AND p.n_all < params.min_n_all_high THEN 'SUPPRESS_THIN_PRIOR'
      WHEN NOT (n.unit_price_psf > COALESCE(p.hi_psf, 0)
            OR n.transacted_price > COALESCE(p.hi_px, 0))
           AND p.n_20 < params.min_n20_low THEN 'SUPPRESS_THIN_RECENT'
      WHEN p.prev_last_year < 2020 THEN 'REVIEW_STALE_BASELINE'
      ELSE 'PUBLISHABLE'
    END AS verdict
  FROM g2_new n
  CROSS JOIN params
  LEFT JOIN g2_prior p
    ON  p.postal_sector  = n.postal_sector
    AND p.property_type  = n.property_type
    AND p.tenure_class   = n.tenure_class
    AND p.type_of_area   = n.type_of_area
  WHERE n.unit_price_psf > COALESCE(p.hi_psf, 0)
     OR (n.yr >= 2020 AND p.lo_psf_20 IS NOT NULL AND n.unit_price_psf < p.lo_psf_20)
     OR n.transacted_price > COALESCE(p.hi_px, 0)
     OR (n.yr >= 2020 AND p.lo_px_20 IS NOT NULL AND n.transacted_price < p.lo_px_20)
),
g3_prior AS (
  SELECT
    project_name, property_type, tenure_class, type_of_area,
    COUNT(*) AS n_all,
    COUNT(*) FILTER (WHERE yr >= 2020) AS n_20,
    MAX(unit_price_psf) AS hi_psf,
    MIN(unit_price_psf) FILTER (WHERE yr >= 2020) AS lo_psf_20,
    MAX(transacted_price) AS hi_px,
    MIN(transacted_price) FILTER (WHERE yr >= 2020) AS lo_px_20,
    (array_agg(yr ORDER BY unit_price_psf DESC, yr DESC))[1] AS prev_hi_psf_year,
    (array_agg(yr ORDER BY transacted_price DESC, yr DESC))[1] AS prev_hi_px_year,
    MAX(yr) AS prev_last_year
  FROM eligible, params
  WHERE id <= params.prev_max_id
    AND project_name NOT IN ('N.A.', 'LANDED HOUSING DEVELOPMENT')
  GROUP BY project_name, property_type, tenure_class, type_of_area
),
g3_new AS (
  SELECT e.* FROM eligible e, params
  WHERE e.id > params.prev_max_id
    AND e.project_name NOT IN ('N.A.', 'LANDED HOUSING DEVELOPMENT')
),
g3 AS (
  SELECT
    'ENCLAVE' AS grain,
    n.project_name AS group_key,
    n.id, n.address, n.project_name, n.property_type, n.tenure_class,
    n.type_of_area, n.postal_district, n.postal_sector, n.street_name,
    n.transacted_price, n.area_sqft, n.unit_price_psf, n.sd AS sale_date,
    CASE WHEN n.unit_price_psf > COALESCE(p.hi_psf, 0) THEN 'HIGH_PSF' END AS psf_flag,
    CASE WHEN n.yr >= 2020 AND p.lo_psf_20 IS NOT NULL
              AND n.unit_price_psf < p.lo_psf_20 THEN 'LOW_PSF' END AS psf_lo_flag,
    CASE WHEN n.transacted_price > COALESCE(p.hi_px, 0) THEN 'HIGH_PX' END AS px_flag,
    CASE WHEN n.yr >= 2020 AND p.lo_px_20 IS NOT NULL
              AND n.transacted_price < p.lo_px_20 THEN 'LOW_PX' END AS px_lo_flag,
    p.hi_psf AS prev_hi_psf, p.lo_psf_20 AS prev_lo_psf_20,
    p.hi_px AS prev_hi_px, p.lo_px_20 AS prev_lo_px_20,
    p.prev_hi_psf_year, p.prev_hi_px_year, p.prev_last_year,
    p.n_all, p.n_20,
    CASE
      WHEN p.n_all IS NULL THEN 'SUPPRESS_NO_PRIOR'
      WHEN (n.unit_price_psf > COALESCE(p.hi_psf, 0)
            OR n.transacted_price > COALESCE(p.hi_px, 0))
           AND p.n_all < params.min_n_all_high THEN 'SUPPRESS_THIN_PRIOR'
      WHEN NOT (n.unit_price_psf > COALESCE(p.hi_psf, 0)
            OR n.transacted_price > COALESCE(p.hi_px, 0))
           AND p.n_20 < params.min_n20_low THEN 'SUPPRESS_THIN_RECENT'
      WHEN p.prev_last_year < 2020 THEN 'REVIEW_STALE_BASELINE'
      ELSE 'PUBLISHABLE'
    END AS verdict
  FROM g3_new n
  CROSS JOIN params
  LEFT JOIN g3_prior p
    ON  p.project_name  = n.project_name
    AND p.property_type = n.property_type
    AND p.tenure_class  = n.tenure_class
    AND p.type_of_area  = n.type_of_area
  WHERE n.unit_price_psf > COALESCE(p.hi_psf, 0)
     OR (n.yr >= 2020 AND p.lo_psf_20 IS NOT NULL AND n.unit_price_psf < p.lo_psf_20)
     OR n.transacted_price > COALESCE(p.hi_px, 0)
     OR (n.yr >= 2020 AND p.lo_px_20 IS NOT NULL AND n.transacted_price < p.lo_px_20)
),
g4_prior AS (
  SELECT
    REGEXP_REPLACE(address, '^\d+[A-Z]?\s+', '') AS street_name,
    postal_district, property_type, tenure_class, type_of_area,
    COUNT(*) AS n_all,
    COUNT(*) FILTER (WHERE yr >= 2020) AS n_20,
    MAX(unit_price_psf) AS hi_psf,
    MIN(unit_price_psf) FILTER (WHERE yr >= 2020) AS lo_psf_20,
    MAX(transacted_price) AS hi_px,
    MIN(transacted_price) FILTER (WHERE yr >= 2020) AS lo_px_20,
    (array_agg(yr ORDER BY unit_price_psf DESC, yr DESC))[1] AS prev_hi_psf_year,
    (array_agg(yr ORDER BY transacted_price DESC, yr DESC))[1] AS prev_hi_px_year,
    MAX(yr) AS prev_last_year
  FROM eligible, params
  WHERE id <= params.prev_max_id
  GROUP BY REGEXP_REPLACE(address, '^\d+[A-Z]?\s+', ''),
           postal_district, property_type, tenure_class, type_of_area
),
g4_new AS (
  SELECT e.* FROM eligible e, params WHERE e.id > params.prev_max_id
),
g4 AS (
  SELECT
    'STREET' AS grain,
    n.street_name || ' D' || n.postal_district AS group_key,
    n.id, n.address, n.project_name, n.property_type, n.tenure_class,
    n.type_of_area, n.postal_district, n.postal_sector, n.street_name,
    n.transacted_price, n.area_sqft, n.unit_price_psf, n.sd AS sale_date,
    CASE WHEN n.unit_price_psf > COALESCE(p.hi_psf, 0) THEN 'HIGH_PSF' END AS psf_flag,
    CASE WHEN n.yr >= 2020 AND p.lo_psf_20 IS NOT NULL
              AND n.unit_price_psf < p.lo_psf_20 THEN 'LOW_PSF' END AS psf_lo_flag,
    CASE WHEN n.transacted_price > COALESCE(p.hi_px, 0) THEN 'HIGH_PX' END AS px_flag,
    CASE WHEN n.yr >= 2020 AND p.lo_px_20 IS NOT NULL
              AND n.transacted_price < p.lo_px_20 THEN 'LOW_PX' END AS px_lo_flag,
    p.hi_psf AS prev_hi_psf, p.lo_psf_20 AS prev_lo_psf_20,
    p.hi_px AS prev_hi_px, p.lo_px_20 AS prev_lo_px_20,
    p.prev_hi_psf_year, p.prev_hi_px_year, p.prev_last_year,
    p.n_all, p.n_20,
    CASE
      WHEN p.n_all IS NULL THEN 'SUPPRESS_NO_PRIOR'
      WHEN (n.unit_price_psf > COALESCE(p.hi_psf, 0)
            OR n.transacted_price > COALESCE(p.hi_px, 0))
           AND p.n_all < params.min_n_all_high THEN 'SUPPRESS_THIN_PRIOR'
      WHEN NOT (n.unit_price_psf > COALESCE(p.hi_psf, 0)
            OR n.transacted_price > COALESCE(p.hi_px, 0))
           AND p.n_20 < params.min_n20_low THEN 'SUPPRESS_THIN_RECENT'
      WHEN p.prev_last_year < 2020 THEN 'REVIEW_STALE_BASELINE'
      ELSE 'PUBLISHABLE'
    END AS verdict
  FROM g4_new n
  CROSS JOIN params
  LEFT JOIN g4_prior p
    ON  p.street_name     = n.street_name
    AND p.postal_district = n.postal_district
    AND p.property_type   = n.property_type
    AND p.tenure_class    = n.tenure_class
    AND p.type_of_area    = n.type_of_area
  WHERE n.unit_price_psf > COALESCE(p.hi_psf, 0)
     OR (n.yr >= 2020 AND p.lo_psf_20 IS NOT NULL AND n.unit_price_psf < p.lo_psf_20)
     OR n.transacted_price > COALESCE(p.hi_px, 0)
     OR (n.yr >= 2020 AND p.lo_px_20 IS NOT NULL AND n.transacted_price < p.lo_px_20)
)
  SELECT * FROM (
  SELECT * FROM g1
  UNION ALL
  SELECT * FROM g2
  UNION ALL
  SELECT * FROM g3
  UNION ALL
  SELECT * FROM g4
) combined
ORDER BY
  CASE verdict WHEN 'PUBLISHABLE' THEN 1 ELSE 2 END,
  CASE grain
    WHEN 'DISTRICT' THEN 1
    WHEN 'SECTOR'   THEN 2
    WHEN 'ENCLAVE'  THEN 3
    WHEN 'STREET'   THEN 4
  END,
  tenure_class, property_type, group_key, sale_date