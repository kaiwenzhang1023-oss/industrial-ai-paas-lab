-- RC2 REVIEW CANDIDATE / NOT APPROVED FOR EXECUTION UNTIL REVIEWED.
-- Source: V16_STAGING_SRM.sql; target: Neon development branch dev-v1-6-backend-pg18.
-- Neon branch cannot be securely identified by current_database(); VERIFY branch in console.
-- Do not run on production. No live credentials included.
BEGIN;
-- MANUAL CONFIRMATION ONLY: does not technically verify Neon branch.
SET LOCAL v16.operator_confirmed_dev_branch = 'dev-v1-6-backend-pg18';
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
DO $guard$
BEGIN
 IF current_database() <> 'industrial_lab_demo' THEN
   RAISE EXCEPTION 'Unexpected database: %', current_database();
 END IF;
 IF current_setting('v16.operator_confirmed_dev_branch', true) IS DISTINCT FROM 'dev-v1-6-backend-pg18' THEN
   RAISE EXCEPTION 'Operator branch confirmation missing. This does NOT verify Neon branch.';
 END IF;
 IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='lab_schema_migrations') THEN
   RAISE EXCEPTION 'Missing migration ledger';
 END IF;
 IF EXISTS (SELECT 1 FROM public.lab_schema_migrations WHERE filename='022_v16_srm_pg18.sql') THEN
   RAISE EXCEPTION 'Already applied: 022_v16_srm_pg18.sql';
 END IF;
END $guard$;
CREATE SCHEMA IF NOT EXISTS srm_v14;
CREATE TABLE IF NOT EXISTS srm_v14.suppliers (supplier_id text PRIMARY KEY, code text NOT NULL UNIQUE, name text NOT NULL, status text NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','INACTIVE')), revision bigint NOT NULL DEFAULT 0, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS srm_v14.supplier_items (supplier_id text NOT NULL REFERENCES srm_v14.suppliers(supplier_id), material_id text NOT NULL REFERENCES mock_erp.materials(material_id), moq numeric(18,4) NOT NULL DEFAULT 0 CHECK(moq>=0), lead_days int NOT NULL DEFAULT 0 CHECK(lead_days>=0), capacity numeric(18,4) CHECK(capacity>0), PRIMARY KEY(supplier_id,material_id));
CREATE TABLE IF NOT EXISTS srm_v14.purchase_requisitions (pr_id text PRIMARY KEY, source_run_id text NOT NULL REFERENCES platform.requirement_runs(run_id), source_result_hash text NOT NULL, source_plan_id text NOT NULL, material_id text NOT NULL REFERENCES mock_erp.materials(material_id), quantity numeric(18,4) NOT NULL CHECK(quantity>0), uom text NOT NULL, need_date date NOT NULL, release_date date NOT NULL, bom_version text, status text NOT NULL DEFAULT 'OPEN' CHECK(status IN ('OPEN','ORDERED')), created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(source_run_id,source_plan_id));
CREATE TABLE IF NOT EXISTS srm_v14.purchase_orders (po_id text PRIMARY KEY, supplier_id text NOT NULL REFERENCES srm_v14.suppliers(supplier_id), status text NOT NULL DEFAULT 'DRAFT' CHECK(status IN ('DRAFT','ISSUED','PARTIALLY_CONFIRMED','CONFIRMED','REJECTED','CANCELLED','FULFILLED')), revision bigint NOT NULL DEFAULT 0, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS srm_v14.purchase_order_lines (po_line_id text PRIMARY KEY, po_id text NOT NULL REFERENCES srm_v14.purchase_orders(po_id), pr_id text NOT NULL UNIQUE REFERENCES srm_v14.purchase_requisitions(pr_id), material_id text NOT NULL REFERENCES mock_erp.materials(material_id), ordered_qty numeric(18,4) NOT NULL CHECK(ordered_qty>0), required_date date NOT NULL);
CREATE TABLE IF NOT EXISTS srm_v14.supplier_confirmations (confirmation_id text PRIMARY KEY, po_id text NOT NULL REFERENCES srm_v14.purchase_orders(po_id), event_hash text NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS srm_v14.supplier_confirmation_schedules (schedule_id text PRIMARY KEY, confirmation_id text NOT NULL REFERENCES srm_v14.supplier_confirmations(confirmation_id), po_line_id text NOT NULL REFERENCES srm_v14.purchase_order_lines(po_line_id), confirmed_qty numeric(18,4) NOT NULL CHECK(confirmed_qty>0), promised_date date NOT NULL);
CREATE TABLE IF NOT EXISTS srm_v14.delivery_changes (change_id text PRIMARY KEY, po_line_id text NOT NULL REFERENCES srm_v14.purchase_order_lines(po_line_id), old_date date NOT NULL, new_date date NOT NULL, reason text NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS srm_v14.supply_exceptions (exception_id text PRIMARY KEY, po_line_id text NOT NULL REFERENCES srm_v14.purchase_order_lines(po_line_id), exception_type text NOT NULL CHECK(exception_type IN ('DELIVERY_DELAY')), risk_qty numeric(18,4) NOT NULL CHECK(risk_qty>0), late_days int NOT NULL CHECK(late_days>0), evidence_hash text NOT NULL, status text NOT NULL DEFAULT 'OPEN', UNIQUE(po_line_id,exception_type));
CREATE TABLE IF NOT EXISTS srm_v14.audit (id bigserial PRIMARY KEY, entity_type text NOT NULL, entity_id text NOT NULL, action text NOT NULL, payload jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now());

INSERT INTO public.lab_schema_migrations(filename,applied_at)
VALUES ('022_v16_srm_pg18.sql', now());
COMMIT;
