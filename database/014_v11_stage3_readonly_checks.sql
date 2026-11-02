-- W2 Stage3 read-only checks. Execute on Neon isolated branch only.
SELECT current_database() AS db, current_user AS db_user, version() AS server_version;
SELECT table_schema, table_name FROM information_schema.tables
 WHERE table_schema IN ('mock_erp','mock_wms','mock_mes','platform','audit') AND table_type='BASE TABLE'
 ORDER BY table_schema,table_name;
SELECT order_id,status,version FROM mock_erp.sales_orders ORDER BY order_id LIMIT 20;
SELECT COUNT(*) AS confirmed_order_count FROM mock_erp.sales_orders WHERE status='CONFIRMED';
SELECT COUNT(*) AS effective_bom_headers FROM mock_erp.effective_bom_headers;
SELECT COUNT(*) AS integrated_payload_count FROM platform.integrated_mrp_payloads;
SELECT COUNT(*) AS pegging_source_count FROM platform.mrp_supply_sources;
SELECT COUNT(*) AS pegging_allocation_count FROM platform.mrp_demand_allocations;
SELECT COUNT(*) AS pegging_edges_count FROM platform.mrp_plan_child_edges;
