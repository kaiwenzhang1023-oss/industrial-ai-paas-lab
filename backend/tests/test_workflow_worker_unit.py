from app.workflow.worker import claim,finish,pump_once,auto_advance
import pytest

def test_claim_validation():
    with pytest.raises(ValueError): claim(None,'',10)
    with pytest.raises(ValueError): claim(None,'w',0)
    with pytest.raises(ValueError): claim(None,'w',10,0)

def test_finish_validation():
    with pytest.raises(ValueError): finish(None,1,'w',max_attempts=0)

def test_auto_advance_blocks_without_mrp(monkeypatch):
    monkeypatch.setattr('app.workflow.worker.read',lambda conn,wid:{'state':'CALCULATING','version':2,'order_id':'SO1'})
    assert auto_advance(None,'WF1')['reason']=='MRP_RUNNER_REQUIRED'

def test_auto_advance_deterministic_start(monkeypatch):
    monkeypatch.setattr('app.workflow.worker.read',lambda conn,wid:{'state':'CREATED','version':0,'order_id':'SO1'})
    calls=[]
    def fake(*args,**kwargs):
        calls.append((args,kwargs));return {'state':'VALIDATING'}
    monkeypatch.setattr('app.workflow.worker.dispatch',fake)
    assert auto_advance(None,'WF1')['state']=='VALIDATING'
    assert calls[0][1]['expected_version']==0
