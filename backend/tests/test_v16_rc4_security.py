"""RC4 static safety and contract gates (no live Neon claim)."""
from pathlib import Path
from app.portfolio_v16 import api


def test_five_existing_routes_unchanged():
    assert set(api.SOURCES) == {
        "mes/work-orders", "srm/requisitions", "srm/exceptions",
        "mapping/versions", "mapping/executions",
    }


def test_reader_guard_fails_closed():
    source = Path(api.__file__).read_text(encoding="utf-8")
    assert "PRIVILEGED_LOGIN_FORBIDDEN" in source
    assert "rolbypassrls" in source and "rolreplication" in source
    assert "portfolio_v16_reader" in source
    assert 'if not dsn: _error("READONLY_READER_NOT_CONFIGURED")' in source
    assert "SET TRANSACTION READ ONLY" in source
    assert "DATABASE_URL owner" in source
