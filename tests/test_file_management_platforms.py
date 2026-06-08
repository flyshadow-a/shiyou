from types import SimpleNamespace

from pages import file_management_platforms as platforms


class FakeDropdown:
    def __init__(self):
        self.values = {
            "facility_code": "",
            "facility_name": "",
        }
        self.options = {}

    def get_value(self, key):
        return self.values.get(key, "")

    def set_options(self, key, options, default=""):
        self.options[key] = list(options)
        if default:
            self.values[key] = default
        elif options:
            self.values[key] = options[0]


def profile(
    code,
    name,
    *,
    branch="Branch",
    op_company="Company",
    oilfield="Field",
    facility_type="Platform",
    category="Production",
    start_time="2024-01-01",
    design_life="25",
):
    return {
        "facility_code": code,
        "facility_name": name,
        "branch": branch,
        "op_company": op_company,
        "oilfield": oilfield,
        "facility_type": facility_type,
        "category": category,
        "start_time": start_time,
        "design_life": design_life,
    }


def patch_summary_profiles(monkeypatch, source_profiles):
    platforms.clear_platform_profiles_cache()
    monkeypatch.setattr(
        platforms,
        "load_platform_summary_source",
        lambda: SimpleNamespace(profiles=source_profiles),
        raising=False,
    )
    monkeypatch.setattr(platforms, "list_facility_profiles", lambda: [])


def test_platform_profiles_are_cached_until_explicit_refresh(monkeypatch):
    calls = []
    source_profiles = [
        [profile("OLD-1", "Old Platform")],
        [profile("NEW-1", "New Platform")],
    ]

    def load_source():
        calls.append("load")
        index = min(len(calls) - 1, len(source_profiles) - 1)
        return SimpleNamespace(profiles=source_profiles[index])

    platforms.clear_platform_profiles_cache()
    monkeypatch.setattr(platforms, "load_platform_summary_source", load_source, raising=False)
    monkeypatch.setattr(platforms, "list_facility_profiles", lambda: [])

    assert platforms.platform_codes() == ["OLD-1"]
    assert platforms.platform_names() == ["Old Platform"]
    assert calls == ["load"]

    assert platforms.platform_codes() == ["OLD-1"]
    assert calls == ["load"]

    assert [item["facility_code"] for item in platforms.refresh_platform_profiles_cache()] == ["NEW-1"]
    assert platforms.platform_codes() == ["NEW-1"]
    assert calls == ["load", "load"]


def test_apply_platform_defaults_to_fields_uses_cached_database_options(monkeypatch):
    patch_summary_profiles(
        monkeypatch,
        [
            profile("NEW-1", "New Platform", branch="Branch A", op_company="Company A", oilfield="Field A"),
            profile("NEW-2", "Second Platform", branch="Branch A", op_company="Company A", oilfield="Field A"),
        ],
    )
    fields = [
        {"key": "division", "options": ["hardcoded"], "default": "hardcoded"},
        {"key": "company", "options": ["hardcoded"], "default": "hardcoded"},
        {"key": "field", "options": ["hardcoded"], "default": "hardcoded"},
        {"key": "facility_code", "options": ["WC19-1D", "WC9-7"], "default": "WC19-1D"},
        {"key": "facility_name", "options": ["WC19-1D Platform"], "default": "WC19-1D Platform"},
        {"key": "design_years", "options": ["15"], "default": "15"},
    ]

    platforms.apply_platform_defaults_to_fields(fields)

    field_map = {item["key"]: item for item in fields}
    assert field_map["division"]["options"] == ["Branch A"]
    assert field_map["company"]["options"] == ["Company A"]
    assert field_map["field"]["options"] == ["Field A"]
    assert field_map["facility_code"]["options"] == ["NEW-1", "NEW-2"]
    assert field_map["facility_name"]["options"] == ["New Platform", "Second Platform"]
    assert field_map["facility_code"]["default"] == "NEW-1"
    assert field_map["facility_name"]["default"] == "New Platform"


def test_apply_platform_defaults_to_fields_gives_long_fields_more_space(monkeypatch):
    patch_summary_profiles(
        monkeypatch,
        [
            profile(
                "NEW-1",
                "Very Long Platform Name",
                op_company="Very Long Operating Company Name",
            ),
        ],
    )
    fields = [
        {"key": "branch"},
        {"key": "company"},
        {"key": "facility_code"},
        {"key": "facility_name"},
    ]

    platforms.apply_platform_defaults_to_fields(fields)

    field_map = {item["key"]: item for item in fields}
    assert field_map["company"]["stretch"] > field_map["branch"]["stretch"]
    assert field_map["facility_name"]["stretch"] > field_map["facility_code"]["stretch"]


