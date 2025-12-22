# -*- coding: utf-8 -*-
# pages/model_files_page.py

import os
import shutil
import datetime

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFontMetrics, QPixmap
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QTableWidget, QGridLayout, QStackedWidget, QSizePolicy,
    QTableWidgetItem, QMessageBox, QFileDialog, QWidget
)

from base_page import BasePage
from dropdown_bar import DropdownBar


# ---------- 可点击的面包屑标签 ----------
class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ModelFilesPage(BasePage):
    """
    文件管理 -> 模型文件 页面

    结构：
    顶部：DropdownBar 下拉条
    中部：蓝色路径栏 + 内容区

    内容区三层：
    1) 首页：当前模型 / 详细设计模型 / 改造1模型 / 改造N模型 四个文件夹
    2) 第二层：每个上级下都有 静力 / 地震 / 疲劳 / 倒塌 / 其他模型 五个文件夹
    3) 叶子层：文件表格，列为
       序号 | 文件类别 | 文件格式 | 修改时间 | 上传 | 下载 | 备注
    """

    def __init__(self, parent=None):
        super().__init__("模型文件", parent)

        # 当前路径（不含“首页”），例如：
        # [] / ["详细设计模型"] / ["详细设计模型","静力"]
        self.current_path = []

        # 文件夹树结构 + 每种模型对应的行配置
        self.folder_tree = self._build_folder_tree()
        self.model_row_configs = self._build_model_row_configs()

        # 每个叶子路径对应的 {row_index: 文件绝对路径}
        self.row_paths_by_path = {}  # { "详细设计模型/静力": {0: path, 1: path, ...}}

        # 当前显示的叶子路径 key 和行配置
        self.current_leaf_key = ""
        self.current_row_configs = []

        # 上传根目录：项目根目录/upload/model_files
        self.upload_root = self._get_upload_root()

        self._build_ui()

    # ------------------------------------------------------------------
    # 路径 & 数据结构
    # ------------------------------------------------------------------
    def _get_project_root(self):
        here = os.path.abspath(__file__)
        pages_dir = os.path.dirname(here)
        return os.path.dirname(pages_dir)

    def _get_upload_root(self):
        project_root = self._get_project_root()
        path = os.path.join(project_root, "upload", "model_files")
        os.makedirs(path, exist_ok=True)
        return path

    def _build_folder_tree(self):
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

    def _build_model_row_configs(self):
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
            "other": [  # 其他模型，可以后续再细化
                {"category": "结构模型文件",        "fmt": "sacinp"},
                {"category": "海况文件",            "fmt": "seainp"},
                {"category": "其他分析模型文件",    "fmt": "othinp"},
                {"category": "其他分析结果文件",    "fmt": "othlst"},
            ],
        }

    def _current_path_key(self) -> str:
        # 用 “/” 拼接当前路径，作为 key
        return "/".join(self.current_path)

    def _get_node_by_path(self, path_list):
        node = {"type": "folder", "children": self.folder_tree}
        for name in path_list:
            children = node.get("children", {})
            node = children.get(name)
            if node is None:
                break
        return node

    # ------------------------------------------------------------------
    # 通用表格工具
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
            /* 关键：选中时的颜色 */
            QTableWidget::item:selected {
                background-color: #dbeafe;    /* 浅蓝底 */
                color: #111827;               /* 深色文字 */
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
    # UI 构建
    # ------------------------------------------------------------------
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

        # ---------- 中部卡片 ----------
        card = QFrame()
        card.setObjectName("CardFrame")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 8, 8, 8)
        card_layout.setSpacing(8)

        # ====== 路径栏 ======
        self.path_bar = QFrame()
        self.path_bar.setObjectName("PathBar")
        path_layout = QHBoxLayout(self.path_bar)
        path_layout.setContentsMargins(10, 4, 10, 4)
        path_layout.setSpacing(8)

        # 左侧小图标
        self.path_icon_label = QLabel()
        self.path_icon_label.setFixedSize(24, 24)
        project_root = self._get_project_root()
        icon_path = os.path.join(project_root, "pict", "wenjian.png")
        if os.path.exists(icon_path):
            pix = QPixmap(icon_path)
            if not pix.isNull():
                pix = pix.scaled(22, 22, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.path_icon_label.setPixmap(pix)
        self.path_icon_label.setStyleSheet("""
            background-color: #004080;   /* 深蓝色 */
            border-radius: 2px;
            padding: 2px;
        """)

        path_layout.addWidget(self.path_icon_label)

        # 面包屑容器
        self.breadcrumb_container = QFrame()
        self.breadcrumb_layout = QHBoxLayout(self.breadcrumb_container)
        self.breadcrumb_layout.setContentsMargins(0, 0, 0, 0)
        self.breadcrumb_layout.setSpacing(4)
        path_layout.addWidget(self.breadcrumb_container)
        path_layout.addStretch()

        card_layout.addWidget(self.path_bar)

        # ====== 内容堆叠：文件夹视图 / 文件表格视图 ======
        self.content_stack = QStackedWidget()
        card_layout.addWidget(self.content_stack, 1)

        # 1) 文件夹页
        self.folder_page = QWidget()
        folder_layout = QVBoxLayout(self.folder_page)
        folder_layout.setContentsMargins(20, 20, 20, 20)
        folder_layout.setSpacing(10)

        self.folder_grid = QGridLayout()
        self.folder_grid.setHorizontalSpacing(60)
        self.folder_grid.setVerticalSpacing(40)
        folder_layout.addLayout(self.folder_grid)
        folder_layout.addStretch()

        # 2) 文件表格页
        self.files_page = QWidget()
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

        self.content_stack.addWidget(self.folder_page)
        self.content_stack.addWidget(self.files_page)

        self.main_layout.addWidget(card, 1)

        # 全局样式
        self.setStyleSheet("""
            QFrame#PathBar {
                background-color: #006bb3;
                color: #ffffff;
            }
            QLabel {
                font-size: 13px;
            }
            QFrame#CardFrame {
                background-color: #f3f4f6;
            }
        """)

        # 初始：首页
        self._update_breadcrumb()
        self._refresh_folder_view()
        self.content_stack.setCurrentWidget(self.folder_page)

    # ------------------------------------------------------------------
    # 面包屑 & 文件夹视图
    # ------------------------------------------------------------------
    def _update_breadcrumb(self):
        # 清空原有面包屑
        while self.breadcrumb_layout.count():
            item = self.breadcrumb_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

        segments = [("首页", [])]
        for i, name in enumerate(self.current_path):
            segments.append((name, self.current_path[: i + 1]))

        for idx, (name, path_prefix) in enumerate(segments):
            is_last = (idx == len(segments) - 1)
            lbl = ClickableLabel(name)
            if is_last:
                lbl.setStyleSheet("color: #ffffff; font-weight: bold;")
            else:
                lbl.setStyleSheet("color: #ffffff; text-decoration: underline;")
                lbl.setCursor(Qt.PointingHandCursor)
                lbl.clicked.connect(lambda p=path_prefix: self._on_breadcrumb_clicked(p))
            self.breadcrumb_layout.addWidget(lbl)

            if idx != len(segments) - 1:
                arrow = QLabel(">")
                arrow.setStyleSheet("color: #ffffff;")
                self.breadcrumb_layout.addWidget(arrow)

    def _on_breadcrumb_clicked(self, path_prefix):
        self.current_path = list(path_prefix)
        self._update_breadcrumb()

        node = self._get_node_by_path(self.current_path)
        if not node:
            return
        if node.get("type") == "folder":
            self._refresh_folder_view()
            self.content_stack.setCurrentWidget(self.folder_page)
        else:
            self._show_files_for_current_leaf()
            self.content_stack.setCurrentWidget(self.files_page)

    def _clear_grid_layout(self, layout: QGridLayout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

    def _refresh_folder_view(self):
        """根据 current_path 显示当前层级的子文件夹。"""
        self._clear_grid_layout(self.folder_grid)

        node = self._get_node_by_path(self.current_path)
        children = node.get("children", {}) if node else {}

        max_cols = 4
        row, col = 0, 0

        project_root = self._get_project_root()
        icon_path = os.path.join(project_root, "pict", "wenjian.png")
        pix = QPixmap(icon_path) if os.path.exists(icon_path) else QPixmap()

        for name, child in children.items():
            # ---- 图标 ----
            lbl_icon = QLabel()
            if not pix.isNull():
                lbl_icon.setPixmap(
                    pix.scaled(80, 60, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )

            # ---- 文字（仍然是可点击的）----
            lbl_text = ClickableLabel(name)
            lbl_text.setAlignment(Qt.AlignHCenter)
            lbl_text.setCursor(Qt.PointingHandCursor)
            lbl_text.clicked.connect(lambda _=None, n=name: self._on_folder_clicked(n))

            # ---- 整个 wrapper 也可点击：点图标或空白都有效 ----
            wrapper = QWidget()
            layout = QVBoxLayout(wrapper)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(4)
            layout.addWidget(lbl_icon, 0, Qt.AlignHCenter)
            layout.addWidget(lbl_text, 0, Qt.AlignHCenter)

            # 关键：把 mousePressEvent 绑定到 wrapper 上
            def make_click_handler(folder_name):
                def handler(event):
                    if event.button() == Qt.LeftButton:
                        self._on_folder_clicked(folder_name)
                return handler

            wrapper.mousePressEvent = make_click_handler(name)
            wrapper.setCursor(Qt.PointingHandCursor)

            self.folder_grid.addWidget(wrapper, row, col)

            col += 1
            if col >= max_cols:
                col = 0
                row += 1


    def _on_folder_clicked(self, folder_name: str):
        node = self._get_node_by_path(self.current_path)
        if not node:
            return
        child = node.get("children", {}).get(folder_name)
        if not child:
            return

        self.current_path.append(folder_name)
        self._update_breadcrumb()

        if child.get("type") == "folder":
            self._refresh_folder_view()
            self.content_stack.setCurrentWidget(self.folder_page)
        else:
            self._show_files_for_current_leaf()
            self.content_stack.setCurrentWidget(self.files_page)

    # ------------------------------------------------------------------
    # 叶子：文件表格
    # ------------------------------------------------------------------
    def _get_row_paths_for(self, path_key: str):
        if path_key not in self.row_paths_by_path:
            # 第一次进入该路径时，从磁盘扫描一次
            self.row_paths_by_path[path_key] = self._scan_existing_uploads_for_path(path_key)
        return self.row_paths_by_path[path_key]

    def _scan_existing_uploads_for_path(self, path_key: str):
        """用于程序重启后恢复已有上传文件。"""
        segs = path_key.split("/") if path_key else []
        row_paths = {}
        # 用当前模型行数扫描即可
        # 如果此时还没设置 current_row_configs，也没关系，稍后 _show_files 会覆盖
        # 这里先简单认为最多 10 行
        max_rows = 10
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
        """根据 current_path 中的叶子节点显示文件表格。"""
        node = self._get_node_by_path(self.current_path)
        if not node or node.get("type") != "leaf":
            return

        model_key = node.get("model_key")
        row_configs = self.model_row_configs.get(model_key, [])
        self.current_row_configs = row_configs

        path_key = self._current_path_key()
        self.current_leaf_key = path_key
        row_paths = self._get_row_paths_for(path_key)

        # 设置表格行数
        self.table.setRowCount(len(row_configs))

        for row, cfg in enumerate(row_configs):
            self._set_center_item(self.table, row, 0, row + 1)
            self._set_center_item(self.table, row, 1, cfg["category"])
            self._set_center_item(self.table, row, 2, cfg["fmt"])

            # 修改时间 / 备注 如果已有上传文件则恢复
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

            # 上传 / 下载 列
            self._set_center_item(self.table, row, 4, "上传")
            self._set_center_item(self.table, row, 5, "下载")

        self._auto_fit_columns_with_padding(self.table, padding=36)
        self._auto_fit_row_height(self.table, padding=12)

    # ------------------------------------------------------------------
    # 上传 / 下载 点击事件
    # ------------------------------------------------------------------
    def _on_table_cell_clicked(self, row: int, col: int):
        if not self.current_leaf_key:
            return
        if col == 4:
            self._handle_upload(row)
        elif col == 5:
            self._handle_download(row)

    def _parse_allowed_exts(self, fmt_text: str):
        if not fmt_text:
            return []
        tmp = fmt_text.replace("，", ",").replace("/", ",")
        parts = [p.strip().lower() for p in tmp.split(",") if p.strip()]
        return parts

    def _handle_upload(self, row: int):
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

        # 记录路径
        row_paths = self._get_row_paths_for(self.current_leaf_key)
        row_paths[row] = dest_path

        # 更新时间 & 备注
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
