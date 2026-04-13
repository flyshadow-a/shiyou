# -*- coding: utf-8 -*-
# pages/new_special_inspection_page.py

import os
import shutil
import datetime
import re
import json
from pathlib import Path
from typing import Any, List
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QWidget,
    QFileDialog, QMessageBox, QScrollArea,
    QAbstractItemView, QSizePolicy, QInputDialog
)
from PyQt5.QtCore import Qt, pyqtSignal

from app_paths import external_path, external_root, first_existing_path
from base_page import BasePage
from file_db_adapter import (
    FileBackendError,
    is_file_db_configured,
    list_storage_paths,
    list_storage_paths_by_prefix,
    soft_delete_storage_path,
    upload_file as upload_file_to_db,
)
from pages.platform_strength_page import InpWireframeView
from pages.upgrade_special_inspection_result_page import UpgradeSpecialInspectionResultPage
from special_strategy_runtime import load_base_config, load_latest_strategy_params, run_special_strategy_calculation


class NewSpecialInspectionPage(BasePage):
    """
    新增检测策略打开的页面：
    - 右侧：黑底模型图（仅一个，不重复创建）
    - 左侧：上半（结构模型信息 + 设置倒塌分析结果文件）
           下半（用户设置：风险等级参数 + 按钮）
    - 整体支持滚轮滚动（ScrollArea）
    """

    CATEGORY_MODEL = "model"
    CATEGORY_COLLAPSE = "collapse"
    CATEGORY_FATIGUE = "fatigue"
    strategy_calculated = pyqtSignal(str, object)

    def __init__(self, facility_code: str, parent=None):
        self.facility_code = facility_code
        self._risk_updated = False
        self._latest_run_id: int | None = None
        self.upload_root = external_path("upload", "model_files")
        self.packaged_upload_root = first_existing_path("upload", "model_files")
        self._collapse_static_demo = False
        self._default_params = self._load_default_params()

        # 页面仅展示“系统文件库”记录（当前用 upload/model_files 代替数据库）
        self.model_files: List[str] = []
        self.collapse_files: List[str] = []
        self.collapse_demo_files: List[str] = []
        self.fatigue_result_files: List[str] = []
        self.fatigue_input_files: List[str] = []

        super().__init__("", parent)
        self._build_ui()
        self._reload_system_files_from_backend()

    def _params_json_path(self) -> Path | None:
        base = Path(__file__).resolve().parent / "output_special_strategy"
        mapping = {
            "WC19-1D": base / "wc19_1d_calc_params.json",
            "WC9-7": base / "wc9_7_calc_params.json",
        }
        return mapping.get((self.facility_code or "").strip().upper())

    def _load_default_params(self) -> dict:
        try:
            return load_latest_strategy_params(self.facility_code)
        except Exception:
            path = self._params_json_path()
            if not path or not path.exists():
                return {}
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                return {}

    @staticmethod
    def _fmt_default_value(value) -> str:
        if value is None:
            return ""
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    def _default_model_param_rows(self) -> list[tuple[str, str]]:
        raw = self._default_params or {}
        return [
            ("构件直线夹角容许误差(度)", self._fmt_default_value(raw.get("x_angle_deviation", 15))),
            ("腿柱节点直径最小值(mm)", self._fmt_default_value(raw.get("min_leg_od", 509))),
            ("Work Point Z(m)", self._fmt_default_value(raw.get("wp_z", 10))),
            ("腿柱数量", self._fmt_default_value(raw.get("no_legs", 4))),
        ]

    def _default_work_points(self) -> list[tuple[int, str, str]]:
        points = list(self._default_params.get("work_points") or [])
        if not points:
            points = [(-10, -8), (-10, 8), (10, -8), (10, 8)]
        rows: list[tuple[int, str, str]] = []
        for idx, pair in enumerate(points, start=1):
            x, y = pair if isinstance(pair, (list, tuple)) and len(pair) >= 2 else ("", "")
            rows.append((idx, self._fmt_default_value(x), self._fmt_default_value(y)))
        return rows

    def _default_risk_specs(self) -> list[dict[str, Any]]:
        raw = self._default_params or {}
        return [
            {
                "label": "生命安全等级",
                "key": "life_safety_level",
                "value": self._fmt_default_value(raw.get("life_safety_level", "S-2")),
                "description": "有人可撤离。有人居住的平台，在极端情况下人员可以实施撤离的情况。",
                "numeric": False,
                "integer": False,
                "editable": True,
            },
            {
                "label": "失效后果等级",
                "key": "failure_consequence_level",
                "value": self._fmt_default_value(raw.get("failure_consequence_level", "C-1")),
                "description": "高后果。发生失效时有可能发生油气泄露的平台；包括失效时不具备关停油气生产、储油或切断主要输油管道能力的平台，以及水深>=120米的平台。",
                "numeric": False,
                "integer": False,
                "editable": True,
            },
            {
                "label": "平台整体暴露等级",
                "key": "global_level_tag",
                "value": self._fmt_default_value(raw.get("global_level_tag", "L-1")),
                "description": "",
                "numeric": False,
                "integer": False,
                "editable": True,
            },
            {
                "label": "平台海域",
                "key": "region",
                "value": self._fmt_default_value(raw.get("region", "中国南海")),
                "description": "",
                "numeric": False,
                "integer": False,
                "editable": True,
            },
            {
                "label": "A",
                "key": "collapse_a_const",
                "value": self._fmt_default_value(raw.get("collapse_a_const", 0.272)),
                "description": "",
                "numeric": True,
                "integer": False,
                "editable": True,
            },
            {
                "label": "B",
                "key": "collapse_b_const",
                "value": self._fmt_default_value(raw.get("collapse_b_const", 0.158)),
                "description": "",
                "numeric": True,
                "integer": False,
                "editable": True,
            },
            {
                "label": "已服役时间（年）",
                "key": "served_years",
                "value": self._fmt_default_value(raw.get("served_years", 1)),
                "description": "",
                "numeric": True,
                "integer": True,
                "editable": True,
            },
            {
                "label": "设计寿命",
                "key": "design_life",
                "value": self._fmt_default_value(raw.get("design_life", 26)),
                "description": "",
                "numeric": True,
                "integer": True,
                "editable": True,
            },
        ]

    def _build_ui(self):
        # 整页浅蓝灰背景
        self.setStyleSheet("""
            QWidget { 
                background: #e6eef7; 
                font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
            }
            QFrame#Card {
                background: #e6eef7;
                border: 1px solid #c7d2e3;
            }
            QLabel#SectionTitle {
                font-weight: bold;
                color: #2b2b2b;
                font-size: 12pt;
            }
            QLabel#RedSectionTitle {
                font-weight: bold;
                color: #d10000;
                font-size: 12pt;
            }
            QPushButton#ActionBtn {
                background: #00a0d6;
                color: white;
                border: 1px solid #007aa3;
                border-radius: 4px;
                padding: 4px 12px;
                min-height: 34px;
                font-size: 12pt;
                font-weight: bold;
            }
            QPushButton#ActionBtn:hover { background: #00b6f2; }

            QPushButton#BigBlueBtn {
                background: #00a0d6;
                color: black;
                border: 1px solid #0a5f7a;
                border-radius: 6px;
                min-height: 50px;
                font-size: 12pt;
                font-weight: bold;
            }
            QPushButton#BigBlueBtn:hover { background: #00b6f2; }

            QTableWidget {
                background: #ffffff;
                gridline-color: #d0d0d0;
                border: 1px solid #d0d0d0;
                font-size: 12pt;
            }
            QHeaderView::section {
                background: #f3f6fb;
                color: #000000;
                border: 1px solid #e6e6e6;
                padding: 6px 6px;
                font-weight: normal;
                font-size: 12pt;
            }
            QLineEdit {
                background: white;
                border: 1px solid #c7d2e3;
                padding: 4px 6px;
                font-size: 12pt;
            }
        """)

        # ===== 关键：用 ScrollArea 包裹“中间主要内容”，滚轮可下滑查看下半部分 =====
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.main_layout.addWidget(scroll, 1)

        container = QWidget()
        scroll.setWidget(container)

        # 依旧是：左（内容） + 右（黑底模型图）
        content = QFrame()
        content.setObjectName("Card")
        lay = QHBoxLayout(content)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(12)

        left = self._build_left_panel()     # 上半 + 下半都在这里
        right = self._build_right_panel()   # 黑底模型图（只创建一次）

        lay.addWidget(left, 3)
        lay.addWidget(right, 2)

        root = QVBoxLayout(container)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(content)

    # ---------------- 左侧：上下拼接 ----------------
    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        v = QVBoxLayout(panel)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)

        # 上半部分：结构模型信息 + 模型文件 + 分析结果文件
        v.addWidget(self._build_model_info_block(), 0)
        self.model_files_block = self._build_model_files_block()
        self.analysis_files_block = self._build_analysis_files_block()
        self.model_files_block.setParent(panel)
        self.analysis_files_block.setParent(panel)
        self.model_files_block.show()
        self.analysis_files_block.show()
        v.addWidget(self.model_files_block, 0)
        v.addWidget(self.analysis_files_block, 0)

        # 下半部分：按你新截图增加的“用户设置/风险等级参数”
        v.addWidget(self._build_risk_level_settings_block(), 1)
        return panel

    # ---------------- 上半：结构模型信息 ----------------
    def _build_model_info_block(self) -> QFrame:
        block = QFrame()
        block.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        block_lay = QVBoxLayout(block)
        block_lay.setContentsMargins(0, 0, 0, 0)
        block_lay.setSpacing(6)

        title_row = QHBoxLayout()
        title = QLabel("结构模型信息")
        title.setObjectName("SectionTitle")

        btn_find = QPushButton("查找节点")
        btn_find.setObjectName("ActionBtn")
        btn_find.clicked.connect(self._on_find_nodes)

        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(btn_find)
        block_lay.addLayout(title_row)

        # 参数表（两列：项目/值，默认从平台参数读取，值列可编辑）
        params = self._default_model_param_rows()
        self.model_param_table = QTableWidget(len(params), 2)
        param_table = self.model_param_table
        param_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        param_table.verticalHeader().setVisible(False)
        param_table.horizontalHeader().setVisible(False)

        for r, (k, val) in enumerate(params):
            item_k = QTableWidgetItem(k)
            item_v = QTableWidgetItem(val)
            item_k.setTextAlignment(Qt.AlignCenter)
            item_v.setTextAlignment(Qt.AlignCenter)
            item_k.setFlags(item_k.flags() & ~Qt.ItemIsEditable)
            item_v.setBackground(Qt.yellow)
            param_table.setItem(r, 0, item_k)
            param_table.setItem(r, 1, item_v)

        self._lock_table_full_display(param_table, row_height=34, show_header=False)
        param_table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
        )
        param_table.setSelectionMode(QAbstractItemView.SingleSelection)

        block_lay.addWidget(param_table)

        # 坐标表（默认从平台参数读取，X/Y 可编辑）
        coords = self._default_work_points()
        self.coord_table = QTableWidget(max(len(coords), 1), 3)
        coord_table = self.coord_table
        coord_table.setHorizontalHeaderLabels(["柱腿工作点坐标", "X坐标（m）", "Y坐标（m）"])
        coord_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        coord_table.verticalHeader().setVisible(False)

        for r, (idx, x, y) in enumerate(coords):
            for c, val in enumerate([idx, x, y]):
                it = QTableWidgetItem(str(val))
                it.setTextAlignment(Qt.AlignCenter)
                if c == 0:
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                else:
                    it.setBackground(Qt.yellow)
                coord_table.setItem(r, c, it)

        self._lock_table_with_scroll(coord_table, row_height=34, visible_rows=min(max(len(coords), 4), 8))
        coord_table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
        )
        coord_table.setSelectionMode(QAbstractItemView.SingleSelection)

        block_lay.addWidget(coord_table)
        block.setMinimumHeight(block.sizeHint().height())
        return block

    # ---------------- 上半：模型文件（新增） ----------------
    def _build_model_files_block(self) -> QFrame:
        block = QFrame()
        block_lay = QVBoxLayout(block)
        block_lay.setContentsMargins(0, 0, 0, 0)
        block_lay.setSpacing(6)

        title_row = QHBoxLayout()
        title = QLabel("设置模型文件")
        title.setObjectName("SectionTitle")

        btn_extract = QPushButton("提取模型")
        btn_extract.setObjectName("ActionBtn")
        btn_extract.clicked.connect(self._on_extract_model_files)

        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(btn_extract)
        block_lay.addLayout(title_row)

        self.model_files_table = QTableWidget(0, 2)
        self.model_files_table.horizontalHeader().setVisible(False)
        self.model_files_table.verticalHeader().setVisible(False)
        self.model_files_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.model_files_table.setColumnWidth(0, 60)
        self.model_files_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.model_files_table.setSelectionBehavior(QAbstractItemView.SelectRows)

        block_lay.addWidget(self.model_files_table, 1)
        return block

    # ---------------- 上半：倒塌分析结果文件 ----------------
    def _build_analysis_files_block(self) -> QFrame:
        block = QFrame()
        block_lay = QVBoxLayout(block)
        block_lay.setContentsMargins(0, 0, 0, 0)
        block_lay.setSpacing(6)

        # 1. 区块主标题与“提取分析”按钮
        title_row = QHBoxLayout()
        title = QLabel("设置分析结果文件")
        title.setObjectName("SectionTitle")

        btn_extract = QPushButton("提取分析")
        btn_extract.setObjectName("ActionBtn")
        btn_extract.clicked.connect(self._on_extract_analysis)

        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(btn_extract)
        block_lay.addLayout(title_row)

        # 2. 初始化核心单表
        self.files_table = QTableWidget(0, 2)
        self.files_table.horizontalHeader().setVisible(False)
        self.files_table.verticalHeader().setVisible(False)

        # 将第 0 列（序号列）设为固定模式，并指定宽度为 60 像素
        self.files_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.files_table.setColumnWidth(0, 60)

        # 第 1 列（路径列）继续保持拉伸，填满剩余空间
        self.files_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.files_table.setSelectionBehavior(QAbstractItemView.SelectRows)

        block_lay.addWidget(self.files_table, 1)

        return block

    # ---------------- 下半：风险等级参数（新增） ----------------
    def _build_risk_level_settings_block(self) -> QFrame:
        block = QFrame()
        v = QVBoxLayout(block)
        v.setContentsMargins(0, 8, 0, 0)
        v.setSpacing(10)
        block.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # 红色标题（对应截图“设置等级参数”）
        title = QLabel("设置等级参数")
        title.setObjectName("RedSectionTitle")
        v.addWidget(title)

        self._risk_param_specs = self._default_risk_specs()
        rows = self._risk_param_specs
        self.risk_param_table = QTableWidget(len(rows), 3)
        table = self.risk_param_table
        table.horizontalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setWordWrap(True)

        for r, spec in enumerate(rows):
            it0 = QTableWidgetItem(str(spec["label"]))
            it1 = QTableWidgetItem(str(spec["value"]))
            it2 = QTableWidgetItem(str(spec["description"]))

            it0.setTextAlignment(Qt.AlignCenter)
            it1.setTextAlignment(Qt.AlignCenter)
            it2.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            it0.setFlags(it0.flags() & ~Qt.ItemIsEditable)
            it2.setFlags(it2.flags() & ~Qt.ItemIsEditable)
            if spec.get("editable", False):
                it1.setBackground(Qt.white)
            else:
                it1.setFlags(it1.flags() & ~Qt.ItemIsEditable)
            table.setItem(r, 0, it0)
            table.setItem(r, 1, it1)
            table.setItem(r, 2, it2)

        highlight = table.item(2, 1)
        if highlight:
            highlight.setBackground(Qt.red)
            highlight.setForeground(Qt.white)
            highlight.setTextAlignment(Qt.AlignCenter)

        table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
        )
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        for r in range(table.rowCount()):
            table.setRowHeight(r, 42 if r < 2 else 34)
        table.setMinimumHeight(360)
        table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        v.addWidget(table, 1)
        # 两个大按钮（对应截图：更新风险等级 / 查看结果）
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        btn_update = QPushButton("更新风险等级")
        btn_update.setObjectName("BigBlueBtn")
        btn_update.setFixedWidth(200)
        btn_update.clicked.connect(self._on_update_risk_level)

        btn_view = QPushButton("查看结果")
        btn_view.setObjectName("BigBlueBtn")
        btn_view.setFixedWidth(200)
        btn_view.clicked.connect(self._on_view_result)

        btn_row.addWidget(btn_update)
        btn_row.addWidget(btn_view)
        btn_row.addStretch(1)

        v.addLayout(btn_row, 0)

        return block

    # ---------------- 右侧：黑底模型图（只保留一个） ----------------
    def _build_right_panel(self) -> QFrame:
        panel = QFrame()
        v = QVBoxLayout(panel)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        title = QLabel("结构模型线框预览（复用平台强度页）")
        title.setObjectName("SectionTitle")
        v.addWidget(title)

        hint = QLabel("左键拖动平移，滚轮缩放，右键拖动旋转，双击复位")
        hint.setStyleSheet("color:#5d6f85; font-size:14px;")
        v.addWidget(hint, 0)

        self.inp_path_label = QLabel("")
        self.inp_path_label.setWordWrap(True)
        self.inp_path_label.setStyleSheet("color:#4a5b70; font-size:14px;")
        v.addWidget(self.inp_path_label, 0)

        img_frame = QFrame()
        img_frame.setStyleSheet("background: #ffffff; border: 1px solid #c7d2e3;")
        img_lay = QVBoxLayout(img_frame)
        img_lay.setContentsMargins(6, 6, 6, 6)

        self.inp_view = InpWireframeView(img_frame)
        self.inp_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        img_lay.addWidget(self.inp_view, 1)

        v.addWidget(img_frame, 1)
        return panel

    # ---------------- actions ----------------
    def _on_find_nodes(self):
        QMessageBox.information(self, "查找节点", f"这里执行：根据 {self.facility_code} 的模型/参数查找节点（待接算法）。")

    def _on_extract_analysis(self):
        self._reload_system_files_from_backend()
        QMessageBox.information(self, "提取分析", "已从系统文件库提取并刷新分析结果文件。")

    def _on_extract_model_files(self):
        self.model_files = self._db_fetch_file_records(self.CATEGORY_MODEL)
        self._refresh_model_files_table()
        self._refresh_model_preview()
        QMessageBox.information(self, "提取模型", "已从系统文件库提取并刷新模型文件。")

    def _on_update_risk_level(self):
        if not self._validate_fatigue_groups():
            return
        try:
            result_bundle = run_special_strategy_calculation(
                self.facility_code,
                param_overrides=self._collect_runtime_overrides(),
                input_overrides=self._collect_runtime_input_overrides(),
            )
        except Exception as exc:
            QMessageBox.warning(self, "更新风险等级失败", f"风险结果计算失败：\n{exc}")
            return

        self._risk_updated = True
        state = result_bundle.get("state") if isinstance(result_bundle, dict) else {}
        run_id = state.get("db_run_id") if isinstance(state, dict) else None
        self._latest_run_id = int(run_id) if isinstance(run_id, int) else run_id
        self.strategy_calculated.emit(self.facility_code, self._latest_run_id)
        QMessageBox.information(self, "更新风险等级", "已按当前参数完成风险结果计算。")

    def _validate_fatigue_groups(self) -> bool:
        result_files = [path for path in self.fatigue_result_files if os.path.exists(path)]
        input_files = [path for path in self.fatigue_input_files if os.path.exists(path)]
        if not result_files and not input_files:
            return True
        if not result_files or not input_files:
            QMessageBox.warning(
                self,
                "疲劳文件组不完整",
                "疲劳分析结果文件组和输入文件组需要同时提供。\n如本次不想覆盖默认疲劳配置，请先删除已导入的疲劳文件。",
            )
            return False
        if len(result_files) != len(input_files):
            QMessageBox.warning(
                self,
                "疲劳文件组数量不一致",
                f"当前疲劳结果文件为 {len(result_files)} 个，输入文件为 {len(input_files)} 个，请先调整一致。",
            )
            return False
        try:
            cfg = load_base_config(self.facility_code)
        except Exception:
            cfg = {}
        expected_result_count = len(cfg.get("ftglst", []) or [])
        expected_input_count = len(cfg.get("ftginp", []) or [])
        if expected_result_count and len(result_files) < expected_result_count:
            QMessageBox.warning(
                self,
                "疲劳结果文件不足",
                f"当前平台默认需要至少 {expected_result_count} 个疲劳结果文件，当前仅有 {len(result_files)} 个。",
            )
            return False
        if expected_input_count and len(input_files) < expected_input_count:
            QMessageBox.warning(
                self,
                "疲劳输入文件不足",
                f"当前平台默认需要至少 {expected_input_count} 个疲劳输入文件，当前仅有 {len(input_files)} 个。",
            )
            return False
        return True

    def _on_view_result(self):
        if not self._risk_updated:
            QMessageBox.information(self, "提示", "请先点击“更新风险等级”，再查看结果。")
            return

        mw = self.window()  # ✅比 self.parent() 稳定

        # ✅这里判断/调用你 main.py 里真实存在的方法名
        if mw is not None and hasattr(mw, "open_upgrade_special_inspection_result_tab"):
            mw.open_upgrade_special_inspection_result_tab(self.facility_code, run_id=self._latest_run_id)
            return

        # 兜底：直接加tab
        if mw is not None and hasattr(mw, "tab_widget"):
            page = UpgradeSpecialInspectionResultPage(self.facility_code, mw, run_id=self._latest_run_id)
            idx = mw.tab_widget.addTab(page, f"{self.facility_code}更新风险结果")
            mw.tab_widget.setCurrentIndex(idx)
            return

        QMessageBox.warning(self, "错误", "未找到 MainWindow/tab_widget，无法打开结果页。")

    # ---------------- 文件来源：后续数据库接入接口（先走 upload/model_files） ----------------
    def _db_fetch_file_records(self, category: str, branch: str | None = None) -> List[str]:
        """
        数据库读取接口（预留）：返回系统文件记录。

        后续接数据库时，只需要替换本方法内部实现即可，页面其余逻辑无需改动。
        当前实现：从 upload/model_files 扫描提取。
        """
        if is_file_db_configured():
            try:
                default_rows = list_storage_paths_by_prefix(
                    file_type_code=category,
                    module_code="model_files",
                    logical_path_prefix=self._default_model_logical_prefix(category, branch),
                    facility_code=(self.facility_code or "").strip() or None,
                )
                if default_rows:
                    return default_rows
                legacy_rows = list_storage_paths(
                    file_type_code=category,
                    module_code="special_strategy",
                    logical_path=self._legacy_special_strategy_logical_path(category),
                    facility_code=(self.facility_code or "").strip() or None,
                )
                if legacy_rows:
                    return self._filter_records_by_branch(category, legacy_rows, branch)
            except FileBackendError:
                pass
        return self._fetch_system_files_from_upload(category, branch)

    def _db_store_local_file(self, local_path: str, category: str, branch: str | None = None) -> str:
        """
        本地文件入库接口（预留）：把本地文件上传到系统文件库，返回系统记录路径/标识。

        后续接数据库时，只需要替换本方法内部实现即可，页面其余逻辑无需改动。
        当前实现：复制到 upload/model_files/<facility>/当前模型/.../用户上传 下。
        """
        if is_file_db_configured():
            try:
                row = upload_file_to_db(
                    local_path,
                    file_type_code=category,
                    module_code="model_files",
                    logical_path=self._db_logical_path(category, branch),
                    facility_code=(self.facility_code or "").strip() or None,
                )
                return os.path.normpath(row["storage_path"])
            except FileBackendError:
                pass
        return self._store_local_file_to_upload(local_path, category, branch)

    def _db_soft_delete_file(self, storage_path: str, category: str) -> bool:
        if not is_file_db_configured():
            return False
        try:
            deleted = soft_delete_storage_path(
                storage_path,
                file_type_code=category,
                module_code="model_files",
                facility_code=(self.facility_code or "").strip() or None,
            )
            if deleted:
                return True
            return soft_delete_storage_path(
                storage_path,
                file_type_code=category,
                module_code="special_strategy",
                logical_path=self._legacy_special_strategy_logical_path(category),
                facility_code=(self.facility_code or "").strip() or None,
            )
        except FileBackendError:
            return False

    def _db_logical_path(self, category: str, branch: str | None = None) -> str:
        segment_map = {
            self.CATEGORY_MODEL: "当前模型/结构模型/用户上传",
            self.CATEGORY_COLLAPSE: "当前模型/倒塌分析/结果/用户上传",
            self.CATEGORY_FATIGUE: f"当前模型/疲劳分析/{'输入' if branch == 'input' else '结果'}/用户上传",
        }
        facility = (self.facility_code or "").strip() or "default_facility"
        tail = segment_map.get(category, "当前模型/其他")
        return f"{facility}/{tail}"

    def _legacy_special_strategy_logical_path(self, category: str) -> str:
        segment_map = {
            self.CATEGORY_MODEL: "当前模型/结构模型",
            self.CATEGORY_COLLAPSE: "当前模型/倒塌分析",
            self.CATEGORY_FATIGUE: "当前模型/疲劳分析",
        }
        facility = (self.facility_code or "").strip() or "default_facility"
        tail = segment_map.get(category, "当前模型/其他")
        return f"{facility}/{tail}"

    def _default_model_logical_prefix(self, category: str, branch: str | None = None) -> str:
        facility = (self.facility_code or "").strip() or "default_facility"
        if category == self.CATEGORY_MODEL:
            tail = "当前模型/结构模型"
        elif category == self.CATEGORY_COLLAPSE:
            tail = "当前模型/倒塌分析"
        elif category == self.CATEGORY_FATIGUE:
            tail = f"当前模型/疲劳分析/{'输入' if branch == 'input' else '结果'}" if branch else "当前模型/疲劳分析"
        else:
            tail = "当前模型"
        return f"{facility}/{tail}"

    def _filter_records_by_branch(self, category: str, records: List[str], branch: str | None) -> List[str]:
        if category != self.CATEGORY_FATIGUE or not branch:
            return records
        return [path for path in records if self._fatigue_branch_for_path(path) == branch]

    def _collect_runtime_overrides(self) -> dict:
        def get_text(table: QTableWidget, row: int, col: int) -> str:
            item = table.item(row, col)
            return item.text().strip() if item is not None else ""

        def parse_number(text: str, *, integer: bool = False):
            raw = (text or "").strip()
            if raw == "":
                return None
            return int(float(raw)) if integer else float(raw)

        overrides: dict[str, Any] = {}

        model_keys = [
            ("x_angle_deviation", False),
            ("min_leg_od", False),
            ("wp_z", False),
            ("no_legs", True),
        ]
        for row, (key, integer) in enumerate(model_keys):
            value = parse_number(get_text(self.model_param_table, row, 1), integer=integer)
            if value is not None:
                overrides[key] = value

        for row, spec in enumerate(getattr(self, "_risk_param_specs", [])):
            key = str(spec.get("key", "")).strip()
            if not key:
                continue
            raw = get_text(self.risk_param_table, row, 1)
            if spec.get("numeric"):
                value = parse_number(raw, integer=bool(spec.get("integer")))
            else:
                value = raw
            if value not in ("", None):
                overrides[key] = value

        work_points: list[list[float]] = []
        for row in range(self.coord_table.rowCount()):
            x_val = parse_number(get_text(self.coord_table, row, 1))
            y_val = parse_number(get_text(self.coord_table, row, 2))
            if x_val is None and y_val is None:
                continue
            if x_val is None or y_val is None:
                raise ValueError("工作点坐标必须成对填写。")
            work_points.append([x_val, y_val])
        if work_points:
            overrides["work_points"] = work_points

        return overrides

    def _collect_runtime_input_overrides(self) -> dict[str, Any]:
        def existing_paths(values: List[str]) -> List[str]:
            out: List[str] = []
            for value in values:
                path = str(value or "").strip()
                if not path or not os.path.exists(path):
                    continue
                out.append(os.path.normpath(path))
            return out

        overrides: dict[str, Any] = {}
        model_candidates = existing_paths(self.model_files)
        if model_candidates:
            overrides["model"] = model_candidates[0]

        collapse_candidates = existing_paths(self.collapse_files)
        if collapse_candidates:
            overrides["clplog"] = collapse_candidates
        fatigue_result_candidates = existing_paths(self.fatigue_result_files)
        fatigue_input_candidates = existing_paths(self.fatigue_input_files)
        if fatigue_result_candidates and fatigue_input_candidates:
            overrides["ftglst"] = fatigue_result_candidates
            overrides["ftginp"] = fatigue_input_candidates
        return overrides

    def _fatigue_branch_for_path(self, path: str) -> str:
        normalized = str(path or "").replace("\\", "/").lower()
        filename = os.path.basename(str(path or "")).lower()
        stem = os.path.splitext(filename)[0]
        ext = os.path.splitext(filename)[1].lower()
        if "/疲劳分析/" in normalized and "/输入/" in normalized:
            return "input"
        if stem.startswith("ftginp"):
            return "input"
        if "/疲劳分析/" in normalized and "/结果/" in normalized:
            return "result"
        if stem.startswith("ftglst") or stem.startswith("wvrinp") or ext in {".wit", ".wjt"}:
            return "result"
        if "/疲劳分析/" in normalized:
            return "result"
        return ""

    def _set_fatigue_groups_from_candidates(self, candidates: List[str]) -> None:
        self.fatigue_result_files = []
        self.fatigue_input_files = []
        for raw_path in candidates:
            path = os.path.normpath(str(raw_path or "").strip())
            if not path:
                continue
            branch = self._fatigue_branch_for_path(path)
            if branch == "input":
                if path not in self.fatigue_input_files:
                    self.fatigue_input_files.append(path)
            else:
                if path not in self.fatigue_result_files:
                    self.fatigue_result_files.append(path)

    def _fetch_system_files_from_upload(self, category: str, branch: str | None = None) -> List[str]:
        search_roots = []
        for root in [self.upload_root, self.packaged_upload_root]:
            if root and os.path.isdir(root) and root not in search_roots:
                search_roots.append(root)

        if not search_roots:
            return []

        ext_map = {
            self.CATEGORY_COLLAPSE: {"clplog", "clplst", "clprst"},
            self.CATEGORY_FATIGUE: {"ftglst", "wvrinp", "wit", "wjt"},
        }

        records = []
        code_lower = (self.facility_code or "").strip().lower()

        for search_root in search_roots:
            for dir_path, _, file_names in os.walk(search_root):
                for fn in file_names:
                    full_path = os.path.normpath(os.path.join(dir_path, fn))
                    full_low = full_path.lower()
                    ext_no_dot = os.path.splitext(fn)[1].lower().lstrip(".")
                    stem = os.path.splitext(fn)[0].lower()

                    keep = False
                    score = 0

                    if category == self.CATEGORY_MODEL:
                        name_score = self._sacinp_name_score(fn)
                        if name_score > 0 and self._scan_model_signature(full_path):
                            keep = True
                            score += name_score
                    else:
                        allow = ext_map.get(category, set())
                        in_special_bucket = f"special_strategy{os.sep}{category}".lower() in full_low
                        if category == self.CATEGORY_FATIGUE and self._fatigue_branch_for_path(full_path):
                            keep = True
                            score += 100
                        elif in_special_bucket or (ext_no_dot in allow):
                            keep = True
                            score += 100

                    if category == self.CATEGORY_FATIGUE and branch:
                        if self._fatigue_branch_for_path(full_path) != branch:
                            keep = False

                    if not keep:
                        continue

                    if code_lower and code_lower in stem:
                        score += 80
                    if code_lower and code_lower in full_low:
                        score += 120

                    try:
                        mtime = os.path.getmtime(full_path)
                    except OSError:
                        mtime = 0.0
                    records.append((score, mtime, full_path))

        records.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [p for _, _, p in records]

    def _store_local_file_to_upload(self, local_path: str, category: str, branch: str | None = None) -> str:
        relative_dir = self._db_logical_path(category, branch).replace("/", os.sep)
        target_dir = os.path.join(self.upload_root, relative_dir)
        os.makedirs(target_dir, exist_ok=True)

        base = os.path.basename(local_path)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = os.path.join(target_dir, f"{stamp}_{base}")
        shutil.copy2(local_path, dest)
        return os.path.normpath(dest)

    def _sacinp_name_score(self, file_name: str) -> int:
        name = (file_name or "").strip().lower()
        if not name:
            return 0

        stem, ext = os.path.splitext(name)
        if stem.startswith("sacinp"):
            return 300
        if ext == ".sacinp":
            return 220
        tokens = [t for t in re.split(r"[^a-z0-9]+", stem) if t]
        if "sacinp" in tokens:
            return 160
        return 0

    def _scan_model_signature(self, file_path: str) -> bool:
        markers_joint = False
        markers_member = False
        encodings = ["utf-8", "utf-8-sig", "gb18030", "gbk", "latin-1"]

        def _scan(fp) -> bool:
            nonlocal markers_joint, markers_member
            for raw in fp:
                line = raw.strip().upper()
                if not line:
                    continue
                if line.startswith("*NODE") or line.startswith("*ELEMENT"):
                    return True
                if line.startswith("JOINT"):
                    markers_joint = True
                elif line.startswith("MEMBER"):
                    markers_member = True
                if markers_joint and markers_member:
                    return True
            return False

        for enc in encodings:
            try:
                with open(file_path, "r", encoding=enc) as f:
                    if _scan(f):
                        return True
            except UnicodeDecodeError:
                continue
            except Exception:
                return False

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return _scan(f)
        except Exception:
            return False

    def _append_unique_path(self, arr: List[str], path: str):
        p = os.path.normpath(path)
        if p in arr:
            arr.remove(p)
        arr.insert(0, p)

    def _pick_system_file_dialog(self, category: str, title: str, branch: str | None = None) -> str:
        candidates = self._db_fetch_file_records(category, branch)
        if not candidates:
            QMessageBox.information(self, "系统导入", "系统文件库中暂无可用文件。")
            return ""

        labels = [f"{idx + 1}. {self._short_path(path)}" for idx, path in enumerate(candidates)]
        picked, ok = QInputDialog.getItem(self, title, "请选择系统文件：", labels, 0, False)
        if not ok or not picked:
            return ""
        idx = labels.index(picked)
        return candidates[idx]

    def _short_path(self, path: str) -> str:
        try:
            rel = os.path.relpath(path, str(external_root()))
            return rel if len(rel) < 140 else f"...{rel[-140:]}"
        except Exception:
            return path

    def _fit_table_height(self, table: QTableWidget):
        total = table.frameWidth() * 2 + 2
        if table.horizontalHeader().isVisible():
            total += table.horizontalHeader().height()
        for r in range(table.rowCount()):
            total += table.rowHeight(r)
        table.setFixedHeight(max(total, 42))

    def _lock_table_full_display(self, table: QTableWidget, row_height: int = 34, show_header: bool = True):
        table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.horizontalHeader().setVisible(show_header)
        if show_header:
            header_height = max(36, table.horizontalHeader().fontMetrics().height() + 16)
            table.horizontalHeader().setMinimumHeight(max(header_height, table.horizontalHeader().minimumHeight()))
        final_row_height = max(row_height, table.fontMetrics().height() + 16)
        for r in range(table.rowCount()):
            table.setRowHeight(r, final_row_height)
        self._fit_table_height(table)

    def _lock_table_with_scroll(self, table: QTableWidget, row_height: int = 34, visible_rows: int = 4):
        table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.horizontalHeader().setVisible(True)
        header_height = max(36, table.horizontalHeader().fontMetrics().height() + 16)
        table.horizontalHeader().setMinimumHeight(max(header_height, table.horizontalHeader().minimumHeight()))

        final_row_height = max(row_height, table.fontMetrics().height() + 16)
        for r in range(table.rowCount()):
            table.setRowHeight(r, final_row_height)

        table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        visible = max(1, min(visible_rows, table.rowCount()))
        total = table.frameWidth() * 2 + 2
        total += table.horizontalHeader().height()
        total += visible * final_row_height
        table.setFixedHeight(max(total, 120))

    def _reload_system_files_from_backend(self):
        self.model_files = self._db_fetch_file_records(self.CATEGORY_MODEL)
        self.collapse_files = self._db_fetch_file_records(self.CATEGORY_COLLAPSE)
        self.collapse_demo_files = self._build_collapse_demo_files(self.collapse_files)
        self._set_fatigue_groups_from_candidates(self._db_fetch_file_records(self.CATEGORY_FATIGUE))

        self._refresh_model_files_table()
        self._refresh_files_table()
        self._refresh_model_preview()

    def _build_collapse_demo_files(self, source: List[str]) -> List[str]:
        fallback = [
            r"D:\SACSW\Strategy\test file\1\clplog",
            r"D:\SACSW\Strategy\test file\2\clplog",
            r"D:\SACSW\Strategy\test file\3\clplog",
        ]

        if source:
            preferred = []
            for p in source:
                ext = os.path.splitext(p)[1].lower().lstrip(".")
                if ext in {"clplog", "clplst", "clprst"}:
                    preferred.append(p)
            if preferred:
                out = preferred[:3]
            else:
                out = source[:3]

            if len(out) < 3:
                out = out + fallback[: (3 - len(out))]
            return out

        return fallback

    # ---------------- 文件动态表格刷新与事件 ----------------
    def _refresh_model_files_table(self):
        self.model_files_table.clearContents()
        self.model_files_table.setRowCount(0)

        self.model_files_table.insertRow(0)
        self.model_files_table.setSpan(0, 0, 1, 2)
        model_buttons = [
            ("本地导入", self._on_add_model_local),
            ("系统导入", self._on_add_model_sys),
            ("删除选中行", self._on_del_model),
        ]
        title_widget = self._create_title_row_widget("设置模型文件", model_buttons)
        self.model_files_table.setCellWidget(0, 0, title_widget)
        self.model_files_table.setRowHeight(0, 38)

        for i, path in enumerate(self.model_files):
            row = i + 1
            self.model_files_table.insertRow(row)

            idx_item = QTableWidgetItem(str(i + 1))
            idx_item.setTextAlignment(Qt.AlignCenter)
            idx_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

            path_item = QTableWidgetItem(self._short_path(path))
            path_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            path_item.setToolTip(path)

            self.model_files_table.setItem(row, 0, idx_item)
            self.model_files_table.setItem(row, 1, path_item)
            self.model_files_table.setRowHeight(row, 32)

        self._fit_table_height(self.model_files_table)

    def _refresh_files_table(self):
        self.files_table.clearContents()
        self.files_table.setRowCount(0)
        self._collapse_row_map: dict[int, int] = {}
        self._fatigue_result_row_map: dict[int, int] = {}
        self._fatigue_input_row_map: dict[int, int] = {}

        collapse_view = self.collapse_demo_files if self._collapse_static_demo else self.collapse_files

        # --- 倒塌分析部分 ---
        self.files_table.insertRow(0)
        self.files_table.setSpan(0, 0, 1, 2)

        col_buttons = [
            ("本地导入", self._on_add_collapse_local),
            ("系统导入", self._on_add_collapse_sys),
            ("删除选中行", self._on_del_collapse)
        ]
        col_title_widget = self._create_title_row_widget("设置倒塌分析结果文件", col_buttons)
        self.files_table.setCellWidget(0, 0, col_title_widget)
        self.files_table.setRowHeight(0, 38)

        for i, path in enumerate(collapse_view):
            row = i + 1
            self.files_table.insertRow(row)

            idx_item = QTableWidgetItem(str(i + 1))
            idx_item.setTextAlignment(Qt.AlignCenter)
            idx_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

            path_item = QTableWidgetItem(self._short_path(path))
            path_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            path_item.setToolTip(path)

            self.files_table.setItem(row, 0, idx_item)
            self.files_table.setItem(row, 1, path_item)
            self.files_table.setRowHeight(row, 32)
            self._collapse_row_map[row] = i

        # --- 疲劳分析结果文件组 ---
        result_header_row = self.files_table.rowCount()
        self.files_table.insertRow(result_header_row)
        self.files_table.setSpan(result_header_row, 0, 1, 2)
        result_buttons = [
            ("本地导入", self._on_add_fatigue_result_local),
            ("系统导入", self._on_add_fatigue_result_sys),
            ("删除选中行", self._on_del_fatigue_result),
        ]
        result_title_widget = self._create_title_row_widget("设置疲劳分析结果文件组", result_buttons)
        self.files_table.setCellWidget(result_header_row, 0, result_title_widget)
        self.files_table.setRowHeight(result_header_row, 38)

        if self.fatigue_result_files:
            for i, path in enumerate(self.fatigue_result_files):
                row = self.files_table.rowCount()
                self.files_table.insertRow(row)

                idx_item = QTableWidgetItem(str(i + 1))
                idx_item.setTextAlignment(Qt.AlignCenter)
                idx_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

                path_item = QTableWidgetItem(self._short_path(path))
                path_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                path_item.setToolTip(path)

                self.files_table.setItem(row, 0, idx_item)
                self.files_table.setItem(row, 1, path_item)
                self.files_table.setRowHeight(row, 32)
                self._fatigue_result_row_map[row] = i
        else:
            row = self.files_table.rowCount()
            self.files_table.insertRow(row)
            self.files_table.setSpan(row, 0, 1, 2)
            empty_widget = QWidget()
            empty_widget.setStyleSheet("background-color: #ffffff;")
            empty_layout = QHBoxLayout(empty_widget)
            empty_layout.setContentsMargins(10, 0, 10, 0)
            empty_label = QLabel("暂未选择疲劳分析结果文件。")
            empty_label.setStyleSheet('color: #666; font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei"; font-size: 12pt;')
            empty_layout.addWidget(empty_label)
            empty_layout.addStretch(1)
            self.files_table.setCellWidget(row, 0, empty_widget)
            self.files_table.setRowHeight(row, 36)

        # --- 疲劳分析输入文件组 ---
        input_header_row = self.files_table.rowCount()
        self.files_table.insertRow(input_header_row)
        self.files_table.setSpan(input_header_row, 0, 1, 2)
        input_buttons = [
            ("本地导入", self._on_add_fatigue_input_local),
            ("系统导入", self._on_add_fatigue_input_sys),
            ("删除选中行", self._on_del_fatigue_input),
        ]
        input_title_widget = self._create_title_row_widget("设置疲劳分析输入文件组", input_buttons)
        self.files_table.setCellWidget(input_header_row, 0, input_title_widget)
        self.files_table.setRowHeight(input_header_row, 38)

        if self.fatigue_input_files:
            for i, path in enumerate(self.fatigue_input_files):
                row = self.files_table.rowCount()
                self.files_table.insertRow(row)

                idx_item = QTableWidgetItem(str(i + 1))
                idx_item.setTextAlignment(Qt.AlignCenter)
                idx_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

                path_item = QTableWidgetItem(self._short_path(path))
                path_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                path_item.setToolTip(path)

                self.files_table.setItem(row, 0, idx_item)
                self.files_table.setItem(row, 1, path_item)
                self.files_table.setRowHeight(row, 32)
                self._fatigue_input_row_map[row] = i
        else:
            row = self.files_table.rowCount()
            self.files_table.insertRow(row)
            self.files_table.setSpan(row, 0, 1, 2)
            empty_widget = QWidget()
            empty_widget.setStyleSheet("background-color: #ffffff;")
            empty_layout = QHBoxLayout(empty_widget)
            empty_layout.setContentsMargins(10, 0, 10, 0)
            empty_label = QLabel("暂未选择疲劳分析输入文件。")
            empty_label.setStyleSheet('color: #666; font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei"; font-size: 12pt;')
            empty_layout.addWidget(empty_label)
            empty_layout.addStretch(1)
            self.files_table.setCellWidget(row, 0, empty_widget)
            self.files_table.setRowHeight(row, 36)

        self._fit_table_height(self.files_table)

    def _on_add_model_local(self):
        fp, _ = QFileDialog.getOpenFileName(self, "选择模型文件", "", "所有文件 (*.*)")
        if not fp:
            return
        try:
            system_path = self._db_store_local_file(fp, self.CATEGORY_MODEL)
        except Exception as e:
            QMessageBox.warning(self, "导入失败", f"本地文件入库失败：\n{e}")
            return

        self._append_unique_path(self.model_files, system_path)
        self._refresh_model_files_table()
        self._refresh_model_preview()
        QMessageBox.information(self, "本地导入", f"文件已入系统库并显示：\n{system_path}")

    def _on_add_model_sys(self):
        chosen = self._pick_system_file_dialog(self.CATEGORY_MODEL, "系统导入模型文件")
        if not chosen:
            return
        self._append_unique_path(self.model_files, chosen)
        self._refresh_model_files_table()
        self._refresh_model_preview()

    def _on_del_model(self):
        selected = self.model_files_table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.warning(self, "提示", "请先在模型文件表中选中要删除的行。")
            return

        rows_to_delete = sorted([idx.row() for idx in selected], reverse=True)
        failed = False
        for r in rows_to_delete:
            if 1 <= r <= len(self.model_files):
                path = self.model_files[r - 1]
                deleted = self._db_soft_delete_file(path, self.CATEGORY_MODEL)
                if is_file_db_configured() and not deleted:
                    failed = True
                    continue
                del self.model_files[r - 1]

        self._refresh_model_files_table()
        self._refresh_model_preview()
        if failed:
            QMessageBox.warning(self, "警告", "部分文件未能同步更新数据库删除状态，已保留在列表中。")

    def _on_add_collapse_local(self):
        if self._collapse_static_demo:
            QMessageBox.information(self, "提示", "当前“设置倒塌分析结果文件”为静态演示模式，已锁定显示。")
            return

        fp, _ = QFileDialog.getOpenFileName(self, "选择倒塌分析结果文件", "", "所有文件 (*.*)")
        if not fp:
            return
        try:
            system_path = self._db_store_local_file(fp, self.CATEGORY_COLLAPSE)
        except Exception as e:
            QMessageBox.warning(self, "导入失败", f"本地文件入库失败：\n{e}")
            return

        self._append_unique_path(self.collapse_files, system_path)
        self._refresh_files_table()

    def _on_add_collapse_sys(self):
        if self._collapse_static_demo:
            QMessageBox.information(self, "提示", "当前“设置倒塌分析结果文件”为静态演示模式，已锁定显示。")
            return

        chosen = self._pick_system_file_dialog(self.CATEGORY_COLLAPSE, "系统导入倒塌分析结果文件")
        if not chosen:
            return
        self._append_unique_path(self.collapse_files, chosen)
        self._refresh_files_table()

    def _on_del_collapse(self):
        if self._collapse_static_demo:
            QMessageBox.information(self, "提示", "当前“设置倒塌分析结果文件”为静态演示模式，已锁定显示。")
            return

        selected = self.files_table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.warning(self, "提示", "请先在表格中点击选中要删除的倒塌文件行。")
            return

        rows_to_delete = sorted([idx.row() for idx in selected], reverse=True)
        failed = False
        for r in rows_to_delete:
            if 1 <= r <= len(self.collapse_files):
                path = self.collapse_files[r - 1]
                deleted = self._db_soft_delete_file(path, self.CATEGORY_COLLAPSE)
                if is_file_db_configured() and not deleted:
                    failed = True
                    continue
                del self.collapse_files[r - 1]

        self._refresh_files_table()
        if failed:
            QMessageBox.warning(self, "警告", "部分文件未能同步更新数据库删除状态，已保留在列表中。")

    def _fatigue_target_list(self, branch: str) -> List[str]:
        return self.fatigue_input_files if branch == "input" else self.fatigue_result_files

    def _fatigue_branch_label(self, branch: str) -> str:
        return "输入文件" if branch == "input" else "结果文件"

    def _on_add_fatigue_local(self, branch: str):
        branch_label = self._fatigue_branch_label(branch)
        fp, _ = QFileDialog.getOpenFileName(self, f"选择疲劳分析{branch_label}", "", "所有文件 (*.*)")
        if not fp:
            return
        actual_branch = self._fatigue_branch_for_path(fp)
        if actual_branch and actual_branch != branch:
            QMessageBox.warning(self, "导入失败", f"当前选择的文件更像疲劳分析{self._fatigue_branch_label(actual_branch)}，请检查后重新导入。")
            return
        try:
            system_path = self._db_store_local_file(fp, self.CATEGORY_FATIGUE, branch)
        except Exception as e:
            QMessageBox.warning(self, "导入失败", f"本地文件入库失败：\n{e}")
            return

        self._append_unique_path(self._fatigue_target_list(branch), system_path)
        self._refresh_files_table()
        QMessageBox.information(self, "本地导入", f"文件已入系统库并显示：\n{system_path}")

    def _on_add_fatigue_sys(self, branch: str):
        branch_label = self._fatigue_branch_label(branch)
        chosen = self._pick_system_file_dialog(self.CATEGORY_FATIGUE, f"系统导入疲劳分析{branch_label}", branch)
        if not chosen:
            return
        self._append_unique_path(self._fatigue_target_list(branch), chosen)
        self._refresh_files_table()

    def _on_del_fatigue(self, branch: str):
        row_map = self._fatigue_input_row_map if branch == "input" else self._fatigue_result_row_map
        selected = self.files_table.selectionModel().selectedRows()
        indexes = sorted({row_map[idx.row()] for idx in selected if idx.row() in row_map}, reverse=True)
        if not indexes:
            QMessageBox.warning(self, "提示", f"请先在疲劳分析{self._fatigue_branch_label(branch)}区域选中要删除的行。")
            return

        failed = False
        target_list = self._fatigue_target_list(branch)
        for idx in indexes:
            if 0 <= idx < len(target_list):
                path = target_list[idx]
                deleted = self._db_soft_delete_file(path, self.CATEGORY_FATIGUE)
                if is_file_db_configured() and not deleted:
                    failed = True
                    continue
                del target_list[idx]

        self._refresh_files_table()
        if failed:
            QMessageBox.warning(self, "警告", "部分疲劳文件未能同步更新数据库删除状态，已保留在列表中。")

    def _on_add_fatigue_result_local(self):
        self._on_add_fatigue_local("result")

    def _on_add_fatigue_result_sys(self):
        self._on_add_fatigue_sys("result")

    def _on_del_fatigue_result(self):
        self._on_del_fatigue("result")

    def _on_add_fatigue_input_local(self):
        self._on_add_fatigue_local("input")

    def _on_add_fatigue_input_sys(self):
        self._on_add_fatigue_sys("input")

    def _on_del_fatigue_input(self):
        self._on_del_fatigue("input")

    def _refresh_model_preview(self):
        if not hasattr(self, "inp_view"):
            return

        path = ""
        for p in self.model_files:
            if os.path.exists(p):
                path = p
                break

        if not path:
            fallback = self._db_fetch_file_records(self.CATEGORY_MODEL)
            path = fallback[0] if fallback else ""

        if not path:
            self.inp_path_label.setText("未找到可预览的模型文件")
            self.inp_view.clear_view("未找到可预览的模型文件\n请先导入或提取模型")
            return

        try:
            self.inp_view.load_inp(path)
            self.inp_path_label.setText(f"当前模型文件：{path}")
        except Exception as e:
            self.inp_path_label.setText("模型加载失败")
            self.inp_view.clear_view(f"模型加载失败：\n{e}")

    def _create_title_row_widget(self, title_text: str, buttons_info: list) -> QWidget:
        """创建一个内嵌于表格标题行的自定义 Widget，包含标题文字和对应按钮"""
        w = QWidget()
        # 背景色与之前的标题行保持一致
        w.setStyleSheet("background-color: #e9edf5;")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(10, 2, 10, 2)
        lay.setSpacing(8)

        # 左侧标题文本
        lbl = QLabel(title_text)
        lbl.setStyleSheet('font-weight: bold; color: #333; border: none; font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei"; font-size: 12pt;')
        lay.addWidget(lbl)

        # 弹簧，将按钮挤到最右侧
        lay.addStretch(1)

        # 动态添加右侧的按钮
        for btn_text, callback in buttons_info:
            btn = QPushButton(btn_text)
            btn.setFixedHeight(32)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background: #ffffff; 
                    border: 1px solid #b9c6d6; 
                    border-radius: 3px; 
                    padding: 0 12px; 
                    color: #1b2a3a; 
                    font-weight: normal;
                    font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
                    font-size: 12pt;
                }
                QPushButton:hover { background: #d9e6f5; }
            """)
            btn.clicked.connect(callback)
            lay.addWidget(btn)

        return w
