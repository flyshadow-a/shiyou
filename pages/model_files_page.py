# -*- coding: utf-8 -*-
# pages/model_files_page.py

import os
import shutil
import datetime
from typing import Dict, List

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFontMetrics
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QSizePolicy, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QStackedWidget, QMessageBox, QFileDialog, QWidget
)

from base_page import BasePage
from dropdown_bar import DropdownBar

# ✅ 直接复用 ConstructionDocsWidget 的文件夹UI与交互（FolderButton / folder_grid / PathBar 等）
from .construction_docs_widget import ConstructionDocsWidget


# ============================================================
# 1) Widget：文件夹UI = ConstructionDocsWidget；叶子表格页 = 旧逻辑表格
#    - 不自写文件夹布局
#    - 保留旧的“表格行配置 + 上传/下载 + 扫描恢复”逻辑
# ============================================================
class ModelFilesDocsWidget(QWidget):
    """
    模型文件专用内容区：
    - Folder View：直接用 ConstructionDocsWidget 画（严格复用其布局/样式/交互）
    - Leaf View：使用旧逻辑的 QTableWidget（序号|类别|格式|修改时间|上传|下载|备注）
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # 当前路径（不含“首页”），例如：
        # [] / ["详细设计模型"] / ["详细设计模型","静力"]
        self.current_path: List[str] = []

        # 文件夹树结构 + 每种模型对应的行配置
        self.folder_tree = self._build_folder_tree()
        self.model_row_configs = self._build_model_row_configs()

        # 每个叶子路径对应的 {row_index: 文件绝对路径}
        self.row_paths_by_path: Dict[str, Dict[int, str]] = {}  # { "详细设计模型/静力": {0: path, 1: path, ...}}

        # 当前显示的叶子路径 key 和行配置
        self.current_leaf_key: str = ""
        self.current_row_configs: List[Dict] = []

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
                {"category": "疲劳分析结果文件",    "fmt": "ftglst"},
            ],
            "collapse": [  # 倒塌
                {"category": "结构模型文件",          "fmt": "sacinp"},
                {"category": "海况文件",              "fmt": "seainp"},
                {"category": "桩基文件",              "fmt": "psiinp"},
                {"category": "倒塌分析模型文件",      "fmt": "clpinp"},
                {"category": "倒塌分析日志文件",      "fmt": "clplog"},
                {"category": "倒塌分析结果文件",      "fmt": "clplst"},
                {"category": "倒塌分析结果文件(补)", "fmt": "clprst"},
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
    # UI 构建：stack = 文件夹(ConstructionDocsWidget) / 叶子表格
    # ------------------------------------------------------------------
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.content_stack = QStackedWidget(self)
        layout.addWidget(self.content_stack, 1)

        # ============================================================
        # 1) 文件夹页：严格复用 ConstructionDocsWidget 的文件夹UI
        # ============================================================
        self.docs_widget = ConstructionDocsWidget(parent=self)

        # 用它画 folder_grid，但点击/面包屑行为走本类逻辑
        # （避免改 ConstructionDocsWidget 源码）
        self.docs_widget._on_folder_clicked = self._on_folder_clicked
        self.docs_widget._on_breadcrumb_clicked = self._on_breadcrumb_clicked

        # 初次刷新它的文件夹UI
        self._refresh_folder_view()

        self.content_stack.addWidget(self.docs_widget)

        # ============================================================
        # 2) 叶子：文件表格页（旧逻辑）
        # ============================================================
        self.files_page = QWidget(self)
        files_layout = QVBoxLayout(self.files_page)
        files_layout.setContentsMargins(0, 0, 0, 0)
        files_layout.setSpacing(0)

        self.table = QTableWidget(0, 7, self.files_page)
        self.table.setHorizontalHeaderLabels(
            ["序号", "文件类别", "文件格式", "修改时间", "上传", "下载", "备注"]
        )
        self._init_table_common(self.table)
        self.table.cellClicked.connect(self._on_table_cell_clicked)

        files_layout.addWidget(self.table)
        self.content_stack.addWidget(self.files_page)

        # 默认：首页文件夹视图
        self.content_stack.setCurrentWidget(self.docs_widget)

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
            self.content_stack.setCurrentWidget(self.docs_widget)
        else:
            self._show_files_for_current_leaf()
            self.content_stack.setCurrentWidget(self.files_page)

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
            self.content_stack.setCurrentWidget(self.docs_widget)
        else:
            self._show_files_for_current_leaf()
            self.content_stack.setCurrentWidget(self.files_page)

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

        # 行数随配置走：但为了兼容“配置变更”，最多扫描 30 行
        max_rows = 30
        for row in range(max_rows):
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

    def _leaf_row_dir(self, path_key: str, row: int, create_dir: bool = True) -> str:
        segs = path_key.split("/") if path_key else []
        d = os.path.join(self.upload_root, *segs, f"row_{row + 1}")
        if create_dir:
            os.makedirs(d, exist_ok=True)
        return d

    def _show_files_for_current_leaf(self):
        """
        根据 current_path 中的叶子节点显示文件表格。
        """
        node = self._get_node_by_path(self.current_path)
        if not node or node.get("type") != "leaf":
            return

        model_key = node.get("model_key")
        row_configs = self.model_row_configs.get(model_key, [])
        self.current_row_configs = row_configs

        path_key = self._current_path_key()
        self.current_leaf_key = path_key
        row_paths = self._get_row_paths_for(path_key)

        self.table.setRowCount(len(row_configs))

        for row, cfg in enumerate(row_configs):
            self._set_center_item(self.table, row, 0, row + 1)
            self._set_center_item(self.table, row, 1, cfg.get("category", ""))
            self._set_center_item(self.table, row, 2, cfg.get("fmt", ""))

            file_path = row_paths.get(row)
            if file_path and os.path.exists(file_path):
                mtime = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                date_str = mtime.strftime("%Y/%m/%d")
                self._set_center_item(self.table, row, 3, date_str)

                remark_item = QTableWidgetItem(os.path.basename(file_path))
                remark_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self.table.setItem(row, 6, remark_item)
            else:
                self._set_center_item(self.table, row, 3, "")
                self._set_center_item(self.table, row, 6, "")

            self._set_center_item(self.table, row, 4, "上传")
            self._set_center_item(self.table, row, 5, "下载")

        self._auto_fit_columns_with_padding(self.table, padding=36)
        self._auto_fit_row_height(self.table, padding=12)

    # ------------------------------------------------------------------
    # 上传 / 下载 点击事件（旧逻辑）
    # ------------------------------------------------------------------
    def _on_table_cell_clicked(self, row: int, col: int):
        if not self.current_leaf_key:
            return
        if col == 4:
            self._handle_upload(row)
        elif col == 5:
            self._handle_download(row)

    def _parse_allowed_exts(self, fmt_text: str) -> List[str]:
        if not fmt_text:
            return []
        tmp = fmt_text.replace("，", ",").replace("/", ",")
        parts = [p.strip().lower() for p in tmp.split(",") if p.strip()]
        return parts

    def _handle_upload(self, row: int):
        if row < 0 or row >= len(self.current_row_configs):
            return

        cfg = self.current_row_configs[row]
        allowed_exts = self._parse_allowed_exts(cfg.get("fmt", ""))

        file_path, _ = QFileDialog.getOpenFileName(self, "选择要上传的文件", "", "所有文件 (*.*)")
        if not file_path:
            return

        ext = os.path.splitext(file_path)[1].lower()
        ext_no_dot = ext[1:] if ext.startswith(".") else ext

        if allowed_exts and ext_no_dot not in allowed_exts:
            QMessageBox.warning(
                self,
                "格式不匹配",
                f"当前行仅允许上传以下格式：{cfg.get('fmt', '')}\n"
                f"你选择的文件后缀为：{ext}",
            )
            return

        row_dir = self._leaf_row_dir(self.current_leaf_key, row, create_dir=True)
        basename = os.path.basename(file_path)
        dest_path = os.path.join(row_dir, basename)

        try:
            shutil.copy2(file_path, dest_path)
        except Exception as e:
            QMessageBox.critical(self, "上传失败", f"复制文件时出错：\n{e}")
            return

        row_paths = self._get_row_paths_for(self.current_leaf_key)
        row_paths[row] = dest_path

        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(dest_path))
        date_str = mtime.strftime("%Y/%m/%d")
        self._set_center_item(self.table, row, 3, date_str)

        remark_item = QTableWidgetItem(basename)
        remark_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.setItem(row, 6, remark_item)

        self._auto_fit_columns_with_padding(self.table, padding=36)
        QMessageBox.information(self, "上传成功", "文件已上传。")

    def _handle_download(self, row: int):
        row_paths = self._get_row_paths_for(self.current_leaf_key)
        path = row_paths.get(row)
        if not path or not os.path.exists(path):
            QMessageBox.information(self, "提示", "该行尚未上传文件，无法下载。")
            return

        default_name = os.path.basename(path)
        save_path, _ = QFileDialog.getSaveFileName(
            self, "选择保存位置", default_name, "所有文件 (*.*)"
        )
        if not save_path:
            return

        try:
            shutil.copy2(path, save_path)
        except Exception as e:
            QMessageBox.critical(self, "下载失败", f"复制文件时出错：\n{e}")
            return

        QMessageBox.information(self, "下载完成", "文件已保存。")


# ============================================================
# 2) Page：DropdownBar + QFrame card(0边距0间距) + docs_widget
#    - 顶部不显示 BasePage 标题
#    - 不自写文件夹布局（文件夹由 ConstructionDocsWidget 渲染）
# ============================================================
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
        fields = [
            {"key": "branch",         "label": "分公司",   "options": ["渤江分公司"],             "default": "渤江分公司"},
            {"key": "op_company",     "label": "作业公司", "options": ["文昌油田群作业公司"],     "default": "文昌油田群作业公司"},
            {"key": "oilfield",       "label": "油气田",   "options": ["文昌19-1油田"],          "default": "文昌19-1油田"},
            {"key": "facility_code",  "label": "设施编号", "options": ["WC19-1WHPC"],           "default": "WC19-1WHPC"},
            {"key": "facility_name",  "label": "设施名称", "options": ["文昌19-1WHPC井口平台"],   "default": "文昌19-1WHPC井口平台"},
            {"key": "facility_type",  "label": "设施类型", "options": ["平台"],                  "default": "平台"},
            {"key": "category",       "label": "分类",     "options": ["井口平台"],              "default": "井口平台"},
            {"key": "start_time",     "label": "投产时间", "options": ["2013-07-15"],           "default": "2013-07-15"},
            {"key": "design_life",    "label": "设计年限", "options": ["15"],                   "default": "15"},
        ]
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

    def on_filter_changed(self, key: str, value: str):
        print(f"[ModelFilesPage] 条件变化：{key} -> {value}")
        # 如果未来要按筛选条件重置目录/刷新，可在此扩展
