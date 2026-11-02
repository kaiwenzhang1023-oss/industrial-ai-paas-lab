"""Run from backend/: python scripts/db_v03.py seed|run|read RUN_ID"""
import sys
from pathlib import Path
from app.db.repository import connect,seed,calculate_and_save,read_run
SEED=Path(__file__).resolve().parents[2]/'datasets/seed/multi_order.json'
def main():
    if len(sys.argv)<2 or sys.argv[1] not in ('seed','run','read'):
        raise SystemExit('Usage: python scripts/db_v03.py seed|run|read RUN_ID')
    with connect() as conn:
        if sys.argv[1]=='seed': print('seed:',seed(conn,SEED))
        elif sys.argv[1]=='run': print(calculate_and_save(conn))
        else: print(read_run(conn,sys.argv[2]))
if __name__=='__main__': main()
