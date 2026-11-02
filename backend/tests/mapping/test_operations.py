import pytest
from app.mapping.operations import apply, transform
from app.mapping.errors import MappingFailure

def test_six_operations():
    src={'a':'2.0000','date':'2026-12-15','state':'BUY'}
    assert apply({'op':'DIRECT','source':'a','target':'x'},src)==('x','2.0000')
    assert apply({'op':'RENAME','source':'a','target':'x'},src)==('x','2.0000')
    assert apply({'op':'TYPE_CAST','source':'a','target':'x','type':'decimal'},src)==('x','2.0000')
    assert apply({'op':'DATE_FORMAT','source':'date','target':'x'},src)==('x','2026-12-15')
    assert apply({'op':'ENUM_MAP','source':'state','target':'x','values':{'BUY':'B'}},src)==('x','B')
    assert apply({'op':'CONST','target':'x','value':'MRP'},src)==('x','MRP')

def test_disallowed_operation():
    with pytest.raises(MappingFailure,match='Operation not allowed'):
        apply({'op':'PYTHON','target':'x'}, {})

def test_duplicate_target():
    with pytest.raises(MappingFailure):
        transform([{'op':'CONST','target':'x','value':1},{'op':'CONST','target':'x','value':2}],{})

def test_invalid_decimal_and_date():
    for rule,src in [({'op':'TYPE_CAST','source':'x','target':'x','type':'decimal'},{'x':'NaN'}),({'op':'DATE_FORMAT','source':'x','target':'x'},{'x':'bad'})]:
        with pytest.raises(MappingFailure): apply(rule,src)
