"""Public, deterministic EM-100 educational MRP example; no database access or writes."""
import hashlib
import json
import os
from fastapi import APIRouter
from app.domain.mrp import BOM, MATERIALS, calculate, procurement_total

router = APIRouter(prefix="/api/v1/portfolio-demo", tags=["portfolio-demo"])

@router.get("/mrp/golden")
def golden_mrp_demo():
    results = calculate(order_qty=100)
    lines = [{"material_id": code, **row, "on_hand": MATERIALS[code].on_hand,
              "reserved": MATERIALS[code].reserved, "blocked": MATERIALS[code].blocked,
              "moq": MATERIALS[code].moq, "lot": MATERIALS[code].lot}
             for code, row in sorted(results.items())]
    inputs = {"order_id": "SO-2026-001", "product_id": "EM-100", "order_quantity": 100,
              "due_date": "2026-11-30", "scenario": "EM-100-GOLDEN-V1",
              "bom": [{"parent": a, "component": b, "qty_per": q} for a,b,q in BOM],
              "materials": [{"material_id": code, "on_hand": m.on_hand,
                             "reserved": m.reserved, "blocked": m.blocked,
                             "receipts": [{"date": d, "qty": q} for d,q in m.receipts],
                             "moq": m.moq, "lot": m.lot, "lead_days": m.lead_days}
                            for code,m in sorted(MATERIALS.items())]}
    result = {"lines": lines, "purchase_amount_cny": str(procurement_total(results))}
    canonical = json.dumps({"inputs": inputs, "result": result}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    pegging = [{"root_order_id": inputs["order_id"], "material_id": row["material_id"],
                "gross": row["gross"], "planned": row["planned"], "need_date": row["need_date"],
                "evidence_type": "SINGLE_ORDER_GOLDEN_DERIVATION"} for row in lines]
    return {"simulation": True, "source": "deterministic-golden-calculator",
            "not_persisted": True, "not_live_inventory": True, "not_platform_pegging": True,
            "scenario": inputs, "result": result, "pegging_illustration": pegging,
            "procurement_suggestions": [row for row in lines if row["kind"] == "BUY" and row["planned"] > 0],
            "snapshot": {"fingerprint_sha256": fingerprint, "rule_version": "EM-100-GOLDEN-V1",
                         "snapshot_kind": "REPRODUCIBLE_IN_MEMORY", "database_run_id": None}}

@router.get("/capabilities")
def capabilities():
    return {"public_demo": True, "operator_execution_available":
            os.getenv("PUBLIC_READ_ONLY") != "1" and os.getenv("DEMO_WRITE_ENABLED") == "1" and bool(os.getenv("DEMO_OPERATOR_KEY"))}
