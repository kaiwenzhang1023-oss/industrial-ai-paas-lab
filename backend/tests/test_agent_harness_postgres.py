import pytest
from pathlib import Path
from app.agent import generate_and_persist, AgentPolicyError
from app.workflow.runtime import create,dispatch,read
from app.workflow.scheduler import durable_mrp_runner
from app.db.integrated import seed_effective_bom
from app.db.repository import seed

pytestmark=pytest.mark.integration

@pytest.fixture
def db():
 import os
 from app.db.repository import connect
 dsn=os.getenv('TEST_DATABASE_URL')
 if not dsn: pytest.skip('TEST_DATABASE_URL required')
 with connect(dsn) as c:
  c.autocommit=True
  yield c

def test_agent_draft_durable_and_replay(db):
 base=Path(__file__).resolve().parents[2]/'datasets/seed/multi_order.json'
 seed(db,base)
 seed_effective_bom(db)
 wid=create(db,'SO-2026-001')['workflow_id']
 dispatch(db,wid,'agent-start-'+wid,'START',{})
 dispatch(db,wid,'agent-validated-'+wid,'VALIDATION_PASSED',{})
 run_id=durable_mrp_runner(db,wid,'SO-2026-001','2026-11-20')
 dispatch(db,wid,'agent-mrp-'+wid,'MRP_COMPLETED',{'mrp_run_id':run_id})
 outcome=generate_and_persist(db,wid)
 assert outcome['workflow']['state']=='WAITING_REVIEW'
 with db.cursor() as cur:
  cur.execute('SELECT count(*),max(draft_hash) FROM platform.agent_drafts WHERE workflow_id=%s',(wid,))
  count,digest=cur.fetchone()
 assert count==1 and digest==outcome['draft_hash']
 with pytest.raises(AgentPolicyError):generate_and_persist(db,wid)
 assert read(db,wid)['state']=='WAITING_REVIEW'
