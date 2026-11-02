-- V0.3 persistent run and order-level pegging, safe to reapply.
CREATE TABLE IF NOT EXISTS platform.requirement_pegs (
 run_id text NOT NULL REFERENCES platform.requirement_runs(run_id) ON DELETE CASCADE,
 material_id text NOT NULL,
 need_date date NOT NULL,
 order_id text NOT NULL,
 gross numeric(18,4) NOT NULL CHECK(gross>=0),
 from_stock numeric(18,4) NOT NULL CHECK(from_stock>=0),
 from_receipts numeric(18,4) NOT NULL CHECK(from_receipts>=0),
 from_planned numeric(18,4) NOT NULL CHECK(from_planned>=0),
 PRIMARY KEY(run_id,material_id,need_date,order_id),
 CHECK(gross=from_stock+from_receipts+from_planned)
);
CREATE INDEX IF NOT EXISTS idx_pegs_order ON platform.requirement_pegs(order_id,run_id);
CREATE INDEX IF NOT EXISTS idx_requirements_run_date ON platform.material_requirements(run_id,need_date);
