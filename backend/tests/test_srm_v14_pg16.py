"""Dedicated DB integration. Requires TEST_DATABASE_URL targeting industrial_lab_v14_test."""
import os
from decimal import Decimal
from datetime import timedelta
import pytest
from app.db.repository import connect
from app.db.integrated import read_integrated_run
from app.srm import service as s

def test_v14_pg16_gate():
    url=os.environ.get('TEST_DATABASE_URL','')
    if not url or url.split('?',1)[0].rsplit('/',1)[-1]!='industrial_lab_v14_test':
        pytest.skip('Requires explicit isolated TEST_DATABASE_URL')
    from pathlib import Path
    from app.db.repository import seed
    from app.db.integrated import seed_effective_bom,run_integrated
    root=Path(__file__).resolve().parents[2]
    with connect(url) as conn:
        seed(conn,root/'datasets/seed/multi_order.json')
        seed_effective_bom(conn)
        created=run_integrated(conn,'2026-11-20')
        run=created['run_id']
        mrp=read_integrated_run(conn,run)
        with conn.cursor() as cur:
            cur.execute('SELECT material_id,make_buy FROM mock_erp.materials')
            kinds=dict(cur.fetchall())
        plans=s.normalize_buy(mrp,kinds)
        first=s.import_mrp(conn,run)
        again=s.import_mrp(conn,run)
        assert first==again and first['count']==len(plans)
        # Source hash mismatch must reject an existing PR without changing persisted evidence.
        class _RollbackProbe(Exception): pass
        with pytest.raises(_RollbackProbe):
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute('UPDATE srm_v14.purchase_requisitions SET source_result_hash=%s WHERE pr_id=%s',('CORRUPTED-HASH',first['pr_ids'][0]))
                with pytest.raises(s.SRMError,match='BUY_SOURCE_CONFLICT'):
                    s.import_mrp(conn,run)
                raise _RollbackProbe()
        with conn.cursor() as cur:
            cur.execute('SELECT source_result_hash FROM srm_v14.purchase_requisitions WHERE pr_id=%s',(first['pr_ids'][0],))
            assert cur.fetchone()[0]==mrp['result_hash']
        pr=first['pr_ids'][0]
        material=plans[0]['material_id']
        s.supplier_upsert(conn,'V14-TEST-SUP','V14-TEST-SUP','V14 Supplier') if not _supplier_exists(conn) else None
        s.supplier_item(conn,'V14-TEST-SUP',material)
        import uuid
        po_id='V14-TEST-'+uuid.uuid4().hex[:16]
        po=s.create_po(conn,po_id,'V14-TEST-SUP',pr)
        issued=s.transition(conn,po_id,'ISSUED',0)
        with pytest.raises(s.SRMError,match='STALE_REVISION'): s.transition(conn,po_id,'CANCELLED',0)
        with pytest.raises(s.SRMError,match='CONFIRMED_QTY_EXCEEDS_ORDER'):
            s.confirm(conn,po_id,'BAD-'+po_id,[{'schedule_id':'BAD-'+po_id,'po_line_id':po['po_line_id'],'confirmed_qty':str(plans[0]['quantity']+1),'promised_date':str(plans[0]['need_date'])}],1)
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM srm_v14.supplier_confirmations WHERE confirmation_id=%s',('BAD-'+po_id,))
            assert cur.fetchone()[0]==0
        # Partial confirmation, then late second batch; cumulative quantities and risk evidence.
        total=plans[0]['quantity']
        early=(total/2).quantize(Decimal('0.0001'))
        late=total-early
        assert early>0 and late>0
        first_schedules=[{'schedule_id':'EARLY-'+po_id,'po_line_id':po['po_line_id'],'confirmed_qty':str(early),'promised_date':str(plans[0]['need_date'])}]
        partial=s.confirm(conn,po_id,'PART-'+po_id,first_schedules,1)
        assert partial['status']=='PARTIALLY_CONFIRMED' and partial['revision']==2
        late_date=plans[0]['need_date']+timedelta(days=5)
        late_schedules=[{'schedule_id':'LATE-'+po_id,'po_line_id':po['po_line_id'],'confirmed_qty':str(late),'promised_date':str(late_date)}]
        confirmed=s.confirm(conn,po_id,'OK-'+po_id,late_schedules,2)
        assert confirmed['status']=='CONFIRMED' and confirmed['revision']==3
        assert s.confirm(conn,po_id,'OK-'+po_id,late_schedules,2)['idempotent'] is True
        with conn.cursor() as cur:
            cur.execute('SELECT risk_qty,late_days FROM srm_v14.supply_exceptions WHERE po_line_id=%s AND exception_type=%s',(po['po_line_id'],'DELIVERY_DELAY'))
            assert cur.fetchone()==(late,5)
            cur.execute('SELECT action,payload FROM srm_v14.audit WHERE entity_type=%s AND entity_id=%s ORDER BY id',('SUPPLY_EXCEPTION',s.stable('EXC',{'line':po['po_line_id'],'type':'DELIVERY_DELAY'})))
            events=cur.fetchall()
            assert len(events)==1 and events[0][0]=='OPEN'
            assert Decimal(events[0][1]['after']['risk_qty'])==late
            cur.execute('SELECT COUNT(*) FROM srm_v14.supplier_confirmation_schedules WHERE po_line_id=%s',(po['po_line_id'],))
            assert cur.fetchone()[0]==2
        # A reused confirmation ID cannot be treated as idempotent for another order.
        if len(first['pr_ids'])>1:
            other_pr=first['pr_ids'][1]
            other_material=plans[1]['material_id']
            s.supplier_item(conn,'V14-TEST-SUP',other_material)
            other_po='V14-OTHER-'+uuid.uuid4().hex[:16]
            s.create_po(conn,other_po,'V14-TEST-SUP',other_pr)
            s.transition(conn,other_po,'ISSUED',0)
            with pytest.raises(s.SRMError,match='CONFIRMATION_ID_CONFLICT'):
                s.confirm(conn,other_po,'OK-'+po_id,late_schedules,1)

def _supplier_exists(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM srm_v14.suppliers WHERE supplier_id='V14-TEST-SUP'")
        return bool(cur.fetchone())
