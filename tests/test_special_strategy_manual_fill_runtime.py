from services import special_strategy_runtime as runtime
from pages.output_special_strategy.inspection_tool import normalize_manual_selector_overrides


def test_manual_selector_overrides_accept_client_dialog_rows_with_raw_keys():
    rows = [
        {
            "raw": {"FileIndex": 1, "Joint": "301L"},
            "ManualBrace": "306L",
        }
    ]

    assert normalize_manual_selector_overrides(rows) == {(1, "301L"): "306L"}


def test_prepare_passes_client_manual_fill_entries_to_pipeline(monkeypatch, tmp_path):
    model_path = tmp_path / "sacinp.JKnew"
    clplog_path = tmp_path / "clplog"
    ftglst_path = tmp_path / "ftglst"
    ftginp_path = tmp_path / "ftginp"
    template_path = tmp_path / "template.xlsm"
    for path in (model_path, clplog_path, ftglst_path, ftginp_path, template_path):
        path.write_text("stub", encoding="utf-8")

    captured: dict = {}
    manual_entries = [{"FileIndex": 1, "Joint": "301L", "ManualBrace": "306L"}]

    def fake_run_artifact_paths(_facility_code, stamp):
        root = tmp_path / f"run_{stamp}"
        root.mkdir(parents=True, exist_ok=True)
        return {
            "root": root,
            "params_json": root / "runtime_params.json",
            "intermediate_workbook": root / "special_strategy.pipeline.xlsx",
            "output_report": root / "special_strategy.docx",
            "report_metadata_json": root / "report_metadata.json",
            "state_json": root / "runtime_state.json",
        }

    def fake_prepare_pipeline(**kwargs):
        captured.update(kwargs)
        return {"prepared": True}

    monkeypatch.setattr(
        runtime,
        "load_base_config",
        lambda _facility_code: {
            "model": str(model_path),
            "clplog": [str(clplog_path)],
            "ftglst": [str(ftglst_path)],
            "ftginp": [str(ftginp_path)],
            "template_xlsm": str(template_path),
            "policy": "strict",
            "seed": 42,
            "enable_topology_inference": False,
        },
    )
    monkeypatch.setattr(runtime, "run_artifact_paths", fake_run_artifact_paths)
    monkeypatch.setattr(runtime, "merge_runtime_params", lambda _code, _overrides=None: {})
    monkeypatch.setattr(runtime, "default_metadata", lambda _code: {})
    monkeypatch.setattr(runtime, "_common_config_path", lambda: tmp_path / "special_strategy_run_config.json")
    monkeypatch.setattr(runtime, "_load_inspection_pipeline_funcs", lambda: (fake_prepare_pipeline, lambda *_args, **_kwargs: {}))

    runtime.prepare_special_strategy_calculation(
        "WC19-1D",
        metadata={
            "manual_fill_entries": manual_entries,
            "disable_server_gui": True,
        },
    )

    assert captured["manual_selector_overrides"] == manual_entries