def test_platform_options_come_from_platform_summary_source(monkeypatch):
    patch_summary_profiles(
        monkeypatch,
        [
            profile("NEW-1", "New Platform", branch="Branch A", oilfield="Field A"),
            profile("WC9-7", "WC9-7 Platform", branch="Branch B", oilfield="Field B"),
        ],
    )

    assert platforms.platform_codes() == ["NEW-1", "WC9-7"]
    assert platforms.platform_names() == ["New Platform", "WC9-7 Platform"]


def test_platform_profiles_fall_back_to_defaults_when_summary_source_empty(monkeypatch):
    patch_summary_profiles(monkeypatch, [])

    assert platforms.platform_codes() == ["WC19-1D", "WC9-7"]


def test_sync_platform_dropdowns_uses_summary_profile_values(monkeypatch):
    patch_summary_profiles(
        monkeypatch,
        [
            profile("WC19-1D", "WC19-1D Platform", oilfield="Field 1", design_life="15"),
            profile("WC9-7", "WC9-7 Platform", oilfield="Field 2", design_life="20"),
        ],
    )
    dropdown = FakeDropdown()
    dropdown.values["facility_code"] = "WC9-7"

    selected = platforms.sync_platform_dropdowns(dropdown, changed_key="facility_code")

    assert selected["facility_code"] == "WC9-7"
    assert dropdown.options["facility_code"] == ["WC9-7"]
    assert dropdown.options["facility_name"] == ["WC9-7 Platform"]
    assert dropdown.values["oilfield"] == "Field 2"


def test_sync_platform_dropdowns_keeps_current_new_platform_after_refresh(monkeypatch):
    patch_summary_profiles(
        monkeypatch,
        [
            profile("NEW-1", "New Platform", branch="Branch A", oilfield="Field A"),
            profile("WC19-1D", "WC19-1D Platform", branch="Branch B", oilfield="Field B"),
        ],
    )
    dropdown = FakeDropdown()
    dropdown.values["facility_code"] = "NEW-1"

    selected = platforms.sync_platform_dropdowns(dropdown, changed_key="facility_code")

    assert selected["facility_code"] == "NEW-1"
    assert dropdown.values["facility_code"] == "NEW-1"
    assert dropdown.options["facility_code"] == ["NEW-1"]
    assert dropdown.values["facility_name"] == "New Platform"


def test_sync_platform_dropdowns_switches_to_first_valid_platform_when_current_missing(monkeypatch):
    patch_summary_profiles(
        monkeypatch,
        [
            profile("NEW-1", "New Platform"),
            profile("WC19-1D", "WC19-1D Platform"),
        ],
    )
    dropdown = FakeDropdown()
    dropdown.values["facility_code"] = "DELETED"

    selected = platforms.sync_platform_dropdowns(dropdown, changed_key="facility_code")

    assert selected["facility_code"] == "NEW-1"
    assert dropdown.values["facility_code"] == "NEW-1"


def test_sync_platform_dropdowns_cascades_options_by_selected_hierarchy(monkeypatch):
    patch_summary_profiles(
        monkeypatch,
        [
            profile("P1", "Name 1", branch="Branch 1", op_company="Company 1", oilfield="Field 1"),
            profile("P2", "Name 2", branch="Branch 1", op_company="Company 1", oilfield="Field 1"),
            profile("P3", "Name 3", branch="Branch 1", op_company="Company 1", oilfield="Field 2"),
            profile("P4", "Name 4", branch="Branch 2", op_company="Company 2", oilfield="Field 3"),
        ],
    )
    dropdown = FakeDropdown()
    dropdown.values["facility_code"] = "P2"

    selected = platforms.sync_platform_dropdowns(dropdown, changed_key="facility_code")

    assert selected["facility_code"] == "P2"
    assert dropdown.options["branch"] == ["Branch 1", "Branch 2"]
    assert dropdown.options["op_company"] == ["Company 1"]
    assert dropdown.options["oilfield"] == ["Field 1", "Field 2"]
    assert dropdown.options["facility_code"] == ["P1", "P2"]
    assert dropdown.options["facility_name"] == ["Name 2"]
    assert dropdown.values["branch"] == "Branch 1"
    assert dropdown.values["op_company"] == "Company 1"
    assert dropdown.values["oilfield"] == "Field 1"
    assert dropdown.values["facility_name"] == "Name 2"


