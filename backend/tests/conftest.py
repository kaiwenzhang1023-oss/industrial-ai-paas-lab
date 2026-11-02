"""Fail-closed E06 collection gate.

Database tests are classified and blocked before fixture setup. With explicit
opt-in, all configured DSNs are allowlisted and their live PG16 identities
are verified before any test module can execute.
"""
import os
from pathlib import Path

import pytest
from e06_isolated_db_guard import check_environment, IsolationDenied

# Conservative classification. A false positive skips a test; a false negative
# could execute a write. Connection-bearing modules are explicitly included.
_DB_FILES = frozenset({
    "test_agent_atomic_v03.py",
    "test_agent_governance_v02.py",
    "test_agent_harness_postgres.py",
    "test_erp_v11_stage3_postgres.py",
    "test_integrated_postgres.py",
    "test_postgres_integration.py",
    "test_pg_contract_v02.py",
    "test_workbench_postgres.py",
    "test_v18_phase4_http_workbench.py",
})


def _is_db_test(item):
    name = Path(str(item.path)).name
    return (
        name in _DB_FILES
        or "postgres" in name
        or "pg16" in name
        or item.get_closest_marker("integration") is not None
        or (name.startswith("test_m10") and name.endswith("_full_gate.py"))
    )


def pytest_collection_modifyitems(items):
    """Skip or block database tests before fixtures or test bodies execute."""
    db_items = [item for item in items if _is_db_test(item)]
    if not db_items:
        return
    if os.environ.get("E06_ALLOW_ISOLATED_DB_TESTS") != "YES":
        for item in db_items:
            item.add_marker(
                pytest.mark.skip(reason="E06: database tests disabled by default")
            )
        return
    try:
        # Explicit opt-in is not enough: prove every target against the live server.
        check_environment(verify_server=True)
    except IsolationDenied as exc:
        pytest.exit(
            "E06 isolated database guard rejected: " + str(exc),
            returncode=4,
        )
