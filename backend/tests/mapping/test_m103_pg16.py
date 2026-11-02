"""Isolated PG16 integration: requires pre-applied 016 migration and test DSN.
Never creates databases, seeds upstream tables, or deletes historical data.
"""
import os, uuid
import pytest
from app.mapping.persistence import execute_preview,replay_preview
from app.mapping.errors import MappingFailure
from app.mapping.contracts import B01_MAPPING_ID,B01_VERSION

@pytest.mark.parametrize('tamper',[False,True])
def test_mapping_pg16_isolated(tamper):
    psycopg=pytest.importorskip('psycopg')
    dsn=os.getenv('TEST_DATABASE_URL','')
    if not dsn or dsn.split('?',1)[0].rsplit('/',1)[-1]!='industrial_lab_v14_test':
        pytest.skip('Requires explicit isolated industrial_lab_v14_test TEST_DATABASE_URL')
    from app.db.integrated import read_integrated_run
    from app.mapping.fingerprints import sha256
    from app.srm.service import normalize_buy
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('mapping_v14.execution_runs')")
            if cur.fetchone()[0] is None: pytest.skip('Apply migration 016 to isolated test DB first')
            cur.execute("SELECT run_id FROM platform.requirement_runs WHERE status='COMPLETED' ORDER BY run_id LIMIT 1")
            found=cur.fetchone()
            if found is None: pytest.skip('Existing completed MRP run required; do not seed in this gate')
            run=read_integrated_run(conn,found[0])
            cur.execute('SELECT material_id,make_buy,uom FROM mock_erp.materials')
            materials={m:{'make_buy':kind,'uom':uom} for m,kind,uom in cur.fetchall()}
        try: normalize_buy(run,{k:v['make_buy'] for k,v in materials.items()})
        except Exception: pytest.skip('Selected run has no valid BUY plan')
        req={'mapping_id':B01_MAPPING_ID,'mapping_version':B01_VERSION,
             'source_system':'MRP','source_object':'BUY_PLAN','target_system':'SRM',
             'target_object':'PR_CANDIDATE','mrp':run,'source_result_hash':run['result_hash'],
             'material_snapshot':materials}
        execution_id='M103-GATE-'+uuid.uuid4().hex
        with conn.cursor() as cur:
            cur.execute('SELECT count(*) FROM srm_v14.purchase_requisitions')
            pr_before=cur.fetchone()[0]
        first=execute_preview(conn,execution_id,req)
        assert first['response']['status']=='VALID' and not first['idempotent']
        again=execute_preview(conn,execution_id,req)
        assert again['idempotent'] and again['response']==first['response']
        replay=replay_preview(conn,execution_id)
        assert replay['replay_match'] and replay['response']==first['response']
        with pytest.raises(MappingFailure,match='different input'):
            execute_preview(conn,execution_id,{**req,'source_result_hash':'DIFFERENT'})
        with conn.cursor() as cur:
            cur.execute('SELECT count(*) FROM srm_v14.purchase_requisitions')
            assert cur.fetchone()[0]==pr_before
            cur.execute('SELECT action FROM mapping_v14.audit_events WHERE execution_id=%s ORDER BY id',(execution_id,))
            assert [x[0] for x in cur.fetchall()]==['EXECUTE','REPLAY']
            cur.execute('SELECT count(*) FROM mapping_v14.execution_runs WHERE execution_id=%s',(execution_id,))
            assert cur.fetchone()[0]==1
        if tamper:
            with pytest.raises(Exception):
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute('UPDATE mapping_v14.execution_runs SET request_hash=%s WHERE execution_id=%s',('x'*64,execution_id))
