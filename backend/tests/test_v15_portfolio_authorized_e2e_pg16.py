"""Opt-in real authorized E2E. Requires populated, isolated PG16 test DBs.

This is deliberately NOT part of the existing release gate. No mocked adapters,
no skipped golden paths, no business mutations. Test authorization rows are
removed after execution; append-only call audit remains as evidence.
"""
import os
import time
import uuid
import pytest

psycopg = pytest.importorskip('psycopg')
from app.mcp_v15.full_gateway import FullGateway, issue_test_token

SECRET = 'portfolio-e2e-local-only-secret-0123456789abcdef'


def _connections():
    runtime_dsn = os.environ['M1_TEST_DATABASE_URL']
    business_dsn = os.environ['V15_BUSINESS_DATABASE_URL']
    runtime = psycopg.connect(runtime_dsn)
    business = psycopg.connect(business_dsn)
    try:
        assert runtime.execute('SELECT current_database()').fetchone()[0] == 'industrial_lab_v15_test'
        assert business.execute('SELECT current_database()').fetchone()[0] == 'industrial_lab_v14_test'
        runtime.commit()
        business.commit()
        return runtime, business
    except BaseException:
        runtime.close(); business.close()
        raise


def _targets(business):
    queries = [
        ('mrp.get_run', 'MRP_RUN', 'run_id', 'SELECT run_id FROM platform.integrated_mrp_payloads ORDER BY run_id LIMIT 1'),
        ('wms.get_inventory', 'MATERIAL', 'material_id', 'SELECT material_id FROM mock_wms.inventory_balances ORDER BY material_id LIMIT 1'),
        ('mes.get_work_order', 'MES_WORK_ORDER', 'work_order_id', 'SELECT work_order_id FROM mes_v13.work_orders ORDER BY work_order_id LIMIT 1'),
        ('srm.list_requisitions', 'MRP_RUN', 'run_id', 'SELECT source_run_id FROM srm_v14.purchase_requisitions ORDER BY source_run_id LIMIT 1'),
        ('mapping.preview_b01', 'MRP_RUN', 'run_id', 'SELECT run_id FROM platform.integrated_mrp_payloads ORDER BY run_id LIMIT 1'),
    ]
    selected = []
    with business.transaction():
        business.execute('SET TRANSACTION READ ONLY')
        for tool, resource_type, arg_key, sql in queries:
            row = business.execute(sql).fetchone()
            assert row is not None, f'MISSING_REAL_BUSINESS_DATA: {tool}; seed approved demo fixtures first'
            selected.append((tool, resource_type, arg_key, str(row[0])))
    return selected


def test_five_real_authorized_tools_and_denial_audit():
    assert os.environ.get('V15_PORTFOLIO_E2E') == '1', 'Set V15_PORTFOLIO_E2E=1 to opt in'
    runtime, business = _connections()
    tenant = 'portfolio_' + uuid.uuid4().hex
    principal = 'demo_reader'
    try:
        selected = _targets(business)
        with runtime.transaction():
            runtime.execute('INSERT INTO mcp_v15.principals(tenant_id,principal_id,status) VALUES (%s,%s,%s)', (tenant,principal,'ACTIVE'))
            runtime.execute('INSERT INTO mcp_v15.principal_permissions(tenant_id,principal_id,permission) VALUES (%s,%s,%s)', (tenant,principal,'read'))
            for kind, rid in sorted({(kind, rid) for _, kind, _, rid in selected}):
                runtime.execute('INSERT INTO mcp_v15.resource_registry(tenant_id,resource_type,resource_id,status,source_fingerprint,verified_at) VALUES (%s,%s,%s,%s,%s,now())', (tenant,kind,rid,'ACTIVE','portfolio-e2e'))
                runtime.execute('INSERT INTO mcp_v15.resource_grants(tenant_id,principal_id,resource_type,resource_id,permission) VALUES (%s,%s,%s,%s,%s)', (tenant,principal,kind,rid,'read'))
        token = issue_test_token(SECRET,tenant,principal,int(time.time())+300)
        gateway = FullGateway(SECRET,release_enabled=True)
        for tool, kind, key, rid in selected:
            response = gateway.invoke(runtime,business,token,tool,{key:rid})
            assert response['status']=='COMPLETED', (tool,response)
            assert response['result'] is not None, tool
            with runtime.transaction():
                row = runtime.execute('SELECT status FROM mcp_v15.tool_call_state WHERE call_id=%s',(response['call_id'],)).fetchone()
                events = [x[0] for x in runtime.execute('SELECT event_type FROM mcp_v15.tool_call_audit WHERE call_id=%s ORDER BY occurred_at,event_type',(response['call_id'],))]
                assert row == ('COMPLETED',), (tool,row)
                assert set(events)=={'RECEIVED','AUTHORIZED','RUNNING','COMPLETED'}, (tool,events)
            print(f'AUTHORIZED_E2E_PASS {tool} call_id={response["call_id"]}')
        denied = gateway.invoke(runtime,business,token,'mrp.get_run',{'run_id':'portfolio-unauthorized-'+uuid.uuid4().hex})
        assert denied['status']=='DENIED' and denied['error_code']=='RESOURCE_DENIED'
        with runtime.transaction():
            assert runtime.execute('SELECT status FROM mcp_v15.tool_call_state WHERE call_id=%s',(denied['call_id'],)).fetchone()==('DENIED',)
        print(f'UNAUTHORIZED_E2E_PASS call_id={denied["call_id"]}')
    finally:
        try:
            runtime.rollback()
            with runtime.transaction():
                runtime.execute('DELETE FROM mcp_v15.resource_grants WHERE tenant_id=%s',(tenant,))
                runtime.execute('DELETE FROM mcp_v15.resource_registry WHERE tenant_id=%s',(tenant,))
                runtime.execute('DELETE FROM mcp_v15.principal_permissions WHERE tenant_id=%s',(tenant,))
                runtime.execute('DELETE FROM mcp_v15.principals WHERE tenant_id=%s',(tenant,))
        finally:
            runtime.close(); business.close()
