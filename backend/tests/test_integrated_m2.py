from datetime import date
from decimal import Decimal
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.db.integrated import canonical_hash, read_integrated_run, SOURCE_TABLES_V2
from app.main import app

class Cursor:
    def __init__(self,row): self.row=row; self.sql=[]
    def execute(self,sql,args=None): self.sql.append((sql,args))
    def fetchone(self): return self.row
    def __enter__(self): return self
    def __exit__(self,*args): pass
class Conn:
    def __init__(self,row): self.c=Cursor(row)
    def cursor(self): return self.c

def test_hash_stable_with_key_order():
    assert canonical_hash({'a':'1','b':['2']})==canonical_hash({'b':['2'],'a':'1'})
def test_hash_changes_with_quantity():
    assert canonical_hash({'qty':'1.00'})!=canonical_hash({'qty':'2.00'})
def test_all_source_tables_in_fence():
    assert 'mock_erp.effective_bom_headers' in SOURCE_TABLES_V2
    assert 'mock_erp.effective_bom_components' in SOURCE_TABLES_V2
    assert 'mock_wms.inventory_balances' in SOURCE_TABLES_V2

def test_readback_hash_integrity():
    result={'mrp_lines':[],'pegging':{'order_allocations':[]}}
    row=('hash','COMPLETED',date(2026,11,20),{'orders':[]},result,canonical_hash(result))
    out=read_integrated_run(Conn(row),'MRP-1')
    assert out['storage']=='postgresql' and out['result']==result

def test_readback_detects_tamper():
    row=('hash','COMPLETED',date(2026,11,20),{}, {'qty':'999'},'0'*64)
    import pytest
    with pytest.raises(ValueError,match='HASH_MISMATCH'):
        read_integrated_run(Conn(row),'MRP-1')

def test_readback_missing_run():
    import pytest
    with pytest.raises(KeyError): read_integrated_run(Conn(None),'missing')

def test_api_no_database_fallback():
    with patch('app.main.db_connect',side_effect=OSError('down')):
        response=TestClient(app).post('/api/v1/db/integrated-mrp/runs')
    assert response.status_code==503

def test_api_readback_not_found():
    with patch('app.main.db_connect') as connection:
        connection.return_value.__enter__.return_value=object()
        with patch('app.main.read_integrated_run',side_effect=KeyError('absent')):
            response=TestClient(app).get('/api/v1/db/integrated-mrp/runs/absent')
    assert response.status_code==404