def test_sync_platform_dropdowns_resets_lower_levels_when_top_level_changes(monkeypatch):
    patch_summary_profiles(
        monkeypatch,
        [
            profile("P1", "Name 1", branch="Branch 1", op_company="Company 1", oilfield="Field 1"),
            profile("P2", "Name 2", branch="Branch 2", op_company="Company 2", oilfield="Field 2"),
        ],
    )
    dropdown = FakeDropdown()
    dropdown.values.update(
        {
            "division": "Branch 2",
            "company": "Company 1",
            "field": "Field 1",
            "facility_code": "P1",
        }
    )

    selected = platforms.sync_platform_dropdowns(dropdown, changed_key="division")

    assert selected["facility_code"] == "P2"
    assert dropdown.options["company"] == ["Company 2"]
    assert dropdown.options["field"] == ["Field 2"]
    assert dropdown.options["facility_code"] == ["P2"]
    assert dropdown.options["facility_name"] == ["Name 2"]
    assert dropdown.values["division"] == "Branch 2"
    assert dropdown.values["company"] == "Company 2"
    assert dropdown.values["field"] == "Field 2"
    assert dropdown.values["facility_code"] == "P2"


def test_sync_platform_dropdowns_matches_company_width_variants_but_keeps_database_text(monkeypatch):
    db_company = "中海石油（中国）有限公司湛江分公司"
    typed_company = "中海石油(中国)有限公司湛江分公司"
    patch_summary_profiles(
        monkeypatch,
        [
            profile("P1", "Name 1", branch="Branch 1", op_company="Other Company", oilfield="Field 1"),
            profile("P2", "Name 2", branch="Branch 1", op_company=db_company, oilfield="Field 2"),
        ],
    )
    dropdown = FakeDropdown()
    dropdown.values.update(
        {
            "branch": "Branch 1",
            "company": typed_company,
        }
    )

    selected = platforms.sync_platform_dropdowns(dropdown, changed_key="company")

    assert selected["facility_code"] == "P2"
    assert dropdown.values["company"] == db_company
    assert db_company in dropdown.options["company"]


def test_sync_platform_dropdowns_selects_platform_when_oilfield_changes(monkeypatch):
    patch_summary_profiles(
        monkeypatch,
        [
            profile("WC19-1D", "WC19-1D Platform", oilfield="Field 1"),
            profile("WC9-7", "WC9-7 Platform", oilfield="Field 2"),
        ],
    )
    dropdown = FakeDropdown()
    dropdown.values["facility_code"] = "WC19-1D"
    dropdown.values["oilfield"] = "Field 2"

    selected = platforms.sync_platform_dropdowns(dropdown, changed_key="oilfield")

    assert selected["facility_code"] == "WC9-7"
    assert dropdown.values["facility_code"] == "WC9-7"
    assert dropdown.values["facility_name"] == "WC9-7 Platform"
    assert dropdown.values["oilfield"] == "Field 2"


def test_sync_platform_dropdowns_updates_alias_keys_used_by_design_files(monkeypatch):
    patch_summary_profiles(
        monkeypatch,
        [
            profile(
                "WC19-1D",
                "WC19-1D Platform",
                branch="Branch 1",
                op_company="Company 1",
                oilfield="Field 1",
                design_life="15",
            ),
            profile(
                "WC9-7",
                "WC9-7 Platform",
                branch="Branch 2",
                op_company="Company 2",
                oilfield="Field 2",
                design_life="20",
            ),
        ],
    )
    dropdown = FakeDropdown()
    dropdown.values.update(
        {
            "facility_code": "WC9-7",
            "division": "",
            "company": "",
            "field": "",
            "design_years": "",
        }
    )

    selected = platforms.sync_platform_dropdowns(dropdown, changed_key="facility_code")

    assert selected["facility_code"] == "WC9-7"
    assert dropdown.options["field"] == ["Field 2"]
    assert dropdown.values["field"] == "Field 2"
    assert dropdown.values["division"] == "Branch 2"
    assert dropdown.values["company"] == "Company 2"
    assert dropdown.options["design_years"] == ["20"]
    assert dropdown.values["design_years"] == "20"
