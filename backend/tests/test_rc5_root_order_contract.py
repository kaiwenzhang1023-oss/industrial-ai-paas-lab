"""RC5 read-only route and front-end contract, no PostgreSQL connection required."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_root_order_trace_is_read_only_and_persisted():
    source = (ROOT / "app" / "workbench.py").read_text(encoding="utf-8")
    start = source.index("@router.get('/root-orders/{order_id}/trace')")
    route = source[start:]
    assert "mock_erp.sales_orders" in route
    assert "platform.mrp_demand_allocations" in route
    assert "platform.requirement_runs" in route
    assert "NO_PERSISTED_ALLOCATION" in route
    assert "INSERT INTO" not in route.upper()
    assert "UPDATE " not in route.upper()

def test_root_order_page_has_real_api_and_no_mock_fallback():
    js = (ROOT / "app" / "web" / "app.js").read_text(encoding="utf-8")
    html = (ROOT / "app" / "web" / "index.html").read_text(encoding="utf-8")
    assert "root-orders/" in js and "/trace" in js
    assert "data-tab=\"root\"" in html
    assert "NO_PERSISTED_ALLOCATION" in js
    assert "data-root-run" in js
