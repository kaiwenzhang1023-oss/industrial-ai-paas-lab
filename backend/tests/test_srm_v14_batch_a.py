"""V1.4 Batch A pure checks; PostgreSQL checks are in the dedicated gate."""
from decimal import Decimal
import pytest
from app.srm.service import normalize_buy,qty,SRMError,digest,stable

def test_quantity_decimal():
    assert qty('100.0000')==Decimal('100')
    with pytest.raises(SRMError): qty('NaN')
    with pytest.raises(SRMError): qty('0')
    with pytest.raises(SRMError): qty('1.00001')

def test_adapter_buy_only():
    m={'status':'COMPLETED','run_id':'M2-A','result_hash':'h','result':{'plan_lots':[
      {'plan_id':'PLAN:BR-01@2026-12-15','material':'BR-01','quantity':'100','need_date':'2026-12-15','release_date':'2026-12-10'},
      {'plan_id':'PLAN:EM-100@2026-12-15','material':'EM-100','quantity':'1','need_date':'2026-12-15','release_date':'2026-12-10'}]}}
    r=normalize_buy(m,{'BR-01':'BUY','EM-100':'MAKE'})
    assert len(r)==1 and r[0]['source_plan_id']=='PLAN:BR-01@2026-12-15'

def test_adapter_duplicate_rejected():
    lot={'plan_id':'P','material':'BR-01','quantity':'1','need_date':'2026-12-15','release_date':'2026-12-10'}
    m={'status':'COMPLETED','run_id':'M2-A','result_hash':'h','result':{'plan_lots':[lot,lot]}}
    with pytest.raises(SRMError,match='DUPLICATE_PLAN_ID'): normalize_buy(m,{'BR-01':'BUY'})

def test_hash_stable():
    assert digest({'a':1,'b':2})==digest({'b':2,'a':1})
    assert stable('PR',{'run':'r','plan':'p'})==stable('PR',{'plan':'p','run':'r'})
