import concurrent.futures
import pytest
from app.mcp_v18.durable_ledger import DurableLedger,LedgerConflict

def test_claim_restart_cache_and_audit(tmp_path):
    path=tmp_path/'ledger.db'; a=DurableLedger(path)
    assert a.claim('t','p','k','tool',{'x':1})['action']=='EXECUTE_ONCE'
    b=DurableLedger(path)
    assert b.claim('t','p','k','tool',{'x':1})['action']=='DO_NOT_REPLAY'
    assert b.inspect('t','p','k',timeout=.000001)['action']=='MANUAL_REVIEW'
    a.complete('t','p','k','tool',{'x':1},{'ok':True})
    assert b.claim('t','p','k','tool',{'x':1})=={'action':'RETURN_CACHED','result':{'ok':True}}
    assert b.audit('t','p','k')==['CLAIMED','DO_NOT_REPLAY','RESULT_COMMITTED','RETURN_CACHED']

def test_conflict_scope_and_result_protection(tmp_path):
    l=DurableLedger(tmp_path/'l.db')
    l.claim('a','p','k','tool',{})
    with pytest.raises(LedgerConflict): l.claim('a','p','k','other',{})
    with pytest.raises(LedgerConflict): l.complete('a','p','k','other',{},1)
    assert l.claim('b','p','k','other',{})['action']=='EXECUTE_ONCE'
    l.complete('a','p','k','tool',{},1)
    with pytest.raises(LedgerConflict): l.complete('a','p','k','tool',{},2)
    assert 'CONFLICT_DENIED' in l.audit('a','p','k')

def test_atomic_claim_concurrent(tmp_path):
    path=tmp_path/'concurrent.db'
    def run(_): return DurableLedger(path).claim('t','p','k','tool',{})['action']
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool: outcomes=list(pool.map(run,range(16)))
    assert outcomes.count('EXECUTE_ONCE')==1
    assert outcomes.count('DO_NOT_REPLAY')==15

def test_unknown_never_replayed(tmp_path):
    l=DurableLedger(tmp_path/'x.db')
    assert l.inspect('t','p','absent')['action']=='NOT_FOUND'
    l.claim('t','p','k','tool',{})
    assert l.claim('t','p','k','tool',{})['action']=='DO_NOT_REPLAY'
    with pytest.raises(ValueError): l.claim('','p','k','tool',{})
