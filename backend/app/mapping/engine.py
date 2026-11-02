"""B01 preview. No DB connections, SQL, HTTP or SRM business mutations."""
from collections.abc import Mapping
from .contracts import B01_MAPPING_ID, B01_VERSION, PUBLISHED
from .errors import MappingFailure
from .operations import transform
from .validators import validate_pr
from .fingerprints import sha256
from app.srm.service import normalize_buy, stable, SRMError

def _error(exc):
    if isinstance(exc, MappingFailure): return exc.as_dict()
    code = str(exc)
    return MappingFailure('SOURCE_SCHEMA_INVALID', 'source_snapshot', code, code.split(':',1)[0]).as_dict()

def preview_b01(request):
    """Pure preview of already verified MRP data and a frozen ERP material snapshot.

    `mrp` must be the unmodified, trusted read_integrated_run() return object;
    `material_snapshot` is a caller-frozen material_id -> {make_buy,uom} mapping.
    This function cannot independently attest DB origin or persisted result integrity.
    """
    mapping_id = request.get('mapping_id') if isinstance(request, Mapping) else None
    version = request.get('mapping_version') if isinstance(request, Mapping) else None
    base = {'mapping_id': mapping_id, 'mapping_version': version}
    try:
        if mapping_id != B01_MAPPING_ID: raise MappingFailure('MAPPING_VERSION_NOT_FOUND','mapping_id','Unknown mapping')
        if version not in PUBLISHED: raise MappingFailure('MAPPING_VERSION_NOT_FOUND','mapping_version','Unknown version')
        if request.get('mapping_status','PUBLISHED') != 'PUBLISHED':
            raise MappingFailure('MAPPING_VERSION_NOT_PUBLISHED','mapping_version','Version not published')
        if 'rules' in request: raise MappingFailure('SOURCE_SCHEMA_INVALID','rules','Runtime rule override forbidden')
        if any(request.get(k) != v for k,v in [('source_system','MRP'),('source_object','BUY_PLAN'),('target_system','SRM'),('target_object','PR_CANDIDATE')]):
            raise MappingFailure('SOURCE_SCHEMA_INVALID','envelope','Unexpected source/target contract')
        mrp = request.get('mrp'); materials = request.get('material_snapshot')
        if not isinstance(mrp, Mapping) or not isinstance(materials, Mapping):
            raise MappingFailure('SOURCE_SCHEMA_INVALID','mrp/material_snapshot','Missing snapshots')
        if not isinstance(mrp.get('run_id'),str) or not mrp['run_id'] or not isinstance(mrp.get('result_hash'),str) or not mrp['result_hash']:
            raise MappingFailure('REQUIRED_FIELD_MISSING','mrp.run_id/result_hash','Missing MRP provenance')
        if not isinstance(mrp.get('result'), Mapping) or not isinstance(mrp['result'].get('plan_lots'),list):
            raise MappingFailure('SOURCE_SCHEMA_INVALID','mrp.result.plan_lots','Expected plan lot list')
        if request.get('source_result_hash') != mrp['result_hash']:
            raise MappingFailure('SOURCE_FINGERPRINT_MISMATCH','source_result_hash','Source hash differs from trusted snapshot')
        kinds = {}
        for material, item in materials.items():
            if not isinstance(item,Mapping) or item.get('make_buy') not in ('BUY','MAKE') or not isinstance(item.get('uom'),str) or not item['uom'].strip():
                raise MappingFailure('SOURCE_SCHEMA_INVALID',f'material_snapshot.{material}','Invalid ERP material')
            kinds[material] = item['make_buy']
        plans = normalize_buy(mrp,kinds)
        candidates=[]
        for x in plans:
            material = x['material_id']
            raw = {**x,'uom':materials[material]['uom'],
                   'pr_id':stable('PR',{'run':mrp['run_id'],'plan':x['source_plan_id']})}
            candidates.append(validate_pr(transform(PUBLISHED[version],raw)))
        candidates.sort(key=lambda x:x['source_plan_id'])
        evidence = {'mapping_id':mapping_id,'mapping_version':version,
                    'source_run_id':mrp['run_id'],'source_result_hash':mrp['result_hash'],
                    'material_snapshot_hash':sha256(materials),'candidate_payloads':candidates}
        return {**base,'status':'VALID','source_run_id':mrp['run_id'],
                'source_result_hash':mrp['result_hash'],'candidate_payloads':candidates,
                'mapping_result_hash':sha256(evidence),'errors':[]}
    except (MappingFailure,SRMError,KeyError,TypeError,ValueError) as exc:
        return {**base,'status':'REJECTED','candidate_payloads':[],
                'mapping_result_hash':None,'errors':[_error(exc)]}
