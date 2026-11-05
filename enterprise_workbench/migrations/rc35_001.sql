-- RC3.5 candidate proposal workflow. Apply ONLY on isolated PG16 test database.
-- No source inventory or external MES/SRM side effects.
CREATE TABLE IF NOT EXISTS version_b_rc2.proposals (
 proposal_id uuid PRIMARY KEY,
 tenant_id text NOT NULL,
 run_id text NOT NULL,
 actor_id text NOT NULL,
 idempotency_key text NOT NULL,
 request_hash text NOT NULL CHECK(length(request_hash)=64),
 input_hash text NOT NULL CHECK(length(input_hash)=64),
 candidate_hash text NOT NULL CHECK(length(candidate_hash)=64),
 change_request jsonb NOT NULL,
 simulation_result jsonb NOT NULL,
 status text NOT NULL DEFAULT 'DRAFT' CHECK(status IN ('DRAFT','CANCELLED','SUBMITTED','APPROVED','REJECTED','COMPENSATION_REQUESTED')),
 command_id uuid,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,idempotency_key),
 UNIQUE(tenant_id,proposal_id),
 FOREIGN KEY (tenant_id,run_id) REFERENCES version_b_rc2.run_tenants(tenant_id,run_id)
);
CREATE INDEX IF NOT EXISTS rc35_proposals_tenant_run ON version_b_rc2.proposals(tenant_id,run_id,created_at DESC);
