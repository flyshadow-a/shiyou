# -*- coding: utf-8 -*-
# pages/new_special_inspection_page.py

import os
import shutil
import datetime
import re
from typing import List
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QWidget,
    QFileDialog, QMessageBox, QScrollArea,
    QAbstractItemView, QSizePolicy, QInputDialog
)
from PyQt5.QtCore import Qt

from app_paths import external_path, external_root, first_existing_path
from base_page import BasePage
from pages.upgrade_special_inspection_result_page import UpgradeSpecialInspectionResultPage


class NewSpecialInspectionPage(BasePage):
    """
    新增检测策略打开的页面：
    - 左侧：上半（结构模型信息 + 设置倒塌分析结果文件）
           下半（用户设置：风险等级参数 + 按钮）
    - 整体支持滚轮滚动（ScrollArea）
    """

    CATEGORY_MODEL = "model"
    CATEGORY_COLLAPSE = "collapse"
    CATEGORY_FATIGUE = "fatigue"

    def __init__(self, facility_code: str, parent=None):
        self.facility_code = facility_code
        self._risk_updated = False
        self.upload_root = external_path("upload", "model_files")
        self.packaged_upload_root = first_existing_path("upload", "model_files")
        self._collapse_static_demo = True

        # 页面仅展示“系统文件库”记录（当前用 upload/model_files 代替数据库）
        self.model_files: List[str] = []
        self.collapse_files: List[str] = []
        self.collapse_demo_files: List[str] = []
        self.fatigue_file: str = ""

        super().__init__("", parent)
        self._build_ui()
        self._reload_system_files_from_backend()

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

        # 保留右侧模型展示区域，但暂时不接入实际渲染，避免页面打不开
        content = QFrame()
        content.setObjectName("Card")
        lay = QHBoxLayout(content)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(12)

        left = self._build_left_panel()
        right = self._build_right_panel()

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
        self.model_files_block.hide()
        self.analysis_files_block.hide()
        # 按当前需求暂时注释掉以下区块：
        # 1. 设置模型文件
        # 2. 设置分析结果文件
        # 3. 设置疲劳分析结果文件（位于分析结果文件区块内）
        # v.addWidget(self.model_files_block, 0)
        # v.addWidget(self.analysis_files_block, 0)

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

        # 参数表（两列：项目/值）
        param_table = QTableWidget(4, 2)
        param_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        param_table.verticalHeader().setVisible(False)
        param_table.horizontalHeader().setVisible(False)

        params = [
            ("构件直线夹角容许误差（度）", "15"),
            ("腿柱管节点撑杆最小管径（mm）", "509"),
            ("工作点高度 Z(m)", "10"),
            ("腿柱数量", "4"),
        ]
        for r, (k, val) in enumerate(params):
            item_k = QTableWidgetItem(k)
            item_v = QTableWidgetItem(val)
            item_k.setTextAlignment(Qt.AlignCenter)
            item_v.setTextAlignment(Qt.AlignCenter)
            param_table.setItem(r, 0, item_k)
            param_table.setItem(r, 1, item_v)

        self._lock_table_full_display(param_table, row_height=34, show_header=False)

        block_lay.addWidget(param_table)

        # 坐标表（示例）
        coord_table = QTableWidget(5, 3)
        coord_table.setHorizontalHeaderLabels(["柱腿工作点坐标", "X坐标（m）", "Y坐标（m）"])
        coord_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        coord_table.verticalHeader().setVisible(False)

        coords = [
            (1, -10, -8),
            (2, -10,  8),
            (3,  10, -8),
            (4,  10,  8),
            (5, "",  ""),
        ]
        for r, (idx, x, y) in enumerate(coords):
            for c, val in enumerate([idx, x, y]):
                it = QTableWidgetItem(str(val))
                it.setTextAlignment(Qt.AlignCenter)
                coord_table.setItem(r, c, it)

        self._lock_table_with_scroll(coord_table, row_height=34, visible_rows=4)

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

        table = QTableWidget(7, 3)
        table.setHorizontalHeaderLabels(["项目", "等级/值", "说明"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)

        # 行内容（按你图的结构填示例）
        rows = [
            ("生命安全等级", "S-2", "有人可撤离——有人员居住的平台，在极端情况下人员可以实施撤离的情况。"),
            ("失效后果等级", "C-3", "低后果——所有井口包含功能齐全的SSSV，在平台失效时，生产系统可以自行运转而不受影响。这些平台可以支持不依托平台的生产，平台仅包含低输量的内部管道，仅含有工艺库存。"),
            ("平台整体暴露等级", "L-2", ""),
            ("平台海域", "中国南海", ""),
            ("A", "0.272", ""),
            ("B", "0.158", ""),
            ("已服役时间（年）", "12", ""),
        ]

        for r, (k, val, desc) in enumerate(rows):
            it0 = QTableWidgetItem(k)
            it1 = QTableWidgetItem(val)
            it2 = QTableWidgetItem(desc)

            it0.setTextAlignment(Qt.AlignCenter)
            it1.setTextAlignment(Qt.AlignCenter)
            it2.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)

            # 描述列允许换行
            it2.setFlags(it2.flags() | Qt.ItemIsSelectable)
            table.setItem(r, 0, it0)
            table.setItem(r, 1, it1)
            table.setItem(r, 2, it2)

        # 让前两行更高，容纳长描述
        table.setRowHeight(0, 70)
        table.setRowHeight(1, 90)

        # “平台整体暴露等级 L-2”黄色高亮（对应截图）
        highlight = table.item(2, 1)
        if highlight:
            highlight.setBackground(Qt.yellow)
            highlight.setForeground(Qt.black)
            highlight.setTextAlignment(Qt.AlignCenter)

        table.setMinimumHeight(300)
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

    # ---------------- 右侧：黑色模型展示区（当前占位，不渲染模型） ----------------
    def _build_right_panel(self) -> QFrame:
        panel = QFrame()
        v = QVBoxLayout(panel)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        title = QLabel("结构模型预览")
        title.setObjectName("SectionTitle")
        v.addWidget(title)

        hint = QLabel("当前已暂时关闭模型渲染，先保留展示区域，后续可继续接入模型图显示。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#5d6f85; font-size:14px;")
        v.addWidget(hint, 0)

        placeholder = QFrame()
        placeholder.setStyleSheet("background: #0b0b0b; border: 1px solid #1f2a36;")
        placeholder.setMinimumHeight(320)

        placeholder_lay = QVBoxLayout(placeholder)
        placeholder_lay.setContentsMargins(12, 12, 12, 12)
        placeholder_lay.setSpacing(8)

        info = QLabel("模型图区域已保留\n当前暂不加载渲染组件")
        info.setAlignment(Qt.AlignCenter)
        info.setStyleSheet("color:#c7d2e3; font-size:12pt; background: transparent;")
        placeholder_lay.addStretch(1)
        placeholder_lay.addWidget(info)
        placeholder_lay.addStretch(1)

        v.addWidget(placeholder, 1)
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
        # 这里你以后接算法，更新完就标记一下
        self._risk_updated = True
        QMessageBox.information(self, "更新风险等级", "已完成风险等级更新（示例）。")

    def _on_view_result(self):
        if not self._risk_updated:
            QMessageBox.information(self, "提示", "请先点击“更新风险等级”，再查看结果。")
            return

        mw = self.window()  # ✅比 self.parent() 稳定

        # ✅这里判断/调用你 main.py 里真实存在的方法名
        if mw is not None and hasattr(mw, "open_upgrade_special_inspection_result_tab"):
            mw.open_upgrade_special_inspection_result_tab(self.facility_code)
            return

        # 兜底：直接加tab
        if mw is not None and hasattr(mw, "tab_widget"):
            page = UpgradeSpecialInspectionResultPage(self.facility_code, mw)
            idx = mw.tab_widget.addTab(page, f"{self.facility_code}更新风险结果")
            mw.tab_widget.setCurrentIndex(idx)
            return

        QMessageBox.warning(self, "错误", "未找到 MainWindow/tab_widget，无法打开结果页。")

    # ---------------- 文件来源：后续数据库接入接口（先走 upload/model_files） ----------------
    def _db_fetch_file_records(self, category: str) -> List[str]:
        """
        数据库读取接口（预留）：返回系统文件记录。

        后续接数据库时，只需要替换本方法内部实现即可，页面其余逻辑无需改动。
        当前实现：从 upload/model_files 扫描提取。
        """
        return self._fetch_system_files_from_upload(category)

    def _db_store_local_file(self, local_path: str, category: str) -> str:
        """
        本地文件入库接口（预留）：把本地文件上传到系统文件库，返回系统记录路径/标识。

        后续接数据库时，只需要替换本方法内部实现即可，页面其余逻辑无需改动。
        当前实现：复制到 upload/model_files/special_strategy/<category>/ 下。
        """
        return self._store_local_file_to_upload(local_path, category)

    def _fetch_system_files_from_upload(self, category: str) -> List[str]:
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
                        if in_special_bucket or (ext_no_dot in allow):
                            keep = True
                            score += 100

                    if not keep:
                        continue

                    if code_lower and code_lower in stem:
                        score += 80

                    try:
                        mtime = os.path.getmtime(full_path)
                    except OSError:
                        mtime = 0.0
                    records.append((score, mtime, full_path))

        records.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [p for _, _, p in records]

    def _store_local_file_to_upload(self, local_path: str, category: str) -> str:
        target_dir = os.path.join(self.upload_root, "special_strategy", category)
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

    def _pick_system_file_dialog(self, category: str, title: str) -> str:
        candidates = self._db_fetch_file_records(category)
        if not candidates:
            QMessageBox.information(self, "系统导入", "系统文件库中暂无可用文件。")
            return ""

        labels = [self._short_path(p) for p in candidates]
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

        fatigue_candidates = self._db_fetch_file_records(self.CATEGORY_FATIGUE)
        if self.fatigue_file and self.fatigue_file in fatigue_candidates:
            pass
        else:
            self.fatigue_file = fatigue_candidates[0] if fatigue_candidates else ""

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

        # --- 疲劳分析部分 ---
        r_fatigue_hdr = len(collapse_view) + 1
        self.files_table.insertRow(r_fatigue_hdr)
        self.files_table.setSpan(r_fatigue_hdr, 0, 1, 2)

        fat_buttons = [
            ("本地导入", self._on_set_fatigue_local),
            ("系统导入", self._on_set_fatigue_sys)
        ]
        fat_title_widget = self._create_title_row_widget("设置疲劳分析结果文件", fat_buttons)
        self.files_table.setCellWidget(r_fatigue_hdr, 0, fat_title_widget)
        self.files_table.setRowHeight(r_fatigue_hdr, 38)

        r_fatigue_val = r_fatigue_hdr + 1
        self.files_table.insertRow(r_fatigue_val)
        self.files_table.setSpan(r_fatigue_val, 0, 1, 2)

        val_widget = QWidget()
        val_widget.setStyleSheet("background-color: #ffffff;")
        val_lay = QHBoxLayout(val_widget)
        val_lay.setContentsMargins(10, 0, 10, 0)
        val_lay.setSpacing(10)

        lbl = QLabel("疲劳结果文件:")
        lbl.setStyleSheet('color: #333; font-weight: normal; font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei"; font-size: 12pt;')

        path_text = self._short_path(self.fatigue_file) if self.fatigue_file else "暂未选择..."
        val = QLabel(path_text)
        val.setStyleSheet('color: #333; font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei"; font-size: 12pt;')
        val.setWordWrap(True)
        val.setToolTip(self.fatigue_file)

        val_lay.addWidget(lbl, 0)
        val_lay.addWidget(val, 1)

        self.files_table.setCellWidget(r_fatigue_val, 0, val_widget)
        self.files_table.setRowHeight(r_fatigue_val, 36)

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
        for r in rows_to_delete:
            if 1 <= r <= len(self.model_files):
                del self.model_files[r - 1]

        self._refresh_model_files_table()
        self._refresh_model_preview()

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
        for r in rows_to_delete:
            if 1 <= r <= len(self.collapse_files):
                del self.collapse_files[r - 1]

        self._refresh_files_table()

    def _on_set_fatigue_local(self):
        fp, _ = QFileDialog.getOpenFileName(self, "选择疲劳分析结果文件", "", "结果文件 (*.wit *.wjt *.csv *.txt);;所有文件 (*.*)")
        if not fp:
            return
        try:
            system_path = self._db_store_local_file(fp, self.CATEGORY_FATIGUE)
        except Exception as e:
            QMessageBox.warning(self, "导入失败", f"本地文件入库失败：\n{e}")
            return

        self.fatigue_file = system_path
        self._refresh_files_table()
        QMessageBox.information(self, "本地导入", f"文件已入系统库并显示：\n{system_path}")

    def _on_set_fatigue_sys(self):
        chosen = self._pick_system_file_dialog(self.CATEGORY_FATIGUE, "系统导入疲劳分析结果文件")
        if not chosen:
            return
        self.fatigue_file = chosen
        self._refresh_files_table()

    def _refresh_model_preview(self):
        return

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
