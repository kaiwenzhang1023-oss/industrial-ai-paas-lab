-- V1.5 M1-01: additive, isolated security schema. TEST DATABASE ONLY.
BEGIN;
DO $$ BEGIN
 IF current_database() <> 'industrial_lab_v15_test' THEN RAISE EXCEPTION 'M1-01 migration is restricted to industrial_lab_v15_test'; END IF;
END $$;
CREATE SCHEMA IF NOT EXISTS mcp_v15;
CREATE TABLE mcp_v15.principals (
 tenant_id text NOT NULL CHECK(length(tenant_id)>0), principal_id text NOT NULL CHECK(length(principal_id)>0),
 status text NOT NULL DEFAULT 'DISABLED' CHECK(status IN ('ACTIVE','DISABLED')),
 PRIMARY KEY(tenant_id,principal_id));
CREATE TABLE mcp_v15.principal_permissions (
 tenant_id text NOT NULL, principal_id text NOT NULL, permission text NOT NULL CHECK(length(permission)>0),
 granted_at timestamptz NOT NULL DEFAULT now(), revoked_at timestamptz,
 PRIMARY KEY(tenant_id,principal_id,permission),
 FOREIGN KEY(tenant_id,principal_id) REFERENCES mcp_v15.principals(tenant_id,principal_id));
CREATE TABLE mcp_v15.resource_registry (
 tenant_id text NOT NULL, resource_type text NOT NULL, resource_id text NOT NULL,
 status text NOT NULL DEFAULT 'STALE' CHECK(status IN ('ACTIVE','STALE','REVOKED')),
 source_fingerprint text, verified_at timestamptz NOT NULL,
 PRIMARY KEY(tenant_id,resource_type,resource_id));
CREATE TABLE mcp_v15.resource_grants (
 tenant_id text NOT NULL, principal_id text NOT NULL, resource_type text NOT NULL,
 resource_id text NOT NULL, permission text NOT NULL, expires_at timestamptz, revoked_at timestamptz,
 PRIMARY KEY(tenant_id,principal_id,resource_type,resource_id,permission),
 FOREIGN KEY(tenant_id,principal_id) REFERENCES mcp_v15.principals(tenant_id,principal_id),
 FOREIGN KEY(tenant_id,resource_type,resource_id) REFERENCES mcp_v15.resource_registry(tenant_id,resource_type,resource_id));
