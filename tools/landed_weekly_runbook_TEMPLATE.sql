-- ============================================================================
-- ATLAS — LANDED weekly URA REALIS ingest runbook — TEMPLATE (S391)
-- Copy to landed_weekly_<YYYYMMDD>_runbook.sql and replace every <<TOKEN>>:
--   <<WM>>        watermark in  = MAX(id) before the append (row count must equal it)
--   <<FIRST>>     first new id  = <<WM>> + 1
--   <<LAST>>      last new id   = <<WM>> + <<N>>
--   <<N>>         batch row count (CSV rows)
--   <<REL1>> <<N1>> / <<REL2>> <<N2>>   release dates (ISO) and rows per release
--   <<PAIRS>>     expected new pairs (Step 5b)   <<BNS>> buy_new_sale baseline (Step 5c floor)
-- Fixes carried in vs the 29 Aug file:
--   * Step 5d — landed_split_merge_review has NO sell_id/buy_id (keyed on address
--     + dates). Column-agnostic jsonb query below (S390).
--   * Gate B — LPAD postal match; triage uses postal_building.lat / lng (there is
--     no latitude/longitude column).
--   * Step 2 — R1 weekend_release table-wide check (S389).
--   * Every write: Tab C verify selects something the RETURNING does not.
-- RUN EACH STEP IN ITS OWN FRESH TAB. The editor shows only the LAST result set.
-- Probe columns (pg_attribute) before querying any object not used this session.
-- ============================================================================


-- STEP 0b — watermark. MUST return <<WM>> / <<WM>>. Halt on mismatch.
SELECT COUNT(*) AS rows_now, MAX(id) AS max_id FROM landed_transactions;


-- STEP 0c — overlap probe (address + sale_date + price). MUST return 0 rows.
WITH batch(address, sale_date, transacted_price) AS (VALUES
  ('<<ADDRESS>>', DATE '<<YYYY-MM-DD>>', 0)   -- one line per CSV row
)
SELECT b.* FROM batch b
JOIN landed_transactions t
  ON upper(trim(t.address)) = upper(trim(b.address))
 AND t.sale_date = b.sale_date AND t.transacted_price = b.transacted_price;


-- STEP 1 — CSV append (NO SQL). Table Editor -> landed_transactions (BASE TABLE,
-- never _geo / _public) -> Insert -> Import data from CSV. Toast must state <<N>> rows.


-- STEP 2 — post-insert checks. Every value must match.
SELECT 'rows_now' AS check, COUNT(*)::text AS value, '<<LAST>>' AS expected FROM landed_transactions
UNION ALL SELECT 'max_id',       MAX(id)::text,  '<<LAST>>' FROM landed_transactions
UNION ALL SELECT 'batch_rows',   COUNT(*)::text, '<<N>>'    FROM landed_transactions WHERE id BETWEEN <<FIRST>> AND <<LAST>>
UNION ALL SELECT 'rel_1',        COUNT(*)::text, '<<N1>>'   FROM landed_transactions WHERE id BETWEEN <<FIRST>> AND <<LAST>> AND release_date = DATE '<<REL1>>'
UNION ALL SELECT 'rel_2',        COUNT(*)::text, '<<N2>>'   FROM landed_transactions WHERE id BETWEEN <<FIRST>> AND <<LAST>> AND release_date = DATE '<<REL2>>'
UNION ALL SELECT 'aborted_null', COUNT(*)::text, '0'        FROM landed_transactions WHERE id BETWEEN <<FIRST>> AND <<LAST>> AND is_aborted IS NULL
UNION ALL SELECT 'aborted_true', COUNT(*)::text, '0'        FROM landed_transactions WHERE id BETWEEN <<FIRST>> AND <<LAST>> AND is_aborted IS TRUE
UNION ALL SELECT 'postal_bad',   COUNT(*)::text, '0'        FROM landed_transactions WHERE id BETWEEN <<FIRST>> AND <<LAST>> AND (postal_code IS NULL OR length(postal_code::text) <> 6)
UNION ALL SELECT 'R1_weekend_release', COUNT(*)::text, '0'  FROM landed_transactions WHERE EXTRACT(ISODOW FROM release_date) IN (6,7);


-- STEP 2b — L-ING-2 AREA-MATCH GATE (pre-P&L). Any row = review with Tony before Step 5.
SELECT n.id, n.address, n.sale_date, n.area_sqft AS new_area, p.area_sqft AS prior_area,
       p.sale_date AS prior_date,
       round(((n.area_sqft - p.area_sqft) / p.area_sqft * 100)::numeric, 1) AS drift_pct
FROM landed_transactions n
JOIN landed_transactions p ON upper(trim(p.address)) = upper(trim(n.address)) AND p.id < <<FIRST>>
WHERE n.id BETWEEN <<FIRST>> AND <<LAST>>
  AND abs((n.area_sqft - p.area_sqft) / p.area_sqft) > 0.05
