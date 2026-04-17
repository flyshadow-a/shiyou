# -*- coding: utf-8 -*-
# pages/model_files_page.py

import os
import shutil
import datetime
from typing import Any, Dict, List

from PyQt5.QtCore import Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices, QFontMetrics, QPixmap
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QSizePolicy, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QStackedWidget, QMessageBox, QFileDialog, QWidget
)

from base_page import BasePage
from dropdown_bar import DropdownBar
from .file_management_platforms import default_platform, sync_platform_dropdowns
from .doc_man import DocManWidget
from file_db_adapter import (
    is_file_db_configured,
    list_files_by_prefix,
    resolve_storage_path,
    soft_delete_record,
    upload_file,
)

# ✅ 直接复用 ConstructionDocsWidget 的文件夹UI与交互（FolderButton / folder_grid / PathBar 等）
from .construction_docs_widget import ConstructionDocsWidget

# ============================================================
# 辅助：可点击 Label（用于“首页”）
# ============================================================
class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


# ============================================================
# 1) Widget：文件夹UI = ConstructionDocsWidget；叶子表格页 = 旧逻辑表格
#    - 不自写文件夹布局
#    - 保留旧的“表格行配置 + 上传/下载 + 扫描恢复”逻辑
#    - ✅ 调整：文件夹/首页页完全使用 ConstructionDocsWidget 自带 PathBar；
#             自己的蓝色面包屑仅在“叶子表格页”显示，避免重复顶栏
# ============================================================
class ModelFilesDocsWidget(QWidget):
    navigationStateChanged = pyqtSignal(bool)
    """
    模型文件专用内容区：
    - Folder View：直接用 ConstructionDocsWidget 画（严格复用其布局/样式/交互）
    - Leaf View：使用旧逻辑的 QTableWidget（序号|类别|格式|修改时间|上传|下载|备注）
    - ✅ Breadcrumb：本文件自带的蓝色 HeaderBar 仅用于叶子页；文件夹页使用 ConstructionDocsWidget 自带 PathBar
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.breadcrumb_font_ratio = 0.015

        # 当前路径（不含“首页”），例如：
        # [] / ["详细设计模型"] / ["详细设计模型","静力"]
        self.current_path: List[str] = []

        # 文件夹树结构 + 每种模型对应的行配置
        self.folder_tree = self._build_folder_tree()
        self.model_row_configs = self._build_model_row_configs()
        self.doc_man_configs = self._build_doc_man_configs()
        self.doc_man_records = self._build_doc_man_records()

        # 每个叶子路径对应的 {row_index: 文件绝对路径}
        self.row_paths_by_path: Dict[str, Dict[int, str]] = {}  # { "详细设计模型/静力": {0: path, 1: path, ...}}
        self.row_db_records_by_path: Dict[str, Dict[int, List[Dict[str, Any]]]] = {}

        # 当前显示的叶子路径 key 和行配置
        self.current_leaf_key: str = ""
        self.current_row_configs: List[Dict] = []
        self.current_table_rows: List[Dict[str, Any]] = []
        self.facility_code = ""

        # 上传根目录：项目根目录/upload/model_files（沿用你旧代码的 upload 路径）
        self.upload_root = self._get_upload_root()

        self._build_ui()

    # ------------------------------------------------------------------
    # 路径 & 数据结构（来自旧代码）
    # ------------------------------------------------------------------
    def _get_project_root(self) -> str:
        here = os.path.abspath(__file__)
        pages_dir = os.path.dirname(here)
        return os.path.dirname(pages_dir)

    def _get_upload_root(self) -> str:
        project_root = self._get_project_root()
        path = os.path.join(project_root, "upload", "model_files")
        os.makedirs(path, exist_ok=True)
        return path

    def set_facility_code(self, code: str):
        new_code = (code or "").strip()
        if new_code != self.facility_code:
            self.row_paths_by_path.clear()
            self.row_db_records_by_path.clear()
        self.facility_code = new_code

    def _build_folder_tree(self) -> Dict:
        """
        首页
          ├─ 当前模型
          │   ├─ 静力
          │   ├─ 地震
          │   ├─ 疲劳
          │   ├─ 倒塌
          │   └─ 其他模型
          ├─ 详细设计模型
          ├─ 改造1模型
          └─ 改造N模型
        """
        def make_model_children():
            return {
                "静力":   {"type": "leaf", "model_key": "static"},
                "地震":   {"type": "leaf", "model_key": "seismic"},
                "疲劳":   {"type": "leaf", "model_key": "fatigue"},
                "倒塌":   {"type": "leaf", "model_key": "collapse"},
                "其他模型": {"type": "leaf", "model_key": "other"},
            }

        return {
            "当前模型":     {"type": "folder", "children": make_model_children()},
            "详细设计模型": {"type": "folder", "children": make_model_children()},
            "改造1模型":    {"type": "folder", "children": make_model_children()},
            "改造N模型":    {"type": "folder", "children": make_model_children()},
        }

    def _build_model_row_configs(self) -> Dict[str, List[Dict]]:
        """
        每种模型类型对应的行配置：
        [{"category": 文件类别, "fmt": "后缀1/后缀2"}...]
        """
        return {
            "static": [  # 静力
                {"category": "结构模型文件",      "fmt": "sacinp"},
                {"category": "海况文件",          "fmt": "seainp"},
                {"category": "桩基文件",          "fmt": "psiinp"},
                {"category": "冲剪节点文件",      "fmt": "jcninp"},
                {"category": "静力分析结果文件",  "fmt": "psilst"},
            ],
            "fatigue": [  # 疲劳
                {"category": "结构模型文件",        "fmt": "sacinp"},
                {"category": "海况文件",            "fmt": "seainp"},
                {"category": "桩基文件",            "fmt": "psiinp"},
                {"category": "动力分析文件",        "fmt": "dyninp"},
                {"category": "疲劳分析模型文件",    "fmt": "ftginp"},
                {"category": "疲劳分析结果文件",    "fmt": "wvrinp"},
                {"category": "疲劳分析结果文件", "fmt": "ftglst"},
            ],
            "collapse": [  # 倒塌
                {"category": "结构模型文件",          "fmt": "sacinp"},
                {"category": "海况文件",              "fmt": "seainp"},
                {"category": "桩基文件",              "fmt": "psiinp"},
                {"category": "倒塌分析模型文件",      "fmt": "clpinp"},
                {"category": "倒塌分析日志文件",      "fmt": "clplog"},
                {"category": "倒塌分析结果文件",      "fmt": "clplst"},
                {"category": "倒塌分析结果文件", "fmt": "clprst"},
            ],
            "seismic": [  # 地震
                {"category": "结构模型文件",        "fmt": "sacinp"},
                {"category": "海况文件",            "fmt": "seainp"},
                {"category": "桩基文件",            "fmt": "psiinp"},
                {"category": "冲剪节点文件",        "fmt": "jcninp"},
                {"category": "动力分析文件",        "fmt": "dyninp"},
                {"category": "动力分析文件(地震)",  "fmt": "dyrinp"},
                {"category": "地震分析模型文件",    "fmt": "pilinp"},
                {"category": "地震分析结果文件",    "fmt": "lst"},
            ],
            "other": [  # 其他模型
                {"category": "结构模型文件",        "fmt": "sacinp"},
                {"category": "海况文件",            "fmt": "seainp"},
                {"category": "其他分析模型文件",    "fmt": "othinp"},
                {"category": "其他分析结果文件",    "fmt": "othlst"},
            ],
        }

    def _current_path_key(self) -> str:
        return "/".join(self.current_path)

    def _get_node_by_path(self, path_list: List[str]):
        node = {"type": "folder", "children": self.folder_tree}
        for name in path_list:
            children = node.get("children", {})
            node = children.get(name)
            if node is None:
                break
        return node

    # ------------------------------------------------------------------
    # （保留）面包屑 HeaderBar：仅用于叶子页（不影响其他逻辑）
    # ------------------------------------------------------------------
    def _build_breadcrumb_bar(self) -> QWidget:
        bar = QFrame(self)
        bar.setObjectName("BreadcrumbBar")
        bar.setFixedHeight(40)

        self.breadcrumb_layout = QHBoxLayout(bar)
        self.breadcrumb_layout.setContentsMargins(12, 0, 12, 0)
        self.breadcrumb_layout.setSpacing(8)
        self.breadcrumb_layout.setAlignment(Qt.AlignVCenter)

        # 统一样式（蓝色 header bar + 白字）
        bar.setStyleSheet("""
            QFrame#BreadcrumbBar { background-color: #1e3a8a; border: none; }
            QLabel { color: #ffffff; }
            QLabel#BreadcrumbHome { font-weight: 600; }
            QLabel#BreadcrumbCrumb { font-weight: 600; }
        """)
        return bar

    def _clear_layout(self, layout: QHBoxLayout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _load_folder_icon_pixmap(self):
        # 优先使用项目根目录/pict 下的资源（按你项目约定）
        project_root = self._get_project_root()
        pict_dir = os.path.join(project_root, "pict")
        candidates = [
            os.path.join(pict_dir, "folder.png"),
            os.path.join(pict_dir, "wenjian.png"),
            os.path.join(pict_dir, "folder_icon.png"),
        ]
        for p in candidates:
            if os.path.exists(p):
                pix = QPixmap(p)
                if not pix.isNull():
                    return pix
        return None

    def _go_home_from_breadcrumb(self):
        # 点击“首页” => 回根目录文件夹视图
        self.current_path = []
        self.current_leaf_key = ""
        self._refresh_folder_view()
        self.docs_widget.content_stack.setCurrentWidget(self.docs_widget.folder_page)

        # ✅ 叶子页面包屑隐藏，文件夹页交给 ConstructionDocsWidget
        self.breadcrumb_bar.hide()
        self._emit_navigation_state()

    def _update_breadcrumb_bar(self):
        # 清空并重建
        self._clear_layout(self.breadcrumb_layout)

        # 文件夹图标
        lbl_folder_icon = QLabel(self.breadcrumb_bar)
        lbl_folder_icon.setFixedSize(18, 18)
        lbl_folder_icon.setScaledContents(True)
        pix = self._load_folder_icon_pixmap()
        if pix:
            lbl_folder_icon.setPixmap(pix)
        else:
            lbl_folder_icon.setText("📁")
            lbl_folder_icon.setAlignment(Qt.AlignCenter)

        # “首页”
        lbl_home = ClickableLabel("首页", self.breadcrumb_bar)
        lbl_home.setObjectName("BreadcrumbHome")
        lbl_home.setCursor(Qt.PointingHandCursor)
        lbl_home.clicked.connect(self._go_home_from_breadcrumb)

        self.breadcrumb_layout.addWidget(lbl_folder_icon, 0)
        self.breadcrumb_layout.addWidget(lbl_home, 0)

        # 逐级面包屑：首页 > A > B > C
        prefix = []
        for idx, name in enumerate(self.current_path):
            # 分隔符 >
            sep = QLabel(">", self.breadcrumb_bar)
            self.breadcrumb_layout.addWidget(sep, 0)

            # 每一级都可点（点到任意一级回退到该层）
            crumb = ClickableLabel(name, self.breadcrumb_bar)
            crumb.setObjectName("BreadcrumbCrumb")
            crumb.setCursor(Qt.PointingHandCursor)

            prefix.append(name)
            crumb_prefix = list(prefix)  # 绑定当前 prefix 的副本
            crumb.clicked.connect(lambda p=crumb_prefix: self._on_breadcrumb_clicked(p))

            self.breadcrumb_layout.addWidget(crumb, 0)

        self.breadcrumb_layout.addStretch(1)
        self._update_breadcrumb_font_scale()

    def _update_breadcrumb_font_scale(self):
        if not hasattr(self, "breadcrumb_layout"):
            return

        font_size = max(11.0, min(20.0, self.width() * self.breadcrumb_font_ratio - 2.0))
        for i in range(self.breadcrumb_layout.count()):
            item = self.breadcrumb_layout.itemAt(i)
            widget = item.widget()
            if widget is None or not isinstance(widget, QLabel):
                continue
            font = widget.font()
            font.setPointSizeF(font_size)
            widget.setFont(font)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_breadcrumb_font_scale()

    # ------------------------------------------------------------------
    # 表格工具（来自旧代码）
    # ------------------------------------------------------------------
    def _init_table_common(self, table: QTableWidget):
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectItems)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)

        table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                gridline-color: #d0d0d0;
            }
            QTableWidget::item {
                border-bottom: 1px solid #d0d0d0;
                border-right:  1px solid #d0d0d0;
            }
            QTableWidget::item:selected {
                background-color: #dbeafe;
                color: #111827;
            }
            QHeaderView::section {
                background-color: #f3f4f6;
                border: 0px;
                border-bottom: 1px solid #d0d0d0;
                border-right:  1px solid #d0d0d0;
                padding: 4px 8px;
            }
        """)

        hh = table.horizontalHeader()
        hh.setDefaultAlignment(Qt.AlignCenter)
        hh.setHighlightSections(False)
        hh.setSectionResizeMode(QHeaderView.Fixed)

        table.verticalHeader().setVisible(False)

    def _set_center_item(self, table: QTableWidget, row: int, col: int, text):
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(Qt.AlignCenter)
        table.setItem(row, col, item)

    def _auto_fit_columns_with_padding(self, table: QTableWidget, padding: int = 24):
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        table.resizeColumnsToContents()

        fm = QFontMetrics(table.font())
        for col in range(table.columnCount()):
            max_width = table.columnWidth(col)
            head_item = table.horizontalHeaderItem(col)
            if head_item:
                w = fm.horizontalAdvance(head_item.text())
                max_width = max(max_width, w + padding)
            for row in range(table.rowCount()):
                item = table.item(row, col)
                if item:
                    w = fm.horizontalAdvance(item.text())
                    max_width = max(max_width, w + padding)
            table.setColumnWidth(col, max_width)

        header.setSectionResizeMode(QHeaderView.Fixed)

    def _auto_fit_row_height(self, table: QTableWidget, padding: int = 10):
        fm = QFontMetrics(table.font())
        h = fm.height() + padding
        table.verticalHeader().setDefaultSectionSize(h)

    # ------------------------------------------------------------------
    # UI 构建：叶子页才显示本文件蓝色面包屑；文件夹/首页完全交给 ConstructionDocsWidget
    # ------------------------------------------------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ============================================================
        # 1) 文件夹页：直接使用 ConstructionDocsWidget（不要覆盖它的点击函数）
        # ============================================================
        self.docs_widget = ConstructionDocsWidget(parent=self)

        # 用我们的 folder_tree 覆盖它自己的树
        self.docs_widget.folder_tree = self.folder_tree
        self.docs_widget.current_path = list(self.current_path)

        # ✅ 关键：不要再做这两句（会导致 PathBar 不更新）
        # self.docs_widget._on_folder_clicked = self._on_folder_clicked
        # self.docs_widget._on_breadcrumb_clicked = self._on_breadcrumb_clicked

        # ============================================================
        # 2) 叶子页：把 ConstructionDocsWidget 的 files_page 替换成我们自己的表格页
        #    并劫持它的 _show_files_for_current_path 来走我们的“填表 + 上传/下载”逻辑
        # ============================================================
        self.custom_files_page = QWidget(self.docs_widget)
        files_layout = QVBoxLayout(self.custom_files_page)
        files_layout.setContentsMargins(0, 0, 0, 0)
        files_layout.setSpacing(0)

        self.table = QTableWidget(0, 7, self.custom_files_page)
        self.table.setHorizontalHeaderLabels(
            ["序号", "文件类别", "文件格式", "修改时间", "上传", "下载", "备注"]
        )
        self._init_table_common(self.table)
        self.table.cellClicked.connect(self._on_table_cell_clicked)
        files_layout.addWidget(self.table)
        self.table.hide()
        self.doc_man_widget = DocManWidget(self._get_doc_man_upload_dir, self.custom_files_page)
        files_layout.addWidget(self.doc_man_widget)

        # ✅ 把我们的页塞进它的 content_stack，并用它的 PathBar 管理“文件夹/叶子”切换
        self.docs_widget.content_stack.addWidget(self.custom_files_page)
        self.docs_widget.files_page = self.custom_files_page  # 让它切到叶子时显示我们的表格页

        # ✅ 劫持：当它认为进入叶子时，调用我们自己的填表逻辑
        def _show_files_proxy():
            # 同步路径（ConstructionDocsWidget 自己维护 current_path）
            self.current_path = list(self.docs_widget.current_path)
            self._show_files_for_current_leaf()

        self.docs_widget._show_files_for_current_path = _show_files_proxy

        # 初次刷新 folder_grid（让首页/文件夹显示正确）
        self.docs_widget._refresh_folder_view()
        self.docs_widget.content_stack.setCurrentWidget(self.docs_widget.folder_page)
        self._emit_navigation_state()

        # 最终只把 docs_widget（含 PathBar + 卡片 + 内容区）放进本组件
        layout.addWidget(self.docs_widget, 1)

    # ------------------------------------------------------------------
    # 文件夹视图刷新 / 点击 / 面包屑
    # ------------------------------------------------------------------
    def _refresh_folder_view(self):
        """
        文件夹UI交给 ConstructionDocsWidget 画
        """
        self.docs_widget.folder_tree = self.folder_tree
        self.docs_widget.current_path = list(self.current_path)
        try:
            self.docs_widget._refresh_folder_view()
        except Exception:
            # 兼容不同版本 ConstructionDocsWidget：若方法名不同，至少不崩
            pass

    def _on_breadcrumb_clicked(self, path_prefix: List[str]):
        self.current_path = list(path_prefix)

        node = self._get_node_by_path(self.current_path)
        if not node:
            return

        if node.get("type") == "folder":
            self._refresh_folder_view()
            self.docs_widget.content_stack.setCurrentWidget(self.docs_widget.folder_page)

            # ✅ 文件夹页：隐藏本文件蓝色面包屑，使用 ConstructionDocsWidget 自带 PathBar
            self.breadcrumb_bar.hide()
        else:
            self._show_files_for_current_leaf()
            self.docs_widget.content_stack.setCurrentWidget(self.docs_widget.files_page)

            # ✅ 叶子页：显示本文件蓝色面包屑（不影响你旧逻辑）
            self._update_breadcrumb_bar()
            self.breadcrumb_bar.show()
        self._emit_navigation_state()

    def _on_folder_clicked(self, folder_name: str):
        node = self._get_node_by_path(self.current_path)
        if not node:
            return

        child = node.get("children", {}).get(folder_name)
        if not child:
            return

        self.current_path.append(folder_name)

        if child.get("type") == "folder":
            self._refresh_folder_view()
            self.docs_widget.content_stack.setCurrentWidget(self.docs_widget.folder_page)

            # ✅ 文件夹页：隐藏本文件蓝色面包屑，使用 ConstructionDocsWidget 自带 PathBar
            self.breadcrumb_bar.hide()
        else:
            self._show_files_for_current_leaf()
            self.docs_widget.content_stack.setCurrentWidget(self.docs_widget.files_page)

            # ✅ 叶子页：显示本文件蓝色面包屑（不影响你旧逻辑）
            self._update_breadcrumb_bar()
            self.breadcrumb_bar.show()
        self._emit_navigation_state()

    # ------------------------------------------------------------------
    # 叶子：文件表格（旧逻辑）
    # ------------------------------------------------------------------
    def _get_row_paths_for(self, path_key: str) -> Dict[int, str]:
        if path_key not in self.row_paths_by_path:
            self.row_paths_by_path[path_key] = self._scan_existing_uploads_for_path(path_key)
        return self.row_paths_by_path[path_key]

    def _scan_existing_uploads_for_path(self, path_key: str) -> Dict[int, str]:
        """
        用于程序重启后恢复已有上传文件。
        """
        row_paths: Dict[int, str] = {}
        db_row_records: Dict[int, List[Dict[str, Any]]] = {}

        if is_file_db_configured() and self.facility_code:
            node = self._get_node_by_path(self.current_path)
            model_key = node.get("model_key") if node else None
            row_configs = self.model_row_configs.get(model_key, [])
            for row, cfg in enumerate(row_configs):
                rows = self._list_db_records_for_row(path_key, cfg)
                if not rows:
                    continue
                db_row_records[row] = rows
                first_path = str(rows[0].get("storage_path") or "")
                if first_path and os.path.exists(first_path):
                    row_paths[row] = first_path

        self.row_db_records_by_path[path_key] = db_row_records

        # 行数随配置走：但为了兼容“配置变更”，最多扫描 30 行
        max_rows = 30
        for row in range(max_rows):
            if row in row_paths:
                continue
            d = self._leaf_row_dir(path_key, row, create_dir=False)
            if not os.path.isdir(d):
                continue
            files = [
                os.path.join(d, f)
                for f in os.listdir(d)
                if os.path.isfile(os.path.join(d, f))
            ]
            if not files:
                continue
            latest = max(files, key=os.path.getmtime)
            row_paths[row] = latest

        return row_paths

    def _list_db_records_for_row(self, path_key: str, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
        prefixes = self._db_prefixes_for_row(path_key, cfg)
        if not prefixes:
            return []
        matches: List[Dict[str, Any]] = []
        seen_ids: set[int] = set()
        for prefix in prefixes:
            rows = list_files_by_prefix(
                module_code="model_files",
                logical_path_prefix=prefix,
                facility_code=self.facility_code,
            )
            for row in rows:
                row_id = row.get("id")
                if row_id in seen_ids:
                    continue
                if not self._db_row_matches_cfg(row, cfg):
                    continue
                seen_ids.add(row_id)
                matches.append(row)
        matches.sort(
            key=lambda item: (
                str(item.get("logical_path") or ""),
                str(item.get("original_name") or ""),
            )
        )
        return matches

    def _db_prefixes_for_row(self, path_key: str, cfg: Dict[str, Any]) -> List[str]:
        if not self.facility_code or not path_key:
            return []
        parts = path_key.split("/")
        if len(parts) < 2:
            return []
        model_root = parts[0]
        base = f"{self.facility_code}/{model_root}"
        fmt = str(cfg.get("fmt") or "").lower()
        if fmt == "sacinp":
            return [f"{base}/结构模型"]
        if fmt.startswith("clp"):
            return [f"{base}/倒塌分析"]
        if fmt.startswith("ftg") or fmt == "wvrinp":
            return [f"{base}/疲劳分析"]
        return []

    def _db_row_matches_cfg(self, row: Dict[str, Any], cfg: Dict[str, Any]) -> bool:
        name = str(row.get("original_name") or "").lower()
        logical_path = str(row.get("logical_path") or "").replace("\\", "/").lower()
        fmt = str(cfg.get("fmt") or "").lower()

        if fmt == "sacinp":
            return name.startswith("sacinp")
        if fmt == "clpinp":
            return name.startswith("clpinp")
        if fmt == "clplog":
            return "clplog" in name
        if fmt == "clplst":
            return "clplst" in name
        if fmt == "clprst":
            return "clprst" in name
        if fmt == "ftginp":
            # 优先匹配带/输入 路径的文件，但如果文件名以 ftginp 开头也接受
            return name.startswith("ftginp") and ("/输入" in logical_path or "/疲劳分析/" in logical_path)
        if fmt == "ftglst":
            # 优先匹配带/结果 路径的文件，但如果文件名以 ftglst 开头也接受
            return name.startswith("ftglst") and ("/结果" in logical_path or "/疲劳分析/" in logical_path)
        if fmt == "wvrinp":
            return name.startswith("wvrinp")
        return False

    def _build_db_remark(self, records: List[Dict[str, Any]]) -> str:
        if not records:
            return ""
        labels: List[str] = []
        for item in records:
            logical_path = str(item.get("logical_path") or "").replace("\\", "/").strip("/")
            original_name = str(item.get("original_name") or "")
            parts = logical_path.split("/")
            tail = "/".join(parts[-2:]) if len(parts) >= 2 else logical_path
            label = f"{tail}/{original_name}".strip("/")
            labels.append(label)
        if len(labels) == 1:
            return labels[0]
        preview = "；".join(labels[:3])
        if len(labels) > 3:
            return f"{preview} 等{len(labels)}个文件"
        return preview

    def _resolve_record_path(self, row: Dict[str, Any]) -> str:
        return resolve_storage_path(row)

    def _record_datetime(self, row: Dict[str, Any], fallback_path: str = "") -> datetime.datetime | None:
        dt_value = row.get("source_modified_at") or row.get("uploaded_at") or row.get("updated_at")
        if isinstance(dt_value, datetime.datetime):
            return dt_value
        if fallback_path and os.path.exists(fallback_path):
            return datetime.datetime.fromtimestamp(os.path.getmtime(fallback_path))
        return None

    def _build_leaf_display_rows(
        self,
        row_configs: List[Dict[str, Any]],
        row_paths: Dict[int, str],
        db_row_records: Dict[int, List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        display_rows: List[Dict[str, Any]] = []
        for row_index, cfg in enumerate(row_configs):
            db_records = db_row_records.get(row_index, [])
            if db_records:
                for record_index, record in enumerate(db_records):
                    record_path = self._resolve_record_path(record)
                    original_name = str(record.get("original_name") or os.path.basename(record_path))
                    display_rows.append(
                        {
                            "cfg": cfg,
                            "row_index": row_index,
                            "file_path": record_path,
                            "remark": original_name,
                            "mtime": self._record_datetime(record, record_path),
                            "upload_enabled": record_index == 0,
                            "download_enabled": bool(record_path),
                        }
                    )
                continue

            file_path = row_paths.get(row_index, "")
            display_rows.append(
                {
                    "cfg": cfg,
                    "row_index": row_index,
                    "file_path": file_path,
                    "remark": os.path.basename(file_path) if file_path else "",
                    "mtime": self._record_datetime({}, file_path),
                    "upload_enabled": True,
                    "download_enabled": bool(file_path),
                }
            )
        return display_rows

    def _doc_category_to_fmt(self, category: str) -> str:
        mapping = {
            "结构模型文件": "sacinp",
            "海况文件": "seainp",
            "桩基文件": "psiinp",
            "冲剪节点文件": "jcninp",
            "静力分析文件": "psilst",
            "动力分析文件": "dyninp",
            "疲劳分析模型文件": "ftginp",
            "疲劳分析结果文件": "ftglst",
            "倒塌分析模型文件": "clpinp",
            "倒塌分析结果文件": "clplog",
            "地震分析模型文件": "pilinp",
            "地震分析结果文件": "lst",
            "其他分析模型文件": "othinp",
            "其他分析结果文件": "othlst",
        }
        return mapping.get(category, "")

    def _format_from_original_name(self, original_name: str) -> str:
        name = (original_name or "").lower()
        if name.startswith("sacinp"):
            return "SACINP"
        if name.startswith("seainp"):
            return "SEAINP"
        if name.startswith("psiinp"):
            return "PSIINP"
        if name.startswith("jcninp"):
            return "JCNINP"
        if name.startswith("psilst"):
            return "PSILST"
        if name.startswith("dyninp"):
            return "DYNINP"
        if name.startswith("dyrinp"):
            return "DYRINP"
        if name.startswith("ftginp"):
            return "FTGINP"
        if name.startswith("ftglst"):
            return "FTGLST"
        if name.startswith("clpinp"):
            return "CLPINP"
        if name == "clplog":
            return "CLPLOG"
        if name == "clplst":
            return "CLPLST"
        if name == "clprst":
            return "CLPRST"
        if name.startswith("pilinp"):
            return "PILINP"
        if name == "lst":
            return "LST"
        if name.startswith("othinp"):
            return "OTHINP"
        if name.startswith("othlst"):
            return "OTHLST"
        return os.path.splitext(original_name or "")[1].lstrip(".").upper()

    def _handle_model_doc_delete(self, selected: List[Dict[str, Any]], _records: List[Dict[str, Any]]):
        total = 0
        for rec in selected:
            record_id = rec.get("record_id")
            if record_id is None:
                continue
            soft_delete_record(int(record_id))
            total += 1
        path_key = self.current_leaf_key
        self.row_paths_by_path.pop(path_key, None)
        self.row_db_records_by_path.pop(path_key, None)
        _records[:] = self._build_model_file_doc_records(path_key)
        QMessageBox.information(self, "提示", f"已删除 {total} 个文件。")

    def _leaf_row_dir(self, path_key: str, row: int, create_dir: bool = True) -> str:
        segs = path_key.split("/") if path_key else []
        facility = (self.facility_code or "").strip()
        d = os.path.join(self.upload_root, *( [facility] if facility else [] ), *segs, f"row_{row + 1}")
        if create_dir:
            os.makedirs(d, exist_ok=True)
        return d
    def _show_files_for_current_leaf(self):
        node = self._get_node_by_path(self.current_path)
        if not node or node.get("type") != "leaf":
            return

        path_key = self._current_path_key()
        if path_key in self.doc_man_configs:
            self.current_leaf_key = path_key
            if self.current_path and self.current_path[0] == "\u5f53\u524d\u6a21\u578b":
                self.doc_man_widget.set_action_handlers(
                    upload_handler=self._handle_model_doc_upload,
                    delete_handler=self._handle_model_doc_delete,
                    download_handler=self._handle_model_doc_download,
                )
                records = self._build_model_file_doc_records(path_key)
            else:
                self.doc_man_widget.set_action_handlers(
                    upload_handler=None,
                    delete_handler=None,
                    download_handler=None,
                )
                records = self.doc_man_records.setdefault(path_key, [])
            self.doc_man_widget.set_context(
                self.current_path,
                records,
                self.doc_man_configs[path_key],
                facility_code=self.facility_code,
                overlay_from_db=not (self.current_path and self.current_path[0] == "\u5f53\u524d\u6a21\u578b"),
                hide_empty_templates=True,
                db_list_mode=not (self.current_path and self.current_path[0] == "\u5f53\u524d\u6a21\u578b"),
            )
            return

        model_key = node.get("model_key")
        row_configs = self.model_row_configs.get(model_key, [])
        self.current_row_configs = row_configs
        self.current_leaf_key = path_key

        row_paths = self._get_row_paths_for(path_key)
        db_row_records = self.row_db_records_by_path.get(path_key, {})
        self.current_table_rows = self._build_leaf_display_rows(row_configs, row_paths, db_row_records)

        self.table.setRowCount(len(self.current_table_rows))
        for row, row_meta in enumerate(self.current_table_rows):
            cfg = row_meta["cfg"]
            self._set_center_item(self.table, row, 0, row + 1)
            self._set_center_item(self.table, row, 1, cfg.get("category", ""))
            self._set_center_item(self.table, row, 2, cfg.get("fmt", ""))

            mtime = row_meta.get("mtime")
            date_str = mtime.strftime("%Y/%m/%d") if isinstance(mtime, datetime.datetime) else ""
            self._set_center_item(self.table, row, 3, date_str)

            remark_item = QTableWidgetItem(str(row_meta.get("remark") or ""))
            remark_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table.setItem(row, 6, remark_item)

            self._set_center_item(self.table, row, 4, "\u4e0a\u4f20" if row_meta.get("upload_enabled") else "")
            self._set_center_item(self.table, row, 5, "\u4e0b\u8f7d" if row_meta.get("download_enabled") else "")

        self._auto_fit_columns_with_padding(self.table, padding=36)
        self._auto_fit_row_height(self.table, padding=12)

    def _get_doc_man_upload_dir(self, path_segments: List[str]) -> str:
        facility = (self.facility_code or "").strip()
        target_dir = os.path.join(self.upload_root, *([facility] if facility else []), *path_segments)
        os.makedirs(target_dir, exist_ok=True)
        return target_dir

    def _on_table_cell_clicked(self, row: int, col: int):
        if not self.current_leaf_key:
            return
        if row < 0 or row >= len(self.current_table_rows):
            return
        row_meta = self.current_table_rows[row]
        if col == 4 and row_meta.get("upload_enabled"):
            self._handle_upload(row)
        elif col == 5 and row_meta.get("download_enabled"):
            self._handle_download(row)

    def _parse_allowed_exts(self, fmt_text: str) -> List[str]:
        if not fmt_text:
            return []
        tmp = fmt_text.replace("\uff0c", ",").replace("/", ",")
        parts = [p.strip().lower() for p in tmp.split(",") if p.strip()]
        return parts

    def _handle_upload(self, row: int):
        if row < 0 or row >= len(self.current_table_rows):
            return

        row_meta = self.current_table_rows[row]
        cfg = row_meta["cfg"]
        allowed_exts = self._parse_allowed_exts(cfg.get("fmt", ""))
        target_row_index = int(row_meta.get("row_index", row))

        file_path, _ = QFileDialog.getOpenFileName(self, "\u9009\u62e9\u8981\u4e0a\u4f20\u7684\u6587\u4ef6", "", "\u6240\u6709\u6587\u4ef6 (*.*)")
        if not file_path:
            return

        ext = os.path.splitext(file_path)[1].lower()
        ext_no_dot = ext[1:] if ext.startswith(".") else ext
        if allowed_exts and ext_no_dot not in allowed_exts:
            QMessageBox.warning(
                self,
                "\u683c\u5f0f\u4e0d\u5339\u914d",
                f"\u5f53\u524d\u884c\u4ec5\u5141\u8bb8\u4e0a\u4f20\u4ee5\u4e0b\u683c\u5f0f\uff1a{cfg.get('fmt', '')}\\n\u4f60\u9009\u62e9\u7684\u6587\u4ef6\u540e\u7f00\u4e3a\uff1a{ext}",
            )
            return

        row_dir = self._leaf_row_dir(self.current_leaf_key, target_row_index, create_dir=True)
        basename = os.path.basename(file_path)
        dest_path = os.path.join(row_dir, basename)
        root, ext = os.path.splitext(dest_path)
        suffix = 1
        while os.path.exists(dest_path):
            dest_path = f"{root} ({suffix}){ext}"
            suffix += 1

        try:
            shutil.copy2(file_path, dest_path)
        except Exception as e:
            QMessageBox.critical(self, "\u4e0a\u4f20\u5931\u8d25", f"\u590d\u5236\u6587\u4ef6\u65f6\u51fa\u9519\uff1a\\n{e}")
            return

        row_paths = self._get_row_paths_for(self.current_leaf_key)
        row_paths[target_row_index] = dest_path
        self._show_files_for_current_leaf()
        QMessageBox.information(self, "\u4e0a\u4f20\u6210\u529f", "\u6587\u4ef6\u5df2\u4e0a\u4f20\u3002")

    def _handle_download(self, row: int):
        if row < 0 or row >= len(self.current_table_rows):
            return
        path = str(self.current_table_rows[row].get("file_path") or "")
        if not path or not os.path.exists(path):
            QMessageBox.information(self, "\u63d0\u793a", "\u8be5\u884c\u5c1a\u672a\u4e0a\u4f20\u6587\u4ef6\uff0c\u65e0\u6cd5\u4e0b\u8f7d\u3002")
            return

        default_name = os.path.basename(path)
        save_path, _ = QFileDialog.getSaveFileName(self, "\u9009\u62e9\u4fdd\u5b58\u4f4d\u7f6e", default_name, "\u6240\u6709\u6587\u4ef6 (*.*)")
        if not save_path:
            return

        try:
            shutil.copy2(path, save_path)
        except Exception as e:
            QMessageBox.critical(self, "\u4e0b\u8f7d\u5931\u8d25", f"\u590d\u5236\u6587\u4ef6\u65f6\u51fa\u9519\uff1a\\n{e}")
            return

        QMessageBox.information(self, "\u4e0b\u8f7d\u5b8c\u6210", "\u6587\u4ef6\u5df2\u4fdd\u5b58\u3002")

# ============================================================
# 2) Page：DropdownBar + QFrame card(0边距0间距) + docs_widget
#    - 顶部不显示 BasePage 标题
#    - 不自写文件夹布局（文件夹由 ConstructionDocsWidget 渲染）
# ============================================================
    # Clean overrides for current-model DB behaviour.
    def _display_name_from_row(self, row: Dict[str, Any]) -> str:
        return str(row.get("original_name") or "")

    def _build_doc_man_configs(self) -> Dict[str, List[str]]:
        leaf_categories: Dict[str, List[str]] = {}
        source_map = {
            "静力": "static",
            "疲劳": "fatigue",
            "倒塌": "collapse",
            "地震": "seismic",
            "其他模型": "other",
        }
        for leaf_name, model_key in source_map.items():
            categories: List[str] = []
            for cfg in self.model_row_configs.get(model_key, []):
                category = str(cfg.get("category") or "").strip()
                if category and category not in categories:
                    categories.append(category)
            if "其他" not in categories:
                categories.append("其他")
            leaf_categories[leaf_name] = categories

        configs: Dict[str, List[str]] = {}
        root_names = ["当前模型", "详细设计模型", "改造1模型", "改造N模型"]
        leaf_mapping = {
            "静力": "静力",
            "疲劳": "疲劳",
            "倒塌": "倒塌",
            "地震": "地震",
            "其他模型": "其他模型",
        }
        for root in root_names:
            for leaf, key in leaf_mapping.items():
                configs[f"{root}/{leaf}"] = list(leaf_categories[key])
        return configs

    def _build_doc_man_records(self) -> Dict[str, List[Dict]]:
        return {path_key: [] for path_key in self.doc_man_configs}

    def _pick_category_option(self, categories: List[str], *keywords: str, fallback: str = "其他") -> str:
        for option in categories:
            if all(word in option for word in keywords):
                return option
        for option in categories:
            if any(word in option for word in keywords):
                return option
        return fallback

    def _category_from_db_row(self, row: Dict[str, Any], categories: List[str]) -> str:
        name = str(row.get("original_name") or "").lower()
        logical_path = str(row.get("logical_path") or "").replace("\\", "/")
        upload_marker = "/用户上传/"
        if upload_marker in logical_path:
            uploaded_category = logical_path.split(upload_marker, 1)[1].strip("/")
            if uploaded_category:
                return uploaded_category.split("/", 1)[0]
        if name.startswith("sacinp"):
            return self._pick_category_option(categories, "结构模型", fallback="结构模型文件")
        if name.startswith("seainp"):
            return self._pick_category_option(categories, "海况", fallback="海况文件")
        if name.startswith("psiinp"):
            return self._pick_category_option(categories, "桩基", fallback="桩基文件")
        if name.startswith("jcninp"):
            return self._pick_category_option(categories, "冲剪", fallback="冲剪节点文件")
        if name.startswith("psilst"):
            return self._pick_category_option(categories, "静力", "结果", fallback="静力分析结果文件")
        if name.startswith("dyninp"):
            return self._pick_category_option(categories, "动力", fallback="动力分析文件")
        if name.startswith("dyrinp"):
            return self._pick_category_option(categories, "动力", "地震", fallback="动力分析文件(地震)")
        if name.startswith("ftginp") or "/疲劳分析/" in logical_path and "/输入/" in logical_path:
            return self._pick_category_option(categories, "疲劳", "模型", fallback="疲劳分析模型文件")
        if name.startswith("ftglst") or "/疲劳分析/" in logical_path and "/结果/" in logical_path:
            return self._pick_category_option(categories, "疲劳", "结果", fallback="疲劳分析结果文件")
        if name.startswith("wvrinp"):
            return self._pick_category_option(categories, "疲劳", "结果", fallback="疲劳分析结果文件")
        if name.startswith("clpinp"):
            return self._pick_category_option(categories, "倒塌", "模型", fallback="倒塌分析模型文件")
        if name == "clplog":
            return self._pick_category_option(categories, "倒塌", "日志", fallback="倒塌分析日志文件")
        if name in {"clplst", "clprst"} or "/倒塌分析/" in logical_path:
            return self._pick_category_option(categories, "倒塌", "结果", fallback="倒塌分析结果文件")
        if name.startswith("pilinp"):
            return self._pick_category_option(categories, "地震", "模型", fallback="地震分析模型文件")
        if name == "lst":
            return self._pick_category_option(categories, "地震", "结果", fallback="地震分析结果文件")
        if name.startswith("othinp"):
            return self._pick_category_option(categories, "其他", "模型", fallback="其他分析模型文件")
        if name.startswith("othlst"):
            return self._pick_category_option(categories, "其他", "结果", fallback="其他分析结果文件")
        return self._pick_category_option(categories, "其他", fallback="其他")

    @staticmethod
    def _category_allows_multiple_files(category: str) -> bool:
        multi_categories = {
            "疲劳分析模型文件",
            "疲劳分析结果文件",
            "倒塌分析日志文件",
            "倒塌分析结果文件",
        }
        return category in multi_categories

    def _doc_category_to_file_type_code(self, category: str) -> str:
        if "疲劳" in category:
            return "fatigue"
        if "倒塌" in category:
            return "collapse"
        if "地震" in category:
            return "seismic"
        if any(word in category for word in ("图", "CAD", "cad")):
            return "drawing"
        if any(word in category for word in ("结构", "模型", "海况", "桩基", "建模")):
            return "model"
        return "other"

    def _handle_model_doc_upload(self, row: int, rec: Dict[str, Any], _records: List[Dict[str, Any]]):
        path_key = self.current_leaf_key
        current_category = str(rec.get("category") or "").strip()
        if not current_category:
            QMessageBox.warning(self, "提示", "请先选择文件类别，再上传文件。")
            return

        title = f"选择上传文件 - {current_category}"
        file_path, _ = QFileDialog.getOpenFileName(self, title, "", "所有文件 (*.*)")
        if not file_path:
            return

        logical_path = rec.get("logical_path") or self._upload_logical_path_for_category(path_key, current_category)
        record_id = rec.get("record_id")
        if record_id is not None and not self._category_allows_multiple_files(current_category):
            soft_delete_record(int(record_id))
        result = upload_file(
            file_path,
            file_type_code=self._doc_category_to_file_type_code(current_category),
            module_code="model_files",
            logical_path=logical_path,
            facility_code=self.facility_code,
            remark=rec.get("remark") or "",
        )
        dt = result.get("source_modified_at") or result.get("uploaded_at")
        resolved_path = resolve_storage_path(result)
        rec["checked"] = False
        rec["category"] = current_category
        rec["fmt"] = self._format_from_original_name(str(result.get("original_name") or os.path.basename(file_path)))
        rec["filename"] = str(result.get("original_name") or os.path.basename(file_path))
        rec["mtime"] = dt.strftime("%Y/%m/%d") if dt else ""
        rec["path"] = resolved_path
        rec["record_id"] = result.get("id")
        rec["logical_path"] = str(result.get("logical_path") or logical_path)
        rec["_force_visible"] = True

        self.row_paths_by_path.pop(path_key, None)
        self.row_db_records_by_path.pop(path_key, None)
        QMessageBox.information(self, "上传成功", "文件已保存到当前目录。")

    def _handle_model_doc_download(self, selected: List[Dict[str, Any]], _records: List[Dict[str, Any]]):
        available: list[tuple[str, str]] = []
        missing = 0
        for rec in selected:
            path = rec.get("path") or ""
            if path and os.path.exists(path):
                available.append((path, rec.get("filename") or os.path.basename(path)))
            else:
                missing += 1

        if not available:
            QMessageBox.information(self, "提示", "未找到可下载的文件。")
            return

        if len(available) == 1:
            src_path, default_name = available[0]
            save_path, _ = QFileDialog.getSaveFileName(self, "保存文件", default_name, "所有文件 (*.*)")
            if not save_path:
                return
            try:
                shutil.copy2(src_path, save_path)
            except Exception as exc:
                QMessageBox.warning(self, "下载失败", str(exc))
                return
            message = "已下载 1 个文件。"
            if missing:
                message += f"\n另有 {missing} 个文件不存在。"
            QMessageBox.information(self, "下载完成", message)
            return

        target_dir = QFileDialog.getExistingDirectory(self, "选择下载文件夹")
        if not target_dir:
            return

        downloaded = 0
        for src_path, filename in available:
            target_path = os.path.join(target_dir, filename)
            root, ext = os.path.splitext(target_path)
            suffix = 1
            while os.path.exists(target_path):
                target_path = f"{root} ({suffix}){ext}"
                suffix += 1
            try:
                shutil.copy2(src_path, target_path)
                downloaded += 1
            except Exception:
                continue

        message = f"已下载 {downloaded} 个文件到：\n{target_dir}"
        if missing:
            message += f"\n另有 {missing} 个文件不存在。"
        QMessageBox.information(self, "下载完成", message)

    def _current_model_prefixes(self, path_key: str) -> List[str]:
        if not self.facility_code or not path_key:
            return []
        parts = path_key.split("/")
        model_root = parts[0] if parts else "当前模型"
        node = self._get_node_by_path(parts)
        model_key = node.get("model_key") if node else ""
        base = f"{self.facility_code}/{model_root}"
        alias_map = {
            "static": ["结构模型", "静力"],
            "seismic": ["地震分析", "地震"],
            "fatigue": ["疲劳分析", "疲劳"],
            "collapse": ["倒塌分析", "倒塌"],
            "other": ["其他", "其他模型"],
        }
        aliases = alias_map.get(model_key, [parts[-1] if parts else ""])
        return [f"{base}/{alias}" for alias in aliases if alias]

    def _upload_logical_path_for_category(self, path_key: str, category: str) -> str:
        parts = path_key.split("/")
        model_root = parts[0] if parts else "当前模型"
        base = f"{self.facility_code}/{model_root}"
        if "结构模型" in category:
            return f"{base}/结构模型/用户上传/{category}"
        if "海况" in category:
            return f"{base}/结构模型/海况/用户上传/{category}"
        if "桩基" in category:
            return f"{base}/结构模型/桩基/用户上传/{category}"
        if "建模" in category or "冲剪" in category:
            return f"{base}/结构模型/建模/用户上传/{category}"
        if "地震" in category:
            branch = "结果" if "结果" in category else "输入"
            return f"{base}/地震分析/{branch}/用户上传/{category}"
        if "疲劳" in category:
            branch = "结果" if "结果" in category else "输入"
            return f"{base}/疲劳分析/{branch}/用户上传/{category}"
        if "倒塌" in category:
            if "日志" in category:
                return f"{base}/倒塌分析/结果/用户上传/{category}"
            branch = "结果" if "结果" in category else "模型"
            return f"{base}/倒塌分析/{branch}/用户上传/{category}"
        return f"{base}/其他/用户上传/{category}"

    def _build_model_file_doc_records(self, path_key: str) -> List[Dict[str, Any]]:
        if not self.facility_code:
            return []
        categories = self.doc_man_configs.get(path_key, [])
        rows: List[Dict[str, Any]] = []
        seen_ids: set[int] = set()
        for prefix in self._current_model_prefixes(path_key):
            for row in list_files_by_prefix(
                module_code="model_files",
                logical_path_prefix=prefix,
                facility_code=self.facility_code,
            ):
                row_id = row.get("id")
                if row_id in seen_ids:
                    continue
                logical_path = str(row.get("logical_path") or "")
                seen_ids.add(row_id)
                dt = row.get("source_modified_at") or row.get("uploaded_at")
                rows.append(
                    {
                        "index": len(rows) + 1,
                        "checked": False,
                        "category": self._category_from_db_row(row, categories),
                        "fmt": self._format_from_original_name(str(row.get("original_name") or "")),
                        "filename": str(row.get("original_name") or ""),
                        "mtime": dt.strftime("%Y/%m/%d") if dt else "",
                        "path": resolve_storage_path(row),
                        "record_id": row.get("id"),
                        "logical_path": logical_path,
                        "remark": str(row.get("remark") or ""),
                    }
                )
        rows.sort(key=lambda item: (str(item.get("category") or ""), str(item.get("logical_path") or ""), str(item.get("filename") or "")))
        for index, row in enumerate(rows, start=1):
            row["index"] = index
        return rows

    def _emit_navigation_state(self):
        self.navigationStateChanged.emit(len(self.current_path) == 0)

class ModelFilesPage(BasePage):
    """文件管理 -> 模型文件 页面（文件夹UI严格复用 ConstructionDocsWidget）"""

    def __init__(self, parent=None):
        # ✅ 删除“模型文件”标题：不给 BasePage 传标题
        super().__init__("", parent)
        self._build_ui()
        self._hide_base_title_if_any()

    def _hide_base_title_if_any(self):
        """兜底：兼容不同 BasePage 实现，隐藏顶部标题控件"""
        for attr in ("title_label", "lbl_title", "label_title", "page_title_label", "page_title", "lblTitle"):
            w = getattr(self, attr, None)
            if isinstance(w, QLabel):
                w.hide()
            else:
                try:
                    if w is not None:
                        w.hide()
                except Exception:
                    pass

        for obj_name in ("PageTitle", "pageTitle", "titleLabel", "lblTitle"):
            w = self.findChild(QLabel, obj_name)
            if w:
                w.hide()

    def _build_ui(self):
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(8)

        # ---------- 顶部下拉条 ----------
        platform_defaults = default_platform()
        fields = [
            {"key": "branch",         "label": "分公司",   "options": ["渤江分公司"],             "default": "渤江分公司"},
            {"key": "op_company",     "label": "作业公司", "options": ["文昌油田群作业公司"],     "default": "文昌油田群作业公司"},
            {"key": "oilfield",       "label": "油气田",   "options": ["文昌19-1油田"],          "default": "文昌19-1油田"},
            {"key": "facility_code",  "label": "设施编码", "options": ["WC19-1WHPC"],           "default": "WC19-1WHPC"},
            {"key": "facility_name",  "label": "设施名称", "options": ["文昌19-1WHPC井口平台"],   "default": "文昌19-1WHPC井口平台"},
            {"key": "facility_type",  "label": "设施类型", "options": ["平台"],                  "default": "平台"},
            {"key": "category",       "label": "分类",     "options": ["井口平台"],              "default": "井口平台"},
            {"key": "start_time",     "label": "投产时间", "options": ["2013-07-15"],           "default": "2013-07-15"},
            {"key": "design_life",    "label": "设计年限", "options": ["15"],                   "default": "15"},
        ]
        field_map = {item["key"]: item for item in fields}
        field_map["oilfield"]["options"] = [platform_defaults["oilfield"]]
        field_map["oilfield"]["default"] = platform_defaults["oilfield"]
        field_map["facility_code"]["options"] = ["WC19-1D", "WC9-7"]
        field_map["facility_code"]["default"] = platform_defaults["facility_code"]
        field_map["facility_name"]["options"] = ["WC19-1D平台", "WC9-7平台"]
        field_map["facility_name"]["default"] = platform_defaults["facility_name"]
        field_map["facility_type"]["options"] = [platform_defaults["facility_type"]]
        field_map["facility_type"]["default"] = platform_defaults["facility_type"]
        field_map["category"]["options"] = [platform_defaults["category"]]
        field_map["category"]["default"] = platform_defaults["category"]
        field_map["start_time"]["options"] = [platform_defaults["start_time"]]
        field_map["start_time"]["default"] = platform_defaults["start_time"]
        field_map["design_life"]["options"] = [platform_defaults["design_life"]]
        field_map["design_life"]["default"] = platform_defaults["design_life"]
        self.dropdown_bar = DropdownBar(fields, parent=self)
        self.main_layout.addWidget(self.dropdown_bar, 0)

        # ---------- 中间容器：QFrame card（0边距、0间距） ----------
        card = QFrame(self)
        card.setObjectName("ModelFilesCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        self.docs_widget = ModelFilesDocsWidget(card)
        card_layout.addWidget(self.docs_widget)

        self.main_layout.addWidget(card, 1)

        # 可选：背景风格（不影响 ConstructionDocsWidget 内部布局）
        self.setStyleSheet("""
            QFrame#ModelFilesCard {
                background-color: #f3f4f6;
                border: none;
            }
        """)

        # 保留联动入口
        self.dropdown_bar.valueChanged.connect(self.on_filter_changed)
        self.docs_widget.docs_widget.navigationStateChanged.connect(self._set_dropdown_visible)
        self._sync_platform_ui()

    def on_filter_changed(self, key: str, value: str):
        self._sync_platform_ui(changed_key=key)

    def _sync_platform_ui(self, changed_key: str | None = None):
        platform = sync_platform_dropdowns(self.dropdown_bar, changed_key=changed_key)
        facility_code = platform["facility_code"]
        platform_name = platform["facility_name"]
        self.docs_widget.set_facility_code(facility_code)
        if self.docs_widget.current_path:
            node = self.docs_widget._get_node_by_path(self.docs_widget.current_path)
            if node and node.get("type") == "leaf":
                self.docs_widget._show_files_for_current_leaf()
            else:
                self.docs_widget._refresh_folder_view()
        window = self.window()
        if hasattr(window, "set_current_platform_name"):
            window.set_current_platform_name(platform_name)

    def get_current_platform_name(self):
        return self.dropdown_bar.get_value("facility_name")

    def _set_dropdown_visible(self, visible: bool):
        self.dropdown_bar.setVisible(visible)
        self.dropdown_bar.setFixedHeight(self.dropdown_bar.sizeHint().height() if visible else 0)
