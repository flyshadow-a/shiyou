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
import openpyxl
from typing import List, Tuple, Dict, Optional

from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QComboBox, QLabel,
    QTableWidget, QTableWidgetItem, QScrollArea, QMessageBox,
    QHeaderView, QToolTip, QFileDialog, QGridLayout
)
from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QColor, QFontMetrics

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
            return
    # 若找不到中文字体，则至少保证负号显示正常
    mpl.rcParams['axes.unicode_minus'] = False



class SimpleLineChart(FigureCanvas):
    """一个简单折线图控件（matplotlib 默认样式/颜色）。"""

    _font_inited = False
    def __init__(self, title: str, x: List[float], y: List[float], xlabel: str = "改建次数", ylabel: str = ""):
        if not SimpleLineChart._font_inited:
            _setup_chinese_matplotlib_font()
            SimpleLineChart._font_inited = True
        fig = Figure(figsize=(3.2, 2.2), dpi=100)
        self.ax = fig.add_subplot(111)
        super().__init__(fig)

        self.ax.set_title(title, fontsize=9)
        self.ax.plot(x, y, marker="o")  # 默认蓝色
        self.ax.set_xlabel(xlabel, fontsize=8)
        if ylabel:
            self.ax.set_ylabel(ylabel, fontsize=8)
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
            ("上部组块总重量T", "weight", "t"),
            ("上部组块重心x(m)", "cgx", "m"),
            ("上部组块重心y(m)", "cgy", "m"),
            ("极端工况最大载荷Fx(KN)", "fx", "KN"),
            ("极端工况最大载荷Fy(KN)", "fy", "KN"),
            ("极端工况最大载荷Fz(KN)", "fz", "KN"),
            ("极端工况最大载荷Mx(KN·m)", "mx", "KN·m"),
            ("极端工况最大载荷My(KN·m)", "my", "KN·m"),
            ("极端工况最大载荷Mz(KN·m)", "mz", "KN·m"),
        ]

        for i, (title, key, unit) in enumerate(charts):
            y = self.series.get(key, [])
            # 长度对齐
            if len(y) != len(x):
                y = (y + [0.0] * len(x))[:len(x)]
            canvas = SimpleLineChart(title, x, y, xlabel="改建次数", ylabel=unit)
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

    DEMO_MAIN_CSV = "platform_load_information_demo_strict.csv"
    DEMO_RESULT_CSV = "platform_load_result_demo.csv"

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


    def __init__(self, parent=None):
        super().__init__("", parent)
        self.data_dir = os.path.join(os.getcwd(), "data")

        # === 红色字段 Excel 导入（仅当前行）===
        self.result_excel_path: Optional[str] = None
        self.red_field_mode: str = 'manual'  # 'manual' or 'excel'
        # 从《平台汇总信息样表.xls》加载下拉选项（失败则回退到原 mock 逻辑）
        self._excel_provider = ReadTableXls()
        self._excel_loaded = False
        try:
            self._excel_provider.load()  # 默认路径：data/平台汇总信息样表.xls
            self._excel_loaded = True
        except Exception:
            self._excel_loaded = False



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
                font-weight: bold;
            }
            QPushButton#TopActionBtn:hover { background: #ffb86b; }

            /* 主表 */
            QTableWidget#MainTable {
                background-color: #ffffff;
                gridline-color: #d0d0d0;
                border: 1px solid #2f3a4a;
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
        # 顶部下拉条（样式与“平台基本信息”一致：DropdownBar）
                # 顶部下拉条：选项从《平台汇总信息样表.xls》提取（若读取失败则用内置 mock）
        def _opts(field_cn: str, fallback_default: str):
            if getattr(self, "_excel_loaded", False):
                opts = self._excel_provider.options_for(field_cn)
                if opts:
                    return opts, self._excel_provider.default_for(field_cn, fallback_default)
            # fallback
            return self._mock_top_options(field_cn, fallback_default), fallback_default

        fields = []
        for key, label, fallback in [
            ("branch",        "分公司",   "湛江分公司"),
            ("op_company",    "作业公司", "文昌油田群作业公司"),
            ("oilfield",      "油气田",   "文昌19-1油田"),
            ("facility_code", "设施编码", "WC19-1WHPC"),
            ("facility_name", "设施名称", "文昌19-1WHPC井口平台"),
            ("facility_type", "设施类型", "平台"),
            ("category",      "分类",     "井口平台"),
            ("start_time",    "投产时间", "2013-07-15"),
            ("design_life",   "设计年限", "15"),
        ]:
            opts, default = _opts(label, fallback)
            fields.append({"key": key, "label": label, "options": opts, "default": default})

        self.dropdown_bar = DropdownBar(fields, parent=self)
        self.dropdown_bar.valueChanged.connect(self._on_top_key_changed)
        top_layout.addWidget(self.dropdown_bar, 1)

        btn_widget = QWidget()
        btn_widget.setFixedWidth(180)
        btn_col = QVBoxLayout(btn_widget)
        btn_col.setContentsMargins(0, 0, 0, 0)
        btn_col.setSpacing(6)

        self.btn_save = QPushButton("保存")
        self.btn_export = QPushButton("导出数据")
        self.btn_import_result = QPushButton("读取结果文件")
        # 红色字段：手动输入 / Excel导入（不影响原有CSV读取结果文件功能）
        self.red_field_mode_combo = QComboBox()
        self.red_field_mode_combo.addItems(['红色字段：手动输入', '红色字段：Excel导入'])
        self.red_field_mode_combo.setMinimumHeight(32)
        self.red_field_mode_combo.setToolTip('仅控制红色字段(Fx~Mz、操作工况、极端工况)的数据来源：手动输入或从Excel导入到当前行')

        self.btn_pick_excel_result = QPushButton('选择结果Excel')
        self.btn_pick_excel_result.setMinimumWidth(150)
        self.btn_pick_excel_result.setMinimumHeight(32)

        self.btn_import_excel_result = QPushButton('导入Excel到当前行')
        self.btn_import_excel_result.setMinimumWidth(150)
        self.btn_import_excel_result.setMinimumHeight(32)
        self.btn_curve = QPushButton("重量中心变化曲线")

        for b in (self.btn_save, self.btn_export, self.btn_import_result, self.btn_curve):
            b.setObjectName("TopActionBtn")
        # 避免右侧按钮被挤压：统一设置最小尺寸
        for b in (self.btn_save, self.btn_export, self.btn_import_result, self.btn_curve):
            b.setMinimumWidth(150)
            b.setMinimumHeight(32)


        self.btn_save.clicked.connect(self._on_save)
        self.btn_export.clicked.connect(self._on_export)
        self.btn_import_result.clicked.connect(self._on_import_result)
        self.red_field_mode_combo.currentIndexChanged.connect(self._on_red_field_mode_changed)
        self.btn_pick_excel_result.clicked.connect(self._pick_result_excel)
        self.btn_import_excel_result.clicked.connect(self._import_excel_to_current_row)
        self.btn_curve.clicked.connect(self._open_curve_page)

        btn_col.addWidget(self.btn_save)
        btn_col.addWidget(self.btn_export)
        btn_col.addStretch(1)
        top_layout.addWidget(btn_widget, 0)
        self.main_layout.addWidget(top_wrap, 0)

        # 滚动区：主表
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        self.main_layout.addWidget(scroll, 1)

        container = QWidget()
        scroll.setWidget(container)
        root = QVBoxLayout(container)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        self.table = self._build_main_table_skeleton()
        self.table.setObjectName("MainTable")

        # 主表允许编辑（但我们会用 item flags 精细控制哪些格可编辑）
        self.table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.SelectedClicked | QTableWidget.EditKeyPressed)

        # 点击“上部组块总操作重量/重心”单元格：跳转到分项目计算表编辑并回填
        self.table.cellClicked.connect(self._on_main_cell_clicked)

        root.addWidget(self.table, 1)

        # 右下角按钮：放在主表格下方右侧两行（读取结果文件 / 重量中心变化曲线）
        bottom_btn_wrap = QWidget()
        bottom_btn_lay = QVBoxLayout(bottom_btn_wrap)
        bottom_btn_lay.setContentsMargins(0, 0, 0, 0)
        bottom_btn_lay.setSpacing(6)
        bottom_btn_lay.addWidget(self.btn_import_result)
        bottom_btn_lay.addWidget(self.btn_curve)
        root.addWidget(bottom_btn_wrap, 0, Qt.AlignRight)

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
        - 同步回填主表所属信息区（字段名用中文）
        """
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
        if bold:
            f = it.font()
            f.setBold(True)
            it.setFont(f)
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
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        bg = QColor("#eef2ff")
        red = QColor("#cc0000")

        table.setRowHeight(0, 26)
        table.setRowHeight(1, 26)
        table.setRowHeight(2, 30)
        table.setRowHeight(3, 60)

        # 顶部默认值
        top_defaults = {k: v for k, v in self.TOP_FIELDS}

        # ===== 所属信息两行（无绿色提示）=====
        # 每行 3 块：7 + 6 + 6 = 19
        # row0：所属分公司 / 所属作业单元 / 所属油气田(田)
        self._set_meta_double(table, 0, 0, total_span=7, label_span=2,
                              label="所属分公司", value=top_defaults.get("分公司", ""), field_key="分公司", bg=bg)
        self._set_meta_double(table, 0, 7, total_span=6, label_span=2,
                              label="所属作业单元", value=top_defaults.get("作业公司", ""), field_key="作业公司", bg=bg)
        self._set_meta_double(table, 0, 13, total_span=6, label_span=2,
                              label="所属油气田\n(田)", value=top_defaults.get("油气田", ""), field_key="油气田", bg=bg)

        # row1：设施名称 / 投产时间 / 设计年限
        self._set_meta_double(table, 1, 0, total_span=7, label_span=2,
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
        table.setItem(2, 15, self._mk_item("桩基承载力安全\n系数（最小）", bold=True, bg=bg))

        table.setSpan(2, 17, 2, 1)
        table.setItem(2, 17, self._mk_item("是否整体\n评估", bold=True, bg=bg))
        table.setSpan(2, 18, 2, 1)
        table.setItem(2, 18, self._mk_item("评估机构", bold=True, bg=bg))

        # ===== 子表头（row3）=====
        for i in range(1,9):
            table.setSpan(2, i, 2, 1)
        table.setItem(2, 1, self._mk_item("改扩建项\n目名称", bold=True, bg=bg))
        table.setItem(2, 2, self._mk_item("改扩建时\n间", bold=True, bg=bg))
        table.setItem(2, 3, self._mk_item("改扩建内\n容", bold=True, bg=bg))

        table.setItem(2, 4, self._mk_item("上部组块\n总操作\n重量,MT", bold=True, bg=bg))
        table.setItem(2, 5, self._mk_item("上部组块\n不可\n超越重量,MT", bold=True, bg=bg))
        table.setItem(2, 6, self._mk_item("重量变化,\nMT", bold=True, bg=bg))
        table.setItem(2, 7, self._mk_item("上部组块\n重心 x,y,z,\nm", bold=True, bg=bg))
        table.setItem(2, 8, self._mk_item("上部组块重心\n不可超越\n半径,m", bold=True, bg=bg))

        # 红色字段（严格：Mz 纵向显示）
        fx_headers = [
            ("Fx,KN", "Fx,KN"),
            ("Fy,KN", "Fy,KN"),
            ("Fz,KN", "Fz,KN"),
            ("Mx,KN·m", "Mx,KN·m"),
            ("My,KN·m", "My,KN·m"),
            ("Mz,KN·m", "M\nz\n,\nK\nN\n·\nm"),
        ]
        red_cols = list(range(9, 15))
        for (src, shown), c in zip(fx_headers, red_cols):
            txt = shown.replace(",", "\n") if src != "Mz,KN·m" else shown
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

        # 写入数据（从 base_rows 开始），并设置可编辑
        for i, row in enumerate(rows):
            rr = base_rows + i
            for c, val in enumerate(row):
                # 数据区：允许编辑
                # 主表中“上部组块总操作重量/重心”不允许直接编辑，需跳转到分项目计算表
                editable = (c not in (4, 7))
                it = self._mk_item(val, editable=editable)

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
                    editable = (base_rows <= r < data_end) and (c not in (4, 7))
                    self.table.setItem(r, c, self._mk_item("", bg=bg, editable=editable))

    # ---------------- 结果文件读取接口 ----------------
    # === 红色字段 Excel 导入模式（仅当前行）===
    def _on_red_field_mode_changed(self, idx: int):
        # 0=手动输入, 1=Excel导入
        self.red_field_mode = 'manual' if idx == 0 else 'excel'
        # Excel模式下：导入按钮可用；手动模式下：禁用导入
        self.btn_pick_excel_result.setEnabled(self.red_field_mode == 'excel')
        self.btn_import_excel_result.setEnabled(self.red_field_mode == 'excel')
        self._apply_red_fields_editability()

    def _apply_red_fields_editability(self):
        # 红色字段列：9..14 Fx~Mz, 15 操作工况, 16 极端工况（与你表头绘制保持一致）
        red_cols = list(range(9, 17))
        base_rows = 4
        data_end = self._find_data_end_row()
        for r in range(base_rows, data_end):
            for c in red_cols:
                it = self.table.item(r, c)
                if it is None:
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
        default_path = self.result_excel_path or self.data_dir
        path, _ = QFileDialog.getOpenFileName(self, '选择结果文件（Excel）', default_path, 'Excel Files (*.xlsx *.xlsm);;All Files (*)')
        if path:
            self.result_excel_path = path

    def _import_excel_to_current_row(self):
        if self.red_field_mode != 'excel':
            QMessageBox.information(self, '提示', '请先将“红色字段模式”切换为 Excel导入。')
            return
        if not self.result_excel_path:
            QMessageBox.information(self, '提示', '请先点击“选择结果Excel”。')
            return
        row = self.table.currentRow()
        base_rows = 4
        data_end = self._find_data_end_row()
        if row < base_rows or row >= data_end:
            QMessageBox.information(self, '提示', '请先在主表数据区选中一行（非表头/说明区）。')
            return
        try:
            values = self._read_result_excel_generic(self.result_excel_path)
            if not values:
                QMessageBox.warning(self, '导入失败', '未在Excel中解析到 Fx/Fy/Fz/Mx/My/Mz/操作工况/极端工况 字段。')
                return
            self._apply_excel_values_to_row(row, values)
            QMessageBox.information(self, '完成', '已导入Excel数据到当前行（红色字段）。')
        except Exception as e:
            QMessageBox.warning(self, '导入失败', str(e))

    def _apply_excel_values_to_row(self, row: int, values: Dict[str, object]):
        keys = ['Fx', 'Fy', 'Fz', 'Mx', 'My', 'Mz', '操作工况', '极端工况']
        cols = [9, 10, 11, 12, 13, 14, 15, 16]
        for k, c in zip(keys, cols):
            v = values.get(k, '')
            it = self.table.item(row, c)
            if it is None:
                it = self._mk_item('', editable=False)
                self.table.setItem(row, c, it)
            it.setText('' if v is None else str(v))

    def _read_result_excel_generic(self, path: str) -> Dict[str, object]:
        """通用Excel解析（没有样例文件前的兼容方案）：
        A) 第一行含字段名(Fx/Fy/.../操作工况/极端工况)，取第二行值；
        B) 表内出现字段名单元格，取右侧(优先)或下方。
        """
        wb = openpyxl.load_workbook(path, data_only=True)
        ws = wb.active
        keys = ['Fx', 'Fy', 'Fz', 'Mx', 'My', 'Mz', '操作工况', '极端工况']
        result: Dict[str, object] = {}
        headers: Dict[str, int] = {}
        for c in range(1, ws.max_column + 1):
            v = ws.cell(1, c).value
            if isinstance(v, str):
                v = v.strip()
                if v in keys:
                    headers[v] = c
        if headers:
            for k, c in headers.items():
                result[k] = ws.cell(2, c).value
            return result
        for r in range(1, ws.max_row + 1):
            for c in range(1, ws.max_column + 1):
                v = ws.cell(r, c).value
                if isinstance(v, str):
                    v = v.strip()
                    if v in keys:
                        right = ws.cell(r, c + 1).value if c + 1 <= ws.max_column else None
                        down = ws.cell(r + 1, c).value if r + 1 <= ws.max_row else None
                        result[v] = right if right is not None else down
        return result

    def _on_import_result(self):
        """读取结果文件：
        - 如果选择的是 Excel（.xlsx/.xlsm），则按“导入当前行”的方式只写入当前选中行的红色字段；
        - 如果选择的是 CSV，则沿用你原有的“按序号匹配多行回填”的逻辑（不改原功能）。
        """
        default_path = os.path.join(self.data_dir, self.DEMO_RESULT_CSV)
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择结果文件（CSV/Excel）",
            default_path,
            "CSV Files (*.csv);;Excel Files (*.xlsx *.xlsm);;All Files (*)"
        )
        if not path:
            return

        ext = os.path.splitext(path)[1].lower()
        try:
            if ext in [".xlsx", ".xlsm", ".xls"]:
                # Excel：只导入当前行（红色字段）
                row = self.table.currentRow()
                base_rows = 4
                data_end = self._find_data_end_row()
                if row < base_rows or row >= data_end:
                    QMessageBox.information(self, "提示", "请先在主表数据区选中一行（非表头/说明区）。")
                    return
                values = self._read_result_excel_generic(path)
                if not values:
                    QMessageBox.warning(self, "读取失败", "未在Excel中解析到 Fx/Fy/Fz/Mx/My/Mz/操作工况/极端工况 字段。")
                    return
                self._apply_excel_values_to_row(row, values)
                QMessageBox.information(self, "读取结果文件", "已从Excel导入并写入当前行（红色字段）。")
            else:
                # CSV：保留原逻辑（按序号匹配全表回填）
                self._apply_result_file(path)
                QMessageBox.information(self, "读取结果文件", "结果文件已回填到红色字段列。")
        except Exception as e:
            QMessageBox.warning(self, "读取失败", f"读取或解析失败：{e}")

    def _apply_result_file(self, csv_path: str):
        """
        结果文件格式（CSV，含表头）：
            序号,Fx,Fy,Fz,Mx,My,Mz,操作工况,极端工况
        其中“序号”用于匹配主表数据区的序号列（0/1/2/3...）
        """
        mapping: Dict[str, Dict[str, str]] = {}
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            required = ["序号", "Fx", "Fy", "Fz", "Mx", "My", "Mz", "操作工况", "极端工况"]
            for k in required:
                if k not in reader.fieldnames:
                    raise ValueError(f"缺少字段：{k}（需要：{required}）")

            for row in reader:
                seq = str(row.get("序号", "")).strip()
                if not seq:
                    continue
                mapping[seq] = row

        base_rows = 4
        data_end = self._find_data_end_row()

        red = QColor("#cc0000")
        red_col_map = {
            "Fx": 9, "Fy": 10, "Fz": 11, "Mx": 12, "My": 13, "Mz": 14,
            "操作工况": 15, "极端工况": 16
        }

        for r in range(base_rows, data_end):
            it_seq = self.table.item(r, 0)
            if it_seq is None:
                continue
            seq = it_seq.text().strip()
            if seq not in mapping:
                continue

            src = mapping[seq]
            for key, col in red_col_map.items():
                val = str(src.get(key, "")).strip()
                it = self.table.item(r, col)
                if it is None:
                    it = self._mk_item(val, editable=True)
                    self.table.setItem(r, col, it)
                else:
                    it.setText(val)
                it.setForeground(red)

    # ---------------- 曲线页面：从主表数据生成 ----------------
    def _collect_series_for_curve(self) -> Dict[str, List[float]]:
        base_rows = 4
        data_end = self._find_data_end_row()

        def to_float(s: str) -> Optional[float]:
            try:
                return float(str(s).strip())
            except Exception:
                return None

        idxs: List[float] = []
        weight: List[float] = []
        cgx: List[float] = []
        cgy: List[float] = []
        fx: List[float] = []
        fy: List[float] = []
        fz: List[float] = []
        mx: List[float] = []
        my: List[float] = []
        mz: List[float] = []

        for r in range(base_rows, data_end):
            seq_item = self.table.item(r, 0)
            if seq_item is None or not seq_item.text().strip():
                continue
            # 只要是数字序号就纳入
            try:
                _ = int(float(seq_item.text().strip()))
            except Exception:
                continue

            idxs.append(len(idxs))  # x轴用改建次数：0,1,2,...

            w = to_float(self._cell_text(r, 4))  # 操作重量
            weight.append(w if w is not None else 0.0)

            xyz = self._cell_text(r, 7)
            x, y = 0.0, 0.0
            parts = [p.strip() for p in str(xyz).split(",")]
            if len(parts) >= 2:
                x = to_float(parts[0]) or 0.0
                y = to_float(parts[1]) or 0.0
            cgx.append(x)
            cgy.append(y)

            fx.append(to_float(self._cell_text(r, 9)) or 0.0)
            fy.append(to_float(self._cell_text(r, 10)) or 0.0)
            fz.append(to_float(self._cell_text(r, 11)) or 0.0)
            mx.append(to_float(self._cell_text(r, 12)) or 0.0)
            my.append(to_float(self._cell_text(r, 13)) or 0.0)
            mz.append(to_float(self._cell_text(r, 14)) or 0.0)

        return {
            "idx": idxs,
            "weight": weight, "cgx": cgx, "cgy": cgy,
            "fx": fx, "fy": fy, "fz": fz,
            "mx": mx, "my": my, "mz": mz
        }

    def _cell_text(self, row: int, col: int) -> str:
        it = self.table.item(row, col)
        return it.text() if it else ""

    # ---------------- 点击重量/重心：跳转到分项目计算表并回填 ----------------
    def _on_main_cell_clicked(self, row: int, col: int):
        base_rows = 4
        data_end = self._find_data_end_row()

        # 仅数据区有效
        if not (base_rows <= row < data_end):
            return

        # 仅“上部组块总操作重量/重心”两列触发跳转（与示意图一致）
        if col not in (4, 7):
            return

        self._open_upper_block_subproject_page(src_row=row)

    def _open_upper_block_subproject_page(self, src_row: int):
        mw = self.window()
        if not hasattr(mw, "tab_widget"):
            QMessageBox.information(self, "提示", "未检测到主窗口Tab组件，无法打开分项目计算表页面。")
            return

        # 去重：同一行只开一个
        key = f"uppercalc::{src_row}"
        if hasattr(mw, "page_tab_map") and key in mw.page_tab_map:
            w = mw.page_tab_map[key]
            idx = mw.tab_widget.indexOf(w)
            if idx != -1:
                mw.tab_widget.setCurrentIndex(idx)
                return

        # 行上下文：用于回填到主表的定位
        row_data = {c: (self.table.item(src_row, c).text() if self.table.item(src_row, c) else "")
                    for c in range(self.table.columnCount())}

        page = UpperBlockSubprojectCalculationTablePage(main_window=mw, parent=mw)
        page.set_context(source_row=src_row, source_row_data=row_data)
        page.saved.connect(self._on_upper_page_saved)

        # tab 标题：优先展示改扩建项目名称
        proj = row_data.get(1, "") or f"序号{row_data.get(0, src_row)}"
        title = f"{proj}-上部组块分项目计算表"

        idx = mw.tab_widget.addTab(page, title)
        mw.tab_widget.setCurrentIndex(idx)
        if hasattr(mw, "page_tab_map"):
            mw.page_tab_map[key] = page

    def _on_upper_page_saved(self, payload: dict):
        """子页面保存后回填主表。

        兼容两种 payload：
        1) 新版（推荐）：{"source_row": int, "write_back": {4: w, 7: "x,y,z", ...}}
        2) 旧版：{"source_row": int, "op_total_w": ..., "op_cg": ...}
        """
        src_row = payload.get("source_row")
        if src_row is None:
            return

        def _fmt_num(v):
            try:
                fv = float(v)
                return f"{fv:.6f}".rstrip("0").rstrip(".")
            except Exception:
                return str(v) if v is not None else ""

        # ---------- 1) 新版 write_back ----------
        wb = payload.get("write_back")
        if isinstance(wb, dict) and wb:
            for col, val in wb.items():
                try:
                    c = int(col)
                except Exception:
                    continue
                it = self.table.item(src_row, c)
                if it is None:
                    # 由分项目计算表回填的列默认只读
                    it = self._mk_item("", editable=False)
                    self.table.setItem(src_row, c, it)
                it.setText(str(val) if val is not None else "")
            return

        # ---------- 2) 旧版字段 ----------
        op_w = payload.get("op_total_w", "")
        op_cg = payload.get("op_cg", "")

        if isinstance(op_cg, (list, tuple)) and len(op_cg) == 3:
            cg_txt = ",".join(_fmt_num(x) for x in op_cg)
        else:
            cg_txt = str(op_cg) if op_cg is not None else ""

        it_w = self.table.item(src_row, 4)
        if it_w is None:
            it_w = self._mk_item("", editable=False)
            self.table.setItem(src_row, 4, it_w)
        it_w.setText(_fmt_num(op_w))

        it_cg = self.table.item(src_row, 7)
        if it_cg is None:
            it_cg = self._mk_item("", editable=False)
            self.table.setItem(src_row, 7, it_cg)
        it_cg.setText(cg_txt)



    def _open_curve_page(self):
        facility_code = self._get_top_value("设施编码") or "XXXX"
        title = f"{facility_code}平台重量中心变化曲线"
        series = self._collect_series_for_curve()

        mw = self.window()
        if hasattr(mw, "tab_widget"):
            # 去重：同一个设施编码只开一个
            key = f"curve::{facility_code}"
            if hasattr(mw, "page_tab_map") and key in mw.page_tab_map:
                w = mw.page_tab_map[key]
                idx = mw.tab_widget.indexOf(w)
                if idx != -1:
                    mw.tab_widget.setCurrentIndex(idx)
                    return

            page = PlatformWeightCenterCurvePage(facility_code, series, mw)
            idx = mw.tab_widget.addTab(page, title)
            mw.tab_widget.setCurrentIndex(idx)
            if hasattr(mw, "page_tab_map"):
                mw.page_tab_map[key] = page
        else:
            QMessageBox.information(self, "提示", "未检测到主窗口Tab组件，无法打开曲线页面。")

    # ---------------- demo files ----------------
    def _ensure_demo_files(self):
        os.makedirs(self.data_dir, exist_ok=True)
        main_path = os.path.join(self.data_dir, self.DEMO_MAIN_CSV)
        if not os.path.exists(main_path):
            cols = self._columns()
            rows = self._generate_mock_rows(n=7, seed=202505)
            with open(main_path, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(cols)
                w.writerows(rows)

        # 结果文件 demo（红色字段）
        res_path = os.path.join(self.data_dir, self.DEMO_RESULT_CSV)
        if not os.path.exists(res_path):
            self._generate_demo_result_csv(res_path, n=7, seed=7788)

    def _generate_demo_result_csv(self, out_path: str, n: int = 7, seed: int = 0):
        rnd = random.Random(seed)
        with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["序号", "Fx", "Fy", "Fz", "Mx", "My", "Mz", "操作工况", "极端工况"])
            # 生成 0..(n-1) 对应主表“序号”
            for i in range(n):
                fx = rnd.uniform(9000, 18000)
                fy = rnd.uniform(9000, 18000)
                fz = rnd.uniform(9000, 18000)
                mx = rnd.uniform(190000, 220000)
                my = rnd.uniform(190000, 220000)
                mz = rnd.uniform(190000, 220000)
                op = rnd.uniform(1.10, 2.60)
                ex = rnd.uniform(1.10, 2.60)
                w.writerow([
                    i,
                    f"{fx:.2f}", f"{fy:.2f}", f"{fz:.2f}",
                    f"{mx:.2f}", f"{my:.2f}", f"{mz:.2f}",
                    f"{op:.2f}", f"{ex:.2f}"
                ])

    def _generate_mock_rows(self, n: int = 7, seed: int = 0) -> List[List[str]]:
        rnd = random.Random(seed)
        rows: List[List[str]] = []

        # 先放两行：0/1（我们后面会在 _apply_data 替换成“提示行”，但这里仍生成占位）
        for i in range(2):
            rows.append([""] * len(self._columns()))

        # 从 2 开始生成真实数据
        for i in range(2, n):
            mod_type = rnd.choice(["新增设备", "扩建", "改造加固"])
            mod_time = f"20{rnd.randint(10, 23):02d}-{rnd.randint(1, 12):02d}"
            mod_content = rnd.choice(["新增井口设备", "生活楼扩建", "甲板加固", "新增工艺模块"])

            w_total = rnd.randint(5000, 18000)
            cg_total = rnd.uniform(8000, 26000)
            dw = rnd.uniform(-120, 320)
            # 为了曲线更像截图，x、y 做成随次数变化
            x = (i - 2) * rnd.uniform(0.4, 0.9)
            y = (i - 2) * rnd.uniform(0.2, 0.7)
            z = rnd.uniform(-0.5, 0.5)
            cg_xyz = f"{x:.2f},{y:.2f},{z:.2f}"
            r_no = rnd.uniform(5.0, 20.0)

            # 红色字段先空（由用户输入/结果文件回填）
            rows.append([
                str(i), mod_type, mod_time, mod_content,
                f"{w_total:.0f}",
                f"{cg_total:.2f}",
                f"{dw:.2f}",
                cg_xyz,
                f"{r_no:.2f}",
                "", "", "", "", "", "",
                "", "",  # 操作工况/极端工况
                rnd.choice(["是", "否"]),
                rnd.choice(["中海油研究总院", "第三方评估机构A", "第三方评估机构B"]),
            ])
        return rows

    # ---------------- actions ----------------
    def _on_save(self):
        QMessageBox.information(self, "保存", "示例：保存（后续接真实存储逻辑）。")

    def _on_export(self):
        export_path = os.path.join(self.data_dir, "platform_load_information_export.csv")
        base_rows = 4
        data_end = self._find_data_end_row()

        if data_end <= base_rows:
            QMessageBox.information(self, "导出数据", "当前无数据可导出。")
            return

        with open(export_path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(self._columns())
            for r in range(base_rows, data_end):
                row = []
                for c in range(self.table.columnCount()):
                    it = self.table.item(r, c)
                    row.append(it.text() if it else "")
                w.writerow(row)

        QMessageBox.information(self, "导出数据", f"已导出：{export_path}")
