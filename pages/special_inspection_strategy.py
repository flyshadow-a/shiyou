# -*- coding: utf-8 -*-
# pages/special_inspection_strategy.py


import os
import csv
from typing import List, Tuple, Dict, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QPen, QColor, QBrush
from PyQt5.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QPushButton, QScrollArea, QSizePolicy, QLabel,

    QDialog, QAbstractItemView, QMessageBox
)
from PyQt5.QtWidgets import QSlider
from core.app_paths import first_existing_path
from core.base_page import BasePage
from core.dropdown_bar import DropdownBar
from pages.file_management_platforms import FILE_MANAGEMENT_PLATFORMS, default_platform, find_platform, sync_platform_dropdowns
from pages.read_table_xls import ReadTableXls
from pages.special_strategy_history_dialog import SpecialStrategyHistoryDialog as SpecialStrategyHistoryDialogView
from services.special_strategy_services import (

    NodeYearLabelMapper,
    SpecialStrategyResultService,
    SpecialStrategySummaryBuilder,
)


from pages.sacs_elevation_risk_view import SacsElevationRiskView
from pages.platform_strength_page import PlatformStrengthPage

NODE_YEAR_DISPLAY_LABELS = ["当前", "+5年", "+10年", "+15年", "+20年", "+25年"]
NODE_YEAR_CONTEXT_MAP = {
    "当前": "当前",
    "+5年": "第5年",
    "+10年": "第10年",
    "+15年": "第15年",
    "+20年": "第20年",
    "+25年": "第25年",
}


class SimpleTowerDiagram(QWidget):
    """右侧黑底“塔架示意图”占位控件（不依赖图片）。"""
    def __init__(self, variant: int = 0, parent=None):
        super().__init__(parent)
        self.variant = variant
        self.setMinimumSize(260, 520)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def paintEvent(self, _evt):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), QColor(0, 0, 0))

        w, h = self.width(), self.height()
        margin = 30
        x1, x2 = margin, w - margin
        y_top, y_bot = margin, h - margin

        pen_line = QPen(QColor(0, 255, 0), 2)
        p.setPen(pen_line)

        p.drawLine(x1, y_top, x1, y_bot)
        p.drawLine(x2, y_top, x2, y_bot)

        for t in [0.18, 0.35, 0.52, 0.70, 0.86]:
            y = int(y_top + (y_bot - y_top) * t)
            p.drawLine(x1, y, x2, y)

        for t in [0.18, 0.35, 0.52, 0.70]:
            yA = int(y_top + (y_bot - y_top) * t)
            yB = int(y_top + (y_bot - y_top) * (t + 0.17))
            p.drawLine(x1, yA, x2, yB)
            p.drawLine(x2, yA, x1, yB)

        if self.variant == 0:
            pts = [
                (0.30, 0.22, QColor(0, 140, 255)),
                (0.70, 0.36, QColor(0, 200, 120)),
                (0.62, 0.66, QColor(255, 210, 0)),
            ]
        else:
            pts = [
                (0.72, 0.26, QColor(0, 140, 255)),
                (0.30, 0.52, QColor(0, 200, 120)),
                (0.78, 0.58, QColor(255, 210, 0)),
            ]

        for fx, fy, c in pts:
            cx = int(x1 + (x2 - x1) * fx)
            cy = int(y_top + (y_bot - y_top) * fy)
            r = 14
            p.setPen(QPen(Qt.NoPen))
            p.setBrush(QBrush(c))
            p.drawEllipse(cx - r, cy - r, 2 * r, 2 * r)

        p.end()


