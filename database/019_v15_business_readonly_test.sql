-- TEST-ONLY role, on industrial_lab_v14_test. No business data mutation.
BEGIN;
DO $$ BEGIN
 IF current_database() <> 'industrial_lab_v14_test' THEN RAISE EXCEPTION 'V14 TEST DATABASE ONLY'; END IF;
 IF to_regclass('platform.integrated_mrp_payloads') IS NULL OR to_regclass('mes_v13.work_orders') IS NULL OR to_regclass('srm_v14.purchase_requisitions') IS NULL THEN RAISE EXCEPTION 'V14 BASELINE MISSING'; END IF;
 IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname='mcp_v15_business_reader_test') THEN
  CREATE ROLE mcp_v15_business_reader_test NOLOGIN NOBYPASSRLS;
 END IF;
END $$;
GRANT mcp_v15_business_reader_test TO CURRENT_USER;
GRANT USAGE ON SCHEMA platform,mock_erp,mock_wms,mes_v13,srm_v14 TO mcp_v15_business_reader_test;
GRANT SELECT (run_id,input_hash,status) ON platform.requirement_runs TO mcp_v15_business_reader_test;
GRANT SELECT (run_id,snapshot_as_of,source_versions,result_json,result_hash) ON platform.integrated_mrp_payloads TO mcp_v15_business_reader_test;
GRANT SELECT (material_id,warehouse_id,on_hand,reserved,blocked,snapshot_at) ON mock_wms.inventory_balances TO mcp_v15_business_reader_test;
GRANT SELECT (work_order_id,source_run_id,source_plan_id,product_id,quantity,due_date,status,revision) ON mes_v13.work_orders TO mcp_v15_business_reader_test;
GRANT SELECT (pr_id,source_run_id,source_plan_id,material_id,quantity,uom,need_date,status,created_at) ON srm_v14.purchase_requisitions TO mcp_v15_business_reader_test;
GRANT SELECT (material_id,make_buy,uom) ON mock_erp.materials TO mcp_v15_business_reader_test;
COMMIT;
