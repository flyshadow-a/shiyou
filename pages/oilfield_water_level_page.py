# -*- coding: utf-8 -*-
# pages/oilfield_water_level_page.py
import re
from copy import deepcopy
from threading import Event, RLock
from typing import Any, List, Dict, Optional

from PyQt5.QtGui import QFont, QFontMetrics
from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout,
    QComboBox, QPushButton, QTableWidget, QTableWidgetItem,
    QStackedWidget, QWidget, QLabel, QHeaderView, QAbstractItemView, QSizePolicy, QMessageBox,
    QToolTip,
)
from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal
from core.base_page import BasePage
from core.dropdown_bar import DropdownBar
from core.table_clipboard import TableClipboardController
from pages.read_table_xls import ReadTableXls
from feasibility_analysis_services.oilfield_env_service import (
    get_env_profile_id,
    load_env_profiles,
    load_metric_items,
    load_water_level_items,
    replace_metric_items,
    replace_water_level_items,
)
from services.inspection_business_db_adapter import load_facility_profile
from pages.file_management_platforms import default_platform, platform_profiles



SONGTI_FONT_FALLBACK = '"SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei"'
_OILFIELD_TOP_DATA_CACHE: dict[str, Any] | None = None
_OILFIELD_TOP_DATA_CACHE_LOCK = RLock()
_OILFIELD_TOP_DATA_PREHEAT_DONE = Event()
_OILFIELD_TOP_DATA_PREHEAT_IN_PROGRESS = False
_OILFIELD_PREHEAT_WAIT_MS = 0



def _normalize_top_cache_value(value: object) -> str:
    txt = "" if value is None else str(value).strip()
    if (not txt) or (txt.lower() == "nan"):
        return ""
    if txt.endswith(".0") and txt[:-2].isdigit():
        return txt[:-2]
    return txt


