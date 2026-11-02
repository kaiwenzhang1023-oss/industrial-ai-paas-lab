import pytest
from app.workflow.runtime import TRANSITIONS, WorkflowConflict, _hash

def test_happy_path_contract():
    states=['CREATED','VALIDATING','CALCULATING','GENERATING_ADVICE','WAITING_REVIEW']
    events=['START','VALIDATION_PASSED','MRP_COMPLETED','ADVICE_DRAFTED']
    for old,event,new in zip(states,events,states[1:]): assert TRANSITIONS[(old,event)]==new

def test_failure_retry():
    assert TRANSITIONS[('CALCULATING','FAIL')]=='FAILED'
    assert TRANSITIONS[('FAILED','RETRY')]=='VALIDATING'

def test_no_approval_bypass():
    assert ('WAITING_REVIEW','APPROVE') not in TRANSITIONS
    assert ('CREATED','MRP_COMPLETED') not in TRANSITIONS

def test_event_hash_stable_and_sensitive():
    assert _hash('START',{'a':1,'b':2})==_hash('START',{'b':2,'a':1})
    assert _hash('START',{})!=_hash('FAIL',{})
