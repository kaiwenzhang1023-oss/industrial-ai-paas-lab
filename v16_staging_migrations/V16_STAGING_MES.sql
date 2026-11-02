-- STAGING ONLY. REVIEW BEFORE EXECUTION. NOT AUTHORIZED FOR PRODUCTION.
-- V1.3 additive MES simulation schema. Apply ONLY to industrial_lab_v13_test.
BEGIN;
CREATE SCHEMA IF NOT EXISTS mes_v13;
CREATE TABLE IF NOT EXISTS mes_v13.routings (
 product_id text NOT NULL, routing_version text NOT NULL, operation_id text NOT NULL,
 sequence integer NOT NULL CHECK(sequence>0), work_center text NOT NULL,
 setup_hours numeric(18,4) NOT NULL CHECK(setup_hours>=0), hours_per_unit numeric(18,4) NOT NULL CHECK(hours_per_unit>0),
 PRIMARY KEY(product_id,routing_version,operation_id), UNIQUE(product_id,routing_version,sequence));
CREATE TABLE IF NOT EXISTS mes_v13.work_orders (
 work_order_id text PRIMARY KEY, source_run_id text NOT NULL REFERENCES platform.requirement_runs(run_id),
 source_plan_id text NOT NULL, source_result_hash text NOT NULL,
 product_id text NOT NULL, quantity numeric(18,4) NOT NULL CHECK(quantity>0),
 due_date date NOT NULL, routing_version text NOT NULL,
 status text NOT NULL DEFAULT 'PLANNED' CHECK(status IN ('PLANNED','RELEASED','IN_PROGRESS','COMPLETED','CANCELLED')),
 revision integer NOT NULL DEFAULT 0 CHECK(revision>=0), created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(source_run_id,source_plan_id));
CREATE TABLE IF NOT EXISTS mes_v13.feedback_events (
 event_id text PRIMARY KEY, work_order_id text NOT NULL REFERENCES mes_v13.work_orders(work_order_id),
 operation_id text NOT NULL, good_qty numeric(18,4) NOT NULL CHECK(good_qty>=0),
 scrap_qty numeric(18,4) NOT NULL CHECK(scrap_qty>=0), event_date date NOT NULL,
 recorded_at timestamptz NOT NULL DEFAULT now(), CHECK(good_qty+scrap_qty>0));
CREATE TABLE IF NOT EXISTS mes_v13.capacity_allocations (
 work_order_id text NOT NULL REFERENCES mes_v13.work_orders(work_order_id),
 operation_id text NOT NULL, work_center text NOT NULL, day date NOT NULL,
 hours numeric(18,4) NOT NULL CHECK(hours>0),
 PRIMARY KEY(work_order_id,operation_id,work_center,day));
CREATE TABLE IF NOT EXISTS mes_v13.audit (
 audit_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, work_order_id text NOT NULL,
 event_type text NOT NULL, detail jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
COMMIT;
