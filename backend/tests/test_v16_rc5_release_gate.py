"""RC5 offline security invariants; live Neon acceptance is a separate mandatory gate."""
from pathlib import Path
from app.portfolio_v16 import api


def test_existing_five_sources_preserved():
    assert len(api.SOURCES) == 5
    assert set(api.SOURCES) == {"mes/work-orders", "srm/requisitions", "srm/exceptions", "mapping/versions", "mapping/executions"}


def test_reader_url_fails_closed_without_database(monkeypatch):
    from fastapi import HTTPException
    monkeypatch.delenv("PORTFOLIO_READONLY_DATABASE_URL", raising=False)
    try:
        api._query("mes/work-orders", 5)
    except HTTPException as e:
        assert e.status_code == 503
        assert e.detail["code"] == "READONLY_READER_NOT_CONFIGURED"
    else:
        assert False, "missing dedicated DSN must fail closed"


def test_privileged_or_wrong_dsn_rejected_before_connect(monkeypatch):
    from fastapi import HTTPException
    for dsn in ("postgresql://neondb_owner:fake@ep-example.neon.tech/demo", "postgresql://portfolio_v16_api_limited:fake@evilneon.tech/demo", "not a uri"):
        monkeypatch.setenv("PORTFOLIO_READONLY_DATABASE_URL", dsn)
        try:
            api._query("mes/work-orders", 5)
        except HTTPException as e:
            assert e.status_code == 503
        else:
            assert False, dsn


def test_read_only_guards_and_static_projections():
    source = Path(api.__file__).read_text(encoding="utf-8")
    for clause in ("SET TRANSACTION READ ONLY", "statement_timeout", "rolbypassrls", "rolreplication", "DEDICATED_READER_REQUIRED"):
        assert clause in source
    for schema, table, columns, order in api.SOURCES.values():
        assert schema in ("mes_v13", "srm_v14", "mapping_v14")
        assert all(c.isalnum() or c in "_., " for c in columns)
        assert all(c.isalnum() or c in "_., " for c in order)
