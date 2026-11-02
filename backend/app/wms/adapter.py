"""Read-only WMS queries; no implicit JSON fallback and no writes."""
from .models import InventoryBalance, InventorySummary

def list_balances(conn, material_id=None, warehouse_id=None, limit=50, offset=0):
    with conn.cursor() as cur:
        cur.execute('''SELECT material_id,warehouse_id,lot_id,on_hand,reserved,blocked,snapshot_at,version
            FROM mock_wms.inventory_balances
            WHERE (%s::text IS NULL OR material_id=%s)
              AND (%s::text IS NULL OR warehouse_id=%s)
            ORDER BY material_id,warehouse_id,lot_id
            LIMIT %s OFFSET %s''',
            (material_id,material_id,warehouse_id,warehouse_id,limit,offset))
        return [InventoryBalance(material_id=r[0],warehouse_id=r[1],lot_id=r[2],on_hand=r[3],
                reserved=r[4],blocked=r[5],snapshot_at=r[6],version=r[7]) for r in cur.fetchall()]

def summarize(conn, material_id, warehouse_id=None):
    with conn.cursor() as cur:
        cur.execute('''SELECT COALESCE(SUM(on_hand),0),COALESCE(SUM(reserved),0),
            COALESCE(SUM(blocked),0),COUNT(*),MAX(snapshot_at)
            FROM mock_wms.inventory_balances
            WHERE material_id=%s AND (%s::text IS NULL OR warehouse_id=%s)''',
            (material_id,warehouse_id,warehouse_id))
        r=cur.fetchone()
    return InventorySummary(material_id=material_id,warehouse_id=warehouse_id,
        on_hand=r[0],reserved=r[1],blocked=r[2],available=r[0]-r[1]-r[2],
        balance_rows=r[3],latest_snapshot_at=r[4])
