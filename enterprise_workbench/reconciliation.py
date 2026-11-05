"""Deterministic same-snapshot numeric comparison; requires independently computed B result.

No implicit mapping between RC8 and backend field semantics. Caller must provide
explicit comparable metric paths and units, otherwise the gate remains HOLD.
"""
from decimal import Decimal, InvalidOperation
from typing import Any


def at_path(data: dict, path: str) -> Any:
    value = data
    for key in path.split('.'):
        if not isinstance(value, dict) or key not in value:
            raise KeyError(path)
        value = value[key]
    return value


def numeric_diff(a: dict, b: dict, mappings: list[dict], *, same_snapshot: bool) -> dict:
    if not same_snapshot:
        return {'status': 'SNAPSHOT_MISMATCH', 'items': [], 'pass': False}
    if not mappings:
        return {'status': 'MAPPING_REQUIRED', 'items': [], 'pass': False}
    items = []
    for mapping in mappings:
        name, ap, bp = mapping['name'], mapping['a_path'], mapping['b_path']
        unit = mapping.get('unit', '')
        try:
            av, bv = at_path(a, ap), at_path(b, bp)
            if isinstance(av, bool) or isinstance(bv, bool):
                raise InvalidOperation('Boolean is not a numeric metric')
            ad, bd = Decimal(str(av)), Decimal(str(bv))
            if not ad.is_finite() or not bd.is_finite():
                raise InvalidOperation('Nonfinite value')
            delta = bd - ad
            tolerance = Decimal(str(mapping.get('tolerance', '0')))
            if tolerance < 0:
                raise InvalidOperation('Negative tolerance')
            status = 'MATCH' if abs(delta) <= tolerance else 'DIFFERENT'
            items.append({'name': name, 'unit': unit, 'a_path': ap, 'b_path': bp,
                          'a': str(ad), 'b': str(bd), 'delta_b_minus_a': str(delta),
                          'tolerance': str(tolerance), 'status': status,
                          'explanation': ('Within declared tolerance' if status == 'MATCH'
                                          else 'Backend and RC8 results differ; investigate input, BOM, timing and rounding')})
        except (KeyError, InvalidOperation, TypeError, ValueError) as exc:
            items.append({'name': name, 'a_path': ap, 'b_path': bp,
                          'status': 'UNCOMPARABLE', 'explanation': str(exc)})
    passed = all(x['status'] == 'MATCH' for x in items)
    return {'status': 'MATCH' if passed else 'DIFFERENCE_OR_UNCOMPARABLE',
            'pass': passed, 'items': items}
