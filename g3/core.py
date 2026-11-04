"""Auditable, frozen-RC8-native-A versus PG16-persisted-B reconciliation.

Live B run is never replaced with client JSON; A witness was actually generated
from unmodified Version A RC8 engine.js under Node and pinned to the seed fixture.
Other snapshots are explicitly UNCOMPARABLE rather than fake PASS.
"""
from __future__ import annotations
import hashlib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REF=ROOT/'g3'/'a_rc8_seed_reference.json'
PINNED_REFERENCE_SHA256='04b0c383163a95d595eedf2c25fb580e94115604e9f6c9ad5f22eaea72386168'
ENGINE=ROOT/'enterprise_workbench'/'site'/'engine.js'
ADAPTER=ROOT/'g3'/'a_rc8_adapter.js'

class IncompatibleSnapshot(ValueError): pass
class InvalidReference(ValueError): pass

def sha_bytes(data): return hashlib.sha256(data).hexdigest()
def digest_file(path): return sha_bytes(Path(path).read_bytes())
def encoding(value): return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf-8')
def num(value):
    try:
        d=Decimal(str(value))
        if not d.is_finite(): raise ValueError()
        return format(d.normalize(), 'f') if d else '0'
    except (InvalidOperation,ValueError,TypeError) as exc:
        raise IncompatibleSnapshot('NONFINITE_OR_INVALID_NUMERIC_FIELD') from exc

def canonicalize(payload):
    """Reject missing semantics; ignore DB formatting like 100.0000 vs fixture 100."""
    try:
        orders=sorted([{'order_id':str(o['order_id']), 'product':str(o['product']),
                        'qty':num(o['qty']),'due':str(o['due']),'priority':int(o['priority'])}
                       for o in payload['orders']],key=lambda x:(x['due'],-x['priority'],x['order_id']))
        items={}
        for code,item in sorted(payload['items'].items()):
            items[code]={'kind':str(item['kind']),'lead_days':int(item['lead_days']),
                         **{key:num(item[key]) for key in ('on_hand','reserved','blocked','safety','moq','lot')},
                         'receipts':sorted([[str(d),num(q)] for d,q in item['receipts']])}
        bom=sorted([[str(p),str(c),num(q)] for p,c,q in payload['bom']])
        return {'as_of':str(payload['as_of']),'orders':orders,'items':items,'bom':bom}
    except (KeyError,TypeError,AttributeError,ValueError) as exc:
        raise IncompatibleSnapshot('MISSING_OR_UNSUPPORTED_SNAPSHOT_SEMANTICS') from exc

def snapshot_hash(payload): return sha_bytes(encoding(canonicalize(payload)))

def make_reference(snapshot,lines):
    return {'reference_id':'RC8_SEED_MULTI_ORDER_V1',
            'provenance':'VERSION_A_RC8_NATIVE_JS_PLAN_BUCKETS',
            'source_engine_sha256':digest_file(ENGINE),
            'source_adapter_sha256':digest_file(ADAPTER),
            'canonical_input_sha256':snapshot_hash(snapshot),
            'lines':lines}

def load_reference():
    reference=json.loads(REF.read_text(encoding='utf-8'))
    if sha_bytes(encoding(reference))!=PINNED_REFERENCE_SHA256:
        raise InvalidReference('RC8_REFERENCE_PAYLOAD_DRIFT')
    if reference.get('source_engine_sha256')!=digest_file(ENGINE) or reference.get('source_adapter_sha256')!=digest_file(ADAPTER):
        raise InvalidReference('RC8_SOURCE_DRIFT')
    if reference.get('provenance')!='VERSION_A_RC8_NATIVE_JS_PLAN_BUCKETS' or not isinstance(reference.get('lines'),list):
        raise InvalidReference('INVALID_RC8_REFERENCE')
    return reference

FIELDS={'gross':('gross_qty','gross'),'net':('net_qty','net'),
        'planned':('planned_qty','planned'),'closing':('closing_qty','closing')}

def explain(field,missing=False):
    if missing:return 'DATE_OR_BOM_BUCKET_MISMATCH'
    return {'gross':'DEMAND_EXPLOSION_OR_BOM_DIFFERENCE',
            'net':'INVENTORY_RECEIPT_OR_SAFETY_POLICY_DIFFERENCE',
            'planned':'MOQ_LOT_MULTIPLE_OR_NETTING_DIFFERENCE',
            'closing':'STOCK_CONSERVATION_OR_ROUNDING_DIFFERENCE'}[field]

def compare(a_lines,b_lines,tolerance='0.001'):
    tol=Decimal(str(tolerance))
    if not tol.is_finite() or tol<0: raise ValueError('INVALID_TOLERANCE')
    def keyed(rows,which):
        out={}
        for row in rows:
            key=(str(row['material_id'] if which=='A' else row['material']),str(row['date']))
            if key in out: raise ValueError('DUPLICATE_MATERIAL_DATE')
            out[key]=row
        return out
    a,b=keyed(a_lines,'A'),keyed(b_lines,'B')
    diffs=[];checked=0
    for key in sorted(set(a)|set(b)):
        if key not in a or key not in b:
            diffs.append({'material_id':key[0],'need_date':key[1],
                          'field':'LINE_PRESENCE','reason':explain('gross',True),
                          'a_present':key in a,'b_present':key in b})
            continue
        for name,(a_field,b_field) in FIELDS.items():
            av,bv=Decimal(str(a[key][a_field])),Decimal(str(b[key][b_field]))
            if not av.is_finite() or not bv.is_finite(): raise ValueError('NONFINITE_RESULT')
            checked+=1
            if abs(av-bv)>tol:
                diffs.append({'material_id':key[0],'need_date':key[1],
                              'field':name,'a':str(av),'b':str(bv),
                              'delta_b_minus_a':str(bv-av),'reason':explain(name)})
    return {'status':'MATCH' if not diffs else 'DIFFERENT','pass':not bool(diffs),
            'a_line_count':len(a),'b_line_count':len(b),
            'field_comparisons':checked,'tolerance_ea':str(tol),'differences':diffs}

def verified_comparison(snapshot,run,reference=None):
    ref=reference or load_reference()
    snap_hash=snapshot_hash(snapshot)
    if ref['canonical_input_sha256']!=snap_hash:
        raise IncompatibleSnapshot('RC8_REFERENCE_SNAPSHOT_NOT_EQUAL_TO_PG16')
    # Backend SHA is derived from source table fence; caller must additionally
    # verify persisted run_inputs.input_hash == platform.requirement_runs.input_hash.
    result=compare(ref['lines'],run['lines'])
    result.update({'comparison_mode':'FROZEN_NATIVE_JS_REFERENCE_VS_LIVE_PG16',
                   'reference_id':ref['reference_id'],'a_input_hash':snap_hash,
                   'b_input_hash':snap_hash,'a_engine_sha256':ref['source_engine_sha256'],
                   'a_adapter_sha256':ref['source_adapter_sha256'],
                   'independent_a_execution_this_request':False,
                   'b_source':'PERSISTED_POSTGRESQL','external_execution':False})
    return result
