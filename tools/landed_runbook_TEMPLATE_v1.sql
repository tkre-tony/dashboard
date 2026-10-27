-- ============================================================================
-- ATLAS — landed_runbook_TEMPLATE_v1.sql   (S412; first landed template)
-- Built from landed_weekly_20261023_runbook.sql. Atlas fills the <...> values per run
-- and saves the copy as landed_weekly_<YYYYMMDD>_runbook.sql.
-- RUN EACH STEP IN ITS OWN FRESH TAB.
--
-- S412 changes vs the dated runbooks:
--   * STEP 5d: landed_split_merge_review has NO sell_id / buy_id columns (S411).
--     Replaced with the column-agnostic JSON match on the batch ids.
--   * L-ING-3: the append CSV must carry postal_code as 6-char zero-padded text.
--     Atlas runs tools/append_csv_guard.py on the file BEFORE handing it over;
--     STEP 2 postal_bad stays as the post-insert backstop.
--
-- Placeholders:
--   <TAG>          ld_<YYYYMMDD>
--   <PREV_MAX>     MAX(id) before the import (= row count when no gaps)
--   <LO> / <HI>    first / last id of the batch  (<LO> = <PREV_MAX> + 1)
--   <ROWS>         batch row count                <SUM>  batch Σ transacted_price
--   <REL_DATE>     release date stamped on the batch (YYYY-MM-DD)
--   <APPEND_FILE>  landed_weekly_<YYYYMMDD>_append.csv
--   <ID_REGEX>     batch ids joined with |   e.g. 80857|80858|...|80871
-- ============================================================================

-- STEP 0b — watermark. MUST return <PREV_MAX> / <PREV_MAX>.
SELECT COUNT(*) AS rows_now, MAX(id) AS max_id FROM landed_transactions;

-- STEP 0c — overlap probe. MUST return 0 rows.
WITH batch(address, sale_date, transacted_price) AS (VALUES
  <BATCH_VALUES>)   -- ('ADDRESS', DATE 'YYYY-MM-DD', price), one per row
SELECT b.* FROM batch b
JOIN landed_transactions t
  ON upper(trim(t.address)) = upper(trim(b.address))
 AND t.sale_date = b.sale_date
 AND t.transacted_price = b.transacted_price;

-- STEP 1 — CSV append (NO SQL)
-- Table Editor -> landed_transactions (BASE TABLE) -> Insert -> Import data from CSV
--   -> <APPEND_FILE>  · success toast must state <ROWS> rows.

-- STEP 2 — post-insert checks (one row each; all must match)
SELECT 'rows_now' AS check, COUNT(*)::text AS value, '<HI>' AS expected
  FROM landed_transactions
UNION ALL SELECT 'max_id', MAX(id)::text, '<HI>' FROM landed_transactions
UNION ALL SELECT 'batch_rows', COUNT(*)::text, '<ROWS>'
  FROM landed_transactions WHERE id BETWEEN <LO> AND <HI>
UNION ALL SELECT 'rel_date', COUNT(*)::text, '<ROWS>'
  FROM landed_transactions WHERE id BETWEEN <LO> AND <HI>
   AND release_date = DATE '<REL_DATE>'
UNION ALL SELECT 'batch_sum', SUM(transacted_price)::text, '<SUM>'
  FROM landed_transactions WHERE id BETWEEN <LO> AND <HI>
UNION ALL SELECT 'aborted_null', COUNT(*)::text, '0'
  FROM landed_transactions WHERE id BETWEEN <LO> AND <HI> AND is_aborted IS NULL
UNION ALL SELECT 'postal_bad', COUNT(*)::text, '0'
  FROM landed_transactions WHERE id BETWEEN <LO> AND <HI>
   AND (postal_code IS NULL OR length(postal_code::text) <> 6);

-- STEP 2b — L-ING-2 AREA-MATCH GATE. Any row = Tony reviews before Step 5.
SELECT n.id, n.address, n.sale_date, n.type_of_sale,
       n.area_sqft AS new_area, p.area_sqft AS prior_area, p.sale_date AS prior_date,
       round(((n.area_sqft - p.area_sqft) / p.area_sqft * 100)::numeric, 1) AS drift_pct
FROM landed_transactions n
JOIN landed_transactions p
  ON upper(trim(p.address)) = upper(trim(n.address)) AND p.id < <LO>
WHERE n.id BETWEEN <LO> AND <HI>
  AND abs((n.area_sqft - p.area_sqft) / p.area_sqft) > 0.05
ORDER BY abs((n.area_sqft - p.area_sqft) / p.area_sqft) DESC;

-- STEP 3 — WITHDRAWALS (only if the diff found any; Atlas supplies the block).

-- STEP 4 — AMENDMENTS (only if the diff found any).
--   Update in place BY ID with an old-value guard; leave aborted rows alone (S411).
--   TAB A dry run (BEGIN … SELECT read-back … ROLLBACK) · TAB B same with COMMIT.

-- STEP 5a — P&L rebuild, ALONE.
SELECT refresh_landed_pnl_pairs();

-- STEP 5b — new pairs from this batch (export CSV)
SELECT sell_id, buy_id, address, buy_price, sell_price, gain, gain_pct,
       hold_days, ann_return, pair_flag, area_diff_pct
FROM landed_pnl_pairs_mv
WHERE sell_id BETWEEN <LO> AND <HI>
ORDER BY gain;

-- STEP 5c — L-PNL-5 constraint. sell_new_sale = 0 AND both_new_sale = 0.
SELECT COUNT(*) AS total_pairs,
  COUNT(*) FILTER (WHERE b.type_of_sale = 'New Sale') AS buy_new_sale,
  COUNT(*) FILTER (WHERE s.type_of_sale = 'New Sale') AS sell_new_sale,
  COUNT(*) FILTER (WHERE b.type_of_sale = 'New Sale'
                     AND s.type_of_sale = 'New Sale') AS both_new_sale
FROM landed_pnl_pairs_mv p
JOIN landed_transactions b ON b.id = p.buy_id
JOIN landed_transactions s ON s.id = p.sell_id;

-- STEP 5d — split/merge review for this batch (read-only; expect 0 rows).
--   Column-agnostic (S411): the view has no sell_id / buy_id columns.
SELECT r.* FROM landed_split_merge_review r
WHERE to_jsonb(r)::text ~ ':\s*(<ID_REGEX>)[,}]';

-- STEP 6 — L-ING-1 GATE A (expect 0)
SELECT COUNT(*) AS gate_a_unstamped FROM landed_transactions
WHERE id BETWEEN <LO> AND <HI> AND release_date IS NULL;

-- STEP 6b — L-ING-1 GATE B, STANDALONE (expect 0 rows)
SELECT DISTINCT lt.postal_code, lt.address FROM landed_transactions lt
WHERE lt.id BETWEEN <LO> AND <HI>
  AND NOT EXISTS (SELECT 1 FROM postal_building pb
                   WHERE pb.postal_code = lt.postal_code
                     AND pb.lat IS NOT NULL AND pb.lng IS NOT NULL);

-- STEP 7 — RECORDS (export CSV)
SELECT * FROM public.pa_records_run(ARRAY['landed'], <PREV_MAX>, '<TAG>');
