"""Explicit operation whitelist; no eval, external I/O, or arbitrary callbacks."""
from datetime import date
from decimal import Decimal, InvalidOperation
from .errors import MappingFailure
from app.srm.service import qty

ALLOWED = frozenset({'DIRECT','RENAME','TYPE_CAST','ENUM_MAP','CONST','DATE_FORMAT'})

def apply(rule, source):
    op = rule.get('op')
    if op not in ALLOWED: raise MappingFailure('UNSUPPORTED_MAPPING_OPERATION', str(rule.get('target','')), 'Operation not allowed')
    target = rule.get('target')
    if not isinstance(target, str) or not target: raise MappingFailure('TARGET_SCHEMA_INVALID', '', 'Missing target field')
    if op == 'CONST':
        if 'value' not in rule: raise MappingFailure('REQUIRED_FIELD_MISSING', target, 'Constant missing')
        return target, rule['value']
    field = rule.get('source')
    if not isinstance(field, str) or field not in source:
        raise MappingFailure('REQUIRED_FIELD_MISSING', str(field), 'Source field missing')
    value = source[field]
    if op in ('DIRECT','RENAME'): return target, value
    if op == 'ENUM_MAP':
        choices = rule.get('values', {})
        if not isinstance(choices, dict) or value not in choices:
            raise MappingFailure('ENUM_VALUE_UNKNOWN', field, 'Unknown enum value')
        return target, choices[value]
    if op == 'TYPE_CAST':
        try:
            kind = rule.get('type')
            if kind == 'decimal': return target, str(qty(value))
            if kind == 'string' and value is not None: return target, str(value)
        except (ValueError, TypeError, InvalidOperation): pass
        raise MappingFailure('TYPE_CONVERSION_FAILED', field, 'Invalid strict conversion')
    if op == 'DATE_FORMAT':
        try:
            if isinstance(value, date) and not isinstance(value, __import__('datetime').datetime): return target, value.isoformat()
            if isinstance(value, str): return target, date.fromisoformat(value).isoformat()
        except ValueError: pass
        raise MappingFailure('TYPE_CONVERSION_FAILED', field, 'Invalid ISO date')
    raise MappingFailure('UNSUPPORTED_MAPPING_OPERATION', target)

def transform(rules, source):
    out = {}
    for rule in rules:
        key, value = apply(rule, source)
        if key in out: raise MappingFailure('TARGET_SCHEMA_INVALID', key, 'Duplicate target assignment')
        out[key] = value
    return out
