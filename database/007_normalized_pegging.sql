-- Run-scoped relational pegging, written atomically with JSONB snapshot.
BEGIN;
CREATE TABLE IF NOT EXISTS platform.mrp_supply_sources (
 run_id text NOT NULL REFERENCES platform.integrated_mrp_payloads(run_id) ON DELETE CASCADE,
 supply_id text NOT NULL, material_id text NOT NULL,
 supply_kind text NOT NULL CHECK (supply_kind IN ('STOCK','RECEIPT','PLAN')),
 source_system text NOT NULL, source_document_id text NOT NULL, source_line_id text NOT NULL,
 capacity_qty numeric(24,6) NOT NULL CHECK(capacity_qty>=0),
 allocated_qty numeric(24,6) NOT NULL CHECK(allocated_qty>=0),
 remaining_qty numeric(24,6) NOT NULL CHECK(remaining_qty>=0),
 PRIMARY KEY(run_id,supply_id),
 CHECK(capacity_qty=allocated_qty+remaining_qty)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_mrp_receipt_origin
 ON platform.mrp_supply_sources(run_id,source_system,source_document_id,source_line_id)
 WHERE supply_kind='RECEIPT';
CREATE TABLE IF NOT EXISTS platform.mrp_demand_allocations (
 allocation_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 run_id text NOT NULL, demand_id text NOT NULL, supply_id text NOT NULL,
 material_id text NOT NULL, root_order_id text, need_date date NOT NULL,
 allocated_qty numeric(24,6) NOT NULL CHECK(allocated_qty>0),
 parent_plan_id text, bom_version text,
 FOREIGN KEY(run_id,supply_id) REFERENCES platform.mrp_supply_sources(run_id,supply_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_mrp_alloc_order ON platform.mrp_demand_allocations(run_id,root_order_id);
CREATE TABLE IF NOT EXISTS platform.mrp_plan_child_edges (
 run_id text NOT NULL REFERENCES platform.integrated_mrp_payloads(run_id) ON DELETE CASCADE,
 parent_plan_id text NOT NULL, child_demand_id text NOT NULL,
 parent_material text NOT NULL, child_material text NOT NULL,
 bom_version text, child_need_date date NOT NULL, child_gross_qty numeric(24,6) NOT NULL CHECK(child_gross_qty>0),
 PRIMARY KEY(run_id,parent_plan_id,child_demand_id),
 FOREIGN KEY(run_id,parent_plan_id) REFERENCES platform.mrp_supply_sources(run_id,supply_id)
);
COMMIT;
