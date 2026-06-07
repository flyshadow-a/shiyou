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


def test_platform_options_come_from_facility_profiles_and_keep_allowed_codes(monkeypatch):
    monkeypatch.setattr(
        platforms,
        "list_facility_profiles",
        lambda: [
            {
                "facility_code": "OTHER",
                "facility_name": "Other平台",
                "branch": "其他分公司",
                "op_company": "其他作业公司",
                "oilfield": "其他油田",
                "facility_type": "平台",
                "category": "其他平台",
                "start_time": "2000-01-01",
                "design_life": "10",
            },
            {
                "facility_code": "WC9-7",
                "facility_name": "WC9-7平台-数据库",
                "branch": "数据库分公司",
                "op_company": "数据库作业公司",
                "oilfield": "WC9-7数据库油田",
                "facility_type": "平台",
                "category": "生产平台",
                "start_time": "2014-02-03",
                "design_life": "20",
            },
            {
                "facility_code": "WC19-1D",
                "facility_name": "WC19-1D平台-数据库",
                "branch": "数据库分公司",
                "op_company": "数据库作业公司",
                "oilfield": "WC19-1数据库油田",
                "facility_type": "平台",
                "category": "生产平台",
                "start_time": "2013-07-15",
                "design_life": "15",
            },
        ],
    )

    assert platforms.platform_codes() == ["WC19-1D", "WC9-7"]
    assert platforms.platform_names() == ["WC19-1D平台-数据库", "WC9-7平台-数据库"]


def test_sync_platform_dropdowns_uses_database_profile_values(monkeypatch):
    monkeypatch.setattr(
        platforms,
        "list_facility_profiles",
        lambda: [
            {
                "facility_code": "WC19-1D",
                "facility_name": "WC19-1D平台-数据库",
                "branch": "湛江分公司-数据库",
                "op_company": "作业公司-数据库",
                "oilfield": "WC19-1油田-数据库",
                "facility_type": "平台",
                "category": "生产平台",
                "start_time": "2013-07-15",
                "design_life": "15",
            },
            {
                "facility_code": "WC9-7",
                "facility_name": "WC9-7平台-数据库",
                "branch": "湛江分公司-数据库",
                "op_company": "作业公司-数据库",
                "oilfield": "WC9-7油田-数据库",
                "facility_type": "平台",
                "category": "生产平台",
                "start_time": "2014-02-03",
                "design_life": "20",
            },
        ],
    )
    dropdown = FakeDropdown()
    dropdown.values["facility_code"] = "WC9-7"

    selected = platforms.sync_platform_dropdowns(dropdown, changed_key="facility_code")

    assert selected["facility_code"] == "WC9-7"
    assert dropdown.options["facility_code"] == ["WC19-1D", "WC9-7"]
    assert dropdown.options["facility_name"] == ["WC19-1D平台-数据库", "WC9-7平台-数据库"]
    assert dropdown.values["oilfield"] == "WC9-7油田-数据库"


def test_sync_platform_dropdowns_keeps_oilfield_options_for_allowed_platforms(monkeypatch):
    monkeypatch.setattr(
        platforms,
        "list_facility_profiles",
        lambda: [
            {
                "facility_code": "WC19-1D",
                "facility_name": "WC19-1D平台",
                "branch": "湛江分公司",
                "op_company": "作业公司",
                "oilfield": "WC19-1油田",
                "facility_type": "平台",
                "category": "生产平台",
                "start_time": "2013-07-15",
                "design_life": "15",
            },
            {
                "facility_code": "WC9-7",
                "facility_name": "WC9-7平台",
                "branch": "湛江分公司",
                "op_company": "作业公司",
                "oilfield": "WC9-7油田",
                "facility_type": "平台",
                "category": "生产平台",
                "start_time": "2014-02-03",
                "design_life": "20",
            },
        ],
    )
    dropdown = FakeDropdown()
    dropdown.values["facility_code"] = "WC9-7"

    platforms.sync_platform_dropdowns(dropdown, changed_key="facility_code")

    assert dropdown.options["oilfield"] == ["WC19-1油田", "WC9-7油田"]
    assert dropdown.values["oilfield"] == "WC9-7油田"


def test_sync_platform_dropdowns_selects_platform_when_oilfield_changes(monkeypatch):
    monkeypatch.setattr(
        platforms,
        "list_facility_profiles",
        lambda: [
            {
                "facility_code": "WC19-1D",
                "facility_name": "WC19-1D平台",
                "branch": "湛江分公司",
                "op_company": "作业公司",
                "oilfield": "WC19-1油田",
                "facility_type": "平台",
                "category": "生产平台",
                "start_time": "2013-07-15",
                "design_life": "15",
            },
            {
                "facility_code": "WC9-7",
                "facility_name": "WC9-7平台",
                "branch": "湛江分公司",
                "op_company": "作业公司",
                "oilfield": "WC9-7油田",
                "facility_type": "平台",
                "category": "生产平台",
                "start_time": "2014-02-03",
                "design_life": "20",
            },
        ],
    )
    dropdown = FakeDropdown()
    dropdown.values["facility_code"] = "WC19-1D"
    dropdown.values["oilfield"] = "WC9-7油田"

    selected = platforms.sync_platform_dropdowns(dropdown, changed_key="oilfield")

    assert selected["facility_code"] == "WC9-7"
    assert dropdown.values["facility_code"] == "WC9-7"
    assert dropdown.values["facility_name"] == "WC9-7平台"
    assert dropdown.values["oilfield"] == "WC9-7油田"


def test_sync_platform_dropdowns_updates_alias_keys_used_by_design_files(monkeypatch):
    monkeypatch.setattr(
        platforms,
        "list_facility_profiles",
        lambda: [
            {
                "facility_code": "WC19-1D",
                "facility_name": "WC19-1D平台",
                "branch": "湛江分公司",
                "op_company": "作业公司",
                "oilfield": "WC19-1油田",
                "facility_type": "平台",
                "category": "生产平台",
                "start_time": "2013-07-15",
                "design_life": "15",
            },
            {
                "facility_code": "WC9-7",
                "facility_name": "WC9-7平台",
                "branch": "湛江分公司",
                "op_company": "作业公司",
                "oilfield": "WC9-7油田",
                "facility_type": "平台",
                "category": "生产平台",
                "start_time": "2014-02-03",
                "design_life": "20",
            },
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
    assert dropdown.options["field"] == ["WC19-1油田", "WC9-7油田"]
    assert dropdown.values["field"] == "WC9-7油田"
    assert dropdown.values["division"] == "湛江分公司"
    assert dropdown.values["company"] == "作业公司"
    assert dropdown.options["design_years"] == ["15", "20"]
    assert dropdown.values["design_years"] == "20"
