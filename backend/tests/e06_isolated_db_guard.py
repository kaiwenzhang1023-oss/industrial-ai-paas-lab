"""E06 test-only fail-closed PostgreSQL target and server identity guard.

Imported only by pytest test configuration; never by production application code.
"""
from __future__ import annotations

import os
from urllib.parse import urlsplit, unquote

ALLOWED_TARGETS = {
    # Legacy isolated databases retained for their dedicated historical suites.
    "industrial_lab_v12_test": None,
    "industrial_lab_test": None,  # requires RC6 disposable-container marker for this target
    "industrial_lab_v13_test": None,
    "industrial_lab_v14_test": None,
    "industrial_lab_v15_test": None,
    "industrial_ai_v18_test": "v18_tester",
    # Dedicated E06 acceptance database created in the user's PG16 test container.
    "industrial_ai_v18_e06_acceptance": "v18_tester",
}
ALLOWED_NAMES = frozenset(ALLOWED_TARGETS)
ALLOWED_PORTS = frozenset({5432, 55432, 55433})
DSN_KEYS = (
    "TEST_DATABASE_URL",
    "M1_TEST_DATABASE_URL",
    "V15_BUSINESS_DATABASE_URL",
    "V18_ISOLATED_PG16_DSN",
)


class IsolationDenied(ValueError):
    """Raised when a configured database target cannot be proven isolated."""


def parse_dsn(dsn: str):
    """Parse a strict local TCP PostgreSQL URL without exposing credentials."""
    if not dsn or not dsn.startswith(("postgresql://", "postgres://")):
        raise IsolationDenied("E06_DSN_URL_REQUIRED")
    try:
        parsed = urlsplit(dsn)
        host = parsed.hostname
        port = parsed.port
        database = unquote(parsed.path.removeprefix("/"))
        username = unquote(parsed.username or "")
        password = parsed.password
    except (ValueError, TypeError):
        raise IsolationDenied("E06_DSN_INVALID") from None

    if (
        host not in ("127.0.0.1", "localhost")
        or port not in ALLOWED_PORTS
        or database not in ALLOWED_NAMES
        or not username
        or parsed.query
        or parsed.fragment
        or not parsed.path.startswith("/")
        or "/" in database
        or "," in parsed.netloc
        or (password is not None and "@" in password)
    ):
        raise IsolationDenied("E06_DSN_TARGET_DENIED")

    expected_user = ALLOWED_TARGETS[database]
    if expected_user is not None and username != expected_user:
        raise IsolationDenied("E06_DSN_USER_DENIED")
    return {
        "host": host,
        "port": port,
        "database": database,
        "username": username,
    }


def check_dsn(dsn: str) -> None:
    """Compatibility wrapper used by the pure unit tests."""
    parse_dsn(dsn)


def verify_server_identity(dsn: str, connect_timeout: int = 5) -> None:
    """Connect only after URL allowlisting, then prove DB/user/PG16/primary identity."""
    expected = parse_dsn(dsn)
    try:
        import psycopg

        with psycopg.connect(dsn, connect_timeout=connect_timeout) as conn:
            row = conn.execute(
                """
                SELECT current_database(),
                       current_user,
                       current_setting('server_version_num')::integer,
                       pg_is_in_recovery()
                """
            ).fetchone()
    except IsolationDenied:
        raise
    except Exception:
        # Do not propagate driver errors: they can contain connection details.
        raise IsolationDenied("E06_SERVER_IDENTITY_CONNECTION_FAILED") from None

    database, username, version_num, in_recovery = row
    if database != expected["database"]:
        raise IsolationDenied("E06_SERVER_DATABASE_IDENTITY_MISMATCH")
    if username != expected["username"]:
        raise IsolationDenied("E06_SERVER_USER_IDENTITY_MISMATCH")
    if not 160000 <= int(version_num) < 170000:
        raise IsolationDenied("E06_SERVER_MUST_BE_POSTGRESQL_16")
    if in_recovery:
        raise IsolationDenied("E06_SERVER_READ_REPLICA_DENIED")


def check_environment(env=None, verify_server: bool = False) -> None:
    env = os.environ if env is None else env
    configured = []
    for key in DSN_KEYS:
        value = env.get(key)
        if value:
            parse_dsn(value)
            configured.append((key, value))

    if env.get("DATABASE_URL"):
        # Production fallback must not be available in a database-test process.
        raise IsolationDenied("E06_DATABASE_URL_MUST_BE_UNSET")
    if not configured:
        raise IsolationDenied("E06_TEST_DSN_MISSING")

    if verify_server:
        # Verify every configured target, including secondary/business DBs.
        for _key, value in configured:
            verify_server_identity(value)
            # The previously excluded general-purpose test name must never be
            # authorized solely by its name/port. Prove this run's random marker.
            if parse_dsn(value)["database"] == "industrial_lab_test":
                token = env.get("RC6_LOCAL_ISOLATION_TOKEN", "")
                if len(token) < 32:
                    raise IsolationDenied("E06_RC6_ISOLATION_MARKER_MISSING")
                try:
                    import psycopg
                    with psycopg.connect(value, connect_timeout=5) as conn:
                        marker = conn.execute(
                            "SELECT token FROM public.rc6_isolation_marker LIMIT 1"
                        ).fetchone()
                    if not marker or marker[0] != token:
                        raise IsolationDenied("E06_RC6_ISOLATION_MARKER_MISMATCH")
                except IsolationDenied:
                    raise
                except Exception:
                    raise IsolationDenied("E06_RC6_ISOLATION_MARKER_UNAVAILABLE") from None
