-- M2 integration: independent effective-dated BOM source and atomic JSONB audit payload.
BEGIN;
CREATE TABLE IF NOT EXISTS mock_erp.effective_bom_headers (
 parent_id text NOT NULL, version text NOT NULL, status text NOT NULL CHECK(status IN ('DRAFT','RELEASED')),
 valid_from date NOT NULL, valid_to_exclusive date,
 PRIMARY KEY(parent_id,version), CHECK(valid_to_exclusive IS NULL OR valid_to_exclusive>valid_from)
);
CREATE TABLE IF NOT EXISTS mock_erp.effective_bom_components (
 parent_id text NOT NULL, version text NOT NULL, line_no int NOT NULL,
 component_id text NOT NULL REFERENCES mock_erp.materials(material_id),
 qty_per numeric(18,4) NOT NULL CHECK(qty_per>0),
 PRIMARY KEY(parent_id,version,line_no),
 FOREIGN KEY(parent_id,version) REFERENCES mock_erp.effective_bom_headers(parent_id,version)
);
CREATE TABLE IF NOT EXISTS platform.integrated_mrp_payloads (
 run_id text PRIMARY KEY REFERENCES platform.requirement_runs(run_id) ON DELETE CASCADE,
 snapshot_as_of date NOT NULL, engine text NOT NULL,
 source_versions jsonb NOT NULL, result_json jsonb NOT NULL,
 result_hash char(64) NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_integrated_mrp_asof ON platform.integrated_mrp_payloads(snapshot_as_of);
COMMIT;