CREATE TABLE mcp_v15.tool_call_state (
 call_id uuid PRIMARY KEY, tenant_id text, principal_id text, tool_id text NOT NULL,
 tool_version text NOT NULL, argument_hash char(64) NOT NULL CHECK(argument_hash ~ '^[0-9a-f]{64}$'),
 status text NOT NULL DEFAULT 'RECEIVED' CHECK(status IN ('RECEIVED','AUTHORIZED','DENIED','RUNNING','COMPLETED','FAILED','TIMED_OUT','UNKNOWN')),
 version integer NOT NULL DEFAULT 0 CHECK(version>=0), deadline_at timestamptz,
 updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE mcp_v15.tool_call_audit (
 event_id uuid PRIMARY KEY, call_id uuid NOT NULL REFERENCES mcp_v15.tool_call_state(call_id),
 event_type text NOT NULL CHECK(event_type IN ('RECEIVED','AUTHORIZED','DENIED','RUNNING','COMPLETED','FAILED','TIMED_OUT','UNKNOWN')),
 occurred_at timestamptz NOT NULL DEFAULT now(), principal_id text, tenant_id text,
 tool_id text NOT NULL, tool_version text NOT NULL,
 argument_hash char(64) NOT NULL CHECK(argument_hash ~ '^[0-9a-f]{64}$'),
 resource_scope_hash char(64), authorization_decision text, outcome text, error_code text,
 duration_ms integer CHECK(duration_ms IS NULL OR duration_ms>=0), correlation_id text, source_version text,
 UNIQUE(call_id,event_type));
CREATE INDEX idx_mcp_v15_audit_call ON mcp_v15.tool_call_audit(call_id,occurred_at);
CREATE INDEX idx_mcp_v15_state_pending ON mcp_v15.tool_call_state(status,updated_at) WHERE status IN ('RECEIVED','AUTHORIZED','RUNNING');
CREATE INDEX idx_mcp_v15_grants_lookup ON mcp_v15.resource_grants(tenant_id,principal_id,permission,resource_type,resource_id);
-- Even table owners cannot change audit records through ordinary UPDATE/DELETE.
CREATE FUNCTION mcp_v15.audit_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'mcp_v15 audit is append-only'; END $$;
CREATE TRIGGER audit_no_update_delete BEFORE UPDATE OR DELETE ON mcp_v15.tool_call_audit
 FOR EACH ROW EXECUTE FUNCTION mcp_v15.audit_append_only();
-- No public access; runtime permissions must be explicitly granted later.
REVOKE ALL ON SCHEMA mcp_v15 FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA mcp_v15 FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA mcp_v15 FROM PUBLIC;
-- Authorization only for active principal, active verified resource and unrevoked/unexpired grants.
CREATE FUNCTION mcp_v15.is_authorized(p_tenant text,p_principal text,p_permission text,p_type text,p_id text)
RETURNS boolean LANGUAGE sql STABLE SECURITY INVOKER SET search_path=pg_catalog AS $$
 SELECT EXISTS (
 SELECT 1 FROM mcp_v15.principals p
 JOIN mcp_v15.principal_permissions pp USING(tenant_id,principal_id)
 JOIN mcp_v15.resource_grants g ON g.tenant_id=p.tenant_id AND g.principal_id=p.principal_id AND g.permission=pp.permission
 JOIN mcp_v15.resource_registry r ON r.tenant_id=g.tenant_id AND r.resource_type=g.resource_type AND r.resource_id=g.resource_id
 WHERE p.tenant_id=p_tenant AND p.principal_id=p_principal AND pp.permission=p_permission
 AND g.resource_type=p_type AND g.resource_id=p_id AND p.status='ACTIVE' AND r.status='ACTIVE'
 AND pp.revoked_at IS NULL AND g.revoked_at IS NULL
 AND (g.expires_at IS NULL OR g.expires_at>now()) AND r.verified_at IS NOT NULL
 );
$$;
-- CAS with same-transaction audit. Controlled execution requires a privileged, trusted caller.
CREATE FUNCTION mcp_v15.advance_call(p_call uuid,p_expected text,p_version integer,p_next text,p_event uuid)
RETURNS boolean LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
DECLARE s mcp_v15.tool_call_state%ROWTYPE;
BEGIN
 IF NOT ((p_expected='RECEIVED' AND p_next IN ('AUTHORIZED','DENIED','FAILED','TIMED_OUT')) OR
 (p_expected='AUTHORIZED' AND p_next IN ('RUNNING','FAILED','TIMED_OUT')) OR
 (p_expected='RUNNING' AND p_next IN ('COMPLETED','FAILED','TIMED_OUT','UNKNOWN'))) THEN
  RAISE EXCEPTION 'invalid state transition % -> %',p_expected,p_next;
 END IF;
 UPDATE mcp_v15.tool_call_state SET status=p_next,version=version+1,updated_at=now()
 WHERE call_id=p_call AND status=p_expected AND version=p_version RETURNING * INTO s;
 IF NOT FOUND THEN RETURN false; END IF;
 INSERT INTO mcp_v15.tool_call_audit(event_id,call_id,event_type,principal_id,tenant_id,tool_id,tool_version,argument_hash)
 VALUES(p_event,s.call_id,p_next,s.principal_id,s.tenant_id,s.tool_id,s.tool_version,s.argument_hash);
 RETURN true;
END $$;
-- New calls must have a durable RECEIVED audit in the same transaction.
CREATE FUNCTION mcp_v15.receive_call(p_call uuid,p_tenant text,p_principal text,p_tool text,p_version text,p_hash char(64),p_event uuid)
RETURNS void LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
BEGIN
 INSERT INTO mcp_v15.tool_call_state(call_id,tenant_id,principal_id,tool_id,tool_version,argument_hash)
 VALUES(p_call,p_tenant,p_principal,p_tool,p_version,p_hash);
 INSERT INTO mcp_v15.tool_call_audit(event_id,call_id,event_type,principal_id,tenant_id,tool_id,tool_version,argument_hash)
 VALUES(p_event,p_call,'RECEIVED',p_principal,p_tenant,p_tool,p_version,p_hash);
END $$;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA mcp_v15 FROM PUBLIC;
COMMIT;
