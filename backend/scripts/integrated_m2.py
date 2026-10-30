"""Usage: python scripts/integrated_m2.py seed|run|read RUN_ID"""
import sys
from pathlib import Path
from app.db.repository import connect,seed
from app.db.integrated import seed_effective_bom,run_integrated,read_integrated_run

ROOT=Path(__file__).resolve().parents[2]
def main():
    if len(sys.argv)<2: raise SystemExit('usage: seed|run|read RUN_ID')
    with connect() as conn:
        if sys.argv[1]=='seed':
            print('seed:',seed(conn,ROOT/'datasets/seed/multi_order.json'))
            print('effective BOM parents:',seed_effective_bom(conn))
        elif sys.argv[1]=='run': print(run_integrated(conn))
        elif sys.argv[1]=='read': print(read_integrated_run(conn,sys.argv[2]))
        else: raise SystemExit('unknown command')
if __name__=='__main__':main()
