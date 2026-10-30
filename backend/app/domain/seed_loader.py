"""Load deterministic JSON seed; no database side effects."""
import json
from pathlib import Path
from decimal import Decimal
from app.domain.timephased import Item, Order
DEFAULT_SEED=Path(__file__).resolve().parents[3]/'datasets/seed/multi_order.json'
def load(path=DEFAULT_SEED):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    items={k:Item(code=k,**{**{n:Decimal(str(v)) for n,v in x.items() if n in ('on_hand','reserved','blocked','safety','moq','lot')},**{n:v for n,v in x.items() if n not in ('on_hand','reserved','blocked','safety','moq','lot','receipts')},'receipts':tuple((d,Decimal(str(q))) for d,q in x.get('receipts',[]))}) for k,x in data['items'].items()}
    orders=[Order(order_id=x['order_id'],product=x['product'],qty=Decimal(x['qty']),due=x['due'],priority=x.get('priority',0)) for x in data['orders']]
    return data,orders,items
