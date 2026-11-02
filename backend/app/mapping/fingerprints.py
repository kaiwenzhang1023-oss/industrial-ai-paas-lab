"""Canonical JSON fingerprints for mapping artifacts (not MRP result hashes)."""
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from types import MappingProxyType

def _plain(value):
    if isinstance(value, (Decimal, date, datetime)): return str(value)
    if isinstance(value, (dict, MappingProxyType)):
        return {str(k): _plain(v) for k,v in value.items()}
    if isinstance(value, (list, tuple)): return [_plain(v) for v in value]
    if isinstance(value, (str, int, bool)) or value is None: return value
    raise TypeError('UNSUPPORTED_CANONICAL_TYPE')

def canonical(value):
    return json.dumps(_plain(value), sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)

def sha256(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()
