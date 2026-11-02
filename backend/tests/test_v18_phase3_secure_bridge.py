import pytest
from app.mcp_v18.durable_ledger import DurableLedger,LedgerConflict
from app.mcp_v18.secure_bridge import SecureBridge,VerifiedIdentity

def test_disabled_and_scope_denied(tmp_path):
    ledger=DurableLedger(tmp_path/'db.sqlite')
    bridge=SecureBridge(ledger,lambda *_:{'ok':True},allowed_tools=['read'],enabled=False)
    identity=VerifiedIdentity('t','p',frozenset({'tool:read'}))
    with pytest.raises(PermissionError): bridge.call(identity,'k','read',{})
    bridge.enabled=True
    with pytest.raises(PermissionError): bridge.call(identity,'k','write',{})
    with pytest.raises(PermissionError): bridge.call({'tenant':'t'},'k','read',{})

def test_result_cached_and_no_replay(tmp_path):
    ledger=DurableLedger(tmp_path/'db.sqlite'); calls=[]
    def invoke(identity,tool,args):
        calls.append(1);return {'ok':True}
    bridge=SecureBridge(ledger,invoke,allowed_tools=['read'],enabled=True)
    identity=VerifiedIdentity('t','p',frozenset({'tool:read'}))
    assert bridge.call(identity,'k','read',{'a':1})=={'ok':True}
    assert bridge.call(identity,'k','read',{'a':1})=={'ok':True}
    assert len(calls)==1
    with pytest.raises(LedgerConflict): bridge.call(identity,'k','read',{'a':2})

def test_crash_unknown_never_replayed(tmp_path):
    ledger=DurableLedger(tmp_path/'db.sqlite');calls=[]
    def fail(*_):
        calls.append(1);raise RuntimeError('downstream failed')
    bridge=SecureBridge(ledger,fail,allowed_tools=['read'],enabled=True)
    identity=VerifiedIdentity('t','p',frozenset({'tool:read'}))
    with pytest.raises(RuntimeError,match='downstream failed'): bridge.call(identity,'k','read',{})
    with pytest.raises(RuntimeError,match='UNCERTAIN_RESULT_NO_REPLAY'): bridge.call(identity,'k','read',{})
    assert len(calls)==1

def test_missing_scope(tmp_path):
    b=SecureBridge(DurableLedger(tmp_path/'db.sqlite'),lambda *_:None,allowed_tools=['read'],enabled=True)
    with pytest.raises(PermissionError): b.call(VerifiedIdentity('t','p',frozenset()),'k','read',{})
