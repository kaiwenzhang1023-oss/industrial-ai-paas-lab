"""Real Docker PG16 contract tests. Never writes business data; audit writes are allowed."""
import os,time
import pytest
from app.mcp_v15.full_gateway import FullGateway,issue_test_token
from app.mcp_v15.integration import execute

@pytest.fixture
def pg():
 dsn=os.getenv('M1_TEST_DATABASE_URL')
 if not dsn: pytest.skip('M1_TEST_DATABASE_URL not configured')
 import psycopg
 with psycopg.connect(dsn) as c:
  db,ver=c.execute("SELECT current_database(),current_setting('server_version_num')").fetchone()
  assert db=='industrial_lab_v15_test' and int(ver)//10000==16
  c.commit()
  yield c

@pytest.mark.parametrize("tool,sql,key", [
 ('mrp.get_run','SELECT run_id FROM platform.integrated_mrp_payloads LIMIT 1','run_id'),
 ('wms.get_inventory','SELECT material_id FROM mock_erp.materials LIMIT 1','material_id'),
 ('mes.get_work_order','SELECT work_order_id FROM mes_v13.work_orders LIMIT 1','work_order_id'),
 ('srm.list_requisitions','SELECT source_run_id FROM srm_v14.purchase_requisitions LIMIT 1','run_id'),
 ('mapping.preview_b01','SELECT run_id FROM platform.integrated_mrp_payloads LIMIT 1','run_id')])
def test_five_business_schemas_and_adapters(tool,sql,key):
 from app.mcp_v15.integration import execute
 import psycopg
 dsn=os.getenv('V15_BUSINESS_DATABASE_URL')
 if not dsn: pytest.skip('V15_BUSINESS_DATABASE_URL not configured')
 with psycopg.connect(dsn) as business:
  assert business.execute('SELECT current_database()').fetchone()[0]=='industrial_lab_v14_test'
  business.execute('SET TRANSACTION READ ONLY')
  business.execute('SET LOCAL ROLE mcp_v15_business_reader_test')
  row=business.execute(sql).fetchone()
  if row is None: pytest.skip(tool + ': persisted business data absent')
  result=execute(business,tool,{key:row[0]})
  assert result is not None


def test_runtime_denial_is_durably_audited(pg):
 secret='pg16-gate-test-only-very-long-secret-0123456789'
 token=issue_test_token(secret,'v15-nonexistent-tenant','v15-nonexistent-principal',int(time.time())+60)
 # Dedicated connections: gateway owns transactions and audit persistence.
 import psycopg
 with psycopg.connect(os.environ['M1_TEST_DATABASE_URL'], autocommit=True) as runtime:
  with psycopg.connect(os.environ['V15_BUSINESS_DATABASE_URL']) as business:
   result=FullGateway(secret).invoke(runtime,business,token,'mrp.get_run',{'run_id':'missing-run'})
   assert result['status']=='DENIED' and result['error_code']=='RESOURCE_DENIED'
   row=pg.execute('SELECT status FROM mcp_v15.tool_call_state WHERE call_id=%s',(result['call_id'],)).fetchone()
   assert row and row[0]=='DENIED'
   count=pg.execute('SELECT count(*) FROM mcp_v15.tool_call_audit WHERE call_id=%s',(result['call_id'],)).fetchone()[0]
   assert count==2
