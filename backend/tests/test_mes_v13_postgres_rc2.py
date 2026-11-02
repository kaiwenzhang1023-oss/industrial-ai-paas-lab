"""RC2 real PG16 gate. Never skips, never uses production or v12 database."""
import os
from pathlib import Path
from decimal import Decimal
from collections import defaultdict
import pytest
from fastapi.testclient import TestClient
from psycopg.conninfo import conninfo_to_dict
from app.db.repository import connect, seed
from app.db.integrated import seed_effective_bom, run_integrated, read_integrated_run, canonical_hash
from app.mes import integration as mes
from app.mes.core import Feedback
from app.main import app

pytestmark = pytest.mark.integration

@pytest.fixture(scope='module')
def dburl():
    url = os.getenv('TEST_DATABASE_URL')
    assert url, 'TEST_DATABASE_URL required; REAL PG gate never skips'
    info = conninfo_to_dict(url)
    assert (info.get('host'),str(info.get('port','5432')),info.get('dbname'),info.get('user')) == ('127.0.0.1','5432','industrial_lab_v13_test','lab'), 'RC2_ISOLATION_GUARD'
    assert not os.getenv('DATABASE_URL'), 'DATABASE_URL must be unset during PG tests'
    with connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), current_setting('server_version_num')::int")
            name,version=cur.fetchone()
            assert name=='industrial_lab_v13_test' and 160000<=version<170000
            cur.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='mes_v13' AND table_type='BASE TABLE'")
            assert cur.fetchone()[0]==5, 'MES migration missing'
    return url

@pytest.fixture(scope='module')
def mrp(dburl):
    root=Path(__file__).resolve().parents[2]
    with connect(dburl) as conn:
        seed(conn,root/'datasets/seed/multi_order.json')
        seed_effective_bom(conn)
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SELECT material_id FROM mock_erp.materials WHERE make_buy='MAKE' ORDER BY material_id")
                make_products=[r[0] for r in cur.fetchall()]
                assert make_products
                for product in make_products:
                    cur.execute("""INSERT INTO mes_v13.routings
                      (product_id,routing_version,operation_id,sequence,work_center,setup_hours,hours_per_unit)
                      VALUES (%s,'V1','ASSEMBLY',1,'WC-A',1,0.5),(%s,'V1','TEST',2,'WC-T',0.5,0.25)
                      ON CONFLICT(product_id,routing_version,operation_id) DO NOTHING""",(product,product))
        created=run_integrated(conn,'2026-11-20')
        stored=read_integrated_run(conn,created['run_id'])
        assert stored['result_hash']==created['result_hash']==canonical_hash(stored['result'])
        assert stored['result']['wms_stock_attribution_contract']=='V12-PLANNING-ONLY-V1'
        assert stored['result']['wms_stock_attribution']
    print('RC2_MRP_EVIDENCE',created['run_id'],created['result_hash'])
    return created

def test_pg01_03_mrp_mes_persistence_idempotency(dburl,mrp):
    with connect(dburl) as conn:
        first=mes.create_from_mrp(conn,mrp['run_id'])
        second=mes.create_from_mrp(conn,mrp['run_id'])
        assert first==second and first['count']>0
        rows=mes.read_orders(conn)
        for wid in first['work_order_ids']:
            matching=[r for r in rows if r['work_order_id']==wid]
            assert len(matching)==1
            row=matching[0]
            assert row['source_run_id']==mrp['run_id']
            assert row['source_result_hash']==mrp['result_hash']
            assert row['source_plan_id']
            with conn.cursor() as cur:
                cur.execute('SELECT count(*) FROM mes_v13.work_orders WHERE work_order_id=%s',(wid,))
                assert cur.fetchone()[0]==1
    print('RC2_MES_EVIDENCE',first)

