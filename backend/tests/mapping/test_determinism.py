from app.mapping.fingerprints import sha256
from app.mapping.contracts import PUBLISHED

def test_canonical_key_order():
    assert sha256({'b':2,'a':1})==sha256({'a':1,'b':2})

def test_immutable_registry():
    import pytest
    with pytest.raises(TypeError): PUBLISHED['1.0.0']=()
    with pytest.raises(TypeError): PUBLISHED['1.0.0'][0]['op']='PYTHON'
