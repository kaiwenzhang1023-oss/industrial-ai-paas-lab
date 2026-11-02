-- DEV/TEST ONLY: execute manually on an isolated PostgreSQL database.
-- Never auto-apply to Neon Production or Render Production.
CREATE TABLE IF NOT EXISTS mcp_v18_calls (
 tenant text NOT NULL, principal text NOT NULL, request_key text NOT NULL,
 fingerprint text NOT NULL, state text NOT NULL CHECK (state IN ('IN_PROGRESS','DONE')),
 result jsonb, created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (tenant,principal,request_key));
CREATE TABLE IF NOT EXISTS mcp_v18_events (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 tenant text NOT NULL, principal text NOT NULL, request_key text NOT NULL,
 event text NOT NULL, occurred_at timestamptz NOT NULL DEFAULT now());
