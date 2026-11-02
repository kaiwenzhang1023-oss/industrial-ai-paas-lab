from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/web/app.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/web/style.css").read_text(encoding="utf-8")


def test_w3_execution_feedback_is_local_and_guarded():
    assert 'id="w3Status"' in JS
    assert "if(w3Submitting)return" in JS
    assert "go.disabled=true" in JS
    assert "w3Submitting=false" in JS
    assert "role=\"status\"" in JS


def test_w3_evidence_preserves_source_truth():
    assert "d.run.input_hash" in JS
    assert "d.run.result_hash" in JS
    assert "d.order_scope.order_ids" in JS
    assert "未归属（原始为空）" in JS
    assert "不推断为当前选中订单" in JS
    assert "w3-evidence" in CSS
