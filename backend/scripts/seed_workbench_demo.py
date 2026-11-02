"""Seed dedicated workbench demo DB; non-destructive upsert only."""
from pathlib import Path
from app.db.repository import connect,seed
from app.db.integrated import seed_effective_bom

if __name__=='__main__':
    with connect() as conn:
        conn.autocommit=True
        count=seed(conn,Path(__file__).resolve().parents[2]/'datasets/seed/multi_order.json')
        seed_effective_bom(conn)
        print('Demo seed ready: orders=%s, materials=%s'%count)
