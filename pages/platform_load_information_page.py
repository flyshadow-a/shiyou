# -*- coding: utf-8 -*-
# platform_load_information_page.py
#
# 本版改进：
# 1) 顶部表头固定不变：分公司、作业公司、油气田、设施编码、设施名称、设施类型、分类、投产时间、设计年限
#    下拉框在表头下方一行；选中后即显示在该单元格中（无需第三行）。
# 2) 主表前两行“所属信息区”仅保留【字段名 + 值】，不再显示绿色提示。
# 3) 主表从“序号0”开始的内容允许用户直接编辑录入（填表说明区不可编辑）。
# 4) 红色字段（Fx~Mz、操作工况、极端工况）支持：
#    - 用户直接编辑录入
#    - 或通过“读取结果文件”接口从CSV读取并回填
# 5) 新增曲线图页面：与当前页面平级（新Tab），标题动态为：
#    “设施编码 + 平台重量中心变化曲线”，展示 3×3 曲线图。
#
# 说明：本文件不依赖其它页面模块，直接可被 nav_config 引用。

import os
import csv
import random
import re
import openpyxl
from typing import List, Tuple, Dict, Optional

from PyQt5.QtWidgets import (
    QAction,
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QComboBox, QLabel,
    QTableWidget, QTableWidgetItem, QScrollArea, QMessageBox,
    QHeaderView, QToolTip, QFileDialog, QGridLayout, QMenu,
    QButtonGroup, QRadioButton, QCheckBox
)
from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QColor, QFont, QFontMetrics

from base_page import BasePage
from dropdown_bar import DropdownBar  # 复用平台基本信息页的顶部下拉条样式
# 从样表提取下拉选项（兼容：pages 包内相对导入 / 直接运行）
from pages.read_table_xls import ReadTableXls
from pages.hover_tip_table import HoverTipTable

# 上部组块分项目计算表页面（点击重量/重心单元格跳转编辑）
try:
    from upper_block_subproject_calculation_table_page import UpperBlockSubprojectCalculationTablePage
except Exception:
    # 兼容 pages 包内运行
    from pages.upper_block_subproject_calculation_table_page import UpperBlockSubprojectCalculationTablePage


# matplotlib 嵌入
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib as mpl
from matplotlib import font_manager

def _setup_chinese_matplotlib_font():
    """为 matplotlib 设置中文字体（避免标题/坐标轴中文变成方块）。

    会在系统已安装字体里按优先级挑选一个可用的中文字体，并设置：
    - mpl.rcParams['font.sans-serif']
    - mpl.rcParams['axes.unicode_minus'] = False
    """
    preferred = [
        "Microsoft YaHei",      # Windows 常见
        "SimHei",               # Windows 常见
        "PingFang SC",          # macOS 常见
        "Heiti SC",             # macOS 常见
        "Noto Sans CJK SC",     # Linux 常见
        "WenQuanYi Zen Hei",    # Linux 常见
        "Source Han Sans SC",   # 思源黑体
        "Arial Unicode MS",
    ]
    installed = {f.name for f in font_manager.fontManager.ttflist}
    for name in preferred:
        if name in installed:
            mpl.rcParams['font.sans-serif'] = [name]
            mpl.rcParams['axes.unicode_minus'] = False
            mpl.rcParams['font.size'] = 12
            mpl.rcParams['axes.titlesize'] = 12
            mpl.rcParams['axes.labelsize'] = 12
            mpl.rcParams['xtick.labelsize'] = 12
            mpl.rcParams['ytick.labelsize'] = 12
            return
    # 若找不到中文字体，则至少保证负号显示正常
    mpl.rcParams['axes.unicode_minus'] = False
    mpl.rcParams['font.size'] = 12
    mpl.rcParams['axes.titlesize'] = 12
    mpl.rcParams['axes.labelsize'] = 12
    mpl.rcParams['xtick.labelsize'] = 12
    mpl.rcParams['ytick.labelsize'] = 12



class SimpleLineChart(FigureCanvas):
    """一个简单折线图控件（matplotlib 默认样式/颜色）。"""

    _font_inited = False
    SMALL_FOUR_PT = 12

    def __init__(self, title: str, x: List[float], y: List[float], xlabel: str = "改建次数", ylabel: str = ""):
        if not SimpleLineChart._font_inited:
            _setup_chinese_matplotlib_font()
            SimpleLineChart._font_inited = True
        fig = Figure(figsize=(3.2, 2.2), dpi=100)
        self.ax = fig.add_subplot(111)
        super().__init__(fig)

        self.ax.set_title(title, fontsize=self.SMALL_FOUR_PT)
        self.ax.plot(x, y, marker="o")  # 默认蓝色
        self.ax.set_xlabel(xlabel, fontsize=self.SMALL_FOUR_PT)
        if ylabel:
            self.ax.set_ylabel(ylabel, fontsize=self.SMALL_FOUR_PT)
        self.ax.tick_params(axis="both", labelsize=self.SMALL_FOUR_PT)
        self.ax.grid(True, linewidth=0.6, alpha=0.6)
        fig.tight_layout()


class PlatformWeightCenterCurvePage(BasePage):
    """曲线图页面：3×3 网格（与截图一致）。"""
    def __init__(self, facility_code: str, series: Dict[str, List[float]], parent=None):
        super().__init__("", parent)
        self.facility_code = facility_code
        self.series = series
        self._build_ui()

    def _build_ui(self):
        # 整体滚动
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        self.main_layout.addWidget(scroll, 1)

        container = QWidget()
        scroll.setWidget(container)
        root = QVBoxLayout(container)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        grid_wrap = QWidget()
        grid = QGridLayout(grid_wrap)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        x = list(range(len(self.series.get("idx", []))))
        # 9张图（3×3）
        charts = [
            ("上部组块重量t", "weight", "上部组块重量t"),
            ("上部组块重心x(m)", "cgx", "上部组块重心x(m)"),
            ("上部组块重心y(m)", "cgy", "上部组块重心y(m)"),
            ("极端工况最大载荷Fx(KN)", "fx", "极端工况最大载荷Fx(KN)"),
            ("极端工况最大载荷Fy(KN)", "fy", "极端工况最大载荷Fy(KN)"),
            ("极端工况最大载荷Fz(KN)", "fz", "极端工况最大载荷Fz(KN)"),
            ("极端工况最大载荷Mx(KN·m)", "mx", "极端工况最大载荷Mx(KN·m)"),
            ("极端工况最大载荷My(KN·m)", "my", "极端工况最大载荷My(KN·m)"),
            ("极端工况最大载荷Mz(KN·m)", "mz", "极端工况最大载荷Mz(KN·m)"),
        ]

        for i, (title, key, unit) in enumerate(charts):
            y = self.series.get(key, [])
            # 长度对齐
            if len(y) != len(x):
                y = (y + [0.0] * len(x))[:len(x)]
            canvas = SimpleLineChart(title, x, y, xlabel="改建次序", ylabel=unit)
            # 外框
            holder = QWidget()
            holder.setStyleSheet("background:#dfe9f6; border:1px solid #b6c2d6;")
            v = QVBoxLayout(holder)
            v.setContentsMargins(6, 6, 6, 6)
            v.addWidget(canvas)
            r, c = divmod(i, 3)
            grid.addWidget(holder, r, c)

        root.addWidget(grid_wrap, 1)