class SpecialStrategyHistoryDialog(QDialog):
    def __init__(self, facility_code: str, parent=None):
        super().__init__(parent)
        self.facility_code = facility_code
        self.selected_run_id: int | None = None
        self.selected_action = "summary"
        self._result_service = SpecialStrategyResultService()
        self.setWindowTitle(f"{facility_code}特检策略历史记录")
        self.resize(760, 420)
        self._build_ui()
        self._load_rows()

    def _build_ui(self) -> None:
        self.setStyleSheet("""
            QDialog {
                background: #e6eef7;
                font-family: "SimSun", "NSimSun", "瀹嬩綋", "Microsoft YaHei UI", "Microsoft YaHei";
                font-size: 12pt;
            }
            QTableWidget {
                background: #ffffff;
                gridline-color: #d0d0d0;
                border: 1px solid #d0d0d0;
            }
            QHeaderView::section {
                background: #f3f6fb;
                color: #000000;
                border: 1px solid #e6e6e6;
                padding: 4px 6px;
                font-weight: normal;
            }
            QPushButton {
                background: #efefef;
                border: 1px solid #666;
                min-height: 32px;
                padding: 4px 12px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        hint = QLabel(f"当前仅显示平台 {self.facility_code} 的历史计算记录")
        layout.addWidget(hint)

        self.table = QTableWidget(0, 5, self)
        self.table.setHorizontalHeaderLabels(["记录ID", "平台编码", "计算时间", "报告时间", "状态"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.itemDoubleClicked.connect(self._accept_result_view)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        self.btn_refresh = QPushButton("刷新")
        self.btn_load_summary = QPushButton("加载到主页")
        self.btn_view_result = QPushButton("查看结果")
        self.btn_close = QPushButton("关闭")

        self.btn_refresh.clicked.connect(self._load_rows)
        self.btn_load_summary.clicked.connect(self._accept_summary_view)
        self.btn_view_result.clicked.connect(self._accept_result_view)
        self.btn_close.clicked.connect(self.reject)

        for button in (self.btn_refresh, self.btn_load_summary, self.btn_view_result, self.btn_close):
            btn_row.addWidget(button)
        layout.addLayout(btn_row)

    def _load_rows(self) -> None:
        rows = self._result_service.list_history(self.facility_code, limit=100)
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                str(row.run_id),
                row.facility_code,
                row.updated_at,
                row.report_generated_at,
                row.status,
            ]
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignCenter)
                if col_index == 0:
                    item.setData(Qt.UserRole, row.run_id)
                self.table.setItem(row_index, col_index, item)
        if rows:
            self.table.selectRow(0)

    @staticmethod
    def _display_time(value: object) -> str:
        if value is None:
            return ""
        if hasattr(value, "strftime"):
            try:
                return value.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                return str(value)
        return str(value)

    def _selected_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        value = item.data(Qt.UserRole)
        try:
            return int(value)
        except Exception:
            return None

    def _accept_summary_view(self, *_args) -> None:
        run_id = self._selected_id()
        if run_id is None:
            QMessageBox.information(self, "提示", "请先选择一条历史记录。")
            return
        self.selected_run_id = run_id
        self.selected_action = "summary"
        self.accept()

    def _accept_result_view(self, *_args) -> None:
        run_id = self._selected_id()
        if run_id is None:
            QMessageBox.information(self, "提示", "请先选择一条历史记录。")
            return
        self.selected_run_id = run_id
        self.selected_action = "result"
        self.accept()


class SpecialInspectionStrategy(BasePage):
    """
    “特检策略”页面（顶部继承 DropdownBar 设计）
    """

    TOP_FIELDS: List[Tuple[str, str]] = [
        ("分公司", "湛江分公司"),
        ("作业公司", "文昌油田群作业公司"),
        ("油气田", "文昌19-1油田"),
        ("设施编码", "WC19-1WHPC"),
        ("设施名称", "文昌19-1WHPC井口平台"),
    ]

    KEY_TO_FIELD: Dict[str, str] = {
        "branch": "分公司",
        "op_company": "作业公司",
        "oilfield": "油气田",
        "facility_code": "设施编码",
        "facility_name": "设施名称",
    }

    def __init__(self, main_window, parent=None):
        if parent is None:
            parent = main_window
        super().__init__("", parent)
        self.main_window = main_window

        self.data_dir = first_existing_path("data")
        self._result_service = SpecialStrategyResultService()
        self._year_mapper = NodeYearLabelMapper()
        self._summary_builder = SpecialStrategySummaryBuilder(self._year_mapper)
        self.current_year = "当前"
        self._active_run_id: int | None = None
        self._active_facility_code = ""
        self.current_year = self._year_mapper.default_display_label()

        self._excel_provider = ReadTableXls()
        self._excel_loaded = False
        try:
            self._excel_provider.load()
            self._excel_loaded = True
        except Exception:
            self._excel_loaded = False

        self._top_records: List[Dict[str, str]] = self._load_top_records_from_excel()
        self._top_cascade_enabled: bool = False
        self._top_cascade_lock: bool = False

        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(8)

        self._build_ui()
        self._sync_platform_ui()

    # ---------------- 顶部下拉（样表驱动 + 级联） ----------------
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

            if not any(rec.get(k) for k in ("分公司", "作业公司", "油气田", "设施编码", "设施名称")):
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

    def _mock_top_options(self, field: str, default: str) -> List[str]:
        options_map = {
            "分公司": ["湛江分公司", "深圳分公司", "上海分公司", "海南分公司", "天津分公司"],
            "作业公司": ["文昌油田群作业公司", "涠洲作业公司", "珠江作业公司", "渤海作业公司"],
            "油气田": ["文昌19-1油田", "文昌19-2油田", "涠洲油田", "珠江口油田"],
            "设施编码": ["WC19-1WHPC", "WC19-2WHPC", "WC9-7DPP", "WC19-1DPPA"],
            "设施名称": ["文昌19-1WHPC井口平台", "文昌19-2WHPC井口平台", "WC9-7DPP井口平台"],
        }
        opts = options_map.get(field, [default])
        return opts if default in opts else [default] + opts

    def _build_top_dropdown_fields(self) -> List[Dict]:
        defaults = {
            "branch": "湛江分公司",
            "op_company": "文昌油田群作业公司",
            "oilfield": "文昌19-1油田",
            "facility_code": "WC19-1WHPC",
            "facility_name": "文昌19-1WHPC井口平台",
            "inspect_seq": "0",
            "inspect_time": "2008-06-26",
        }
        stretch_map = {
            "branch": 1,
            "op_company": 2,
            "oilfield": 2,
            "facility_code": 2,
            "facility_name": 3,
            "inspect_seq": 1,
            "inspect_time": 2,
        }

        fields: List[Dict] = []
        dynamic_keys = ["branch", "op_company", "oilfield", "facility_code", "facility_name"]
        for key in dynamic_keys:
            label = self.KEY_TO_FIELD[key]
            fallback = defaults[key]
            if self._top_cascade_enabled:
                opts = self._unique_record_values(self._top_records, label)
                default = opts[0] if opts else fallback
            else:
                opts = self._mock_top_options(label, fallback)
                default = fallback
            fields.append({
                "key": key,
                "label": label,
                "options": opts,
                "default": default,
                "stretch": stretch_map.get(key, 1),
            })

        fields.extend([
            {
                "key": "inspect_seq",
                "label": "检测序号",
                "options": ["0", "1", "2", "3"],
                "default": defaults["inspect_seq"],
                "stretch": stretch_map["inspect_seq"],
            },
            {
                "key": "inspect_time",
                "label": "检测时间",
                "options": ["2008-06-26", "2008-07-12", "2008-08-21"],
                "default": defaults["inspect_time"],
                "stretch": stretch_map["inspect_time"],
            },
        ])
        return fields

    def _apply_top_cascade(self, changed_key: Optional[str] = None, changed_value: str = ""):
        if (not self._top_cascade_enabled) or (not hasattr(self, "dropdown_bar")):
            return

        records = self._top_records
        keys = ["branch", "op_company", "oilfield", "facility_code", "facility_name"]
        current = {k: self.dropdown_bar.get_value(k) for k in keys}
        if changed_key:
            current[changed_key] = self._normalize_top_value(changed_value)

        reset_downstream = {
            "branch": {"op_company", "oilfield", "facility_code", "facility_name"},
            "op_company": {"oilfield", "facility_code", "facility_name"},
            "oilfield": {"facility_code", "facility_name"},
            "facility_code": {"facility_name"},
            "facility_name": {"facility_code"},
        }
        reset = reset_downstream.get(changed_key or "", set())

        branches = self._unique_record_values(records, "分公司")
        branch = self._pick_option(branches, current.get("branch", ""))
        branch_rows = [r for r in records if r.get("分公司", "") == branch] if branch else list(records)

        op_opts = self._unique_record_values(branch_rows, "作业公司")
        op_pref = "" if "op_company" in reset else current.get("op_company", "")
        op = self._pick_option(op_opts, op_pref)
        op_rows = [r for r in branch_rows if r.get("作业公司", "") == op] if op else list(branch_rows)

        oil_opts = self._unique_record_values(op_rows, "油气田")
        oil_pref = "" if "oilfield" in reset else current.get("oilfield", "")
        oilfield = self._pick_option(oil_opts, oil_pref)
        oil_rows = [r for r in op_rows if r.get("油气田", "") == oilfield] if oilfield else list(op_rows)

        code_opts = self._unique_record_values(oil_rows, "设施编码")
        name_opts = self._unique_record_values(oil_rows, "设施名称")

        selected_row: Optional[Dict[str, str]] = None
        if changed_key == "facility_name":
            name_pref = current.get("facility_name", "")
            selected_name = self._pick_option(name_opts, name_pref)
            for rec in oil_rows:
                if rec.get("设施名称", "") == selected_name:
                    selected_row = rec
                    break
        else:
            code_pref = "" if "facility_code" in reset else current.get("facility_code", "")
            selected_code = self._pick_option(code_opts, code_pref)
            for rec in oil_rows:
                if rec.get("设施编码", "") == selected_code:
                    selected_row = rec
                    break

        if selected_row is None and oil_rows:
            selected_row = oil_rows[0]

        selected_code = self._normalize_top_value((selected_row or {}).get("设施编码", ""))
        selected_name = self._normalize_top_value((selected_row or {}).get("设施名称", ""))

        self._top_cascade_lock = True
        try:
            self.dropdown_bar.set_options("branch", branches, branch)
            self.dropdown_bar.set_options("op_company", op_opts, op)
            self.dropdown_bar.set_options("oilfield", oil_opts, oilfield)
            self.dropdown_bar.set_options("facility_code", code_opts, selected_code)
            self.dropdown_bar.set_options("facility_name", name_opts, selected_name)
        finally:
            self._top_cascade_lock = False

    def _on_top_key_changed(self, key: str, txt: str):
        if key in {"branch", "op_company", "oilfield", "facility_code", "facility_name"}:
            if self._top_cascade_enabled:
                if self._top_cascade_lock:
                    return
                self._apply_top_cascade(changed_key=key, changed_value=txt)
            self._sync_platform_ui(changed_key=key)

    # ---------------- UI ----------------
    def _build_ui(self):
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(8)

        self.main_layout.addWidget(self._build_top_bar_dropdown_style(), 0)

        bottom = QFrame()
        bottom_lay = QHBoxLayout(bottom)
        bottom_lay.setContentsMargins(0, 0, 0, 0)
        bottom_lay.setSpacing(10)

        left = self._build_left_tables()
        right = self._build_right_diagrams()

        # 右侧再给大一点，但不要夸张
        bottom_lay.addWidget(left, 6)
        bottom_lay.addWidget(right, 5)

        self.main_layout.addWidget(bottom, 1)

    # ---------------- 顶部：DropdownBar + 补充操作栏（同风格） ----------------
    def _build_top_bar_dropdown_style(self) -> QWidget:
        wrap = QFrame()
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # 左侧：样表驱动 + 级联下拉
        self.dropdown_bar = DropdownBar(self._build_top_dropdown_fields(), parent=self)
        self.dropdown_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.dropdown_bar.valueChanged.connect(self._on_top_key_changed)
        if self._top_cascade_enabled:
            self._apply_top_cascade()

        # DropdownBar 在不同 DPI/字体下可能需要更高的高度，否则第二行控件会被遮挡
        # 这里给一个可靠的最小高度，并在后面用真实 sizeHint 取最大值。
        self.dropdown_bar.setMinimumHeight(72)

        lay.addWidget(self.dropdown_bar, 1)

        # 右侧 3 列：补充栏（模仿 DropdownBar：蓝底标题 + 白底按钮/按钮）
        right = QFrame()
        right.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # 使用与 dropdown_bar.py 一致的主色（你项目里为 #0090d0）
        right.setStyleSheet("""
            QFrame#RightActions { background-color: #0090d0; }
            QLabel { 
                color: white; 
                font-weight: bold;
                font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
                font-size: 12pt;
            }
            QPushButton { 
                background: #efefef; 
                border: 1px solid #666;
                font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
                font-size: 12pt;
            }
            QPushButton:hover { background: #f7f7f7; }
            QPushButton#AddBtn { background:#cfe6b8; font-weight:bold; }
        """)
        right.setObjectName("RightActions")

        g = QVBoxLayout(right)
        g.setContentsMargins(10, 10, 10, 10)
        g.setSpacing(6)

        # 标题行
        titles = QFrame()
        tl = QHBoxLayout(titles)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(8)

        for t in ["结果查看", "历史记录", "操作"]:
            lab = QLabel(t)
            lab.setAlignment(Qt.AlignCenter)
            lab.setMinimumWidth(90)
            lab.setMinimumHeight(22)
            tl.addWidget(lab)

        g.addWidget(titles, 0)

        # 控件行
        row = QFrame()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(8)

        self.btn_view_strategy = QPushButton("查看结果")
        self.btn_view_history = QPushButton("查看历史")
        self.btn_add = QPushButton("新增特检策略")
        self.btn_add.setObjectName("AddBtn")
        self.btn_view_history.setEnabled(False)

        for b in [self.btn_view_strategy, self.btn_view_history]:
            b.setFixedSize(90, 30)
        # self.btn_add.setFixedSize(120, 30)
        self.btn_add.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.btn_add.setMinimumHeight(30)

        self.btn_view_strategy.clicked.connect(self._on_view_strategy)
        self.btn_view_history.clicked.connect(self._on_view_history)
        self.btn_add.clicked.connect(self._on_add_strategy)

        rl.addWidget(self.btn_view_strategy)
        rl.addWidget(self.btn_view_history)
        rl.addWidget(self.btn_add)

        g.addWidget(row, 0)

        # 让顶部整条栏位“足够高”，避免内容被遮挡（取 sizeHint / minimumHeight 的最大值）
        h_candidates = [
            self.dropdown_bar.sizeHint().height(),
            self.dropdown_bar.minimumSizeHint().height(),
            self.dropdown_bar.minimumHeight(),
            72,
        ]
        bar_h = max([v for v in h_candidates if v and v > 0])
        wrap.setMinimumHeight(bar_h)
        right.setFixedHeight(bar_h)

        lay.addWidget(right, 0)
        return wrap

    # ---------------- 左侧表格区 ----------------
    def _build_left_tables(self) -> QWidget:
        left = QWidget()
        v = QVBoxLayout(left)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(10)

        # 1. 上表：构件检验汇总
        self.component_table = QTableWidget(6, 5)
        self.component_table.setHorizontalHeaderLabels(
            ["构件风险等级", "构件数量", "检验等级II", "检验等级III", "检验等级IV"])
        self._style_summary_table(self.component_table)

        # ====== 召唤动态高度工具，拒绝写死像素 ======
        self._lock_table_height_only(self.component_table)
        v.addWidget(self._wrap_with_title("构件检验汇总", self.component_table), 0)

        # 2. 年份切换条
        v.addWidget(self._build_year_bar(), 0)

        # 3. 下表：节点风险等级汇总
        self.node_table = QTableWidget(6, 5)
        self.node_table.setHorizontalHeaderLabels(
            ["节点风险等级", "节点焊缝数量", "检验等级II", "检验等级III", "检验等级IV"])
        self._style_summary_table(self.node_table)

        # ====== 召唤动态高度工具，拒绝写死像素 ======
        self._lock_table_height_only(self.node_table)
        v.addWidget(self._wrap_with_title("节点风险等级汇总", self.node_table), 0)

        # ====== 底部弹簧，吸收所有多余空间 ======
        v.addStretch(1)

        return left

    def _build_right_diagrams(self) -> QWidget:
        right = QWidget()
        h = QHBoxLayout(right)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)

        panel = QFrame()
        panel.setStyleSheet("QFrame { background: #ffffff; border: 1px solid #b9c6d6; }")
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        panel.setMinimumWidth(620)
        panel.setMaximumWidth(700)

        outer = QVBoxLayout(panel)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(6)

        title = QLabel("模型立面风险图")
        title.setStyleSheet("""
            color: #1d2b3a;
            font-weight: bold;
            font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
            font-size: 12pt;
        """)
        outer.addWidget(title, 0)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        lbl_row = QLabel("立面：")
        lbl_row.setStyleSheet('color:#1d2b3a; font-size:12pt;')

        self.row_combo = QComboBox()
        self.row_combo.setStyleSheet("""
            QComboBox {
                background: #ffffff;
                border: 1px solid #b9c6d6;
                min-height: 28px;
                padding: 2px 8px;
                font-size: 12pt;
            }
        """)
        self.row_combo.addItems(["XZ 前"])
        self.row_combo.setCurrentText("XZ 前")
        self.row_combo.currentTextChanged.connect(self._on_row_changed)

        top_row.addWidget(lbl_row, 0)
        top_row.addWidget(self.row_combo, 0)
        top_row.addStretch(1)
        outer.addLayout(top_row, 0)

        self.elevation_hint_label = QLabel("当前显示：XZ 1 立面轮廓图；滚轮缩放，双击恢复初始视图。")
        self.elevation_hint_label.setWordWrap(False)
        self.elevation_hint_label.setFixedHeight(24)
        self.elevation_hint_label.setStyleSheet("color:#5d6f85; font-size:12px;")
        outer.addWidget(self.elevation_hint_label, 0)

        view_row = QHBoxLayout()
        view_row.setContentsMargins(0, 0, 0, 0)
        view_row.setSpacing(6)

        self.elevation_view = SacsElevationRiskView(panel)
        self.elevation_view.set_info_label(self.elevation_hint_label)

        # 改成立方形规格，接近三维结构图的显示感觉
        self.elevation_view.setMinimumSize(560, 560)
        self.elevation_view.setMaximumSize(620, 620)
        self.elevation_view.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        self.slider_v = QSlider(Qt.Vertical)
        self.slider_v.setRange(-100, 100)
        self.slider_v.setValue(0)
        self.slider_v.setFixedHeight(560)

        view_row.addStretch(1)
        view_row.addWidget(self.elevation_view, 0, Qt.AlignHCenter | Qt.AlignVCenter)
        view_row.addWidget(self.slider_v, 0)
        view_row.addStretch(1)

        outer.addLayout(view_row, 1)

        self.slider_h = QSlider(Qt.Horizontal)
        self.slider_h.setRange(-100, 100)
        self.slider_h.setValue(0)
        self.slider_h.setFixedWidth(560)

        slider_row = QHBoxLayout()
        slider_row.setContentsMargins(0, 0, 0, 0)
        slider_row.setSpacing(0)
        slider_row.addStretch(1)
        slider_row.addWidget(self.slider_h, 0)
        slider_row.addStretch(1)

        outer.addLayout(slider_row, 0)

        self.elevation_view.bind_sliders(self.slider_h, self.slider_v)

        self.slider_h.valueChanged.connect(
            lambda v: self.elevation_view.pan_view(v, self.slider_v.value())
        )
        self.slider_v.valueChanged.connect(
            lambda v: self.elevation_view.pan_view(self.slider_h.value(), v)
        )

        h.addWidget(panel, 1)
        return right

    def _find_platform_strength_page(self):
        mw = self.window()
        tab_widget = getattr(mw, "tab_widget", None)
        if tab_widget is None:
            return None

        facility_code = self._active_facility_code or self._get_dropdown_value("facility_code")
        for i in range(tab_widget.count()):
            page = tab_widget.widget(i)
            if isinstance(page, PlatformStrengthPage):
                try:
                    if page._get_top_value("facility_code") == facility_code:
                        return page
                except Exception:
                    pass
        return None

    def _get_shared_section_params(self, context: Dict) -> tuple[float, int]:
        page = self._find_platform_strength_page()
        if page is not None:
            return page._get_workpoint_value(), page._get_level_threshold()

        # 回退：结构强度页没开时，再从 context 里取
        wp = self.elevation_view._extract_workpoint_from_context(context)
        thr = self.elevation_view._extract_level_threshold_from_context(context)
        return wp, thr

    def _sync_dynamic_row_combo_from_view(self):
        if not hasattr(self, "row_combo") or not hasattr(self, "elevation_view"):
            return

        options = self.elevation_view.available_row_names()
        if not options:
            return

        current = getattr(self.elevation_view, "_row_name", "") or self.row_combo.currentText().strip()
        old_options = [self.row_combo.itemText(i) for i in range(self.row_combo.count())]

        self.row_combo.blockSignals(True)
        try:
            if old_options != options:
                self.row_combo.clear()
                self.row_combo.addItems(options)

            if current in options:
                self.row_combo.setCurrentText(current)
            else:
                self.row_combo.setCurrentText(options[1] if len(options) > 1 else options[0])
        finally:
            self.row_combo.blockSignals(False)

    def _build_year_bar(self) -> QWidget:
        bar = QFrame()
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.year_buttons = []
        years = self._year_mapper.display_labels()

        for y in years:
            btn = QPushButton(y)
            btn.setCheckable(True)
            btn.setFixedHeight(28)
            btn.setStyleSheet("""
                QPushButton { 
                    background: #efefef; 
                    border: 1px solid #333; 
                    padding: 2px 14px; 
                    font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
                    font-size: 12pt;
                }
                QPushButton:checked { 
                    background: #d6f0d0; 
                    font-weight: bold; 
                }
            """)
            btn.clicked.connect(lambda _, yy=y: self._on_year_changed(yy))
            lay.addWidget(btn)
            self.year_buttons.append(btn)

        lay.addStretch(1)
        self._sync_year_buttons(self.current_year)
        return bar

    # ---------------- helpers ----------------
    def _wrap_with_title(self, title: str, table: QTableWidget) -> QWidget:
        frame = QFrame()
        v = QVBoxLayout(frame)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        title_bar = QFrame()
        title_bar.setFixedHeight(28)
        title_bar.setStyleSheet("background:#4f79bd;")
        tl = QHBoxLayout(title_bar)
        tl.setContentsMargins(10, 4, 10, 4)

        title_label = QLabel(title)
        title_label.setStyleSheet("""
            color: white;
            font-weight: bold;
            font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
            font-size: 12pt;
        """)
        tl.addWidget(title_label)
        tl.addStretch(1)

        v.addWidget(title_bar, 0)
        v.addWidget(table, 1)
        return frame

    def _style_summary_table(self, table: QTableWidget):
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setShowGrid(True)

        # 表格自身出现滚动条（原型有）
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        table.setStyleSheet("""
            QTableWidget { 
                background-color: #ffffff; 
                gridline-color: #d0d0d0; 
                font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
                font-size: 12pt;
            }
            QHeaderView::section { 
                background-color: #f3f6fb; 
                color: #000000; 
                font-weight: normal; 
                border: 1px solid #e6e6e6; 
                font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
                font-size: 12pt;
            }
        """)

        row_heads = ["一", "二", "三", "四", "五", "总计"]
        for r, head in enumerate(row_heads):
            it = QTableWidgetItem(head)
            it.setTextAlignment(Qt.AlignCenter)
            it.setBackground(QColor("#f3f6fb"))
            it.setForeground(QColor("#000000"))
            table.setItem(r, 0, it)

        for r in range(table.rowCount()):
            for c in range(1, table.columnCount()):
                it = QTableWidgetItem("-")
                it.setTextAlignment(Qt.AlignCenter)
                table.setItem(r, c, it)

    def _lock_table_height_only(self, table: QTableWidget):
        """动态计算并锁死表格高度，完美适配 Win11 的 DPI 缩放"""
        # 1. 根据当前系统字体高度，动态设定舒适的行高（字体高度 + 14像素留白）
        base_row_h = table.fontMetrics().height() + 14
        table.verticalHeader().setDefaultSectionSize(base_row_h)

        # 2. 获取表头在当前系统下的真实渲染高度（sizeHint能获取到准确值）
        header_h = table.horizontalHeader().sizeHint().height()
        if header_h < 20:  # 极端情况兜底
            header_h = base_row_h

        # 3. 精准计算总高度：表头高度 + (行高 × 行数) + 上下边框(4px)
        total_h = header_h + (base_row_h * table.rowCount()) + 4
        table.setFixedHeight(total_h)

    # ---------------- data ----------------
    def _sync_platform_ui(self, changed_key: str | None = None):
        platform = sync_platform_dropdowns(self.dropdown_bar, changed_key=changed_key)
        facility_code = platform["facility_code"]
        platform_name = platform["facility_name"]
        window = self.window()
        if hasattr(window, "set_current_platform_name"):
            window.set_current_platform_name(platform_name)
        self._load_runtime_summary(facility_code)

    def _select_facility_code(self, facility_code: str) -> None:
        platform = find_platform(facility_code=facility_code)
        facility_codes = [item["facility_code"] for item in FILE_MANAGEMENT_PLATFORMS]
        facility_names = [item["facility_name"] for item in FILE_MANAGEMENT_PLATFORMS]
        self.dropdown_bar.set_options("facility_code", facility_codes, platform["facility_code"])
        self.dropdown_bar.set_options("facility_name", facility_names, platform["facility_name"])
        sync_platform_dropdowns(self.dropdown_bar, changed_key="facility_code")

    def refresh_runtime_summary(
        self,
        facility_code: str | None = None,
        run_id: object = None,
        *,
        sync_dropdown: bool = False,
    ) -> None:
        target_facility = (facility_code or self._get_dropdown_value("facility_code") or self._active_facility_code).strip()
        if not target_facility:
            return
        normalized_run_id: int | None
        try:
            normalized_run_id = int(run_id) if run_id not in ("", None) else None
        except Exception:
            normalized_run_id = None
        if sync_dropdown:
            self._select_facility_code(target_facility)
        self._load_runtime_summary(target_facility, normalized_run_id)

    @staticmethod
    def _display_cell(value: object) -> str:
        if value in ("", None):
            return "-"
        return str(value)

    def _clear_summary_table(self, table: QTableWidget):
        blank_rows = [("-", "-", "-", "-") for _ in range(6)]
        self._fill_rows(table, blank_rows)

    def _load_runtime_summary(self, facility_code: str, run_id: int | None = None):
        bundle = self._result_service.load_result_bundle(facility_code, run_id)
        if not bundle:
            self._clear_summary_table(self.component_table)
            self._clear_summary_table(self.node_table)
            self._active_facility_code = facility_code
            self._active_run_id = run_id

            if hasattr(self, "elevation_view"):
                self.elevation_view._draw_message("当前没有可用的特检结果")
            return

        context = bundle["context"]

        print("[Strategy] context keys =", list(context.keys()))
        for k, v in context.items():
            if isinstance(v, list) and v:
                print("[Strategy]", k, "sample =", v[0])
            elif isinstance(v, (str, dict)):
                print("[Strategy]", k, "=", v)


        self._active_facility_code = facility_code
        self._active_run_id = run_id
        self._fill_component_from_context(context)
        self._fill_node_from_context(context, self.current_year)

        self._refresh_elevation_view(context)


    def _fill_component_from_context(self, context: Dict):
        self._fill_rows(self.component_table, self._summary_builder.build_component_inspection_rows(context))

    def _fill_node_from_context(self, context: Dict, year: str):
        self._fill_rows(self.node_table, self._summary_builder.build_node_inspection_rows(context, year))


    def _refresh_elevation_view(self, context: Optional[Dict] = None):
        if not hasattr(self, "elevation_view"):
            return

        if context is None:
            facility_code = self._active_facility_code or self._get_dropdown_value("facility_code")
            if not facility_code:
                return
            bundle = self._result_service.load_result_bundle(facility_code, self._active_run_id)
            if not bundle:
                self.elevation_view._draw_message("当前没有可用的特检结果")
                return
            context = bundle.get("context") or {}

        facility_code = self._active_facility_code or self._get_dropdown_value("facility_code")
        row_name = self.row_combo.currentText().strip() if hasattr(self, "row_combo") else "XZ 1"

        workpoint_override, level_threshold_override = self._get_shared_section_params(context)

        self.elevation_view.load_for_facility(
            facility_code=facility_code,
            context=context,
            year_label=self.current_year,
            row_name=row_name,
            workpoint_override=workpoint_override,
            level_threshold_override=level_threshold_override,
        )

        self._sync_dynamic_row_combo_from_view()


    def _fill_rows(self, table: QTableWidget, rows: List[Tuple[str, str, str, str]]):
        for r, row in enumerate(rows):
            if r >= table.rowCount():
                break
            for i, val in enumerate(row):
                c = 1 + i
                if c >= table.columnCount():
                    break
                it = QTableWidgetItem(str(val))
                it.setTextAlignment(Qt.AlignCenter)
                table.setItem(r, c, it)

    def _fill_table_from_csv(self, table: QTableWidget, filepath: str, start_col: int = 0):
        for r in range(table.rowCount()):
            for c in range(start_col, table.columnCount()):
                it = QTableWidgetItem("-")
                it.setTextAlignment(Qt.AlignCenter)
                table.setItem(r, c, it)

        if not os.path.exists(filepath):
            return

        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            try:
                next(reader)
            except StopIteration:
                return

            for r, row in enumerate(reader):
                if r >= table.rowCount():
                    break
                for c, val in enumerate(row):
                    col = start_col + c
                    if col >= table.columnCount():
                        break
                    it = QTableWidgetItem("-" if val == "-" else str(val))
                    it.setTextAlignment(Qt.AlignCenter)
                    table.setItem(r, col, it)

    # ---------------- actions ----------------
    def _on_year_changed(self, year: str):
        self.current_year = year
        self._sync_year_buttons(year)
        self._load_runtime_summary(self._get_dropdown_value("facility_code"), self._active_run_id)


    def _get_workpoint_value(self) -> Optional[float]:
        if not hasattr(self, "edt_workpoint"):
            return None
        txt = self.edt_workpoint.text().strip()
        if not txt:
            return None
        try:
            return float(txt)
        except Exception:
            return None

    def _get_level_threshold_value(self) -> Optional[int]:
        if not hasattr(self, "edt_level_threshold"):
            return None
        txt = self.edt_level_threshold.text().strip()
        if not txt:
            return None
        try:
            return int(float(txt))
        except Exception:
            return None

    def _on_level_threshold_changed(self):
        self._refresh_elevation_view()

    def _on_workpoint_changed(self):
        self._refresh_elevation_view()

    def _on_row_changed(self, _row_text: str):
        self._refresh_elevation_view()


    def _sync_year_buttons(self, year: str):
        for btn in getattr(self, "year_buttons", []):
            btn.setChecked(btn.text() == year)

    def _get_dropdown_value(self, key: str) -> str:
        """兼容不同 DropdownBar 实现的取值方式。"""
        if not hasattr(self, "dropdown_bar"):
            return ""
        bar = self.dropdown_bar
        if hasattr(bar, "get_value"):
            try:
                v = bar.get_value(key)
                return (v or "").strip()
            except Exception:
                pass
        if hasattr(bar, "values") and isinstance(bar.values, dict):
            return (bar.values.get(key, "") or "").strip()
        # 兜底：尝试在 bar 内部找同名 combobox
        for attr in ("combos", "combo_boxes", "widgets"):
            d = getattr(bar, attr, None)
            if isinstance(d, dict) and key in d and isinstance(d[key], QComboBox):
                return d[key].currentText().strip()
        return ""

    def _on_add_strategy(self):
        facility_code = self._get_dropdown_value("facility_code")
        if self.main_window is not None and hasattr(self.main_window, "open_new_special_strategy_tab"):
            self.main_window.open_new_special_strategy_tab(facility_code)

    def _on_view_strategy(self):
        facility_code = self._active_facility_code or self._get_dropdown_value("facility_code")
        if self.main_window is not None and hasattr(self.main_window, "open_upgrade_special_inspection_result_tab"):
            self.main_window.open_upgrade_special_inspection_result_tab(facility_code, run_id=None)

    def _on_view_history(self):
        return None

    # Clean overrides for platform linkage.
