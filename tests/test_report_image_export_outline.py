from __future__ import annotations

from services.report_image_batch_export_process import _load_context_for_export_mode


def test_outline_export_does_not_load_special_strategy_result_bundle() -> None:
    calls = []

    def load_bundle(_facility_code, _run_id):
        calls.append("load")
        raise AssertionError("outline export must not load result snapshot")

    context = _load_context_for_export_mode(
        facility_code="WC19-1D",
        run_id=None,
        mode="outline",
        load_bundle=load_bundle,
    )

    assert context == {}
    assert calls == []


def test_risk_export_loads_special_strategy_result_bundle_context() -> None:
    def load_bundle(_facility_code, _run_id):
        return {"context": {"node": {"A001": "II"}}}

    context = _load_context_for_export_mode(
        facility_code="WC19-1D",
        run_id=3,
        mode="risk",
        load_bundle=load_bundle,
    )

    assert context == {"node": {"A001": "II"}}
