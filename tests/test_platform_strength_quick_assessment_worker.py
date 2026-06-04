from services.platform_strength_quick_assessment import run_quick_assessment_preparation


def test_run_quick_assessment_preparation_uses_plain_payload_and_returns_job_name(monkeypatch):
    calls = []

    def fake_get_env_profile_id(*, branch, op_company, oilfield, create_if_missing):
        calls.append(("profile", branch, op_company, oilfield, create_if_missing))
        return 123

    def fake_replace_splash(profile_id, facility_code, items, **_kwargs):
        calls.append(("splash", profile_id, facility_code, items))

    def fake_replace_marine(profile_id, facility_code, items, **_kwargs):
        calls.append(("marine", profile_id, facility_code, items))

    def fake_save_structure(mysql_url, **kwargs):
        calls.append(("structure", mysql_url, kwargs))

    def fake_import_bundle(**kwargs):
        calls.append(("import", kwargs))
        return {"job_name": kwargs["job_name"], "joints": 10}

    monkeypatch.setattr(
        "services.platform_strength_quick_assessment.get_env_profile_id",
        fake_get_env_profile_id,
    )
    monkeypatch.setattr(
        "services.platform_strength_quick_assessment.replace_platform_strength_splash_items",
        fake_replace_splash,
    )
    monkeypatch.setattr(
        "services.platform_strength_quick_assessment.replace_platform_strength_marine_items",
        fake_replace_marine,
    )
    monkeypatch.setattr(
        "services.platform_strength_quick_assessment.save_structure_model_info",
        fake_save_structure,
    )
    monkeypatch.setattr(
        "services.platform_strength_quick_assessment.import_model_bundle_to_db",
        fake_import_bundle,
    )

    payload = {
        "mysql_url": "mysql+pymysql://user:pass@localhost/db",
        "facility_code": "WC19",
        "branch": "branch",
        "op_company": "company",
        "oilfield": "oilfield",
        "model_path": "C:/model/sacinp",
        "sea_file": "C:/model/seainp",
        "workpoint": 9.1,
        "workpoint_m": None,
        "mud_level": -83.0,
        "level_threshold": 40,
        "splash_items": [{"sort_order": 1}],
        "marine_items": [{"sort_order": 1}],
    }

    result = run_quick_assessment_preparation(payload)

    assert result["job_name"] == "WC19"
    assert result["import_result"] == {"job_name": "WC19", "joints": 10}
    assert calls[0] == ("profile", "branch", "company", "oilfield", True)
    assert calls[-1][0] == "import"
    assert calls[-1][1]["overwrite_job"] is True
