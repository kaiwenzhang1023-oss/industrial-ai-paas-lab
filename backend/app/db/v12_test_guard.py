"""Strict, test-only connection gate for the local V1.2 isolated PostgreSQL database."""
import os
from psycopg.conninfo import conninfo_to_dict

def require_v12_test_url(url=None):
    url = url or os.getenv("TEST_DATABASE_URL")
    if not url:
        raise ValueError("TEST_DATABASE_URL_MISSING")
    info = conninfo_to_dict(url)
    if (info.get("host"), str(info.get("port", "5432")), info.get("dbname"), info.get("user")) != ("127.0.0.1", "5432", "industrial_lab_v12_test", "lab"):
        raise ValueError("V12_TEST_DB_GUARD_REJECTED")
    if os.getenv("DATABASE_URL"):
        raise ValueError("DATABASE_URL_MUST_BE_UNSET")
    return url