def test_pg04_05_feedback_rollback_and_readback(dburl,mrp):
    with connect(dburl) as conn:
        ids=mes.create_from_mrp(conn,mrp['run_id'])['work_order_ids']
        wid=ids[0]
        wo,rev=mes.reconstruct(conn,wid)
        if wo.status.value=='PLANNED':
            mes.transition(conn,wid,'RELEASED',rev)
            wo,rev=mes.reconstruct(conn,wid)
        if wo.status.value=='RELEASED':
            mes.transition(conn,wid,'IN_PROGRESS',rev)
            wo,rev=mes.reconstruct(conn,wid)
        assert wo.status.value=='IN_PROGRESS'
        qty=wo.spec.quantity
        before=len(wo.feedback)
        with pytest.raises(ValueError,match='WORK_ORDER_QUANTITY_EXCEEDED'):
            mes.feedback(conn,wid,Feedback('RC2-INVALID-'+wid,wo.routing.operations[0].operation_id,qty+1,Decimal(0),'2026-11-25'),rev)
        with conn.cursor() as cur:
            cur.execute('SELECT count(*) FROM mes_v13.feedback_events WHERE event_id=%s',('RC2-INVALID-'+wid,))
            assert cur.fetchone()[0]==0
        event=Feedback('RC2-OK-'+wid,wo.routing.operations[0].operation_id,qty,Decimal(0),'2026-11-25')
        saved=mes.feedback(conn,wid,event,rev)
        again=mes.feedback(conn,wid,event,rev)
        assert saved['idempotent'] is False and again['idempotent'] is True
        assert saved['revision']==again['revision']
    with connect(dburl) as conn:
        restored,newrev=mes.reconstruct(conn,wid)
        assert newrev==saved['revision']
        assert len(restored.feedback)==before+1
        assert restored.completed_good(restored.routing.operations[0].operation_id)==qty
        with pytest.raises(ValueError,match='STALE_MES_REVISION'):
            mes.transition(conn,wid,'COMPLETED',rev)

def test_pg06_capacity_persisted_and_conflict(dburl,mrp):
    with connect(dburl) as conn:
        ids=mes.create_from_mrp(conn,mrp['run_id'])['work_order_ids']
        # Ample horizon and hours, deterministic planning for all imported orders.
        from datetime import date,timedelta
        caps=[{'work_center':c,'day':(date(2026,11,25)+timedelta(days=i)).isoformat(),'hours':'1000000'}
              for c in ('WC-A','WC-T') for i in range(30)]
        result=mes.plan_capacity(conn,ids,caps,'2026-11-25')
        assert result['allocations']
        with conn.cursor() as cur:
            cur.execute('SELECT count(*) FROM mes_v13.capacity_allocations WHERE work_order_id=ANY(%s)',(ids,))
            assert cur.fetchone()[0]==len(result['allocations'])
        again=mes.plan_capacity(conn,ids,caps,'2026-11-25')
        assert result==again
    with connect(dburl) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT count(*) FROM mes_v13.capacity_allocations WHERE work_order_id=ANY(%s)',(ids,))
            assert cur.fetchone()[0]==len(result['allocations'])
        if len(ids)>1:
            with pytest.raises(ValueError,match='EXTERNAL_CAPACITY_RESERVATION_CONFLICT'):
                mes.plan_capacity(conn,ids[:1],caps,'2026-11-25')

def test_ui01_sec01_workbench_and_public_readonly(dburl,mrp,monkeypatch):
    import app.mes.api as api
    import app.workbench as wb
    monkeypatch.setattr(api,'connect',lambda:connect(dburl))
    monkeypatch.setattr(wb,'connect',lambda:connect(dburl))
    monkeypatch.setenv('PUBLIC_READ_ONLY','1')
    monkeypatch.delenv('DEMO_WRITE_ENABLED',raising=False)
    client=TestClient(app)
    html=client.get('/workbench/')
    assert html.status_code==200 and 'MES' in html.text
    js=client.get('/workbench/app.js')
    assert js.status_code==200 and 'loadMes' in js.text
    listing=client.get('/api/v1/mes/work-orders')
    assert listing.status_code==200 and listing.json()
    wid=listing.json()[0]['work_order_id']
    details=client.get('/api/v1/mes/work-orders/'+wid)
    assert details.status_code==200 and details.json()['simulation'] is True
    for path,body in [('/api/v1/mes/import-mrp',{'run_id':mrp['run_id']}),
        ('/api/v1/mes/work-orders/'+wid+'/transition',{'status':'RELEASED','expected_revision':0}),
        ('/api/v1/mes/work-orders/'+wid+'/feedback',{'event_id':'RC2-DENY','operation_id':'ASSEMBLY','good_qty':'1','scrap_qty':'0','event_date':'2026-11-25','expected_revision':0}),
        ('/api/v1/mes/capacity-plan',{'work_order_ids':[wid],'start_date':'2026-11-25','daily_capacity':[]})]:
        denied=client.post(path,json=body,headers={'x-operator-key':'anything'})
        assert denied.status_code==403,(path,denied.text)