def _dedupe_top_records(records: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen = set()
    for row in records:
        key = (row.get("branch", ""), row.get("op_company", ""), row.get("oilfield", ""))
        if not all(key) or key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _top_record_from_profile(profile: dict[str, Any]) -> dict[str, str]:
    return {
        "branch": _normalize_top_cache_value(profile.get("branch") or ""),
        "op_company": _normalize_top_cache_value(profile.get("op_company") or ""),
        "oilfield": _normalize_top_cache_value(profile.get("oilfield") or ""),
    }


def _platform_top_records() -> list[dict[str, str]]:
    try:
        records = [_top_record_from_profile(profile) for profile in platform_profiles()]
    except Exception:
        records = []
    return _dedupe_top_records(records)


def clear_oilfield_top_data_cache() -> None:
    global _OILFIELD_TOP_DATA_CACHE, _OILFIELD_TOP_DATA_PREHEAT_IN_PROGRESS

    with _OILFIELD_TOP_DATA_CACHE_LOCK:
        _OILFIELD_TOP_DATA_CACHE = None
        _OILFIELD_TOP_DATA_PREHEAT_IN_PROGRESS = False
        _OILFIELD_TOP_DATA_PREHEAT_DONE.clear()


def _get_oilfield_top_data_cache(wait_ms: int = 0) -> dict[str, Any] | None:
    with _OILFIELD_TOP_DATA_CACHE_LOCK:
        if _OILFIELD_TOP_DATA_CACHE is None:
            should_wait = wait_ms > 0 and _OILFIELD_TOP_DATA_PREHEAT_IN_PROGRESS
        else:
            return deepcopy(_OILFIELD_TOP_DATA_CACHE)

    if should_wait:
        _OILFIELD_TOP_DATA_PREHEAT_DONE.wait(wait_ms / 1000)

    with _OILFIELD_TOP_DATA_CACHE_LOCK:
        if _OILFIELD_TOP_DATA_CACHE is None:
            return None
        return deepcopy(_OILFIELD_TOP_DATA_CACHE)


def preheat_oilfield_top_data(force: bool = False) -> bool:
    global _OILFIELD_TOP_DATA_CACHE, _OILFIELD_TOP_DATA_PREHEAT_IN_PROGRESS

    with _OILFIELD_TOP_DATA_CACHE_LOCK:
        if _OILFIELD_TOP_DATA_CACHE is not None and not force:
            return True
        if _OILFIELD_TOP_DATA_PREHEAT_IN_PROGRESS and not force:
            should_wait = True
        else:
            should_wait = False
            _OILFIELD_TOP_DATA_PREHEAT_IN_PROGRESS = True
            _OILFIELD_TOP_DATA_PREHEAT_DONE.clear()

    if should_wait:
        return _OILFIELD_TOP_DATA_PREHEAT_DONE.wait(3)

    try:
        platform_defaults = dict(default_platform())
        facility_code = str(platform_defaults.get("facility_code") or "").strip()
        profile = dict(load_facility_profile(facility_code, defaults=platform_defaults))

        records = _platform_top_records()
        records.append({
            "branch": _normalize_top_cache_value(profile.get("branch") or platform_defaults.get("branch") or ""),
            "op_company": _normalize_top_cache_value(
                profile.get("op_company") or platform_defaults.get("op_company") or ""
            ),
            "oilfield": _normalize_top_cache_value(
                profile.get("oilfield") or platform_defaults.get("oilfield") or ""
            ),
        })
        deduped = _dedupe_top_records(records)

        top_data = {
            "platform_defaults": platform_defaults,
            "facility_code": facility_code,
            "profile": profile,
            "records": deduped,
        }

        branch = _normalize_top_cache_value(profile.get("branch") or platform_defaults.get("branch") or "")
        op_company = _normalize_top_cache_value(
            profile.get("op_company") or platform_defaults.get("op_company") or ""
        )
        oilfield = _normalize_top_cache_value(
            profile.get("oilfield") or platform_defaults.get("oilfield") or ""
        )
        table_data: dict[str, Any] = {
            "branch": branch,
            "op_company": op_company,
            "oilfield": oilfield,
            "profile_id": None,
            "water_items": [],
            "wind_items": [],
            "wave_items": [],
            "current_items": [],
        }
        try:
            if branch and op_company and oilfield:
                profile_id = get_env_profile_id(
                    branch=branch,
                    op_company=op_company,
                    oilfield=oilfield,
                    create_if_missing=False,
                )
                table_data["profile_id"] = profile_id
                if profile_id:
                    table_data["water_items"] = load_water_level_items(profile_id)
                    table_data["wind_items"] = load_metric_items("oilfield_wind_param_item", profile_id)
                    table_data["wave_items"] = load_metric_items("oilfield_wave_param_item", profile_id)
                    table_data["current_items"] = load_metric_items("oilfield_current_param_item", profile_id)
        except Exception:
            pass
        top_data["table_data"] = table_data
    except Exception as exc:
        with _OILFIELD_TOP_DATA_CACHE_LOCK:
            _OILFIELD_TOP_DATA_PREHEAT_IN_PROGRESS = False
            _OILFIELD_TOP_DATA_PREHEAT_DONE.set()
        return False

    with _OILFIELD_TOP_DATA_CACHE_LOCK:
        if _OILFIELD_TOP_DATA_CACHE is None or force:
            _OILFIELD_TOP_DATA_CACHE = top_data
        _OILFIELD_TOP_DATA_PREHEAT_IN_PROGRESS = False
        _OILFIELD_TOP_DATA_PREHEAT_DONE.set()
    return True


def _load_oilfield_top_data_for_page_worker() -> dict[str, Any] | None:
    with _OILFIELD_TOP_DATA_CACHE_LOCK:
        if _OILFIELD_TOP_DATA_CACHE is not None:
            return deepcopy(_OILFIELD_TOP_DATA_CACHE)
        should_wait = _OILFIELD_TOP_DATA_PREHEAT_IN_PROGRESS

    if should_wait:
        _OILFIELD_TOP_DATA_PREHEAT_DONE.wait()
        cached_top_data = _get_oilfield_top_data_cache()
        if cached_top_data is not None:
            return cached_top_data

    if preheat_oilfield_top_data():
        return _get_oilfield_top_data_cache()
    return _get_oilfield_top_data_cache()


class _OilfieldEnvPageLoadWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def run(self) -> None:
        try:
            cached_top_data = _load_oilfield_top_data_for_page_worker()
            if cached_top_data is not None:
                self.finished.emit(cached_top_data)
            else:
                self.failed.emit("海洋环境数据后台加载失败。")
        except Exception as exc:
            self.failed.emit(str(exc))


class OilfieldWaterLevelPage(BasePage):
    """
    油气田信息页面：
    - 顶部：分公司 / 作业公司 / 油气田 下拉选择 + 保存按钮
    - 中部：水深水位、风参数、波浪参数、海流参数 四个子页
            用按钮模拟选项卡 + 内部 QStackedWidget 切换
    """

    TOP_FIELDS: List[tuple] = [
        ("分公司", "湛江分公司"),
        ("作业公司", "中海石油(中国)有限公司湛江分公司"),
        ("油气田", "WC19-1油田"),
    ]

    KEY_TO_FIELD: Dict[str, str] = {
        "branch": "分公司",
        "op_company": "作业公司",
        "oilfield": "油气田",
    }

    TOP_KEY_ORDER = ["branch", "op_company", "oilfield"]

    @staticmethod
    def _songti_small_four_font(bold: bool = False) -> QFont:
        font = QFont("SimSun", 12)
        font.setBold(bold)
        return font

    def __init__(self, parent=None):
        super().__init__("", parent)
        self.tab_buttons = []
        self.tab_pages = None
        self.water_table = None
        self.wind_table = None
        self.wave_table = None
        self.current_table = None
        self._table_clipboard_controllers: list[TableClipboardController] = []
        self._syncing_top_dropdowns = False
        self._default_water_items: list[dict[str, Any]] = []
        self._default_wind_items: list[dict[str, Any]] = []
        self._default_wave_items: list[dict[str, Any]] = []
        self._default_current_items: list[dict[str, Any]] = []
        self._oilfield_load_thread: QThread | None = None
        self._oilfield_load_worker: _OilfieldEnvPageLoadWorker | None = None

        self.build_ui()

    def _normalize_top_value(self, value: object) -> str:
        txt = "" if value is None else str(value).strip()
        if (not txt) or (txt.lower() == "nan"):
            return ""
        if txt.endswith(".0") and txt[:-2].isdigit():
            return txt[:-2]
        return txt

    def _load_top_records_from_excel(self) -> List[Dict[str, str]]:
        if (not self._excel_loaded) or (not hasattr(self._excel_provider, "df")):
            return []

        df = self._excel_provider.df
        if df is None:
            return []

        fields = [f for f, _ in self.TOP_FIELDS]
        resolved: Dict[str, str] = {}
        for field in fields:
            col = self._excel_provider._resolve_col(field) if hasattr(self._excel_provider, "_resolve_col") else None
            if not col:
                return []
            resolved[field] = col

        rows: List[Dict[str, str]] = []
        seen = set()
        for _, row in df.iterrows():
            rec: Dict[str, str] = {}
            for field, col in resolved.items():
                raw = self._excel_provider._clean(row[col]) if hasattr(self._excel_provider, "_clean") else row[col]
                rec[field] = self._normalize_top_value(raw)

            if not any(rec.get(k) for k in ("分公司", "作业公司", "油气田")):
                continue

            sig = tuple(rec.get(f, "") for f in fields)
            if sig in seen:
                continue
            seen.add(sig)
            rows.append(rec)

        return rows

    def _unique_record_values(self, records: List[Dict[str, str]], field: str) -> List[str]:
        out: List[str] = []
        seen = set()
        for rec in records:
            v = self._normalize_top_value(rec.get(field, ""))
            if (not v) or (v in seen):
                continue
            seen.add(v)
            out.append(v)
        return out

    def _pick_option(self, options: List[str], preferred: str = "") -> str:
        p = self._normalize_top_value(preferred)
        if p and p in options:
            return p
        return options[0] if options else ""

    def _table_text(self, table: QTableWidget, row: int, col: int) -> str:
        item = table.item(row, col)
        if item is None:
            return ""
        return str(item.text() or "").strip()

    def _parse_decimal(self, value: Any) -> float:
        text = str(value or "").strip().replace(",", "")
        if not text:
            raise ValueError("empty numeric value")
        return float(text)

    def _extract_unit_from_item_name(self, item_name: str, default_unit: str) -> str:
        match = re.search(r"\(([^()]+)\)\s*$", item_name)
        if not match:
            return default_unit
        unit = match.group(1).strip()
        if (not unit) or any(token in unit for token in ("倍水深", "@")):
            return default_unit
        return unit
    def _get_env_context(self) -> dict[str, str]:
        cached_top_data = _get_oilfield_top_data_cache()
        if cached_top_data is not None:
            platform_defaults = cached_top_data.get("platform_defaults", {}) or {}
            facility_code = str(cached_top_data.get("facility_code") or "").strip()
            profile = cached_top_data.get("profile", {}) or {}
        else:
            platform_defaults = default_platform()
            facility_code = str(platform_defaults.get("facility_code") or "").strip()
            profile = platform_defaults
        values = self.dropdown_bar.get_all_values() if hasattr(self, "dropdown_bar") else {}
        return {
            "facility_code": facility_code,
            "branch": self._normalize_top_value(values.get("branch") or profile.get("branch") or ""),
            "op_company": self._normalize_top_value(values.get("op_company") or profile.get("op_company") or ""),
            "oilfield": self._normalize_top_value(values.get("oilfield") or profile.get("oilfield") or ""),
        }

    def _format_number_display(self, value: Any) -> str:
        text = self._normalize_top_value(value)
        if not text:
            return ""
        try:
            number = float(text)
        except Exception:
            return text
        return f"{number:.3f}".rstrip("0").rstrip(".")
    def _load_env_top_records(self) -> list[dict[str, str]]:
        cached_top_data = _get_oilfield_top_data_cache()
        if cached_top_data is not None:
            return list(cached_top_data.get("records", []) or [])

        platform_defaults = default_platform()
        record = {
            "branch": self._normalize_top_value(platform_defaults.get("branch") or ""),
            "op_company": self._normalize_top_value(platform_defaults.get("op_company") or ""),
            "oilfield": self._normalize_top_value(platform_defaults.get("oilfield") or ""),
        }
        return [record] if all(record.values()) else []

    def _restore_default_tables(self):
        self._apply_water_level_items(self._default_water_items)
        self._apply_metric_items(self.wind_table, self._default_wind_items)
        self._apply_metric_items(self.wave_table, self._default_wave_items)
        self._apply_metric_items(self.current_table, self._default_current_items)

    def _clear_table_values_for_loading(self) -> None:
        if self.water_table is not None:
            for row in range(2, self.water_table.rowCount()):
                self._apply_cell_text(self.water_table, row, 2, "")
        for table in (self.wind_table, self.wave_table, self.current_table):
            if table is None:
                continue
            for row in range(3, table.rowCount()):
                for col in range(2, 7):
                    self._apply_cell_text(table, row, col, "")

    def _set_table_status_message(self, message: str) -> None:
        self._clear_table_values_for_loading()
        if self.water_table is not None:
            self._apply_cell_text(self.water_table, 2, 2, message)
        for table in (self.wind_table, self.wave_table, self.current_table):
            if table is not None:
                self._apply_cell_text(table, 3, 2, message)

    def _set_table_loading_message(self) -> None:
        self._set_table_status_message("数据正在读取中...")

    def _set_save_enabled(self, enabled: bool) -> None:
        if hasattr(self, "btn_save"):
            self.btn_save.setEnabled(enabled)

    def _apply_cell_text(self, table: QTableWidget, row: int, col: int, text: str):
        item = table.item(row, col)
        if item is None:
            self._set_item(table, row, col, text)
            return
        item.setText(text)

    def _apply_water_level_items(self, items: list[dict[str, Any]]):
        if self.water_table is None:
            return
        values = {
            (
                self._normalize_top_value(item.get("group_name", "")),
                self._normalize_top_value(item.get("item_name", "")),
            ): self._format_number_display(item.get("value", ""))
            for item in items
        }

        current_group = ""
        for row in range(2, self.water_table.rowCount()):
            group_text = self._table_text(self.water_table, row, 0)
            item_name = self._table_text(self.water_table, row, 1)
            if group_text:
                current_group = group_text
            if not item_name:
                item_name = group_text
                group_name = ""
            else:
                group_name = current_group
            text = values.get((group_name, item_name), "")
            self._apply_cell_text(self.water_table, row, 2, text)

    def _apply_metric_items(self, table: QTableWidget | None, items: list[dict[str, Any]]):
        if table is None:
            return
        values = {
            (
                self._normalize_top_value(item.get("group_name", "")),
                self._normalize_top_value(item.get("item_name", "")),
                int(item.get("return_period", 0) or 0),
            ): self._format_number_display(item.get("value", ""))
            for item in items
        }
        periods = [int(self._table_text(table, 2, col) or 0) for col in range(2, 7)]

        current_group = ""
        for row in range(3, table.rowCount()):
            group_text = self._table_text(table, row, 0)
            item_name = self._table_text(table, row, 1)
            if group_text:
                current_group = group_text
            if not item_name:
                continue
            for offset, period in enumerate(periods):
                text = values.get((current_group, item_name, period), "")
                self._apply_cell_text(table, row, 2 + offset, text)
    def _load_tables_for_current_profile(self):
        context = self._get_env_context()
        if not (context["branch"] and context["op_company"] and context["oilfield"]):
            self._clear_table_values_for_loading()
            self._set_save_enabled(False)
            return

        if self._apply_cached_tables_for_context(context):
            return

        table_data = self._load_table_data_for_context(context)
        self._apply_table_data(table_data)

    def _load_initial_tables_for_current_profile(self) -> None:
        context = self._get_env_context()
        if not (context["branch"] and context["op_company"] and context["oilfield"]):
            self._clear_table_values_for_loading()
            self._set_save_enabled(False)
            return

        if self._apply_cached_tables_for_context(context):
            return

        self._set_table_loading_message()
        self._set_save_enabled(False)
        self._start_async_current_profile_load()

    def _apply_cached_tables_for_context(self, context: dict[str, str]) -> bool:
        cached_top_data = _get_oilfield_top_data_cache(wait_ms=_OILFIELD_PREHEAT_WAIT_MS)
        cached_table_data = (cached_top_data or {}).get("table_data", {}) or {}
        cache_key = (
            cached_table_data.get("branch", ""),
            cached_table_data.get("op_company", ""),
            cached_table_data.get("oilfield", ""),
        )
        context_key = (context["branch"], context["op_company"], context["oilfield"])
        if cache_key == context_key and cached_table_data.get("profile_id"):
            self._apply_table_data(cached_table_data)
            self._set_save_enabled(True)
            return True
        return False

    def _load_table_data_for_context(self, context: dict[str, str]) -> dict[str, Any]:
        profile_id = get_env_profile_id(
            branch=context["branch"],
            op_company=context["op_company"],
            oilfield=context["oilfield"],
            create_if_missing=False,
        )
        if not profile_id:
            return {
                "branch": context["branch"],
                "op_company": context["op_company"],
                "oilfield": context["oilfield"],
                "profile_id": None,
                "water_items": [],
                "wind_items": [],
                "wave_items": [],
                "current_items": [],
            }

        water_items = load_water_level_items(profile_id)
        wind_items = load_metric_items("oilfield_wind_param_item", profile_id)
        wave_items = load_metric_items("oilfield_wave_param_item", profile_id)
        current_items = load_metric_items("oilfield_current_param_item", profile_id)

        return {
            "branch": context["branch"],
            "op_company": context["op_company"],
            "oilfield": context["oilfield"],
            "profile_id": profile_id,
            "water_items": water_items,
            "wind_items": wind_items,
            "wave_items": wave_items,
            "current_items": current_items,
        }

    def _apply_table_data(self, table_data: dict[str, Any]) -> None:
        self._clear_table_values_for_loading()
        self._apply_water_level_items(list(table_data.get("water_items") or []))
        self._apply_metric_items(self.wind_table, list(table_data.get("wind_items") or []))
        self._apply_metric_items(self.wave_table, list(table_data.get("wave_items") or []))
        self._apply_metric_items(self.current_table, list(table_data.get("current_items") or []))
        self._set_save_enabled(True)

    def _start_async_current_profile_load(self) -> None:
        if self._oilfield_load_thread is not None and self._oilfield_load_thread.isRunning():
            return

        thread = QThread(self)
        worker = _OilfieldEnvPageLoadWorker()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_async_current_profile_loaded)
        worker.failed.connect(self._on_async_current_profile_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_async_current_profile_worker)
        self._oilfield_load_thread = thread
        self._oilfield_load_worker = worker
        thread.start()

    def _clear_async_current_profile_worker(self) -> None:
        self._oilfield_load_thread = None
        self._oilfield_load_worker = None

    def _on_async_current_profile_loaded(self, cached_top_data: object) -> None:
        if not isinstance(cached_top_data, dict):
            return
        if not hasattr(self, "dropdown_bar"):
            return

        self._apply_top_cascade(load_tables=False)
        context = self._get_env_context()
        cached_table_data = cached_top_data.get("table_data", {}) or {}
        cache_key = (
            cached_table_data.get("branch", ""),
            cached_table_data.get("op_company", ""),
            cached_table_data.get("oilfield", ""),
        )
        context_key = (context["branch"], context["op_company"], context["oilfield"])
        if cache_key == context_key and cached_table_data.get("profile_id"):
            self._apply_table_data(cached_table_data)

    def _on_async_current_profile_failed(self, message: str) -> None:
        self._set_table_status_message("数据读取失败，请稍后重试")
        self._set_save_enabled(False)

    def refresh_platform_options(self) -> None:
        clear_oilfield_top_data_cache()
        if hasattr(self, "dropdown_bar"):
            self._start_async_current_profile_load()

    def _collect_water_level_items(self) -> list[dict[str, Any]]:
        if self.water_table is None:
            return []

        items: list[dict[str, Any]] = []
        sort_order = 1
        current_group = ""
        for row in range(2, self.water_table.rowCount()):
            group_text = self._table_text(self.water_table, row, 0)
            item_name = self._table_text(self.water_table, row, 1)
            if group_text:
                current_group = group_text
            if not item_name:
                item_name = group_text
                group_name = ""
            else:
                group_name = current_group
            value_text = self._table_text(self.water_table, row, 2)
            if not (item_name and value_text):
                continue
            items.append({
                "group_name": group_name,
                "item_name": item_name,
                "value": self._parse_decimal(value_text),
                "unit": "m",
                "sort_order": sort_order,
            })
            sort_order += 1
        return items

    def _collect_metric_items(self, table: QTableWidget, default_unit: str) -> list[dict[str, Any]]:
        periods = [self._table_text(table, 2, col) for col in range(2, 7)]
        period_values = [int(period) for period in periods if period]
        if len(period_values) != 5:
            raise ValueError("回归周期表头不完整")

        items: list[dict[str, Any]] = []
        sort_order = 1
        current_group = ""
        for row in range(3, table.rowCount()):
            group_text = self._table_text(table, row, 0)
            item_name = self._table_text(table, row, 1)
            if group_text:
                current_group = group_text
            if not item_name:
                continue
            unit = self._extract_unit_from_item_name(item_name, default_unit)
            for offset, return_period in enumerate(period_values):
                value_text = self._table_text(table, row, 2 + offset)
                if not value_text:
                    continue
                items.append({
                    "group_name": current_group,
                    "item_name": item_name,
                    "return_period": return_period,
                    "value": self._parse_decimal(value_text),
                    "unit": unit,
                    "sort_order": sort_order,
                })
                sort_order += 1
        return items

    def _mock_top_options(self, field: str, default: str) -> List[str]:
        options_map = {
            "分公司": ["湛江分公司", "南海分公司", "东海分公司"],
            "作业公司": ["中海石油(中国)有限公司湛江分公司", "测试作业公司", "珠江作业公司"],
            "油气田": ["WC19-1油田", "WC9-7油田"],
        }
        opts = options_map.get(field, [default])
        return opts if default in opts else [default] + opts

    def _build_top_dropdown_fields(self) -> List[Dict]:
        cached_top_data = _get_oilfield_top_data_cache(wait_ms=_OILFIELD_PREHEAT_WAIT_MS)
        if cached_top_data is not None:
            profile = cached_top_data.get("profile", {}) or {}
            records = list(cached_top_data.get("records", []) or [])
        else:
            platform_defaults = default_platform()
            profile = platform_defaults
            records = self._load_env_top_records()
        defaults = {
            "branch": str(profile.get("branch") or self.TOP_FIELDS[0][1]),
            "op_company": str(profile.get("op_company") or self.TOP_FIELDS[1][1]),
            "oilfield": str(profile.get("oilfield") or self.TOP_FIELDS[2][1]),
        }
        stretch_map = {
            "branch": 0,
            "op_company": 0,
            "oilfield": 0,
        }

        fields: List[Dict] = []
        for key in self.TOP_KEY_ORDER:
            label = self.KEY_TO_FIELD[key]
            fallback = defaults[key]
            opts = self._unique_record_values(records, key)
            if fallback and not opts:
                opts.insert(0, fallback)
            default = fallback

            fields.append({
                "key": key,
                "label": label,
                "options": opts,
                "default": default,
                "stretch": stretch_map.get(key, 1),
                "expand": False,
            })
        return fields
    def _apply_top_cascade(
            self,
            changed_key: Optional[str] = None,
            changed_value: str = "",
            load_tables: bool = True,
    ):
        if not hasattr(self, "dropdown_bar"):
            return
        if self._syncing_top_dropdowns:
            return

        records = self._load_env_top_records()
        values = self.dropdown_bar.get_all_values()
        branch = self._normalize_top_value(changed_value if changed_key == "branch" else values.get("branch", ""))
        op_company = self._normalize_top_value(changed_value if changed_key == "op_company" else values.get("op_company", ""))
        oilfield = self._normalize_top_value(changed_value if changed_key == "oilfield" else values.get("oilfield", ""))

        branch_options = self._unique_record_values(records, "branch")
        branch = self._pick_option(branch_options, branch)

        company_records = [row for row in records if row.get("branch") == branch] if branch else records
        company_options = self._unique_record_values(company_records, "op_company")
        op_company = self._pick_option(company_options, op_company)

        oilfield_records = [
            row for row in company_records
            if (not op_company) or row.get("op_company") == op_company
        ]
        oilfield_options = self._unique_record_values(oilfield_records, "oilfield")
        oilfield = self._pick_option(oilfield_options, oilfield)

        self._syncing_top_dropdowns = True
        try:
            self.dropdown_bar.set_options("branch", branch_options, branch)
            self.dropdown_bar.set_options("op_company", company_options, op_company)
            self.dropdown_bar.set_options("oilfield", oilfield_options, oilfield)
        finally:
            self._syncing_top_dropdowns = False

        if load_tables:
            self._load_tables_for_current_profile()

    def _on_top_key_changed(self, key: str, txt: str):
        if self._syncing_top_dropdowns:
            return
        if key in self.TOP_KEY_ORDER:
            self._apply_top_cascade(changed_key=key, changed_value=txt)
    def build_ui(self):
        self.setStyleSheet("""
                    /* 顶部按钮 */
                    QPushButton#TopActionBtn {
                        background: #f6a24a;
                        border: 1px solid #2f3a4a;
                        border-radius: 3px;
                        padding: 6px 16px;
                        font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
                        font-weight: 400;
                        font-size: 12pt;
                    }
                    QPushButton#TopActionBtn:hover { background: #ffb86b; }
                """)
        # # 椤堕儴绛涢€夋潯
        # top_bar = QFrame()
        # top_bar_layout = QHBoxLayout(top_bar)
        # top_bar_layout.setContentsMargins(0, 0, 0, 0)
        # top_bar_layout.setSpacing(10)
        #
        # cb_division = QComboBox()
        # cb_division.addItems(["娓ゆ睙鍒嗗叕鍙?, "鍗楁捣鍒嗗叕鍙?, "涓滄捣鍒嗗叕鍙?])
        #
        # cb_company = QComboBox()
        # cb_company.addItems(["鏂囨槍娌圭敯缇や綔涓氬叕鍙?, "娴嬭瘯浣滀笟鍏徃"])
        #
        # cb_field = QComboBox()
        # cb_field.addItems(["鏂囨槍19-1娌圭敯", "鏂囨槍X娌圭敯"])
        #
        # btn_save = QPushButton("淇濆瓨")
        #
        # top_bar_layout.addWidget(cb_division)
        # top_bar_layout.addWidget(cb_company)
        # top_bar_layout.addWidget(cb_field)
        # top_bar_layout.addStretch()
        # top_bar_layout.addWidget(btn_save)
        #
        # self.main_layout.addWidget(btn_save)

        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(8)

        # 椤堕儴绛涢€変笌鎿嶄綔鍖?
        top_wrap = QWidget()
        top_layout = QHBoxLayout(top_wrap)
        top_layout.setContentsMargins(10, 8, 10, 0)
        top_layout.setSpacing(12)

        # ---------- 椤堕儴涓嬫媺鏉?----------
        self.dropdown_bar = DropdownBar(self._build_top_dropdown_fields(), parent=self)
        self.dropdown_bar.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.dropdown_bar.valueChanged.connect(self._on_top_key_changed)
        self._apply_top_cascade(load_tables=False)

        top_layout.addWidget(self.dropdown_bar, 0, Qt.AlignLeft | Qt.AlignVCenter)

        self.btn_save = QPushButton("保存")
        self.btn_save.setObjectName("TopActionBtn")
        self.btn_save.setMinimumWidth(150)
        self.btn_save.setMinimumHeight(34)
        self.btn_save.setFont(self._songti_small_four_font())
        self.btn_save.clicked.connect(self._on_save)
        self.btn_save.setEnabled(False)

        top_layout.addStretch(1)
        top_layout.addWidget(self.btn_save, 0, Qt.AlignRight | Qt.AlignVCenter)

        self.main_layout.addWidget(top_wrap)

        # 閫夐」鍗℃寜閽潯
        tab_bar = QFrame()
        tab_layout = QHBoxLayout(tab_bar)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(0)

        def create_tab_button(text: str) -> QPushButton:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setMinimumHeight(42)
            btn.setStyleSheet(f"""
                QPushButton {{
                    border: 1px solid #888;
                    border-bottom: none;
                    padding: 7px 20px;
                    background-color: #efefef;
                    font-family: {SONGTI_FONT_FALLBACK};
                    font-size: 12pt;
                    font-weight: 600;
                }}
                QPushButton:checked {{
                    background-color: #d6f0d0;
                    font-weight: bold;
                }}
            """)
            return btn

        btn_water = create_tab_button("水深水位")
        btn_wind = create_tab_button("风参数")
        btn_wave = create_tab_button("波浪参数")
        btn_current = create_tab_button("海流参数")

        self.tab_buttons = [btn_water, btn_wind, btn_wave, btn_current]

        for btn in self.tab_buttons:
            tab_layout.addWidget(btn)
        tab_layout.addStretch()

        self.main_layout.addWidget(tab_bar)

        # 閫夐」鍗″唴瀹瑰尯鍩?
        self.tab_pages = QStackedWidget()

        water_page = self.build_water_level_page()
        wind_page = self.build_wind_param_page()
        wave_page = self.build_wave_param_page()
        current_page = self.build_current_param_page()

        self.tab_pages.addWidget(water_page)
        self.tab_pages.addWidget(wind_page)
        self.tab_pages.addWidget(wave_page)
        self.tab_pages.addWidget(current_page)

        self.main_layout.addWidget(self.tab_pages)

        for index, btn in enumerate(self.tab_buttons):
            btn.clicked.connect(lambda checked, i=index: self.switch_tab(i))

        self.switch_tab(0)
        self._default_water_items = self._collect_water_level_items()
        self._default_wind_items = self._collect_metric_items(self.wind_table, default_unit="m/s")
        self._default_wave_items = self._collect_metric_items(self.wave_table, default_unit="m")
        self._default_current_items = self._collect_metric_items(self.current_table, default_unit="m/s")
        self._load_initial_tables_for_current_profile()

    # ---------- 灏忓伐鍏凤細璁剧疆鍗曞厓鏍?----------
    def _set_item(self, table: QTableWidget, r: int, c: int, text: str,
                  align=Qt.AlignCenter, bold: bool = False, editable: bool = False):
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(align)
        font = table.font()
        font.setBold(bold)
        item.setFont(font)
        flags = item.flags()
        if editable:
            flags |= Qt.ItemIsEditable | Qt.ItemIsSelectable
        else:
            flags &= ~Qt.ItemIsEditable
        item.setFlags(flags)
        table.setItem(r, c, item)

    def _finalize_table_style(self, table: QTableWidget):
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setVisible(False)  # 鉁?鍘绘帀椤堕儴 1..n
        table.setCornerButtonEnabled(False)
        table.setFont(self._songti_small_four_font())

        table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
            | QAbstractItemView.AnyKeyPressed
        )
        table.setSelectionBehavior(QAbstractItemView.SelectItems)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        table.setShowGrid(True)

        table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setStyleSheet("""
            QTableWidget {
                gridline-color: #d9d9d9;
                background-color: #ffffff;
                font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
                font-size: 12pt;
            }
            QTableWidget::item {
                border: 1px solid #ffffff;
                padding: 8px 12px;
            }
            QTableWidget::item:selected {
                background-color: #dbe9ff;
                color: #000000;
            }
            QTableWidget::item:focus {
                outline: none;
            }
        """)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def _install_env_table_clipboard(
        self,
        table: QTableWidget,
        *,
        data_start_row: int,
        editable_cols: set[int],
    ) -> None:
        controller = TableClipboardController(
            table,
            can_paste_cell=lambda row, col, target=table, start=data_start_row, cols=editable_cols:
                self._can_paste_env_table_cell(target, row, col, start, cols),
            on_paste_rows_ignored=lambda count, target=table:
                self._show_env_table_tip(target, f"粘贴内容超出现有数据区，已忽略 {count} 行。"),
            on_paste_cells_skipped=lambda count, target=table:
                self._show_env_table_tip(target, f"部分单元格不可粘贴，已跳过 {count} 个单元格。"),
        )
        table._table_clipboard = controller
        self._table_clipboard_controllers.append(controller)

    def _can_paste_env_table_cell(
        self,
        table: QTableWidget,
        row: int,
        col: int,
        data_start_row: int,
        editable_cols: set[int],
    ) -> bool:
        if not (data_start_row <= row < table.rowCount()):
            return False
        if col not in editable_cols:
            return False
        if table.cellWidget(row, col) is not None:
            return False
        item = table.item(row, col)
        if item is None:
            return True
        return bool(item.flags() & Qt.ItemIsEditable)

    def _show_env_table_tip(self, table: QTableWidget, message: str) -> None:
        rect = table.viewport().rect()
        pos = table.viewport().mapToGlobal(rect.center())
        QToolTip.showText(pos, message, table, rect, 2500)

    def _fit_table_height(self, table: QTableWidget):
        # 鍥哄畾楂樺害锛氬垰濂藉绾虫墍鏈夎锛岄伩鍏嶆粴鍔ㄦ潯
        total_h = table.frameWidth() * 2 + 2
        for r in range(table.rowCount()):
            total_h += table.rowHeight(r)
        table.setFixedHeight(total_h)

    def _expand_table_width(self, table: QTableWidget) -> None:
        table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _apply_table_width_scheme_a(
            self,
            table: QTableWidget,
            group_col_w: int = 190,  # 绗?鍒楋細鍒嗙粍锛堜富鏋佸€?xxx鏉′欢涓嬫瀬鍊硷級
            elem_col_w: int = 320,  # 绗?鍒楋細鍏冪礌锛堣〃灞?涓眰/鏈変箟娉㈤珮...锛?
            num_min_w: int = 76  # 鏁板€煎垪鏈€灏忓搴︼紙绐楀彛寰堢獎鏃堕槻姝㈠お鎸わ級
    ):
        """
        鏂规A锛氬浐瀹氬乏涓ゅ垪瀹藉害锛屾暟鍊煎垪鍧囧垎濉弧锛堥€傜敤浜?7 鍒楃粨鏋勶細0=缁勫埆, 1=鍏冪礌, 2~6=鏁板€煎垪锛?
        """
        header = table.horizontalHeader()

        # 0銆?鍒楀浐瀹氾細閬垮厤琚唴瀹规拺姝?
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        table.setColumnWidth(0, group_col_w)
        table.setColumnWidth(1, elem_col_w)

        # 2~6鍒楀潎鍒嗛摵婊″墿浣欏搴?
        for c in range(2, 7):
            header.setSectionResizeMode(c, QHeaderView.Stretch)

        self._expand_table_width(table)

    # ----------------- 瀛愰〉鏋勫缓 ----------------- #
    def build_water_level_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignTop)

        table = QTableWidget(14, 3, page)
        self.water_table = table
        self._finalize_table_style(table)
        table.setStyleSheet(table.styleSheet() + """
            QTableWidget {
                border: 1px solid #cfd8e3;
            }
        """)

        for r in range(table.rowCount()):
            table.setRowHeight(r, 36)
        table.setRowHeight(0, 42)
        table.setRowHeight(1, 38)

        table.setSpan(0, 0, 2, 2)
        self._set_item(table, 0, 0, "元素", bold=True)
        self._set_item(table, 0, 2, "相对海图基准面", bold=True)
        self._set_item(table, 1, 2, "m", bold=True)

        base_rows = [
            ("海图基准面 (CD)", ""),
            ("最高天文潮 (HAT)", ""),
            ("最低天文潮 (LAT)", ""),
            ("平均海平面 (MSL)", ""),
        ]
        for i, (elem, val) in enumerate(base_rows):
            rr = 2 + i
            table.setSpan(rr, 0, 1, 2)
            self._set_item(table, rr, 0, elem, align=Qt.AlignCenter)
            self._set_item(table, rr, 2, val, editable=True)
            self._set_item(table, rr, 1, "")

        table.setSpan(6, 0, 4, 1)
        self._set_item(table, 6, 0, "最高水位")
        high_rows = [
            ("1年回归周期", ""),
            ("50年回归周期", ""),
            ("100年回归周期", ""),
            ("1000年回归周期", ""),
        ]
        for i, (elem, val) in enumerate(high_rows):
            rr = 6 + i
            self._set_item(table, rr, 1, elem)
            self._set_item(table, rr, 2, val, editable=True)

        table.setSpan(10, 0, 4, 1)
        self._set_item(table, 10, 0, "最低水位")
        low_rows = [
            ("1年回归周期", ""),
            ("50年回归周期", ""),
            ("100年回归周期", ""),
            ("1000年回归周期", ""),
        ]
        for i, (elem, val) in enumerate(low_rows):
            rr = 10 + i
            self._set_item(table, rr, 1, elem)
            self._set_item(table, rr, 2, val, editable=True)

        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        table.setColumnWidth(0, 190)
        table.setColumnWidth(1, 220)

        self._fit_table_height(table)
        self._expand_table_width(table)
        self._install_env_table_clipboard(table, data_start_row=2, editable_cols={2})
        layout.addWidget(table, 0, Qt.AlignTop)
        return page
    def build_wind_param_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        frame = QFrame()
        frame.setStyleSheet("QFrame { border: 1px solid #888; }")
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        table = QTableWidget(15, 7, frame)
        self.wind_table = table
        self._finalize_table_style(table)
        for r in range(table.rowCount()):
            table.setRowHeight(r, 34)
        table.setRowHeight(0, 36)
        table.setRowHeight(1, 34)
        table.setRowHeight(2, 34)

        table.setSpan(0, 0, 1, 7)
        self._set_item(table, 0, 0, "风速@10m (m/s)", bold=True)
        table.setSpan(1, 0, 2, 2)
        self._set_item(table, 1, 0, "元素", bold=True)
        table.setSpan(1, 2, 1, 5)
        self._set_item(table, 1, 2, "回归周期 (年)", bold=True)

        periods = ["1", "10", "25", "50", "100"]
        for i, p in enumerate(periods):
            self._set_item(table, 2, 2 + i, p, bold=True)

        groups = [
            ("主极值", [
                ("1 h", ["", "", "", "", ""]),
                ("10 min", ["", "", "", "", ""]),
                ("1 min", ["", "", "", "", ""]),
                ("3 s", ["", "", "", "", ""]),
            ]),
            ("波浪主极值下条件极值", [
                ("1 h", ["", "", "", "", ""]),
                ("10 min", ["", "", "", "", ""]),
                ("1 min", ["", "", "", "", ""]),
                ("3 s", ["", "", "", "", ""]),
            ]),
            ("海流主极值下条件极值", [
                ("1 h", ["", "", "", "", ""]),
                ("10 min", ["", "", "", "", ""]),
                ("1 min", ["", "", "", "", ""]),
                ("3 s", ["", "", "", "", ""]),
            ]),
        ]
        r0 = 3
        for group_name, rows in groups:
            table.setSpan(r0, 0, len(rows), 1)
            self._set_item(table, r0, 0, group_name)
            for offset, (duration, values) in enumerate(rows):
                row_index = r0 + offset
                self._set_item(table, row_index, 1, duration)
                for value_index, value in enumerate(values):
                    self._set_item(table, row_index, 2 + value_index, value, editable=True)
            r0 += len(rows)

        self._apply_table_width_scheme_a(table, group_col_w=190, elem_col_w=260, num_min_w=76)
        self._fit_table_height(table)
        self._install_env_table_clipboard(table, data_start_row=3, editable_cols=set(range(2, 7)))
        layout.setAlignment(Qt.AlignTop)
        frame_layout.setAlignment(Qt.AlignTop)
        frame_layout.addWidget(table)
        layout.addWidget(frame, 0, Qt.AlignTop)
        return page

    def build_wave_param_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        frame = QFrame()
        frame.setStyleSheet("QFrame { border: 1px solid #888; }")
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        table = QTableWidget(19, 7, frame)
        self.wave_table = table
        self._finalize_table_style(table)
        for r in range(table.rowCount()):
            table.setRowHeight(r, 34)
        table.setRowHeight(0, 36)

        table.setSpan(0, 0, 1, 7)
        self._set_item(table, 0, 0, "波浪参数", bold=True)
        table.setSpan(1, 0, 2, 2)
        self._set_item(table, 1, 0, "元素", bold=True)
        table.setSpan(1, 2, 1, 5)
        self._set_item(table, 1, 2, "回归周期 (年)", bold=True)

        periods = ["1", "10", "25", "50", "100"]
        for i, p in enumerate(periods):
            self._set_item(table, 2, 2 + i, p, bold=True)

        groups = [
            ("主极值", [
                ("有义波高 Hs(m)", ["", "", "", "", ""]),
                ("波峰高度 Crest(m)", ["", "", "", "", ""]),
                ("最大波高 Hmax(m)", ["", "", "", "", ""]),
                ("跨零周期 Tz(s)", ["", "", "", "", ""]),
                ("谱峰周期 Tp(s)", ["", "", "", "", ""]),
                ("平均周期 Tm(s)", ["", "", "", "", ""]),
            ]),
            ("风主极值条件下极值", [
                ("有义波高 Hs(m)", ["", "", "", "", ""]),
                ("最大波高 Hmax(m)", ["", "", "", "", ""]),
                ("跨零周期 Tz(s)", ["", "", "", "", ""]),
                ("谱峰周期 Tp(s)", ["", "", "", "", ""]),
                ("平均周期 Tm(s)", ["", "", "", "", ""]),
            ]),
            ("海流主极值条件下极值", [
                ("有义波高 Hs(m)", ["", "", "", "", ""]),
                ("最大波高 Hmax(m)", ["", "", "", "", ""]),
                ("跨零周期 Tz(s)", ["", "", "", "", ""]),
                ("谱峰周期 Tp(s)", ["", "", "", "", ""]),
                ("平均周期 Tm(s)", ["", "", "", "", ""]),
            ]),
        ]
        r0 = 3
        for group_name, rows in groups:
            table.setSpan(r0, 0, len(rows), 1)
            self._set_item(table, r0, 0, group_name)
            for offset, (element, values) in enumerate(rows):
                row_index = r0 + offset
                self._set_item(table, row_index, 1, element, align=Qt.AlignLeft | Qt.AlignVCenter)
                for value_index, value in enumerate(values):
                    self._set_item(table, row_index, 2 + value_index, value, editable=True)
            r0 += len(rows)

        header = table.horizontalHeader()
        self._apply_table_width_scheme_a(table, group_col_w=200, elem_col_w=320, num_min_w=76)
        table.setColumnWidth(1, 260)
        for c in range(2, 7):
            header.setSectionResizeMode(c, QHeaderView.Stretch)
        self._fit_table_height(table)
        self._install_env_table_clipboard(table, data_start_row=3, editable_cols=set(range(2, 7)))
        layout.setAlignment(Qt.AlignTop)
        frame_layout.setAlignment(Qt.AlignTop)
        frame_layout.addWidget(table)
        layout.addWidget(frame, 0, Qt.AlignTop)
        return page

    def build_current_param_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        frame = QFrame()
        frame.setStyleSheet("QFrame { border: 1px solid #888; }")
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        table = QTableWidget(15, 7, frame)
        self.current_table = table
        self._finalize_table_style(table)
        for r in range(table.rowCount()):
            table.setRowHeight(r, 34)
        table.setRowHeight(0, 36)

        table.setSpan(0, 0, 1, 7)
        self._set_item(table, 0, 0, "海流速度 (m/s)", bold=True)
        table.setSpan(1, 0, 2, 2)
        self._set_item(table, 1, 0, "元素", bold=True)
        table.setSpan(1, 2, 1, 5)
        self._set_item(table, 1, 2, "回归周期 (年)", bold=True)

        periods = ["1", "10", "25", "50", "100"]
        for i, p in enumerate(periods):
            self._set_item(table, 2, 2 + i, p, bold=True)

        groups = [
            ("主极值", [
                ("表层 (0.1倍水深)", ["", "", "", "", ""]),
                ("中层 (0.5倍水深)", ["", "", "", "", ""]),
                ("底层 (0.9倍水深)", ["", "", "", "", ""]),
                ("+1m@ASB", ["", "", "", "", ""]),
            ]),
            ("风主极值条件下极值", [
                ("表层 (0.1倍水深)", ["", "", "", "", ""]),
                ("中层 (0.5倍水深)", ["", "", "", "", ""]),
                ("底层 (0.9倍水深)", ["", "", "", "", ""]),
                ("+1m@ASB", ["", "", "", "", ""]),
            ]),
            ("波浪主极值条件下极值", [
                ("表层 (0.1倍水深)", ["", "", "", "", ""]),
                ("中层 (0.5倍水深)", ["", "", "", "", ""]),
                ("底层 (0.9倍水深)", ["", "", "", "", ""]),
                ("+1m@ASB", ["", "", "", "", ""]),
            ]),
        ]
        r0 = 3
        for group_name, rows in groups:
            table.setSpan(r0, 0, len(rows), 1)
            self._set_item(table, r0, 0, group_name)
            for offset, (layer, values) in enumerate(rows):
                row_index = r0 + offset
                self._set_item(table, row_index, 1, layer, align=Qt.AlignLeft | Qt.AlignVCenter)
                for value_index, value in enumerate(values):
                    self._set_item(table, row_index, 2 + value_index, value, editable=True)
            r0 += len(rows)

        self._apply_table_width_scheme_a(table, group_col_w=210, elem_col_w=320, num_min_w=76)
        self._fit_table_height(table)
        self._install_env_table_clipboard(table, data_start_row=3, editable_cols=set(range(2, 7)))
        layout.setAlignment(Qt.AlignTop)
        frame_layout.setAlignment(Qt.AlignTop)
        frame_layout.addWidget(table)
        layout.addWidget(frame, 0, Qt.AlignTop)
        return page
    def _beautify_table_width_7cols(
            self,
            table: QTableWidget,
            group_col_w: int = 180,  # 绗?鍒楋細缁勫埆
            elem_col_w: int = 320,  # 绗?鍒楋細鍏冪礌/鍒嗗眰
            min_num_col_w: int = 72  # 鏁板€煎垪鏈€灏忓搴︼紙闃叉澶尋锛?
    ):
        header = table.horizontalHeader()

        # 0銆?鍒楀浐瀹氬搴︼細瑙嗚鏇寸ǔ
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        table.setColumnWidth(0, group_col_w)
        table.setColumnWidth(1, elem_col_w)

        # 2~6 鏁板€煎垪锛氬潎鍒嗗～婊?
        for c in range(2, 7):
            header.setSectionResizeMode(c, QHeaderView.Stretch)

        # 鍙€夛細淇濊瘉鏁板€煎垪涓嶄細灏忓埌闅剧湅
        table.setStyleSheet(table.styleSheet() + f"""
            QTableWidget::item {{ padding: 6px 10px; }}
        """)
        for c in range(2, 7):
            table.setColumnWidth(c, max(table.columnWidth(c), min_num_col_w))

    # ----------------- 閫夐」鍗″垏鎹㈤€昏緫 ----------------- #
    def switch_tab(self, index: int):
        """
        鍒囨崲椤堕儴閫夐」鍗★紝鍚屾椂璋冩暣鎸夐挳閫変腑鐘舵€併€?
        """
        for i, btn in enumerate(self.tab_buttons):
            btn.setChecked(i == index)
        self.tab_pages.setCurrentIndex(index)

    # ----------------- 鈥滀繚瀛樷€濇寜閽€昏緫 ----------------- #
    def _on_save(self):
        try:
            context = self._get_env_context()
            if not (context["branch"] and context["op_company"] and context["oilfield"]):
                raise ValueError("facility_profile 中缺少分公司/作业公司/油气田信息，无法保存海洋环境数据。")

            profile_id = get_env_profile_id(
                branch=context["branch"],
                op_company=context["op_company"],
                oilfield=context["oilfield"],
                create_if_missing=True,
            )
            if not profile_id:
                raise ValueError("未能创建或获取油气田环境主表记录。")

            water_items = self._collect_water_level_items()
            wind_items = self._collect_metric_items(self.wind_table, default_unit="m/s")
            wave_items = self._collect_metric_items(self.wave_table, default_unit="m")
            current_items = self._collect_metric_items(self.current_table, default_unit="m/s")

            replace_water_level_items(profile_id, water_items)
            replace_metric_items("oilfield_wind_param_item", profile_id, wind_items)
            (replace_metric_items
             ("oilfield_wave_param_item", profile_id, wave_items))
            replace_metric_items("oilfield_current_param_item", profile_id, current_items)
            clear_oilfield_top_data_cache()

            QMessageBox.information(
                self,
                "保存成功",
                (
                    f"已保存油气田“{context['oilfield']}”海洋环境数据。\n"
                    f"水深水位 {len(water_items)} 条，风参数 {len(wind_items)} 条，"
                    f"波浪参数 {len(wave_items)} 条，海流参数 {len(current_items)} 条。"
                ),
            )
        except Exception as exc:
            QMessageBox.critical(self, "保存失败", f"海洋环境数据保存失败：\n{exc}")



