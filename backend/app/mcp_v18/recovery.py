"""V1.8 conservative durable ledger triage; NEVER retries ambiguous effects."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Decision:
    action: str
    reason: str

def decide(status, age_seconds, *, timeout=300, idempotent=False, persisted_result=False):
    if not isinstance(age_seconds,(int,float)) or age_seconds<0 or timeout<=0:
        return Decision('MANUAL_REVIEW','Invalid clock or threshold')
    if status=='DONE' and persisted_result:
        return Decision('RETURN_CACHED','Durable result already recorded')
    if status=='DONE':
        return Decision('MANUAL_REVIEW','Completed without durable result')
    if status=='IN_PROGRESS' and age_seconds<timeout:
        return Decision('WAIT','Execution may be active')
    if status in ('IN_PROGRESS','FAILED','UNKNOWN'):
        return Decision('MANUAL_REVIEW','Outcome ambiguous; no automatic replay')
    return Decision('MANUAL_REVIEW','Unrecognized ledger state')
