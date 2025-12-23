# -*- coding: utf-8 -*-
"""
历史检测及结论 页面

结构：
- 顶部：DropdownBar（分公司 / 作业公司 / 油气田 / 设施编号 / 名称 / 类型 / 分类 / 投产时间 / 设计年限）
- 中部卡片：
    - 面包屑：文件夹小图标 + “首页 > 完工检测”等
    - 内容区域：QStackedWidget
        - 首页：4 个文件夹图标
        - 完工检测：文件表格（带上传/下载/备注）
        - 第1次检测：同上
        - 第N次检测：同上
        - 历史抽检记录：表格 + 蓝底白字说明
"""

import os
import shutil
from typing import Dict, List

from PyQt5.QtCore import Qt, QDateTime, QSize, QUrl, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap, QDesktopServices, QFont
from PyQt5.QtWidgets import (
    QWidget,
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFileDialog,
    QMessageBox,
    QAbstractItemView,
    QSizePolicy,
    QSpacerItem,
)

from base_page import BasePage
from dropdown_bar import DropdownBar


# ----------------------------------------------------------------------
# 小工具：可点击的 QLabel，用于面包屑“首页”
# ----------------------------------------------------------------------
class LinkLabel(QLabel):
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


# ----------------------------------------------------------------------
# 主页面
# ----------------------------------------------------------------------
class HistoryInspectionSummaryPage(BasePage):
    """
    文件管理 -> 历史检测及结论 页面
    """

    # 列索引常量
    COL_INDEX = 0
    COL_CATEGORY = 1
    COL_FORMAT = 2
    COL_MTIME = 3
    COL_UPLOAD = 4
    COL_DOWNLOAD = 5
    COL_REMARK = 6

    def __init__(self, parent=None):
        super().__init__("历史检测及结论", parent)

        # 当前所在“文件夹”
        self.current_folder_key = "home"

        # 各文件夹每一行上传的真实路径：
        # {folder_key: {row_index: file_path}}
        self.file_paths: Dict[str, Dict[int, str]] = {}

        # 预设每个文件夹的表格数据
        self.folder_rows = self._build_folder_rows()

        # 资源路径（小文件夹图标）
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.folder_icon_path = os.path.join(project_root, "pict", "wenjian.png")

        self._build_ui()

    # ------------------------------------------------------------------
    # 数据定义
    # ------------------------------------------------------------------
    def _build_folder_rows(self) -> Dict[str, List[Dict]]:
        """定义 4 个文件夹显示的行内容。"""

        complete_rows = [
            {"category": "检测策略报告", "format": "word/pdf"},
            {"category": "节点风险评估表", "format": "excel/pdf"},
            {"category": "节点检测计划表", "format": "excel/pdf"},
            {"category": "构件风险评估表", "format": "excel/pdf"},
            {"category": "构件检测计划表", "format": "excel/pdf"},
            {"category": "节点构件检测计划位置", "format": "dwg/pdf"},
        ]

        first_rows = [
            {"category": "检测策略报告", "format": "word/pdf"},
            {"category": "节点风险评估表", "format": "excel/pdf"},
            {"category": "节点检测计划表", "format": "excel/pdf"},
            {"category": "构件风险评估表", "format": "excel/pdf"},
            {"category": "构件检测计划表", "format": "excel/pdf"},
            {"category": "节点构件检测计划位置", "format": "dwg/pdf"},
            {"category": "抽检记录表", "format": "excel/pdf"},
        ]

        # 第 N 次检测：布局同第一次检测，这里直接复用
        nth_rows = list(first_rows)

        # 历史抽检记录：只有 3 行
        history_rows = [
            {"category": "第一次抽检记录表", "format": "excel/pdf"},
            {"category": "第二次抽检记录表", "format": "excel/pdf"},
            {"category": "第三次抽检记录表", "format": "excel/pdf"},
        ]

        return {
            "complete": complete_rows,
            "first": first_rows,
            "nth": nth_rows,
            "history_sampling": history_rows,
        }

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _build_ui(self):
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(8)

        # ---------- 顶部 DropdownBar ----------
        fields = [
            {"key": "branch", "label": "分公司", "options": ["渤江分公司"], "default": "渤江分公司"},
            {"key": "op_company", "label": "作业公司", "options": ["文昌油田群作业公司"], "default": "文昌油田群作业公司"},
            {"key": "oilfield", "label": "油气田", "options": ["文昌19-1油田"], "default": "文昌19-1油田"},
            {"key": "facility_code", "label": "设施编号", "options": ["WC19-1WHPC"], "default": "WC19-1WHPC"},
            {"key": "facility_name", "label": "设施名称", "options": ["文昌19-1WHPC井口平台"], "default": "文昌19-1WHPC井口平台"},
            {"key": "facility_type", "label": "设施类型", "options": ["平台"], "default": "平台"},
            {"key": "category", "label": "分类", "options": ["井口平台"], "default": "井口平台"},
            {"key": "start_time", "label": "投产时间", "options": ["2013-07-15"], "default": "2013-07-15"},
            {"key": "design_life", "label": "设计年限", "options": ["15"], "default": "15"},
        ]
        self.dropdown_bar = DropdownBar(fields, parent=self)
        self.main_layout.addWidget(self.dropdown_bar, 0)

        # ---------- 中部卡片 ----------
        card = QFrame(self)
        card.setObjectName("HistoryInspectionCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # 面包屑
        self.breadcrumb_bar = self._create_breadcrumb_bar(card)
        card_layout.addWidget(self.breadcrumb_bar, 0)

        # 内容堆栈
        self.stack = QStackedWidget(card)
        card_layout.addWidget(self.stack, 1)

        self.main_layout.addWidget(card, 1)

        # 四个子页面
        self.pages: Dict[str, QWidget] = {}
        self.pages["home"] = self._build_home_page()
        self.pages["complete"] = self._build_folder_table_page("完工检测", "complete")
        self.pages["first"] = self._build_folder_table_page("第1次检测", "first")
        self.pages["nth"] = self._build_folder_table_page("第N次检测", "nth")
        self.pages["history_sampling"] = self._build_history_sampling_page()

        for key in ["home", "complete", "first", "nth", "history_sampling"]:
            self.stack.addWidget(self.pages[key])

        # 默认在首页
        self._switch_to("home")

        # 统一样式
        self._apply_stylesheet()

    # ------------------------------------------------------------------
    # 面包屑
    # ------------------------------------------------------------------
    def _create_breadcrumb_bar(self, parent: QWidget) -> QFrame:
        bar = QFrame(parent)
        bar.setObjectName("BreadcrumbBar")
        bar.setFixedHeight(40)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(6)

        # 小文件夹图标 (深蓝底)
        self.path_icon_label = QLabel(bar)
        self.path_icon_label.setFixedSize(24, 24)
        self.path_icon_label.setAlignment(Qt.AlignCenter)
        self.path_icon_label.setObjectName("BreadcrumbIcon")

        pix = QPixmap(self.folder_icon_path)
        if not pix.isNull():
            pix = pix.scaled(18, 18, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.path_icon_label.setPixmap(pix)

        layout.addWidget(self.path_icon_label)

        # “首页”
        self.lbl_home_link = LinkLabel("首页", bar)
        self.lbl_home_link.setObjectName("BreadcrumbHome")
        self.lbl_home_link.clicked.connect(lambda: self._switch_to("home"))
        layout.addWidget(self.lbl_home_link)

        # 分隔符 >
        self.lbl_sep = QLabel(" >", bar)
        self.lbl_sep.setObjectName("BreadcrumbSep")
        layout.addWidget(self.lbl_sep)

        # 第二级标题：完工检测 / 第1次检测 / 第N次检测 / 历史抽检记录
        self.lbl_second = QLabel("", bar)
        self.lbl_second.setObjectName("BreadcrumbSecond")
        layout.addWidget(self.lbl_second)

        layout.addStretch(1)

        return bar

    def _update_breadcrumb(self):
        """根据 current_folder_key 更新面包屑显示。"""
        if self.current_folder_key == "home":
            self.lbl_sep.setVisible(False)
            self.lbl_second.setVisible(False)
        else:
            self.lbl_sep.setVisible(True)
            self.lbl_second.setVisible(True)
            name_map = {
                "complete": "完工检测",
                "first": "第1次检测",
                "nth": "第N次检测",
                "history_sampling": "历史抽检记录",
            }
            self.lbl_second.setText(name_map.get(self.current_folder_key, ""))

    # ------------------------------------------------------------------
    # 首页：四个文件夹
    # ------------------------------------------------------------------
    def _build_home_page(self) -> QWidget:
        page = QWidget(self.stack)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 16, 0, 16)
        layout.setSpacing(0)

        # 中间一行四个文件夹
        row = QHBoxLayout()
        row.setContentsMargins(0, 40, 0, 0)
        row.setSpacing(80)

        row.addStretch(1)
        row.addWidget(self._create_folder_button("完工检测", "complete"))
        row.addWidget(self._create_folder_button("第1次检测", "first"))
        row.addWidget(self._create_folder_button("第N次检测", "nth"))
        row.addWidget(self._create_folder_button("历史抽检记录", "history_sampling"))
        row.addStretch(1)

        layout.addLayout(row)
        layout.addStretch(1)

        return page

    def _create_folder_button(self, text: str, folder_key: str) -> QToolButton:
        btn = QToolButton()
        btn.setObjectName("FolderButton")
        btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        btn.setIcon(QIcon(self.folder_icon_path))
        btn.setIconSize(QSize(96, 72))
        btn.setText(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(lambda: self._switch_to(folder_key))
        btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        return btn

    # ------------------------------------------------------------------
    # 完工 / 第1次 / 第N次 检测：纯表格
    # ------------------------------------------------------------------
    def _build_folder_table_page(self, title: str, folder_key: str) -> QWidget:
        page = QWidget(self.stack)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(0)

        table = self._create_table_for_folder(folder_key)
        layout.addWidget(table)

        return page

    # ------------------------------------------------------------------
    # 历史抽检记录：表格 + 蓝底说明
    # ------------------------------------------------------------------
    def _build_history_sampling_page(self) -> QWidget:
        page = QWidget(self.stack)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 8, 0, 16)
        layout.setSpacing(8)

        # 顶部表格
        table = self._create_table_for_folder("history_sampling")
        layout.addWidget(table, 0)

        # 蓝底说明区域
        desc_frame = QFrame(page)
        desc_frame.setObjectName("SamplingDescFrame")

        desc_layout = QVBoxLayout(desc_frame)
        desc_layout.setContentsMargins(32, 20, 32, 24)
        desc_layout.setSpacing(0)

        desc_text = QLabel(
            "xxxx年五年特检报告显示，水下导管架杆件结构完整、未发现凹陷变形与机械损伤，"
            "牺牲阳极均在位，连接牢固；焊缝检测未发现缺陷，飞溅区构件测厚结果最小腐蚀厚度0.1mm，"
            "最大腐蚀厚度0.5mm，平台水下结构状况良好。"
        )
        desc_text.setObjectName("SamplingDescText")
        desc_text.setWordWrap(True)
        desc_text.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        desc_layout.addWidget(desc_text)

        layout.addWidget(desc_frame, 0)

        return page

    # ------------------------------------------------------------------
    # 构造单个文件夹的表格
    # ------------------------------------------------------------------
    def _create_table_for_folder(self, folder_key: str) -> QTableWidget:
        rows = self.folder_rows.get(folder_key, [])
        table = QTableWidget(len(rows), 7, self)
        table.setObjectName(f"HistoryTable_{folder_key}")

        headers = ["序号", "文件类别", "文件格式", "修改时间", "上传", "下载", "备注"]
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(False)

        # 自适应宽度
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)

        # 选择样式
        table.setSelectionBehavior(QAbstractItemView.SelectItems)
        table.setSelectionMode(QAbstractItemView.SingleSelection)

        # 每一行
        for row_idx, row in enumerate(rows):
            # 序号
            item_index = QTableWidgetItem(str(row_idx + 1))
            item_index.setTextAlignment(Qt.AlignCenter)
            item_index.setFlags(item_index.flags() & ~Qt.ItemIsEditable)
            table.setItem(row_idx, self.COL_INDEX, item_index)

            # 文件类别
            item_cat = QTableWidgetItem(row["category"])
            item_cat.setTextAlignment(Qt.AlignCenter)
            item_cat.setFlags(item_cat.flags() & ~Qt.ItemIsEditable)
            table.setItem(row_idx, self.COL_CATEGORY, item_cat)

            # 文件格式
            item_fmt = QTableWidgetItem(row["format"])
            item_fmt.setTextAlignment(Qt.AlignCenter)
            item_fmt.setFlags(item_fmt.flags() & ~Qt.ItemIsEditable)
            table.setItem(row_idx, self.COL_FORMAT, item_fmt)

            # 修改时间
            item_time = QTableWidgetItem(row.get("mtime", ""))
            item_time.setTextAlignment(Qt.AlignCenter)
            item_time.setFlags(item_time.flags() & ~Qt.ItemIsEditable)
            table.setItem(row_idx, self.COL_MTIME, item_time)

            # 上传
            item_upload = QTableWidgetItem("上传")
            item_upload.setTextAlignment(Qt.AlignCenter)
            item_upload.setFlags(item_upload.flags() & ~Qt.ItemIsEditable)
            table.setItem(row_idx, self.COL_UPLOAD, item_upload)

            # 下载
            item_download = QTableWidgetItem("下载")
            item_download.setTextAlignment(Qt.AlignCenter)
            item_download.setFlags(item_download.flags() & ~Qt.ItemIsEditable)
            table.setItem(row_idx, self.COL_DOWNLOAD, item_download)

            # 备注（可编辑）
            item_remark = QTableWidgetItem("")
            # 默认 flags 已包含可编辑，这里保持不变
            item_remark.setTextAlignment(Qt.AlignCenter)
            table.setItem(row_idx, self.COL_REMARK, item_remark)

        # 绑定单元格点击事件
        table.cellClicked.connect(
            lambda r, c, key=folder_key, t=table: self._on_table_cell_clicked(key, t, r, c)
        )

        # 初始化 file_paths 字典
        self.file_paths.setdefault(folder_key, {})

        return table

    # ------------------------------------------------------------------
    # 点击“上传 / 下载”
    # ------------------------------------------------------------------
    def _on_table_cell_clicked(self, folder_key: str, table: QTableWidget, row: int, col: int):
        if col == self.COL_UPLOAD:
            self._handle_upload(folder_key, table, row)
        elif col == self.COL_DOWNLOAD:
            self._handle_download(folder_key, table, row)

    # 上传
    def _handle_upload(self, folder_key: str, table: QTableWidget, row: int):
        fmt_text = table.item(row, self.COL_FORMAT).text()

        # 选择文件
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择文件上传",
            "",
            "所有文件 (*);;文档 (*.pdf *.doc *.docx *.xls *.xlsx *.dwg)",
        )
        if not file_path:
            return

        ext = os.path.splitext(file_path)[1].lower()
        allowed_exts = self._guess_allowed_exts(fmt_text)

        if allowed_exts and ext not in allowed_exts:
            QMessageBox.warning(
                self,
                "文件格式不匹配",
                f"该行要求文件格式：{fmt_text}\n\n"
                f"当前选择的文件扩展名为：{ext}，请重新选择。",
            )
            return

        # 目标目录
        upload_root = self._get_upload_root()
        target_dir = os.path.join(upload_root, folder_key)
        os.makedirs(target_dir, exist_ok=True)

        base_name = os.path.basename(file_path)
        target_path = os.path.join(target_dir, base_name)

        try:
            shutil.copy2(file_path, target_path)
        except Exception as e:
            QMessageBox.critical(self, "上传失败", f"复制文件失败：{e}")
            return

        # 记录路径
        self.file_paths.setdefault(folder_key, {})[row] = target_path

        # 更新“修改时间”列为当前时间
        now_str = QDateTime.currentDateTime().toString("yyyy/M/d")
        table.item(row, self.COL_MTIME).setText(now_str)

        QMessageBox.information(self, "上传成功", "文件上传成功。")

    # 下载（直接用系统默认程序打开）
    def _handle_download(self, folder_key: str, table: QTableWidget, row: int):
        path = self.file_paths.get(folder_key, {}).get(row)
        if not path or not os.path.exists(path):
            QMessageBox.information(self, "提示", "该行尚未上传文件，无法下载。")
            return

        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    # ------------------------------------------------------------------
    # path & 样式等辅助
    # ------------------------------------------------------------------
    def _get_upload_root(self) -> str:
        """历史检测及结论上传文件根目录。"""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(project_root, "uploads", "history_inspection")

    def _guess_allowed_exts(self, fmt_text: str):
        """根据“文件格式”文本推断允许的扩展名列表。"""
        mapping = {
            "word": [".doc", ".docx"],
            "pdf": [".pdf"],
            "excel": [".xls", ".xlsx"],
            "dwg": [".dwg"],
        }
        exts = []
        for part in fmt_text.split("/"):
            key = part.strip().lower()
            exts.extend(mapping.get(key, []))
        return exts

    def _switch_to(self, folder_key: str):
        """切换到指定子页面。"""
        self.current_folder_key = folder_key
        widget = self.pages.get(folder_key)
        if widget is not None:
            self.stack.setCurrentWidget(widget)
        self._update_breadcrumb()

    def _apply_stylesheet(self):
        """统一样式，包含：
        - 面包屑
        - 文件夹按钮
        - 表格选中颜色
        - 蓝底说明框
        """
        self.setStyleSheet(
            """
            /* 中部卡片背景 */
            QFrame#HistoryInspectionCard {
                background-color: #f3f4f6;
                border: none;
            }

            /* 面包屑上方蓝条 */
            QFrame#BreadcrumbBar {
                background-color: #0069b4;
            }
            QLabel#BreadcrumbIcon {
                background-color: #004a87;
                border-radius: 3px;
            }
            QLabel#BreadcrumbHome,
            QLabel#BreadcrumbSep,
            QLabel#BreadcrumbSecond {
                color: white;
                font-size: 14px;
            }
            QLabel#BreadcrumbHome {
                padding-left: 6px;
                padding-right: 2px;
            }

            /* 文件夹按钮 */
            QToolButton#FolderButton {
                border: none;
                background: transparent;
                font-size: 14px;
            }
            QToolButton#FolderButton:hover {
                color: #0069b4;
            }

            /* 表格基础样式 */
            QTableWidget {
                background-color: white;
                gridline-color: #d0d7e2;
                font-size: 14px;
            }
            QHeaderView::section {
                background-color: #f1f3f6;
                padding: 6px 4px;
                border: 1px solid #d0d7e2;
                font-weight: 500;
                font-size: 14px;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QTableWidget::item:selected {
                background-color: #0f5ea5;
                color: white;
            }

            /* 历史抽检记录说明区域 */
            QFrame#SamplingDescFrame {
                background-color: #0f5ea5;
                border-radius: 18px;
            }
            QLabel#SamplingDescText {
                color: white;
                font-size: 14px;
                line-height: 1.6;
            }
            """
        )
