"""Validate target shape against frozen SRM PR DDL and service contract."""
from datetime import date
from decimal import Decimal
from .contracts import TARGET_FIELDS
from .errors import MappingFailure
from app.srm.service import qty

def validate_pr(row):
    if set(row) != TARGET_FIELDS:
        raise MappingFailure('TARGET_SCHEMA_INVALID', 'candidate_payload', 'Unexpected or missing PR fields')
    for key in ('pr_id','source_run_id','source_result_hash','source_plan_id','material_id','uom'):
        if not isinstance(row[key], str) or not row[key].strip():
            raise MappingFailure('TARGET_SCHEMA_INVALID', key, 'Required nonempty text')
    if row['bom_version'] is not None and not isinstance(row['bom_version'],str):
        raise MappingFailure('TARGET_SCHEMA_INVALID','bom_version','Invalid optional text')
    try: qty(row['quantity'])
    except (ValueError,TypeError): raise MappingFailure('TARGET_SCHEMA_INVALID','quantity','Invalid numeric(18,4)') from None
    for field in ('need_date','release_date'):
        try: date.fromisoformat(row[field])
        except (TypeError,ValueError): raise MappingFailure('TARGET_SCHEMA_INVALID',field,'Invalid date') from None
    return row
