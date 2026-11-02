"""Pure unit tests for the E06 local-target and live identity gate."""
from types import SimpleNamespace
import sys

import pytest

from e06_isolated_db_guard import (
    ALLOWED_NAMES,
    IsolationDenied,
    check_dsn,
    check_environment,
    parse_dsn,
    verify_server_identity,
)


@pytest.mark.parametrize("dsn", [
    "postgresql://lab:pw@127.0.0.1:55432/industrial_lab_v14_test",
    "postgres://lab:pw@localhost:5432/industrial_lab_v12_test",
    "postgresql://v18_tester:pw@127.0.0.1:55432/industrial_ai_v18_test",
    "postgresql://v18_tester:pw@127.0.0.1:55432/industrial_ai_v18_e06_acceptance",
])
def test_accept_local_isolated_targets(dsn):
    check_dsn(dsn)


@pytest.mark.parametrize("dsn", [
    "postgresql://lab:pw@neon.tech:5432/industrial_lab_v14_test",
    "postgresql://lab:pw@127.0.0.1:5432/production",
    "postgresql://lab:pw@127.0.0.1:5432/industrial_lab_v14_test?host=remote",
    "postgresql://lab:pw@127.0.0.1:5432/industrial_lab_v14_test?service=prod",
    "host=127.0.0.1 dbname=industrial_lab_v14_test",
    "postgresql:///industrial_lab_v14_test",
    "postgresql://lab:pw@127.0.0.1:5433/industrial_lab_v14_test",
    "postgresql://lab:pw@127.0.0.1:5432/industrial_lab_v14_test#ignored",
    "postgresql://wrong_user:pw@127.0.0.1:55432/industrial_ai_v18_e06_acceptance",
])
def test_reject_unsafe_targets(dsn):
    with pytest.raises(IsolationDenied):
        check_dsn(dsn)


def test_e06_acceptance_database_is_allowlisted_for_v18_tester():
    assert "industrial_ai_v18_e06_acceptance" in ALLOWED_NAMES
    parsed = parse_dsn(
        "postgresql://v18_tester:pw@127.0.0.1:55432/industrial_ai_v18_e06_acceptance"
    )
    assert parsed["database"] == "industrial_ai_v18_e06_acceptance"
    assert parsed["username"] == "v18_tester"


def test_reject_production_fallback():
    with pytest.raises(IsolationDenied, match="DATABASE_URL_MUST_BE_UNSET"):
        check_environment({"DATABASE_URL": "opaque-secret"})


def test_reject_remote_secondary_database():
    with pytest.raises(IsolationDenied):
        check_environment({
            "V15_BUSINESS_DATABASE_URL":
                "postgresql://lab:pw@remote.example:5432/industrial_lab_v14_test"
        })


def test_reject_missing_dsn_even_with_opt_in():
    with pytest.raises(IsolationDenied, match="E06_TEST_DSN_MISSING"):
        check_environment({})


def test_live_identity_accepts_only_matching_pg16_primary(monkeypatch):
    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, _sql):
            return SimpleNamespace(fetchone=lambda: (
                "industrial_ai_v18_e06_acceptance", "v18_tester", 160015, False
            ))

    monkeypatch.setitem(sys.modules, "psycopg", SimpleNamespace(connect=lambda *a, **k: FakeConnection()))
    verify_server_identity(
        "postgresql://v18_tester:pw@127.0.0.1:55432/industrial_ai_v18_e06_acceptance"
    )


@pytest.mark.parametrize("row,reason", [
    (("wrong_db", "v18_tester", 160015, False), "DATABASE_IDENTITY_MISMATCH"),
    (("industrial_ai_v18_e06_acceptance", "wrong_user", 160015, False), "USER_IDENTITY_MISMATCH"),
    (("industrial_ai_v18_e06_acceptance", "v18_tester", 150010, False), "MUST_BE_POSTGRESQL_16"),
    (("industrial_ai_v18_e06_acceptance", "v18_tester", 160015, True), "READ_REPLICA_DENIED"),
])
def test_live_identity_rejects_mismatch(monkeypatch, row, reason):
    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, _sql):
            return SimpleNamespace(fetchone=lambda: row)

    monkeypatch.setitem(sys.modules, "psycopg", SimpleNamespace(connect=lambda *a, **k: FakeConnection()))
    with pytest.raises(IsolationDenied, match=reason):
        verify_server_identity(
            "postgresql://v18_tester:pw@127.0.0.1:55432/industrial_ai_v18_e06_acceptance"
        )


def test_connection_failure_is_sanitized(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("secret-password-must-not-leak")

    monkeypatch.setitem(sys.modules, "psycopg", SimpleNamespace(connect=fail))
    with pytest.raises(IsolationDenied, match="SERVER_IDENTITY_CONNECTION_FAILED") as exc:
        verify_server_identity(
            "postgresql://v18_tester:pw@127.0.0.1:55432/industrial_ai_v18_e06_acceptance"
        )
    assert "secret-password" not in str(exc.value)


def test_collection_gate_is_early_and_live_verified():
    from pathlib import Path

    text = (Path(__file__).parent / "conftest.py").read_text(encoding="utf-8")
    assert "pytest_collection_modifyitems" in text
    assert "pytest_runtest_setup" not in text
    assert "check_environment(verify_server=True)" in text


def test_e06_rc2_local_55433_allowlist():
    from e06_isolated_db_guard import parse_dsn, IsolationDenied
    parsed = parse_dsn('postgresql://v18_tester:placeholder@127.0.0.1:55433/industrial_ai_v18_e06_acceptance')
    assert parsed['port'] == 55433
    import pytest
    with pytest.raises(IsolationDenied):
        parse_dsn('postgresql://v18_tester:placeholder@127.0.0.1:55434/industrial_ai_v18_e06_acceptance')