class PlatformLoadInformationPage(BasePage):
    """平台载荷信息页面（严格表格结构 + 顶部/所属信息联动 + 结果文件读取 + 曲线页面）。"""
    MAX_EXPAND_ROWS = 55  # 与 summary_information_table_page 保持一致
    DEMO_MAIN_CSV = "platform_load_information_demo_strict.csv"
    DEMO_RESULT_CSV = "platform_load_result_demo.csv"

    TOP_KEY_ORDER: List[str] = [
        "branch", "op_company", "oilfield", "facility_code", "facility_name",
        "facility_type", "category", "start_time", "design_life",
    ]

    # 顶部固定表头（9字段）
    TOP_FIELDS: List[Tuple[str, str]] = [
        ("分公司", "湛江分公司"),
        ("作业公司", "文昌油田群作业公司"),
        ("油气田", "文昌19-1油田"),
        ("设施编码", "WC19-1WHPC"),
        ("设施名称", "文昌19-1WHPC井口平台"),
        ("设施类型", "平台"),
        ("分类", "井口平台"),
        ("投产时间", "2013-07-15"),
        ("设计年限", "15"),
    ]

    # DropdownBar 的 key 与“所属信息区”字段名（中文）映射
    KEY_TO_FIELD: Dict[str, str] = {
        "branch": "分公司",
        "op_company": "作业公司",
        "oilfield": "油气田",
        "facility_code": "设施编码",
        "facility_name": "设施名称",
        "facility_type": "设施类型",
        "category": "分类",
        "start_time": "投产时间",
        "design_life": "设计年限",
    }
    FIELD_TO_KEY: Dict[str, str] = {v: k for k, v in KEY_TO_FIELD.items()}

    @staticmethod
    def _songti_small_four_font(bold: bool = False) -> QFont:
        font = QFont("SimSun")
        font.setPointSize(12)
        font.setBold(bold)
        return font

    @staticmethod
    def _menu_qss() -> str:
        return """
            QMenu {
                background-color: #ffffff;
                color: #1d2b3a;
                border: 1px solid #cfd8e3;
                padding: 4px 0;
            }
            QMenu::item {
                padding: 6px 18px;
                background-color: transparent;
                color: #1d2b3a;
            }
            QMenu::item:selected {
                background-color: #dbe9ff;
                color: #1d2b3a;
            }
            QMenu::item:disabled {
                color: #8a94a6;
                background-color: #f7f9fc;
            }
        """


    def __init__(self, parent=None):
        super().__init__("", parent)
        self.data_dir = os.path.join(os.getcwd(), "data")
        self._num_pat = r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"

        # === 红色字段 Excel 导入（仅当前行）===
        self.result_excel_path: Optional[str] = None
        self.red_field_mode: str = 'manual'  # 'manual' or 'excel'
        # 数据区行勾选（单选）：用于“读取结果文件”定位目标行
        self._row_radio_group: Optional[QButtonGroup] = None
        # 缓存子计算表用户输入的数据
        self._uppercalc_saved_data: Dict[int, dict] = {}
        # 从《platform_total.xls》加载下拉选项（失败则回退到原 mock 逻辑）
        self._excel_provider = ReadTableXls()
        self._excel_loaded = False
        try:
            self._excel_provider.load()  # 默认路径：data/platform_total.xls
            self._excel_loaded = True
        except Exception:
            self._excel_loaded = False

        # 顶部下拉：优先使用汇总信息样表构建级联数据
        self._top_records: List[Dict[str, str]] = self._load_top_records_from_excel()
        self._top_cascade_enabled: bool = len(self._top_records) > 0
        self._top_cascade_lock: bool = False



        self._build_ui()
        self._ensure_demo_files()
        self.load_from_csv(os.path.join(self.data_dir, self.DEMO_MAIN_CSV))

    # ---------------- UI ----------------
    def _build_ui(self):
        self.setStyleSheet("""
            QWidget { background: #e6eef7; }

            /* 顶部按钮（保持原样） */
            QPushButton#TopActionBtn {
                background: #f6a24a;
                border: 1px solid #2f3a4a;
                border-radius: 3px;
                padding: 6px 16px;
                font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
                font-size: 12pt;
                font-weight: bold;
            }
            QPushButton#TopActionBtn:hover { background: #ffb86b; }

            /* 主表 */
            QTableWidget#MainTable {
                background-color: #ffffff;
                gridline-color: #d0d0d0;
                border: 1px solid #2f3a4a;
                font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
                font-size: 12pt;
            }
            QTableWidget#MainTable::item {
                border-bottom: 1px solid #d0d0d0;
                border-right:  1px solid #d0d0d0;
            }
            QTableWidget::item:selected { background-color: #dbe9ff; color: #000000; }
            QTableWidget::item:focus { outline: none; }

        """)

        # 顶部固定区：表头+下拉（2行） + 右侧按钮
        top_wrap = QWidget()
        top_layout = QHBoxLayout(top_wrap)
        top_layout.setContentsMargins(10, 10, 10, 0)
        top_layout.setSpacing(10)

        top_layout.setAlignment(Qt.AlignTop)
        # 顶部下拉条：优先按样表记录构建级联；失败时回退 mock 选项
        fallback_defaults = {k: v for k, v in self.TOP_FIELDS}
        stretch_map = {
            "branch": 1,
            "op_company": 2,
            "oilfield": 2,
            "facility_code": 2,
            "facility_name": 3,
            "facility_type": 1,
            "category": 1,
            "start_time": 2,
            "design_life": 1,
        }
        fields = []
        for key in self.TOP_KEY_ORDER:
            label = self.KEY_TO_FIELD[key]
            fallback = fallback_defaults.get(label, "")
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

        self.dropdown_bar = DropdownBar(fields, parent=self)
        self.dropdown_bar.valueChanged.connect(self._on_top_key_changed)
        if self._top_cascade_enabled:
            self._apply_top_cascade()
        top_layout.addWidget(self.dropdown_bar, 1)

        self.btn_save = QPushButton("保存")
        self.btn_export = QPushButton("导出数据")
        self.btn_curve = QPushButton("重量中心变化曲线")

        for b in (self.btn_save, self.btn_export, self.btn_curve):
            b.setObjectName("TopActionBtn")
            b.setFont(self._songti_small_four_font(bold=True))
            b.setMinimumHeight(32)

        # 按钮尺寸调整
        self.btn_save.setMinimumWidth(100)
        self.btn_export.setMinimumWidth(100)
        self.btn_curve.setMinimumWidth(160)

        self.btn_save.clicked.connect(self._on_save)
        self.btn_export.clicked.connect(self._on_export)
        self.btn_curve.clicked.connect(self._open_curve_page)

        self.main_layout.addWidget(top_wrap, 0)

        # 外层滚动区域（用于整体垂直滚动）
        outer_scroll = QScrollArea(self)
        outer_scroll.setWidgetResizable(True)
        outer_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # 禁用外层水平滚动
        self.main_layout.addWidget(outer_scroll, 1)

        container = QWidget()
        outer_scroll.setWidget(container)
        root = QVBoxLayout(container)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        self.table = self._build_main_table_skeleton()
        self.table.setObjectName("MainTable")
        self.table.setFont(self._songti_small_four_font())
        # 只保留外层 table_scroll 的横向滚动条，避免双滚动条
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # 开启右键菜单策略
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_table_context_menu)

        # 监听单元格变动，用于手动修改时恢复背景色
        self.table.itemChanged.connect(self._on_item_changed)

        # 主表允许编辑（但我们会用 item flags 精细控制哪些格可编辑）
        self.table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.SelectedClicked | QTableWidget.EditKeyPressed)

        # 点击“上部组块重心”单元格：跳转到分项目计算表并回填
        self.table.cellClicked.connect(self._on_main_cell_clicked)

        # 创建内部滚动区域，用于表格的水平/垂直滚动
        self.table_scroll = QScrollArea()
        self.table_scroll.setWidgetResizable(False)  # 不自动调整内部部件大小
        self.table_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.table_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)  # 临时，后面会动态调整
        self.table_scroll.setWidget(self.table)

        # 将内部滚动区域添加到主布局，并设置拉伸因子
        root.addWidget(self.table_scroll, 1)

        # 底部按钮区：保存、导出、重心曲线，横向居中排列
        bottom_btn_wrap = QWidget()
        bottom_btn_lay = QHBoxLayout(bottom_btn_wrap)
        bottom_btn_lay.setContentsMargins(0, 10, 0, 0)
        bottom_btn_lay.setSpacing(15)
        
        bottom_btn_lay.addStretch(1)
        bottom_btn_lay.addWidget(self.btn_save)
        bottom_btn_lay.addWidget(self.btn_export)
        bottom_btn_lay.addWidget(self.btn_curve)
        bottom_btn_lay.addStretch(1)
        
        root.addWidget(bottom_btn_wrap, 0)

    # ---------------- 顶部表：固定表头 + 下拉行 ----------------
    def _build_top_header_combo_table(self) -> QTableWidget:
        fields = self.TOP_FIELDS
        col_count = len(fields)

        table = QTableWidget(2, col_count)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.setFocusPolicy(Qt.NoFocus)

        table.setRowHeight(0, 88)
        table.setRowHeight(1, 45)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self._top_combos: List[QComboBox] = []
        for c, (title, default) in enumerate(fields):
            # 固定表头（用 QLabel 作为 cellWidget，避免全局 QSS 覆盖 item 背景导致不生效）
            lab = QLabel(title)
            lab.setAlignment(Qt.AlignCenter)
            lab.setStyleSheet(
                "background-color:#00BFFF;"
                "color:#001018;"
                "border:1px solid #7f8ea3;"
                "font-weight:bold;"
            )
            table.setCellWidget(0, c, lab)

            # 下拉框（值）
            cb = QComboBox()
            cb.setEditable(False)
            cb.setMaximumHeight(28)
            cb.addItems(self._mock_top_options(title, default))
            cb.setCurrentText(default)
            cb.currentTextChanged.connect(lambda txt, field=title: self._on_top_field_changed(field, txt))
            table.setCellWidget(1, c, cb)
            self._top_combos.append(cb)

        return table

    def _on_top_field_changed(self, field: str, txt: str):
        """顶部下拉改变：同步回填主表所属信息区。"""
        self._sync_meta_value(field, txt)

    def _sync_meta_value(self, field: str, txt: str):
        if not hasattr(self, "_meta_value_items"):
            return
        it = self._meta_value_items.get(field)
        if it is None:
            return
        it.setText(txt)

    def _normalize_top_value(self, value: object) -> str:
        txt = "" if value is None else str(value).strip()
        if (not txt) or (txt.lower() == "nan"):
            return ""
        if re.fullmatch(r"[-+]?\d+\.0+", txt):
            txt = txt.split(".", 1)[0]
        return txt

    def _load_top_records_from_excel(self) -> List[Dict[str, str]]:
        if (not getattr(self, "_excel_loaded", False)) or (not hasattr(self._excel_provider, "df")):
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

        records: List[Dict[str, str]] = []
        seen = set()
        for _, row in df.iterrows():
            rec: Dict[str, str] = {}
            for field, col in resolved.items():
                raw = self._excel_provider._clean(row[col]) if hasattr(self._excel_provider, "_clean") else row[col]
                rec[field] = self._normalize_top_value(raw)

            if not any(rec.get(k) for k in ("分公司", "作业公司", "油气田", "设施编码", "设施名称")):
                continue

            uniq = tuple(rec.get(f, "") for f in fields)
            if uniq in seen:
                continue
            seen.add(uniq)
            records.append(rec)

        return records

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

    def _apply_top_cascade(self, changed_key: Optional[str] = None, changed_value: str = ""):
        if (not self._top_cascade_enabled) or (not hasattr(self, "dropdown_bar")):
            return

        records = self._top_records
        current = {k: self.dropdown_bar.get_value(k) for k in self.TOP_KEY_ORDER}
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

        if selected_code and selected_code not in code_opts:
            code_opts = [selected_code] + code_opts
        if selected_name and selected_name not in name_opts:
            name_opts = [selected_name] + name_opts

        fixed_key_to_field = {
            "facility_type": "设施类型",
            "category": "分类",
            "start_time": "投产时间",
            "design_life": "设计年限",
        }
        fixed_values: Dict[str, str] = {}
        for k, field_cn in fixed_key_to_field.items():
            val = self._normalize_top_value((selected_row or {}).get(field_cn, ""))
            fixed_values[k] = val

        self._top_cascade_lock = True
        try:
            self.dropdown_bar.set_options("branch", branches, branch)
            self.dropdown_bar.set_options("op_company", op_opts, op)
            self.dropdown_bar.set_options("oilfield", oil_opts, oilfield)
            self.dropdown_bar.set_options("facility_code", code_opts, selected_code)
            self.dropdown_bar.set_options("facility_name", name_opts, selected_name)

            for k in ("facility_type", "category", "start_time", "design_life"):
                v = fixed_values.get(k, "")
                self.dropdown_bar.set_options(k, [v] if v else [], v)
        finally:
            self._top_cascade_lock = False

        self._sync_all_top_meta_values()

    def _sync_all_top_meta_values(self):
        for field_cn in self.FIELD_TO_KEY.keys():
            self._sync_meta_value(field_cn, self._get_top_value(field_cn))

    def _current_top_defaults(self) -> Dict[str, str]:
        defaults = {k: v for k, v in self.TOP_FIELDS}
        if hasattr(self, "dropdown_bar"):
            for field_cn in defaults.keys():
                cur = self._get_top_value(field_cn)
                if cur:
                    defaults[field_cn] = cur
        return defaults

    def _mock_top_options(self, field: str, default: str) -> List[str]:
        options_map = {
            "分公司": ["湛江分公司", "深圳分公司", "上海分公司", "海南分公司", "天津分公司"],
            "作业公司": ["文昌油田群作业公司", "涠洲作业公司", "珠江作业公司", "渤海作业公司"],
            "油气田": ["文昌19-1油田", "文昌19-2油田", "涠洲油田", "珠江口油田"],
            "设施编码": ["WC19-1WHPC", "WC19-2WHPC", "WC9-7DPP", "WC19-1DPPA"],
            "设施名称": ["文昌19-1WHPC井口平台", "文昌19-2WHPC井口平台", "WC9-7DPP井口平台"],
            "设施类型": ["平台", "导管架", "浮式"],
            "分类": ["井口平台", "生产平台", "生活平台"],
            "投产时间": ["2013-07-15", "2008-06-26", "2010-03-10"],
            "设计年限": ["10", "15", "20", "25", "30"],
        }
        opts = options_map.get(field, [default])
        return opts if default in opts else [default] + opts

    def _on_top_key_changed(self, key: str, txt: str):
        """
        顶部 DropdownBar 改变：
        - 级联刷新下拉值
        - 同步回填主表所属信息区（字段名用中文）
        """
        if self._top_cascade_enabled:
            if self._top_cascade_lock:
                return
            self._apply_top_cascade(changed_key=key, changed_value=txt)
            return

        field = self.KEY_TO_FIELD.get(key, key)
        self._sync_meta_value(field, txt)

    def _get_top_value(self, field: str) -> str:
        """获取顶部 DropdownBar 当前值（field 为中文表头名，如“设施编码”）。"""
        if hasattr(self, "dropdown_bar"):
            key = self.FIELD_TO_KEY.get(field)
            if key:
                return self.dropdown_bar.get_value(key)
        return ""


    # ---------------- 主表（严格结构） ----------------
    def _columns(self) -> List[str]:
        return [
            "序号",
            "改扩建项目名称",
            "改扩建时间",
            "改扩建内容",
            "上部组块总\n操作重量\nMT",
            "上部组块不\n可超越\n重量,MT",
            "重量变化\nMT",
            "上部组块\n重心(x,y,z)\nm",
            "上部组块重心\n不可超越半径\nm",
            "Fx,KN",
            "Fy,KN",
            "Fz,KN",
            "Mx,KN·m",
            "My,KN·m",
            "Mz,KN·m",
            "操作工况",
            "极端工况",
            "是否整体\n评估",
            "评估机构",
        ]

    def _mk_item(self, text: str, *, editable: bool=False, bold: bool=False,
                 fg: QColor=None, bg: QColor=None,
                 align: Qt.AlignmentFlag = Qt.AlignCenter) -> QTableWidgetItem:
        it = QTableWidgetItem(text)
        flags = it.flags()
        if editable:
            flags |= Qt.ItemIsEditable
        else:
            flags &= ~Qt.ItemIsEditable
        it.setFlags(flags)
        it.setTextAlignment(align)
        it.setFont(self._songti_small_four_font(bold=bold))
        if fg is not None:
            it.setForeground(fg)
        if bg is not None:
            it.setBackground(bg)
        return it

    def _set_meta_double(self, table: HoverTipTable, row: int, start: int,
                         total_span: int, label_span: int,
                         label: str, value: str, field_key: str,
                         bg: QColor):
        """所属信息：label + value（两段合并），value item 记录下来供顶部联动。"""
        value_span = max(1, total_span - label_span)

        table.setSpan(row, start, 1, label_span)
        table.setItem(row, start, self._mk_item(label, bg=bg, align=Qt.AlignLeft | Qt.AlignVCenter))

        table.setSpan(row, start + label_span, 1, value_span)
        it_val = self._mk_item(value, bg=bg, align=Qt.AlignCenter)
        table.setItem(row, start + label_span, it_val)

        if not hasattr(self, "_meta_value_items"):
            self._meta_value_items = {}
        self._meta_value_items[field_key] = it_val

    def _build_main_table_skeleton(self) -> HoverTipTable:
        cols = self._columns()
        col_count = len(cols)

        # 行：0-1 所属信息，2-3 表头
        base_rows = 4
        table = HoverTipTable(base_rows, col_count)
        table.setFont(self._songti_small_four_font())
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setVisible(False)
        # table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        bg = QColor("#eef2ff")
        red = QColor("#cc0000")

        table.setRowHeight(0, 26)
        table.setRowHeight(1, 26)
        table.setRowHeight(2, 30)
        table.setRowHeight(3, 60)

        # 顶部默认值（来自当前下拉）
        top_defaults = self._current_top_defaults()

        # ===== 所属信息两行（无绿色提示）=====
        # 每行 3 块：7 + 6 + 6 = 19
        # row0：所属分公司 / 所属作业单元 / 所属油气田(田)
        self._set_meta_double(table, 0, 0, total_span=7, label_span=3,
                              label="所属分公司", value=top_defaults.get("分公司", ""), field_key="分公司", bg=bg)
        self._set_meta_double(table, 0, 7, total_span=6, label_span=2,
                              label="所属作业单元", value=top_defaults.get("作业公司", ""), field_key="作业公司", bg=bg)
        self._set_meta_double(table, 0, 13, total_span=6, label_span=2,
                              label="所属油（气）田", value=top_defaults.get("油气田", ""), field_key="油气田", bg=bg)

        # row1：设施名称 / 投产时间 / 设计年限
        self._set_meta_double(table, 1, 0, total_span=7, label_span=3,
                              label="设施名称", value=top_defaults.get("设施名称", ""), field_key="设施名称", bg=bg)
        self._set_meta_double(table, 1, 7, total_span=6, label_span=2,
                              label="投产时间", value=top_defaults.get("投产时间", ""), field_key="投产时间", bg=bg)
        self._set_meta_double(table, 1, 13, total_span=6, label_span=2,
                              label="设计年限", value=top_defaults.get("设计年限", ""), field_key="设计年限", bg=bg)

        # ===== 分组表头（row2）=====
        table.setSpan(2, 0, 2, 1)
        table.setItem(2, 0, self._mk_item("序号", bold=True, bg=bg))

        # table.setSpan(2, 1, 1, 3)
        # table.setItem(2, 1, self._mk_item("改扩建", bold=True, bg=bg))

        # table.setSpan(2, 4, 1, 5)
        # table.setItem(2, 4, self._mk_item("上部组块重控", bold=True, bg=bg))

        table.setSpan(2, 9, 1, 6)
        table.setItem(2, 9, self._mk_item("极端工况最大载荷", bold=True, bg=bg))

        table.setSpan(2, 15, 1, 2)
        table.setItem(2, 15, self._mk_item("桩基承载力安全系数（最小）", bold=True, bg=bg))

        table.setSpan(2, 17, 2, 1)
        table.setItem(2, 17, self._mk_item("是否整体\n评估", bold=True, bg=bg))
        table.setSpan(2, 18, 2, 1)
        table.setItem(2, 18, self._mk_item("评估机构", bold=True, bg=bg))

        # ===== 子表头（row3）=====
        for i in range(1,9):
            table.setSpan(2, i, 2, 1)
        table.setItem(2, 1, self._mk_item("改扩建项目名称", bold=True, bg=bg))
        table.setItem(2, 2, self._mk_item("改扩建时间", bold=True, bg=bg))
        table.setItem(2, 3, self._mk_item("改扩建内容", bold=True, bg=bg))

        table.setItem(2, 4, self._mk_item("上部组块总操作重量,（MT）", bold=True, bg=bg))
        table.setItem(2, 5, self._mk_item("上部组块不可超越重量,（MT）", bold=True, bg=bg))
        table.setItem(2, 6, self._mk_item("重量变化,（MT）", bold=True, bg=bg))
        table.setItem(2, 7, self._mk_item("上部组块重心 x,y,z,\n（m）", bold=True, bg=bg))
        table.setItem(2, 8, self._mk_item("上部组块重心\n不可超越\n半径,（m）", bold=True, bg=bg))

        # 红色字段（严格：Mz 纵向显示）
        fx_headers = [
            ("Fx,（KN）", "Fx,（KN）"),
            ("Fy,（KN）", "Fy,（KN）"),
            ("Fz,（KN）", "Fz,（KN）"),
            ("Mx,（KN·m）", "Mx,（KN·m）"),
            ("My,（KN·m）", "My,（KN·m）"),
            ("Mz,（KN·m）", "Mz,（KN·m）"),
        ]
        red_cols = list(range(9, 15))
        for (src, shown), c in zip(fx_headers, red_cols):
            txt = shown.replace(",", "\n") if src != "Mz,（KN·m）" else shown
            table.setItem(3, c, self._mk_item(txt, bold=True, bg=bg, fg=red))

        table.setItem(3, 15, self._mk_item("操作工况", bold=True, bg=bg, fg=red))
        table.setItem(3, 16, self._mk_item("极端工况", bold=True, bg=bg, fg=red))

        # 补齐背景（未被 span 覆盖的单元格）
        for r in range(0, 4):
            for c in range(col_count):
                if table.item(r, c) is None and table.cellWidget(r, c) is None:
                    table.setItem(r, c, self._mk_item("", bg=bg))
        return table

    # ---------------- 数据加载 ----------------
    def load_from_csv(self, csv_path: str):
        if not os.path.exists(csv_path):
            QMessageBox.warning(self, "提示", f"未找到数据文件：{csv_path}")
            return

        cols = self._columns()
        rows: List[List[str]] = []
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            all_rows = list(reader)

        if not all_rows:
            return

        start_idx = 0
        if all_rows[0] and "序号" in all_rows[0][0]:
            start_idx = 1

        for r in all_rows[start_idx:]:
            if not r:
                continue
            r = (r + [""] * len(cols))[:len(cols)]
            rows.append([str(x) for x in r])

        self._apply_data(rows)

    def _find_data_end_row(self) -> int:
        """找到填表说明起始行（不含），作为数据区结束行。"""
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 0)
            if it and it.text().startswith("填表说明"):
                return r
        return self.table.rowCount()

    def _rebuild_row_checkbox_selectors(self, data_start: int, data_end: int):
        """在数据区每行首列放置复选框，用于批量操作。"""
        # 移除旧的 cellWidget
        for r in range(self.table.rowCount()):
            self.table.removeCellWidget(r, 0)

        self._row_checkboxes: Dict[int, QCheckBox] = {}

        for row_idx in range(data_start, data_end):
            seq_item = self.table.item(row_idx, 0)
            seq_text = seq_item.text().strip() if seq_item else ""

            cb = QCheckBox()
            cb.setCursor(Qt.PointingHandCursor)
            # 记录复选框引用
            self._row_checkboxes[row_idx] = cb

            holder = QWidget(self.table)
            lay = QHBoxLayout(holder)
            lay.setContentsMargins(8, 0, 8, 0)
            lay.setSpacing(8)
            lay.addWidget(cb, 0, Qt.AlignCenter)

            seq_lab = QLabel(seq_text)
            seq_lab.setAlignment(Qt.AlignCenter)
            seq_lab.setFont(self._songti_small_four_font())
            lay.addWidget(seq_lab, 0, Qt.AlignCenter)
            lay.addStretch(1)

            self.table.setCellWidget(row_idx, 0, holder)

    def _on_item_changed(self, item: QTableWidgetItem):
        """处理单元格变动：如果是红色列的手动修改，恢复背景色为白色。"""
        if getattr(self, "_loading_data", False):
            return

        row = item.row()
        col = item.column()
        base_rows = 4
        data_end = self._find_data_end_row()

        # 仅处理数据区的红色字段列：9..16
        if (base_rows <= row < data_end) and (9 <= col <= 16):
            # 如果当前背景色是淡蓝色（导入态），手动改动后应切回白色
            if item.background().color() == QColor("#e1f5fe"):
                self.table.blockSignals(True)
                item.setBackground(QColor("white"))
                self.table.blockSignals(False)

    def _text_pixel_width(self, text: str, fm: QFontMetrics) -> int:
        lines = str(text).splitlines() or [str(text)]
        return max(fm.horizontalAdvance(line) for line in lines)

    def _auto_fit_main_table_columns(self):
        """按文字内容自适应主表列宽（忽略跨列单元格，避免异常拉宽）。"""
        if not hasattr(self, "table") or self.table is None:
            return

        table = self.table
        col_count = table.columnCount()
        data_end = self._find_data_end_row()
        fm = QFontMetrics(table.font())

        min_width = 72
        max_width = 420
        padding = 24

        for c in range(col_count):
            best = min_width
            for r in range(data_end):
                # 跳过跨列单元格，避免分组标题/说明区影响单列宽度
                if table.columnSpan(r, c) > 1:
                    continue
                it = table.item(r, c)
                if it is None:
                    continue
                cand = self._text_pixel_width(it.text(), fm) + padding
                if cand > best:
                    best = cand

            # 首列包含“单选框 + 序号”控件，给更大最小宽度
            if c == 0:
                best = max(best, 110)

            table.setColumnWidth(c, min(max_width, best))

        total_width = table.frameWidth() * 2 + sum(table.columnWidth(c) for c in range(col_count))
        table.setFixedWidth(total_width + 2)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def _apply_data(self, rows: List[List[str]]):
        base_rows = 4
        bg = QColor("#eef2ff")
        green = QColor(0, 170, 0)
        red = QColor("#cc0000")

        explain = [
            "填表说明：",
            "1. 改扩建时间：0行填原设计，后续填写改扩建完工的年月（如2023年10月）。",
            "2. 改扩建内容：平台本次改扩建增加或拆除的结构或设备。0行不填。",
            "3. 上部组块重量：0行为组块操作重量，后续为上一行重量与本行重量变化之和。",
            "4. 重量变化：0行为0，后续为重量增加填“+增加吨数”，如重量减少填“-减少吨数”。",
            "5. 极端工况最大载荷：填写最大值。",
        ]

        total = base_rows + len(rows) + len(explain)
        self.table.setRowCount(total)

        # 数据行高度
        for rr in range(base_rows, base_rows + len(rows)):
            self.table.setRowHeight(rr, 44)

        # 截图提示行（前两行：0、1）— 仍然保留示例文字，但允许用户编辑
        if rows:
            tip0 = ["0", "原设计", "用户设置", "\\",
                    "", "", "0", "", "",
                    "", "", "", "", "", "",
                    "\\", "\\", "\\", "\\"]
            tip1 = ["1", "（预定义名称？）", "用户设置", "用户输入",
                    "用户输入", "用户输入", "用户输入", "用户输入", "用户输入",
                    "用户输入", "用户输入", "用户输入", "用户输入", "用户输入", "用户输入",
                    "用户输入", "用户输入", "\\", "\\"]
            rows[0] = (tip0 + [""] * self.table.columnCount())[:self.table.columnCount()]
            if len(rows) > 1:
                rows[1] = (tip1 + [""] * self.table.columnCount())[:self.table.columnCount()]

        red_cols = set(range(9, 17))
        calc_bg = QColor("#d8ffcf")  # 计算回显项的显著淡绿色

        # 写入数据（从 base_rows 开始），并设置可编辑
        for i, row in enumerate(rows):
            rr = base_rows + i
            for c, val in enumerate(row):
                # 数据区：允许编辑
                # 主表中“上部组块重心”不允许直接编辑，需跳转到分项目计算表
                editable = (c not in (0, 7))
                it = self._mk_item(val, editable=editable)

                # 重心列（第 7 列）：强制染色
                if c == 7:
                    it.setBackground(calc_bg)

                # 红色字段列添加操作提示
                if c in red_cols:
                    it.setToolTip("双击可手动输入数据；右键点击可读取本行对应的分析结果文件。")

                # 示例：第0/1行的提示用绿/红区分（但依然可编辑）
                if i in (0, 1) and val:
                    it.setForeground(red if c in red_cols else green)
                else:
                    if c in red_cols and val:
                        it.setForeground(red)

                self.table.setItem(rr, c, it)

        # 填表说明（整行合并，不可编辑）
        start = base_rows + len(rows)
        for k, line in enumerate(explain):
            rr = start + k
            self.table.setRowHeight(rr, 24 if k else 28)
            self.table.setSpan(rr, 0, 1, self.table.columnCount())
            it = self._mk_item(line, bold=(k == 0), bg=bg, align=Qt.AlignLeft | Qt.AlignVCenter, editable=False)
            self.table.setItem(rr, 0, it)

        # 补齐背景（空格）—— 数据区空格也允许编辑
        data_end = start
        for r in range(0, self.table.rowCount()):
            for c in range(self.table.columnCount()):
                if self.table.item(r, c) is None and self.table.cellWidget(r, c) is None:
                    editable = (base_rows <= r < data_end) and (c not in (0, 7))
                    # 关键修复：补齐背景时也要保留重心列颜色
                    item_bg = calc_bg if c == 7 else bg
                    it = self._mk_item("", bg=item_bg, editable=editable)
                    if (base_rows <= r < data_end) and (c in red_cols):
                        it.setToolTip("双击可手动输入数据；右键点击可读取本行对应的分析结果文件。")
                    self.table.setItem(r, c, it)

        # ========== 新增：确保序号连续 ==========
        data_start = base_rows
        data_end = self._find_data_end_row()
        for idx, row_idx in enumerate(range(data_start, data_end)):
            seq_item = self.table.item(row_idx, 0)
            if seq_item is not None:
                seq_item.setText(str(idx))  # 从0开始连续编号

        # 刷新复选框显示
        self._rebuild_row_checkbox_selectors(data_start, data_end)

        data_n = len(rows)

        # 动态设置垂直滚动策略和表格高度
        if data_n <= self.MAX_EXPAND_ROWS:  # 需要定义 MAX_EXPAND_ROWS = 50（可在类属性中添加）
            self.table_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            total_height = 0
            for r in range(total):  # 计算所有行总高度（包括表头、数据、说明）
                total_height += self.table.rowHeight(r)
            self.table.setFixedHeight(total_height + 2)
        else:
            self.table_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            self.table.setFixedHeight(-1)  # 取消固定高度
            self.table.setMinimumHeight(300)  # 设置一个合理的最小高度

        # 列宽按文字内容自适应，并由外层 table_scroll 统一承接横向滚动
        self._auto_fit_main_table_columns()
    # ---------------- 结果文件读取接口 ----------------

    def _on_table_context_menu(self, pos):
        """表格右键菜单逻辑：首列支持行操作，红色列支持读取结果文件。"""
        base_rows = 4
        data_end = self._find_data_end_row()
        row = self.table.rowAt(pos.y())
        col = self.table.columnAt(pos.x())
        if not (base_rows <= row < data_end):
            return

        if col == 0:
            self._show_row_context_menu(row, pos)
            return

        # 红色字段列：9..16 (Fx~Mz, 操作工况, 极端工况)
        if 9 <= col <= 16:
            menu = QMenu(self.table)
            menu.setStyleSheet(self._menu_qss())
            action = menu.addAction("读取该行关联的结果文件 (.inp)")
            action.triggered.connect(lambda: self._on_import_result(target_row=row))
            menu.exec_(self.table.viewport().mapToGlobal(pos))

    def _checked_data_rows(self) -> List[int]:
        data_end = self._find_data_end_row()
        rows: List[int] = []
        for row_idx, checkbox in getattr(self, "_row_checkboxes", {}).items():
            if row_idx < data_end and checkbox.isChecked():
                rows.append(row_idx)
        return sorted(rows)

    def _show_row_context_menu(self, row: int, pos):
        menu = QMenu(self.table)
        menu.setStyleSheet(self._menu_qss())

        add_above_action = QAction("在上方新增一行", menu)
        add_below_action = QAction("在下方新增一行", menu)
        add_above_action.triggered.connect(lambda _=False, target=row: self._insert_row_at(target))
        add_below_action.triggered.connect(lambda _=False, target=row + 1: self._insert_row_at(target))
        menu.addAction(add_above_action)
        menu.addAction(add_below_action)

        checked_rows = self._checked_data_rows()
        if checked_rows:
            delete_action = QAction(f"删除已勾选行（{len(checked_rows)}）", menu)
            delete_action.triggered.connect(lambda _=False, rows=checked_rows: self._delete_checked_rows(rows))
            menu.addAction(delete_action)
        else:
            hint_action = QAction("请先勾选要删除的行", menu)
            hint_action.setEnabled(False)
            menu.addAction(hint_action)

        menu.exec_(self.table.viewport().mapToGlobal(pos))

    def _on_import_result(self, target_row: int = None):
        """读取结果文件（INP）：按指定行序号匹配文件名并回填该行红色字段。"""
        base_rows = 4
        data_end = self._find_data_end_row()
        row = target_row if target_row is not None else self.table.currentRow()
        if row < base_rows or row >= data_end:
            QMessageBox.information(self, "提示", "请先在主表数据区选中或右键点击一行。")
            return

        seq = self._cell_text(row, 0).strip()
        if not seq:
            QMessageBox.warning(self, "读取失败", "该行缺少序号，无法匹配结果文件。")
            return

        path = self._find_result_inp_by_seq(seq)
        if not path:
            roots = "\n".join(self._result_inp_search_roots())
            QMessageBox.warning(self, "读取失败", f"未找到序号 {seq} 对应的 INP 结果文件。\n请按序号命名（例如：{seq}.inp）。\n\n搜索目录：\n{roots}")
            return

        try:
            values = self._read_result_inp_generic(path)
            keys = ['Fx', 'Fy', 'Fz', 'Mx', 'My', 'Mz', '操作工况', '极端工况']
            if not any(str(values.get(k, '')).strip() for k in keys):
                QMessageBox.warning(self, "读取失败", "在INP文件中未解析到有效字段。")
                return
            self._apply_excel_values_to_row(row, values, bg_color=QColor("#e1f5fe"))
            QMessageBox.information(self, "读取结果文件", f"已按序号 {seq} 读取并回填成功。\n文件：{path}")
        except Exception as e:
            QMessageBox.warning(self, "读取失败", f"读取或解析失败：{e}")

    def _on_red_field_mode_changed(self, idx: int):
        self.red_field_mode = 'manual' if idx == 0 else 'excel'
        self.btn_pick_excel_result.setEnabled(self.red_field_mode == 'excel')
        self.btn_import_excel_result.setEnabled(self.red_field_mode == 'excel')
        self._apply_red_fields_editability()

    def _apply_red_fields_editability(self):
        red_cols = list(range(9, 17))
        base_rows, data_end = 4, self._find_data_end_row()
        for r in range(base_rows, data_end):
            for c in red_cols:
                it = self.table.item(r, c)
                if not it:
                    it = self._mk_item('', editable=True)
                    self.table.setItem(r, c, it)
                flags = it.flags()
                if self.red_field_mode == 'manual':
                    it.setFlags(flags | Qt.ItemIsEditable)
                    it.setBackground(QColor('white'))
                else:
                    it.setFlags(flags & ~Qt.ItemIsEditable)
                    it.setBackground(QColor('#f2f2f2'))

    def _pick_result_excel(self):
        path, _ = QFileDialog.getOpenFileName(self, '选择结果文件（Excel）', self.data_dir, 'Excel Files (*.xlsx *.xlsm);;All Files (*)')
        if path: self.result_excel_path = path

    def _import_excel_to_current_row(self):
        if self.red_field_mode != 'excel': return
        if not self.result_excel_path: return
        row = self.table.currentRow()
        if row < 4 or row >= self._find_data_end_row(): return
        try:
            values = self._read_result_excel_generic(self.result_excel_path)
            if values:
                self._apply_excel_values_to_row(row, values, bg_color=QColor("#e1f5fe"))
                QMessageBox.information(self, '完成', '已导入Excel数据到当前行。')
        except Exception as e: QMessageBox.warning(self, '导入失败', str(e))

    def _apply_excel_values_to_row(self, row: int, values: Dict[str, object], bg_color: QColor = None):
        keys = ['Fx', 'Fy', 'Fz', 'Mx', 'My', 'Mz', '操作工况', '极端工况']
        cols = [9, 10, 11, 12, 13, 14, 15, 16]
        red = QColor("#cc0000")
        for k, c in zip(keys, cols):
            v = values.get(k, '')
            it = self.table.item(row, c)
            if not it:
                it = self._mk_item('', editable=True)
                self.table.setItem(row, c, it)
            it.setText('' if v is None else str(v))
            if str(v).strip(): it.setForeground(red)
            if bg_color: it.setBackground(bg_color)
        self._auto_fit_main_table_columns()

    def _read_result_excel_generic(self, path: str) -> Dict[str, object]:
        wb = openpyxl.load_workbook(path, data_only=True)
        ws = wb.active
        keys = ['Fx', 'Fy', 'Fz', 'Mx', 'My', 'Mz', '操作工况', '极端工况']
        result = {}
        for r in range(1, ws.max_row + 1):
            for c in range(1, ws.max_column + 1):
                v = ws.cell(r, c).value
                if isinstance(v, str) and v.strip() in keys:
                    result[v.strip()] = ws.cell(r, c + 1).value or ws.cell(r + 1, c).value
        return result

    def _to_float(self, value: object) -> Optional[float]:
        try: return float(str(value).strip())
        except: return None

    def _fmt_float(self, value: object) -> str:
        fv = self._to_float(value)
        return f"{fv:.6f}".rstrip("0").rstrip(".") if fv is not None else (str(value) if value else "")

    # ---------------- 表格行操作（新增/删除） ----------------
    def _insert_row_at(self, row: int):
        """在数据区指定位置新增一行。"""
        base_rows = 4
        data_end = self._find_data_end_row()
        insert_row = max(base_rows, min(row, data_end))
        self.table.insertRow(insert_row)
        
        # 初始化新行的样式
        cols = self.table.columnCount()
        calc_bg = QColor("#d8ffcf")
        red_cols = set(range(9, 17))
        
        for c in range(cols):
            # 第0列是序号/单选，第7列是跳转重心，这两个不可直接编辑
            editable = (c not in (0, 7))
            bg = calc_bg if c == 7 else QColor("white")
            it = self._mk_item("", bg=bg, editable=editable)
            if c in red_cols:
                it.setToolTip("双击可手动输入数据；右键点击可读取本行对应的分析结果文件。")
            self.table.setItem(insert_row, c, it)
            
        self._refresh_table_layout_and_seq()

    def _delete_checked_rows(self, rows: Optional[List[int]] = None):
        """删除已勾选的数据行。"""
        base_rows = 4
        data_end = self._find_data_end_row()
        target_rows = sorted(rows if rows is not None else self._checked_data_rows())

        if not target_rows:
            QMessageBox.information(self, "提示", "请先勾选要删除的行。")
            return
        if target_rows[0] < base_rows or target_rows[-1] >= data_end:
            return
        if len(target_rows) >= data_end - base_rows:
            QMessageBox.information(self, "提示", "表格至少保留一条数据行。")
            return

        ret = QMessageBox.question(
            self,
            "确认删除",
            f"确定删除选中的 {len(target_rows)} 行信息吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ret != QMessageBox.Yes:
            return

        for row in reversed(target_rows):
            self.table.removeRow(row)

        self._refresh_table_layout_and_seq()

    def _refresh_table_layout_and_seq(self):
        """统一刷新序号、单选框、行高及表格总高度。"""
        base_rows = 4
        data_end = self._find_data_end_row()
        
        # 1. 重新设置序号（连续编号）
        for idx, row_idx in enumerate(range(base_rows, data_end)):
            it = self.table.item(row_idx, 0)
            if it: it.setText(str(idx))
            self.table.setRowHeight(row_idx, 44)
            
        # 2. 重新构建复选框
        self._rebuild_row_checkbox_selectors(base_rows, data_end)
        
        # 3. 重新计算总高度
        total_rows = self.table.rowCount()
        data_n = data_end - base_rows
        if data_n <= self.MAX_EXPAND_ROWS:
            self.table_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            total_h = sum(self.table.rowHeight(r) for r in range(total_rows))
            self.table.setFixedHeight(total_h + 2)
        else:
            self.table_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            self.table.setFixedHeight(-1)
            self.table.setMinimumHeight(300)
            
        self._auto_fit_main_table_columns()

    def _extract_numbers(self, text: str) -> List[float]:
        return [float(s) for s in re.findall(self._num_pat, text or "") if self._to_float(s) is not None]

    def _read_text_file_with_fallback(self, path: str) -> str:
        for enc in ["utf-8", "gb18030", "gbk", "latin-1"]:
            try:
                with open(path, "r", encoding=enc) as f: return f.read()
            except: continue
        return ""

    def _result_inp_search_roots(self) -> List[str]:
        return [self.data_dir, os.path.join(os.getcwd(), "upload")]

    def _find_result_inp_by_seq(self, seq_text: str) -> Optional[str]:
        seq = str(seq_text).strip()
        roots = self._result_inp_search_roots()
        for root in roots:
            for dir_path, _, file_names in os.walk(root):
                for fn in file_names:
                    if fn.lower() == f"{seq}.inp" or fn.lower() == f"row_{seq}.inp":
                        return os.path.normpath(os.path.join(dir_path, fn))
        return None

    def _extract_loads_from_text(self, text: str) -> Dict[str, str]:
        loads = {}
        for key in ["Fx", "Fy", "Fz", "Mx", "My", "Mz"]:
            m = re.search(rf"(?i)\b{key}\b.*?\b({self._num_pat})\b", text)
            if m: loads[key] = self._fmt_float(m.group(1))
        return loads

    def _extract_safety_from_text(self, text: str) -> Dict[str, str]:
        out = {}
        m_op = re.search(rf"(?im)操作工况.*?({self._num_pat})", text)
        if m_op: out["操作工况"] = self._fmt_float(m_op.group(1))
        m_ex = re.search(rf"(?im)极端工况.*?({self._num_pat})", text)
        if m_ex: out["极端工况"] = self._fmt_float(m_ex.group(1))
        return out

    def _read_result_inp_generic(self, path: str) -> Dict[str, object]:
        text = self._read_text_file_with_fallback(path)
        res = {}
        res.update(self._extract_loads_from_text(text))
        res.update(self._extract_safety_from_text(text))
        return res

    def _collect_series_for_curve(self) -> Dict[str, List[float]]:
        base_rows, data_end = 4, self._find_data_end_row()
        idxs, weight, cgx, cgy, fx, fy, fz, mx, my, mz = [], [], [], [], [], [], [], [], [], []
        for r in range(base_rows, data_end):
            seq = self._cell_text(r, 0).strip()
            if not seq.isdigit(): continue
            idxs.append(len(idxs))
            weight.append(self._to_float(self._cell_text(r, 4)) or 0.0)
            xyz = self._cell_text(r, 7).split(",")
            cgx.append(self._to_float(xyz[0]) if len(xyz)>0 else 0.0)
            cgy.append(self._to_float(xyz[1]) if len(xyz)>1 else 0.0)
            fx.append(self._to_float(self._cell_text(r, 9)) or 0.0)
            fy.append(self._to_float(self._cell_text(r, 10)) or 0.0)
            fz.append(self._to_float(self._cell_text(r, 11)) or 0.0)
            mx.append(self._to_float(self._cell_text(r, 12)) or 0.0)
            my.append(self._to_float(self._cell_text(r, 13)) or 0.0)
            mz.append(self._to_float(self._cell_text(r, 14)) or 0.0)
        return {"idx": idxs, "weight": weight, "cgx": cgx, "cgy": cgy, "fx": fx, "fy": fy, "fz": fz, "mx": mx, "my": my, "mz": mz}

    def _cell_text(self, row: int, col: int) -> str:
        it = self.table.item(row, col)
        return it.text() if it else ""

    def _on_main_cell_clicked(self, row: int, col: int):
        if 4 <= row < self._find_data_end_row() and col == 7:
            self._open_upper_block_subproject_page(src_row=row)

    def _open_upper_block_subproject_page(self, src_row: int):
        mw = self.window()
        if not hasattr(mw, "tab_widget"): return
        key = f"uppercalc::{src_row}"
        if key in getattr(mw, "page_tab_map", {}):
            idx = mw.tab_widget.indexOf(mw.page_tab_map[key])
            if idx != -1: mw.tab_widget.setCurrentIndex(idx); return
        
        row_data = {c: self._cell_text(src_row, c) for c in range(self.table.columnCount())}
        page = UpperBlockSubprojectCalculationTablePage(main_window=mw, parent=mw)
        page.set_context(source_row=src_row, source_row_data=row_data)
        if src_row in self._uppercalc_saved_data: page.load_table_data(self._uppercalc_saved_data[src_row])
        page.saved.connect(self._on_upper_page_saved)
        title = f"{(row_data.get(1) or '序号'+str(src_row))}-上部组块分项目计算表"
        idx = mw.tab_widget.addTab(page, title)
        mw.tab_widget.setCurrentIndex(idx)
        if hasattr(mw, "page_tab_map"): mw.page_tab_map[key] = page

    def _on_upper_page_saved(self, payload: dict):
        src_row = payload.get("source_row")
        if src_row is None: return
        if "table_data" in payload: self._uppercalc_saved_data[src_row] = payload["table_data"]
        calc_bg = QColor("#d8ffcf")
        wb = payload.get("write_back", {})
        for col, val in wb.items():
            it = self.table.item(src_row, int(col))
            if not it:
                it = self._mk_item("", editable=(int(col)!=7))
                self.table.setItem(src_row, int(col), it)
            it.setText(str(val))
            if int(col) == 7: it.setBackground(calc_bg)
        self._auto_fit_main_table_columns()

    def _open_curve_page(self):
        code = self._get_top_value("设施编码") or "XXXX"
        mw = self.window()
        if not hasattr(mw, "tab_widget"): return
        key = f"curve::{code}"
        if key in getattr(mw, "page_tab_map", {}):
            idx = mw.tab_widget.indexOf(mw.page_tab_map[key])
            if idx != -1: mw.tab_widget.setCurrentIndex(idx); return
        page = PlatformWeightCenterCurvePage(code, self._collect_series_for_curve(), mw)
        idx = mw.tab_widget.addTab(page, f"{code}平台重量中心变化曲线")
        if hasattr(mw, "page_tab_map"): mw.page_tab_map[key] = page
        mw.tab_widget.setCurrentIndex(idx)

    def _ensure_demo_files(self):
        os.makedirs(self.data_dir, exist_ok=True)

    def _on_save(self): QMessageBox.information(self, "保存", "数据已保存（模拟）。")

    def _on_export(self):
        path = os.path.join(self.data_dir, "platform_load_information_export.csv")
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(self._columns())
            for r in range(4, self._find_data_end_row()):
                w.writerow([self._cell_text(r, c) for c in range(self.table.columnCount())])
        QMessageBox.information(self, "导出数据", f"已导出：{path}")
