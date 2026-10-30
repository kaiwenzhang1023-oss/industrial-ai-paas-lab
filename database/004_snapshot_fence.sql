-- M2-02-01: immutable metadata for the locked source snapshot of each MRP run.
CREATE TABLE IF NOT EXISTS platform.run_snapshot_fences (
 run_id text PRIMARY KEY REFERENCES platform.requirement_runs(run_id) ON DELETE CASCADE,
 as_of date NOT NULL,
 source_versions jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
