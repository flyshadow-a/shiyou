# -*- coding: utf-8 -*-
# pages/construction_docs_widget.py

import os
import shutil
from typing import Dict, List

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QStackedWidget,
    QGridLayout, QToolButton, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QMessageBox, QAbstractItemView
)
from PyQt5.QtGui import QPixmap, QIcon, QDesktopServices
from PyQt5.QtCore import Qt, QSize, QDateTime, pyqtSignal, QUrl

from pages.doc_man import DocManWidget


class ClickableLabel(QLabel):
    """一个简单的可点击 QLabel，发出 clicked() 信号。"""
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ConstructionDocsWidget(QWidget):
    navigationStateChanged = pyqtSignal(bool)
    """
    建设阶段完工文件 复用组件：

    首页
      └─ 详细设计
          └─ 结构
              ├─ 规格书
              ├─ 设计图纸
              ├─ 分析报告
              └─ 重控报告

    这四个叶子目录都是 7 列表格：

        序号 | 文件类别 | 文件格式 | 修改时间 | 上传 | 下载 | 备注

    - 备注默认空，可编辑；
    - 上传：点击对应行“上传”单元格或上方按钮触发；
    - 下载：点击“下载”单元格，在有文件时用系统默认程序打开；
    - 修改时间 = 上传时间，未上传前为空。
    """

    # ================== 上传根目录 ==================
    def _get_upload_root(self) -> str:
        """
        上传文件的根目录。

        若要修改物理存放位置，只改这里即可。
        """
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        facility = (getattr(self, "facility_code", "") or "").strip()
        return os.path.join(project_root, "upload", facility) if facility else os.path.join(project_root, "upload")
    # =================================================

    def __init__(self, parent=None, show_platform_description=False):
        super().__init__(parent)
        self.setObjectName("ConstructionDocsWidget")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.show_platform_description = show_platform_description
        self.breadcrumb_font_ratio = 0.015
        self.platform_name = ""
        self.platform_description = ""
        self.facility_code = ""

        # 当前路径：["详细设计", "结构", "规格书"] 之类
        self.current_path: List[str] = []

        # 文件夹树结构 & 文件记录
        self.folder_tree = self._build_folder_tree()
        self.file_records: Dict[str, List[Dict]] = self._build_demo_file_records()
        self.doc_man_configs = self._build_doc_man_configs()

        # 资源路径：项目根目录
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.folder_icon_path = os.path.join(self.project_root, "pict/wenjian.png")

        self._build_ui()

    # ---------------- 文件夹树 / 初始数据 ---------------- #
    # ---------------- 一些工具方法 ---------------- #
    def _current_path_key(self) -> str:
        return "/".join(self.current_path)

    def _is_upload_only_path(self, path: List[str]) -> bool:
        return path in (["完工文件"], ["安装文件"])

    def _get_node_by_path(self, path: List[str]) -> Dict:
        node = {"type": "folder", "children": self.folder_tree}
        for name in path:
            children = node.get("children", {})
            node = children.get(name)
            if node is None:
                break
        return node

    # 将 "pdf/word" 等解析为 ['pdf','doc','docx']
    def _parse_allowed_exts(self, spec: str) -> List[str]:
        spec = spec.replace("，", ",").replace("/", ",")
        raw = [s.strip().lower() for s in spec.split(",") if s.strip()]
        exts: List[str] = []
        for s in raw:
            if s == "word":
                exts += ["doc", "docx"]
            elif s == "excel":
                exts += ["xls", "xlsx"]
            else:
                exts.append(s)
        # 去重
        return list(dict.fromkeys(exts))

    # ---------------- UI 构建 ---------------- #
    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)

        # 整体样式
        self.setStyleSheet("""
            QWidget#ConstructionDocsWidget {
                background-color: #f3f4f6;
            }

            QFrame#DocsContainer {
                background-color: #f3f4f6;
            }

            QFrame#DocsCard {
                background-color: #ffffff;
                border-radius: 8px;
                border: 1px solid #d1d5db;
            }

            QFrame#PathBar {
                background-color: #006bb3;
                color: #ffffff;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }

            QLabel#Breadcrumb {
                color: #ffffff;
                background-color: transparent;
            }
            QLabel#Breadcrumb:hover {
                text-decoration: underline;
            }
            QLabel#BreadcrumbCurrent {
                font-weight: bold;
                color: #ffffff;
                background-color: transparent;
            }
            QLabel#BreadcrumbArrow {
                color: #ffffff;
                background-color: transparent;
            }

            QToolButton#FolderButton {
                border: none;
                padding: 4px;
                color: #374151;
                font-size: 14pt;
            }
            QToolButton#FolderButton:hover {
                background-color: #e5f0ff;
                border-radius: 6px;
            }

            QPushButton.UploadButton {
                background-color: #0090d0;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 13px;
            }
            QPushButton.UploadButton:hover {
                background-color: #00a4f2;
            }

            QTableWidget {
                gridline-color: #d1d5db;
                background-color: #f9fafb;
                border: none;
            }
            QHeaderView::section {
                background-color: #e5e7eb;
                color: #111827;
                padding: 4px 6px;
                border: 0px;
                border-right: 1px solid #d1d5db;
            }
            QTableWidget::item {
                padding: 2px 4px;
            }

            QFrame#PlatformDescriptionCard {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #0f5ea5,
                    stop: 1 #1e88d8
                );
                border: none;
                border-radius: 16px;
            }

            QLabel#PlatformDescriptionTitle {
                color: #dbeeff;
                font-size: 14px;
                font-weight: 600;
                background: transparent;
            }

            QLabel#PlatformDescriptionText {
                color: #ffffff;
                font-size: 14px;
                line-height: 1.6;
                background: transparent;
            }
        """)

        if self.show_platform_description:
            self.platform_desc_card = QFrame(self)
            self.platform_desc_card.setObjectName("PlatformDescriptionCard")

            desc_layout = QVBoxLayout(self.platform_desc_card)
            desc_layout.setContentsMargins(20, 18, 20, 18)
            desc_layout.setSpacing(8)

            self.platform_desc_title = QLabel("平台描述", self.platform_desc_card)
            self.platform_desc_title.setObjectName("PlatformDescriptionTitle")

            self.platform_desc_label = QLabel(self.platform_desc_card)
            self.platform_desc_label.setObjectName("PlatformDescriptionText")
            self.platform_desc_label.setWordWrap(True)
            self.platform_desc_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)

            desc_layout.addWidget(self.platform_desc_title)
            desc_layout.addWidget(self.platform_desc_label)
            main_layout.addWidget(self.platform_desc_card)
            self._update_platform_description_label()

        # 外层容器
        container = QFrame()
        container.setObjectName("DocsContainer")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(12, 8, 12, 12)
        container_layout.setSpacing(8)

        # 白色卡片
        card = QFrame()
        card.setObjectName("DocsCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # === 顶部蓝色路径栏 ===
        self.path_bar = QFrame()
        self.path_bar.setObjectName("PathBar")
        path_layout = QHBoxLayout(self.path_bar)
        path_layout.setContentsMargins(10, 4, 10, 4)
        path_layout.setSpacing(8)

        # 左侧小图标
        self.path_icon_label = QLabel()
        self.path_icon_label.setFixedSize(22, 22)
        self.path_icon_label.setStyleSheet("""
            background-color: #004a87;
            border-radius: 3px;
        """)
        if os.path.exists(self.folder_icon_path):
            pix = QPixmap(self.folder_icon_path)
            if not pix.isNull():
                pix = pix.scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.path_icon_label.setPixmap(pix)

        # 面包屑
        self.breadcrumb_container = QFrame()
        self.breadcrumb_layout = QHBoxLayout(self.breadcrumb_container)
        self.breadcrumb_layout.setContentsMargins(0, 0, 0, 0)
        self.breadcrumb_layout.setSpacing(4)
        self._update_path_label()

        path_layout.addWidget(self.path_icon_label)
        path_layout.addWidget(self.breadcrumb_container)
        path_layout.addStretch()

        card_layout.addWidget(self.path_bar)

        # === 中间内容区域 ===
        middle = QFrame()
        middle_layout = QVBoxLayout(middle)
        middle_layout.setContentsMargins(14, 10, 14, 14)
        middle_layout.setSpacing(8)

        self.content_stack = QStackedWidget()
        middle_layout.addWidget(self.content_stack)

        # 1）文件夹视图
        self.folder_page = QWidget()
        folder_layout = QVBoxLayout(self.folder_page)
        folder_layout.setContentsMargins(10, 10, 10, 10)
        folder_layout.setSpacing(12)

        self.folder_grid = QGridLayout()
        self.folder_grid.setHorizontalSpacing(32)
        self.folder_grid.setVerticalSpacing(26)
        self.folder_grid.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        folder_layout.addLayout(self.folder_grid)

        folder_layout.addStretch()

        self.content_stack.addWidget(self.folder_page)

        # 2）文件列表视图
        self.files_page = QWidget()
        files_layout = QVBoxLayout(self.files_page)
        files_layout.setContentsMargins(0, 0, 0, 0)
        files_layout.setSpacing(0)

        self.file_view_stack = QStackedWidget()
        files_layout.addWidget(self.file_view_stack)

        # 空页面
        self.empty_page = QWidget()
        empty_layout = QVBoxLayout(self.empty_page)
        empty_layout.setContentsMargins(0, 40, 0, 20)
        empty_layout.setSpacing(8)
        empty_layout.addStretch()

        self.btn_upload_empty = QPushButton("上传文件")
        self.btn_upload_empty.setFixedSize(160, 40)
        self.btn_upload_empty.setProperty("class", "UploadButton")
        self.btn_upload_empty.setCursor(Qt.PointingHandCursor)
        self.btn_upload_empty.clicked.connect(self._handle_upload_click)
        empty_layout.addWidget(self.btn_upload_empty, 0, Qt.AlignHCenter)
        empty_layout.addStretch()

        self.file_view_stack.addWidget(self.empty_page)

        self.doc_man_widget = DocManWidget(self._get_doc_man_upload_dir, self.files_page)
        self.file_view_stack.addWidget(self.doc_man_widget)

        # 表格页面：顶部按钮 + 表格
        self.table_page = QWidget()
        table_layout = QVBoxLayout(self.table_page)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)

        top_bar = QFrame()
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(12, 8, 12, 4)
        top_bar_layout.setSpacing(8)

        self.btn_upload_table = QPushButton("上传文件")
        self.btn_upload_table.setFixedSize(100, 30)
        self.btn_upload_table.setProperty("class", "UploadButton")
        self.btn_upload_table.setCursor(Qt.PointingHandCursor)
        self.btn_upload_table.clicked.connect(self._handle_upload_click)
        top_bar_layout.addStretch()
        top_bar_layout.addWidget(self.btn_upload_table)

        table_layout.addWidget(top_bar)

        self.files_table = QTableWidget(0, 7, self.table_page)
        self.files_table.setHorizontalHeaderLabels(
            ["序号", "文件类别", "文件格式", "修改时间", "上传", "下载", "备注"]
        )
        self.files_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.files_table.verticalHeader().setVisible(False)
        self.files_table.setAlternatingRowColors(True)
        # 允许编辑，但我们在每个单元格上控制哪些可编辑
        self.files_table.setEditTriggers(QAbstractItemView.AllEditTriggers)

        # 点击上传 / 下载
        self.files_table.cellClicked.connect(self._on_table_cell_clicked)
        # 修改备注时写回数据
        self.files_table.cellChanged.connect(self._on_table_cell_changed)

        table_layout.addWidget(self.files_table)
        self.file_view_stack.addWidget(self.table_page)

        self.content_stack.addWidget(self.files_page)

        # 组装
        card_layout.addWidget(middle)
        container_layout.addWidget(card)
        main_layout.addWidget(container)

        # 初始
        self._refresh_folder_view()
        self.content_stack.setCurrentWidget(self.folder_page)
        self._emit_navigation_state()

    # ---------------- 面包屑 ---------------- #
    def _update_path_label(self):
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
                lbl.setObjectName("BreadcrumbCurrent")
            else:
                lbl.setObjectName("Breadcrumb")
                lbl.setCursor(Qt.PointingHandCursor)
                lbl.clicked.connect(
                    lambda p=path_prefix: self._on_breadcrumb_clicked(p)
                )
            self.breadcrumb_layout.addWidget(lbl)

            if idx != len(segments) - 1:
                arrow = QLabel(">")
                arrow.setObjectName("BreadcrumbArrow")
                self.breadcrumb_layout.addWidget(arrow)

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

    def _on_breadcrumb_clicked(self, path_prefix: List[str]):
        self.current_path = list(path_prefix)
        self._update_path_label()

        if self._is_upload_only_path(self.current_path):
            self._show_files_for_current_path()
            self.content_stack.setCurrentWidget(self.files_page)
            self._emit_navigation_state()
            return

        node = self._get_node_by_path(self.current_path)
        if not node:
            return
        if node.get("type") == "folder":
            self._refresh_folder_view()
            self.content_stack.setCurrentWidget(self.folder_page)
        else:
            self._show_files_for_current_path()
            self.content_stack.setCurrentWidget(self.files_page)
        self._emit_navigation_state()

    # ---------------- 文件夹视图 ---------------- #
    def _clear_grid_layout(self, layout: QGridLayout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

    def _refresh_folder_view(self):
        self._clear_grid_layout(self.folder_grid)

        if hasattr(self, "platform_desc_card"):
            self.platform_desc_card.setVisible(len(self.current_path) == 0)

        node = self._get_node_by_path(self.current_path)
        children = node.get("children", {}) if node else {}

        max_cols = 10
        row, col = 0, 0
        icon = QIcon(self.folder_icon_path) if os.path.exists(self.folder_icon_path) else None

        for name, child in children.items():
            btn = QToolButton()
            btn.setObjectName("FolderButton")
            if icon is not None:
                btn.setIcon(icon)
                btn.setIconSize(QSize(96, 72))
            btn.setText(name)
            btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, n=name: self._on_folder_clicked(n))

            self.folder_grid.addWidget(btn, row, col, Qt.AlignLeft | Qt.AlignTop)  # ✅ 每个格子也靠左
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
        self._update_path_label()

        if self._is_upload_only_path(self.current_path):
            self._show_files_for_current_path()
            self.content_stack.setCurrentWidget(self.files_page)
            self._emit_navigation_state()
            return

        if child.get("type") == "folder":
            self._refresh_folder_view()
            self.content_stack.setCurrentWidget(self.folder_page)
        else:
            self._show_files_for_current_path()
            self.content_stack.setCurrentWidget(self.files_page)
        self._emit_navigation_state()

    # ---------------- 文件列表视图 ---------------- #
    def _show_files_for_current_path(self):
        key = self._current_path_key()
        records = self.file_records.setdefault(key, [])
        categories = self.doc_man_configs.get(key, [])
        self.doc_man_widget.set_context(
            self.current_path,
            records,
            categories,
            facility_code=self.facility_code,
            hide_empty_templates=True,
            db_list_mode=True,
        )
        self.file_view_stack.setCurrentWidget(self.doc_man_widget)

    def _fill_table(self, records: List[Dict]):
        """将记录填充到 7 列表格中，并控制可编辑列。"""
        self.files_table.blockSignals(True)

        self.files_table.setRowCount(len(records))
        for row, rec in enumerate(records):
            values = [
                rec.get("index", row + 1),
                rec.get("category", ""),
                rec.get("fmt", ""),
                rec.get("mtime", ""),
                "上传",
                "下载",
                rec.get("remark", ""),
            ]
            for col, v in enumerate(values):
                item = QTableWidgetItem(str(v))
                if col in (0, 1, 2, 3, 4, 5):
                    # 这些列只读
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                else:
                    # 备注列可编辑
                    item.setFlags(item.flags() | Qt.ItemIsEditable)

                # 对齐方式
                if col in (0, 3, 4, 5):
                    item.setTextAlignment(Qt.AlignCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                self.files_table.setItem(row, col, item)

        self.files_table.blockSignals(False)

    # 点击表格单元格：处理上传 / 下载
    def _on_table_cell_clicked(self, row: int, column: int):
        key = self._current_path_key()
        records = self.file_records.get(key, [])
        if row < 0 or row >= len(records):
            return

        if column == 4:  # 上传
            self._upload_for_row(row)
        elif column == 5:  # 下载
            self._handle_cell_download(row)

    # 备注列变化时写回数据
    def _on_table_cell_changed(self, row: int, column: int):
        if column != 6:
            return
        key = self._current_path_key()
        records = self.file_records.get(key, [])
        if row < 0 or row >= len(records):
            return
        item = self.files_table.item(row, column)
        records[row]["remark"] = item.text() if item else ""

    # 顶部/空白页“上传文件”按钮：对当前选中行/第一行执行上传
    def _handle_upload_click(self):
        key = self._current_path_key()
        records = self.file_records.get(key)
        if not records:
            QMessageBox.information(self, "提示", "当前目录没有预定义行，请直接在表格中点击某一行的“上传”单元格进行上传。")
            return

        row = self.files_table.currentRow()
        if row < 0:
            row = 0
        self._upload_for_row(row)

    # 具体某一行的上传逻辑
    def _upload_for_row(self, row: int):
        key = self._current_path_key()
        records = self.file_records.get(key, [])
        if row < 0 or row >= len(records):
            return
        rec = records[row]

        file_path, _ = QFileDialog.getOpenFileName(
            self, f"选择上传文件 - {rec.get('category', '')}", "", "所有文件 (*.*)"
        )
        if not file_path:
            return

        ext = os.path.splitext(file_path)[1].lstrip(".").lower()
        allowed_spec = rec.get("fmt", "")
        allowed_exts = self._parse_allowed_exts(allowed_spec)

        if allowed_exts and ext not in allowed_exts:
            QMessageBox.warning(
                self,
                "格式不匹配",
                f"当前行允许的文件格式为：{allowed_spec}\n"
                f"你选择的文件后缀为 .{ext}，不符合要求。",
            )
            return

        upload_root = self._get_upload_root()
        os.makedirs(upload_root, exist_ok=True)
        subdir = os.path.join(upload_root, *self.current_path)
        os.makedirs(subdir, exist_ok=True)

        filename = os.path.basename(file_path)
        dest_path = os.path.join(subdir, filename)
        root, ext = os.path.splitext(dest_path)
        suffix = 1
        while os.path.exists(dest_path):
            dest_path = f"{root} ({suffix}){ext}"
            suffix += 1

        try:
            shutil.copy2(file_path, dest_path)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"复制文件失败：{e}")
            return

        now_str = QDateTime.currentDateTime().toString("yyyy/M/d")
        rec["mtime"] = now_str
        rec["path"] = dest_path

        self._fill_table(records)

        QMessageBox.information(self, "上传成功", f"文件已上传到：\n{dest_path}")

    # 下载逻辑：打开对应行的文件
    def _handle_cell_download(self, row: int):
        key = self._current_path_key()
        records = self.file_records.get(key, [])
        if row < 0 or row >= len(records):
            return

        rec = records[row]
        path = rec.get("path") or ""
        if not path or not os.path.exists(path):
            QMessageBox.information(self, "提示", "当前行还没有上传文件，无法下载。")
            return

        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _build_doc_man_configs(self) -> Dict[str, List[str]]:
        spec_key = "/".join(["详细设计", "结构", "规格书"])
        drawing_key = "/".join(["详细设计", "结构", "设计图纸"])
        analysis_key = "/".join(["详细设计", "结构", "分析报告"])
        weight_key = "/".join(["详细设计", "结构", "重控报告"])
        general_key = "/".join(["详细设计", "总图"])
        other_key = "/".join(["详细设计", "其他文件"])
        return {
            spec_key: [
                "平台结构设计规划书",
                "其他",
            ],
            drawing_key: [
                "结构设计图",
                "其他",
            ],
            analysis_key: [
                "强度校核报告",
                "检测策略报告",
                "平台结构在位工况分析报告",
                "其他",
            ],
            weight_key: [
                "平台重量控制程序",
                "平台重量控制报告",
                "其他",
            ],
            general_key: [
                "平台总图及设计图纸",
                "其他",
            ],
            other_key: [
                "图纸送审记录",
                "其他设计类文件",
                "其他",
            ],
        }

    def _get_doc_man_upload_dir(self, path_segments: List[str]) -> str:
        upload_root = self._get_upload_root()
        target_dir = os.path.join(upload_root, *path_segments)
        os.makedirs(target_dir, exist_ok=True)
        return target_dir

    def _build_folder_tree(self) -> Dict:
        return {
            "\u8be6\u7ec6\u8bbe\u8ba1": {
                "type": "folder",
                "children": {
                    "\u7ed3\u6784": {
                        "type": "folder",
                        "children": {
                            "\u89c4\u683c\u4e66": {"type": "file_view"},
                            "\u8bbe\u8ba1\u56fe\u7eb8": {"type": "file_view"},
                            "\u5206\u6790\u62a5\u544a": {"type": "file_view"},
                            "\u91cd\u63a7\u62a5\u544a": {"type": "file_view"},
                        },
                    },
                    "\u603b\u56fe": {"type": "file_view"},
                    "\u5176\u4ed6\u6587\u4ef6": {"type": "file_view"},
                },
            },
            "\u5b8c\u5de5\u6587\u4ef6": {"type": "folder", "children": {}},
            "\u5b89\u88c5\u6587\u4ef6": {"type": "folder", "children": {}},
        }

    def _build_demo_file_records(self) -> Dict[str, List[Dict]]:
        records: Dict[str, List[Dict]] = {}

        def path_key(path_list: List[str]) -> str:
            return "/".join(path_list)

        records[path_key(["\u8be6\u7ec6\u8bbe\u8ba1", "\u7ed3\u6784", "\u89c4\u683c\u4e66"])] = [
            {"index": 1, "checked": False, "category": "\u5e73\u53f0\u7ed3\u6784\u8bbe\u8ba1\u89c4\u5212\u4e66", "fmt": "", "mtime": "", "path": "", "remark": ""},
        ]
        records[path_key(["\u8be6\u7ec6\u8bbe\u8ba1", "\u7ed3\u6784", "\u8bbe\u8ba1\u56fe\u7eb8"])] = [
            {"index": 1, "checked": False, "category": "\u7ed3\u6784\u8bbe\u8ba1\u56fe", "fmt": "", "mtime": "", "path": "", "remark": ""},
        ]
        records[path_key(["\u8be6\u7ec6\u8bbe\u8ba1", "\u7ed3\u6784", "\u5206\u6790\u62a5\u544a"])] = [
            {"index": 1, "checked": False, "category": "\u5f3a\u5ea6\u6821\u6838\u62a5\u544a", "fmt": "", "mtime": "", "path": "", "remark": ""},
            {"index": 2, "checked": False, "category": "\u68c0\u6d4b\u7b56\u7565\u62a5\u544a", "fmt": "", "mtime": "", "path": "", "remark": ""},
            {"index": 3, "checked": False, "category": "\u5e73\u53f0\u7ed3\u6784\u5728\u4f4d\u5de5\u51b5\u5206\u6790\u62a5\u544a", "fmt": "", "mtime": "", "path": "", "remark": ""},
        ]
        records[path_key(["\u8be6\u7ec6\u8bbe\u8ba1", "\u7ed3\u6784", "\u91cd\u63a7\u62a5\u544a"])] = [
            {"index": 1, "checked": False, "category": "\u5e73\u53f0\u91cd\u91cf\u63a7\u5236\u7a0b\u5e8f", "fmt": "", "mtime": "", "path": "", "remark": ""},
            {"index": 2, "checked": False, "category": "\u5e73\u53f0\u91cd\u91cf\u63a7\u5236\u62a5\u544a", "fmt": "", "mtime": "", "path": "", "remark": ""},
        ]
        records[path_key(["\u8be6\u7ec6\u8bbe\u8ba1", "\u603b\u56fe"])] = [
            {"index": 1, "checked": False, "category": "\u5e73\u53f0\u603b\u56fe\u53ca\u8bbe\u8ba1\u56fe\u7eb8", "fmt": "", "mtime": "", "path": "", "remark": ""},
        ]
        records[path_key(["\u8be6\u7ec6\u8bbe\u8ba1", "\u5176\u4ed6\u6587\u4ef6"])] = [
            {"index": 1, "checked": False, "category": "\u56fe\u7eb8\u9001\u5ba1\u8bb0\u5f55", "fmt": "", "mtime": "", "path": "", "remark": ""},
            {"index": 2, "checked": False, "category": "\u5176\u4ed6\u8bbe\u8ba1\u7c7b\u6587\u4ef6", "fmt": "", "mtime": "", "path": "", "remark": ""},
        ]

        return records

    def set_platform_name(self, name: str):
        self.platform_name = name or ""
        self._update_platform_description_label()

    def set_facility_code(self, code: str):
        self.facility_code = (code or "").strip()

    def set_platform_description(self, description: str):
        self.platform_description = description or ""
        self._update_platform_description_label()

    def _update_platform_description_label(self):
        if not hasattr(self, "platform_desc_label"):
            return

        if self.platform_description:
            text = self.platform_description
        elif self.platform_name:
            text = (
                f"{self.platform_name}\uff0c\u5f53\u524d\u5df2\u88ab\u9009\u4e2d\u4e3a\u5efa\u8bbe\u9636\u6bb5\u5b8c\u5de5\u6587\u4ef6\u7684"
                "\u7ba1\u7406\u5bf9\u8c61\uff0c\u53ef\u5728\u4e0a\u65b9\u6587\u4ef6\u5939\u4e2d\u6309\u4e13\u4e1a\u5206\u7c7b\u67e5\u770b\u548c"
                "\u7ef4\u62a4\u5bf9\u5e94\u8bbe\u8ba1\u4e0e\u5b8c\u5de5\u8d44\u6599\u3002"
            )
        else:
            text = "\u8bf7\u5148\u5728\u4e0a\u65b9\u4e0b\u62c9\u6846\u4e2d\u9009\u62e9\u5e73\u53f0\uff0c\u8fd9\u91cc\u4f1a\u663e\u793a\u5f53\u524d\u9009\u4e2d\u5e73\u53f0\u7684\u63cf\u8ff0\u4fe1\u606f\u3002"

        self.platform_desc_label.setText(text)

    def _emit_navigation_state(self):
        self.navigationStateChanged.emit(len(self.current_path) == 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_breadcrumb_font_scale()