ORDER BY abs((n.area_sqft - p.area_sqft) / p.area_sqft) DESC;


-- STEP 3 — ABORTED CAVEATS (present in DB, absent from fresh export). UPDATE, never DELETE.
-- TAB A (dry run): expect 1 row per id, then ROLLBACK
BEGIN;
UPDATE landed_transactions SET is_aborted = TRUE
WHERE id IN (<<ABORTED_IDS>>) AND is_aborted IS NOT TRUE
RETURNING id;
ROLLBACK;
-- TAB B (commit, fresh tab): same UPDATE ... RETURNING id; then COMMIT;
-- TAB C (verify, fresh tab) — differs from RETURNING: table-wide aborted count + each flag.
-- SELECT (SELECT COUNT(*) FROM landed_transactions WHERE is_aborted IS TRUE) AS aborted_total,
--        bool_and(is_aborted) AS all_flagged
-- FROM landed_transactions WHERE id IN (<<ABORTED_IDS>>);


-- STEP 4 — amendments (if any): same three-tab pattern; Tab C checks the changed field directly.


-- STEP 5a — P&L rebuild (returns NULL — normal). Run AFTER Step 3 commits.
SELECT refresh_landed_pnl_pairs();


-- STEP 5b — new pairs from this batch. Expect <<PAIRS>> rows.
-- MV columns: gain / gain_pct / pair_flag / hold_days / ann_return (NOT `profit`).
SELECT sell_id, buy_id, address, buy_price, sell_price, gain, gain_pct,
       hold_days, ann_return, pair_flag, area_diff_pct
FROM landed_pnl_pairs_mv WHERE sell_id BETWEEN <<FIRST>> AND <<LAST>> ORDER BY gain;


-- STEP 5c — L-PNL-5 constraint (after EVERY refresh). MV has NO type_of_sale — join back.
-- sell_new_sale = 0 AND both_new_sale = 0. buy_new_sale >= <<BNS>> (a FLOOR, not a point).
-- Also the read-back that closes the ingest: total_pairs = landed_pnl_pairs_mv count.
SELECT COUNT(*) AS total_pairs,
       COUNT(*) FILTER (WHERE b.type_of_sale = 'New Sale') AS buy_new_sale,
       COUNT(*) FILTER (WHERE s.type_of_sale = 'New Sale') AS sell_new_sale,
       COUNT(*) FILTER (WHERE b.type_of_sale = 'New Sale' AND s.type_of_sale = 'New Sale') AS both_new_sale
FROM landed_pnl_pairs_mv p
JOIN landed_transactions b ON b.id = p.buy_id
JOIN landed_transactions s ON s.id = p.sell_id;


-- STEP 5d — split/merge divertees (CORRECTED S390). The view has NO id columns;
-- this finds any review row referencing a batch id in ANY column. Expect 0 rows
-- unless Step 2b flagged a subdivision (then that address must appear here and
-- be ABSENT from 5b).
SELECT r.* FROM landed_split_merge_review r
WHERE EXISTS (SELECT 1 FROM jsonb_each_text(to_jsonb(r)) e
              WHERE e.value ~ '^\d+$' AND e.value::bigint BETWEEN <<FIRST>> AND <<LAST>>);
-- If 0 rows but 2b flagged something, also check by address/date:
-- SELECT * FROM landed_split_merge_review WHERE upper(address) = upper('<<ADDRESS>>');


-- STEP 6 — L-ING-1 GATES. BOTH must close at zero.
-- GATE A — release_date stamping, batch-scoped. Expect 0.
SELECT COUNT(*) AS gate_a_unstamped FROM landed_transactions
WHERE id BETWEEN <<FIRST>> AND <<LAST>> AND release_date IS NULL;

-- GATE B — geocode coverage, batch-scoped (LPAD). Expect 0 rows. Run STANDALONE —
-- never as part of a multi-column screenshot that can cut it off.
SELECT DISTINCT n.postal_code, n.address
FROM landed_transactions n
WHERE n.id BETWEEN <<FIRST>> AND <<LAST>>
  AND NOT EXISTS (SELECT 1 FROM postal_building pb
                  WHERE pb.postal_code = LPAD(n.postal_code::text, 6, '0'))
ORDER BY 1;
-- GATE B triage: absent = INSERT, present-with-NULL = UPDATE (columns lat / lng).
-- SELECT postal_code, lat, lng FROM postal_building WHERE postal_code IN ('<<POSTAL>>');
-- Geocode via the OneMap batch console route (2 s spacing) — never rapid-fire.


-- STEP 7 — record breakers: run landed_record_breakers.sql with watermark <<WM>>.

-- ============================================================================
-- NOT NEEDED: ANALYZE / NOTIFY pgrst / deploy / seed refresh. Landed is live-fetch
-- via landed_transactions_geo. UAT (Incognito): Landed chip -> This week = <<N>>
-- -> new pins render -> pair badges correct.
-- END OF FILE
