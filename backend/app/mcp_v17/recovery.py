"""Fail-closed recovery inspection through the operator-only ledger API."""
from dataclasses import dataclass

@dataclass(frozen=True)
class RecoveryDecision:
    status: str
    action: str
    reason: str

def classify(status, age_seconds, threshold=300):
    if status == 'DONE': return RecoveryDecision('DONE','RETURN_CACHED','Already finalized')
    if status != 'IN_PROGRESS': return RecoveryDecision('UNKNOWN','MANUAL_REVIEW','Unexpected ledger state')
    if age_seconds < 0: return RecoveryDecision('UNKNOWN','MANUAL_REVIEW','Clock anomaly')
    if age_seconds < threshold: return RecoveryDecision('IN_PROGRESS','WAIT','Execution may still be active')
    return RecoveryDecision('UNKNOWN','MANUAL_REVIEW','Stale call; no automatic replay')

def inspect_stale(conn, threshold=300, limit=100):
    if not (1 <= threshold <= 86400 and 1 <= limit <= 500):
        raise ValueError('INVALID_RECOVERY_BOUNDS')
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute('SET LOCAL ROLE mcp_v15_ledger_operator_test')
            cur.execute('SELECT tenant_id,principal_id,request_id,status,age_seconds '
                        'FROM mcp_v15.ledger_inspect_stale(%s,%s)',(threshold,limit))
            return [{'tenant_id':row[0],'principal_id':row[1],'request_id':row[2],
                     'decision':classify(row[3],row[4],threshold).__dict__} for row in cur.fetchall()]
