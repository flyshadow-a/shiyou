# -*- coding: utf-8 -*-
# pages/construction_docs_widget.py

import os
import shutil
from typing import Dict, List

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QStackedWidget,
    QGridLayout, QToolButton, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QFileDialog, QMessageBox
)
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtCore import Qt, QSize, QDateTime, pyqtSignal


class ClickableLabel(QLabel):
    """一个简单的可点击 QLabel，发出 clicked() 信号。"""
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ConstructionDocsWidget(QWidget):
    """
    建设阶段完工文件 复用组件（UI 美化版）：

    - 浅灰背景 + 白色卡片容器；
    - 顶部蓝色路径栏（当前位置面包屑，可点击跳转各级目录）；
    - 内容区：
        * 文件夹视图：大图标 + 悬浮高亮；
        * 叶子目录：文件表格 + 上传按钮（真上传，复制到本地目录）；
        * 无文件：中间显示一个上传按钮。
    """

    # ====== 文件实际存储的根目录（上传文件会被复制到这里） ======
    def _get_upload_root(self) -> str:
        """
        上传文件的根目录。

        ⚠️ 如果你要修改文件的存储位置，只需要改这个函数即可。
        例如改成 D 盘某个目录：
            return r"D:/platform_files/uploads"
        """
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(project_root, "uploads")
    # ============================================================

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ConstructionDocsWidget")

        self.setAttribute(Qt.WA_StyledBackground, True)

        # 当前路径（不含“首页”），例如 [] / ["详细设计"] / ["详细设计","结构"]
        self.current_path: List[str] = []

        # 文件夹树结构 & 文件记录
        self.folder_tree = self._build_folder_tree()
        self.file_records: Dict[str, List[Dict]] = self._build_demo_file_records()

        # 资源路径：项目根目录
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.folder_icon_path = os.path.join(self.project_root, "pict/wenjian.png")

        self._build_ui()

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
                font-size: 12px;
                color: #ffffff;
                background-color: transparent;
            }
            QLabel#Breadcrumb:hover {
                text-decoration: underline;
            }
            QLabel#BreadcrumbCurrent {
                font-weight: bold;
                font-size: 12px;
                color: #ffffff;
                background-color: transparent;
            }
            QLabel#BreadcrumbArrow {
                font-size: 12px;
                color: #ffffff;
                background-color: transparent;
            }

            QToolButton#FolderButton {
                border: none;
                padding: 4px;
                color: #374151;
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
        """)

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

        # 面包屑容器：里面动态添加“首页 > 详细设计 > 结构”
        self.breadcrumb_container = QFrame()
        self.breadcrumb_layout = QHBoxLayout(self.breadcrumb_container)
        self.breadcrumb_layout.setContentsMargins(0, 0, 0, 0)
        self.breadcrumb_layout.setSpacing(4)

        # 初始化一次
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

        # 内容堆叠
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

        # 无文件页面
        self.empty_page = QWidget()
        empty_layout = QVBoxLayout(self.empty_page)
        empty_layout.setContentsMargins(0, 40, 0, 20)
        empty_layout.setSpacing(8)

        empty_layout.addStretch()

        self.btn_upload_empty = QPushButton("上传文件")
        self.btn_upload_empty.setFixedSize(160, 40)
        self.btn_upload_empty.setProperty("class", "UploadButton")
        self.btn_upload_empty.setObjectName("")
        self.btn_upload_empty.setCursor(Qt.PointingHandCursor)
        self.btn_upload_empty.clicked.connect(self._handle_upload_click)

        empty_layout.addWidget(self.btn_upload_empty, 0, Qt.AlignHCenter)
        empty_layout.addStretch()

        self.file_view_stack.addWidget(self.empty_page)

        # 有文件页面：顶部上传按钮 + 表格
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
        self.btn_upload_table.setObjectName("")
        self.btn_upload_table.setCursor(Qt.PointingHandCursor)
        self.btn_upload_table.clicked.connect(self._handle_upload_click)

        top_bar_layout.addStretch()
        top_bar_layout.addWidget(self.btn_upload_table)

        table_layout.addWidget(top_bar)

        self.files_table = QTableWidget(0, 7, self.table_page)
        self.files_table.setHorizontalHeaderLabels(
            ["序号", "文件类别", "文件格式", "修改时间", "上传路径", "下载", "备注"]
        )
        self.files_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.files_table.verticalHeader().setVisible(False)
        self.files_table.setAlternatingRowColors(True)
        table_layout.addWidget(self.files_table)

        self.file_view_stack.addWidget(self.table_page)
        self.content_stack.addWidget(self.files_page)

        # 组装 card
        card_layout.addWidget(middle)
        container_layout.addWidget(card)
        main_layout.addWidget(container)

        # 初始状态
        self._refresh_folder_view()
        self.content_stack.setCurrentWidget(self.folder_page)

    # ---------------- 文件夹树 / 路径 ---------------- #
    def _build_folder_tree(self) -> Dict:
        """
        文件夹树结构：

        首页
        ├─ 基本信息
        ├─ 详细设计
        │   ├─ 结构
        │   │   ├─ 规格书
        │   │   ├─ 设计图纸
        │   │   ├─ 分析报告
        │   │   └─ 重控报告
        │   ├─ 总图
        │   └─ 其他文件
        ├─ 完工文件
        └─ 安装文件
        """
        return {
            "基本信息": {"type": "folder", "children": {}},
            "详细设计": {
                "type": "folder",
                "children": {
                    "结构": {
                        "type": "folder",
                        "children": {
                            "规格书": {"type": "file_view"},
                            "设计图纸": {"type": "file_view"},
                            "分析报告": {"type": "file_view"},
                            "重控报告": {"type": "file_view"},
                        },
                    },
                    "总图": {"type": "file_view"},
                    "其他文件": {"type": "file_view"},
                },
            },
            "完工文件": {"type": "folder", "children": {}},
            "安装文件": {"type": "folder", "children": {}},
        }

    def _build_demo_file_records(self) -> Dict[str, List[Dict]]:
        """
        示例文件数据：仅在“详细设计/结构/分析报告”下放 3 条记录，
        方便你查看 UI 效果，其它目录初始为空。
        """
        records: Dict[str, List[Dict]] = {}

        def path_key(path_list: List[str]) -> str:
            return "/".join(path_list)

        demo_path = ["详细设计", "结构", "分析报告"]
        records[path_key(demo_path)] = [
            {
                "index": 1,
                "category": "强度校核报告",
                "fmt": "pdf/word",
                "mtime": "2025/09/16 10:00",
                "path": "",
                "remark": "",
            },
            {
                "index": 2,
                "category": "检测策略报告",
                "fmt": "pdf/word",
                "mtime": "2025/09/17 10:00",
                "path": "",
                "remark": "",
            },
            {
                "index": 3,
                "category": "平台结构在位工况分析报告",
                "fmt": "pdf/word",
                "mtime": "2025/09/22 10:00",
                "path": "",
                "remark": "",
            },
        ]
        return records

    def _current_path_key(self) -> str:
        return "/".join(self.current_path)

    def _get_node_by_path(self, path: List[str]) -> Dict:
        node = {"type": "folder", "children": self.folder_tree}
        for name in path:
            children = node.get("children", {})
            node = children.get(name)
            if node is None:
                break
        return node

    def _update_path_label(self):
        """根据 current_path 重新绘制可点击的面包屑。"""
        # 先清空原来的控件
        while self.breadcrumb_layout.count():
            item = self.breadcrumb_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

        # 构造每一级的路径：
        # 第 0 级：("首页", [])
        # 后面依次：("详细设计", ["详细设计"]), ("结构", ["详细设计","结构"]), ...
        segments = [("首页", [])]
        for i, name in enumerate(self.current_path):
            segments.append((name, self.current_path[: i + 1]))

        for idx, (name, path_prefix) in enumerate(segments):
            is_last = (idx == len(segments) - 1)

            lbl = ClickableLabel(name)
            if is_last:
                # 当前级：高亮显示，不可点击
                lbl.setObjectName("BreadcrumbCurrent")
            else:
                # 中间级：可点击
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

    def _on_breadcrumb_clicked(self, path_prefix: List[str]):
        """
        点击面包屑某一级：
        - path_prefix 为空列表 [] 表示首页
        - 否则表示 ["详细设计"]、["详细设计","结构"] 等
        """
        self.current_path = list(path_prefix)
        self._update_path_label()

        node = self._get_node_by_path(self.current_path)
        if not node:
            return

        if node.get("type") == "folder":
            # 点击的是一个“文件夹级别”
            self._refresh_folder_view()
            self.content_stack.setCurrentWidget(self.folder_page)
        else:
            # 点击的是叶子文件夹（file_view）
            self._show_files_for_current_path()
            self.content_stack.setCurrentWidget(self.files_page)

    # ---------------- 文件夹视图 ---------------- #
    def _clear_grid_layout(self, layout: QGridLayout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)

    def _refresh_folder_view(self):
        """根据当前路径显示当前层级的所有子文件夹。"""
        self._clear_grid_layout(self.folder_grid)

        node = self._get_node_by_path(self.current_path)
        children = node.get("children", {}) if node else {}

        max_cols = 4
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

            self.folder_grid.addWidget(btn, row, col, Qt.AlignTop)
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

        if child.get("type") == "folder":
            self._refresh_folder_view()
            self.content_stack.setCurrentWidget(self.folder_page)
        else:
            self._show_files_for_current_path()
            self.content_stack.setCurrentWidget(self.files_page)

    # ---------------- 文件列表视图 ---------------- #
    def _show_files_for_current_path(self):
        key = self._current_path_key()
        records = self.file_records.get(key, [])

        if not records:
            self.file_view_stack.setCurrentWidget(self.empty_page)
        else:
            self._fill_table(records)
            self.file_view_stack.setCurrentWidget(self.table_page)

    def _fill_table(self, records: List[Dict]):
        self.files_table.setRowCount(len(records))
        for row, rec in enumerate(records):
            idx_item = QTableWidgetItem(str(rec.get("index", row + 1)))
            cat_item = QTableWidgetItem(rec.get("category", ""))
            fmt_item = QTableWidgetItem(rec.get("fmt", ""))
            time_item = QTableWidgetItem(rec.get("mtime", ""))
            path_item = QTableWidgetItem(rec.get("path", ""))
            download_item = QTableWidgetItem("下载")
            remark_item = QTableWidgetItem(rec.get("remark", ""))

            for item in [
                idx_item, cat_item, fmt_item, time_item,
                path_item, download_item, remark_item
            ]:
                item.setTextAlignment(Qt.AlignCenter)

            self.files_table.setItem(row, 0, idx_item)
            self.files_table.setItem(row, 1, cat_item)
            self.files_table.setItem(row, 2, fmt_item)
            self.files_table.setItem(row, 3, time_item)
            self.files_table.setItem(row, 4, path_item)
            self.files_table.setItem(row, 5, download_item)
            self.files_table.setItem(row, 6, remark_item)

    # ---------------- 上传文件逻辑 ---------------- #
    def _handle_upload_click(self):
        """
        选择本地文件并复制到 uploads/当前路径 目录，
        同时在当前叶子文件夹记录中追加一条记录并刷新表格。
        """
        node = self._get_node_by_path(self.current_path)
        if not node or node.get("type") != "file_view":
            QMessageBox.information(self, "提示", "请先进入具体的文件夹再上传文件。")
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择要上传的文件", "", "所有文件 (*.*)"
        )
        if not file_path:
            return  # 用户取消

        # 目标根目录（文件真正存储位置入口）
        upload_root = self._get_upload_root()
        os.makedirs(upload_root, exist_ok=True)

        # 子目录：uploads/详细设计/结构/分析报告
        subdir = os.path.join(upload_root, *self.current_path)
        os.makedirs(subdir, exist_ok=True)

        filename = os.path.basename(file_path)
        dest_path = os.path.join(subdir, filename)

        try:
            shutil.copy2(file_path, dest_path)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"复制文件失败：{e}")
            return

        key = self._current_path_key()
        if key not in self.file_records:
            self.file_records[key] = []

        rec_list = self.file_records[key]
        new_index = len(rec_list) + 1
        ext = os.path.splitext(filename)[1]
        fmt = ext.lstrip(".") if ext else "未知"
        now_str = QDateTime.currentDateTime().toString("yyyy/MM/dd HH:mm")

        rec_list.append({
            "index": new_index,
            "category": os.path.splitext(filename)[0],
            "fmt": fmt,
            "mtime": now_str,
            "path": dest_path,
            "remark": "",
        })

        self._show_files_for_current_path()

        QMessageBox.information(self, "成功", f"文件已上传到:\n{dest_path}")
