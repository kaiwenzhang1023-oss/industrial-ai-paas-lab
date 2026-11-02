from pathlib import Path
from app.db.integrated import canonical_hash

def test_normalized_migration_has_required_keys():
    s=(Path(__file__).resolve().parents[2]/'database/007_normalized_pegging.sql').read_text()
    for token in ('mrp_supply_sources','mrp_demand_allocations','mrp_plan_child_edges',
                  'source_document_id','source_line_id','FOREIGN KEY(run_id,supply_id)',
                  'capacity_qty=allocated_qty+remaining_qty'):
        assert token in s

def test_canonical_hash_is_key_order_invariant():
    assert canonical_hash({'a':1,'b':2})==canonical_hash({'b':2,'a':1})
