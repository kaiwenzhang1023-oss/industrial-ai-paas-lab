from app.db.repository import SOURCE_TABLES, _snapshot_hash
from app.domain.seed_loader import load

def test_source_tables_all_required():
    assert len(SOURCE_TABLES)==6
    assert len(set(SOURCE_TABLES))==len(SOURCE_TABLES)
    assert 'mock_wms.inventory_balances' in SOURCE_TABLES
    assert 'mock_erp.bom_items' in SOURCE_TABLES

def test_snapshot_hash_deterministic():
    data,orders,items=load()
    first=_snapshot_hash(data['as_of'],orders,items,data['bom'])
    assert first==_snapshot_hash(data['as_of'],orders,items,data['bom'])
    assert len(first)==64

def test_snapshot_hash_sensitive_to_date():
    data,orders,items=load()
    assert _snapshot_hash(data['as_of'],orders,items,data['bom']) != _snapshot_hash('2026-11-01',orders,items,data['bom'])

def test_snapshot_hash_sensitive_to_bom():
    data,orders,items=load()
    modified=list(data['bom']); p,c,q=modified[0];modified[0]=(p,c,str(float(q)+1))
    assert _snapshot_hash(data['as_of'],orders,items,data['bom']) != _snapshot_hash(data['as_of'],orders,items,modified)
