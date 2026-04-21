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
    QFormLayout,
    QLabel,
    QToolButton,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFileDialog,
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QMessageBox,
    QAbstractItemView,
    QTextEdit,
    QSizePolicy,
    QSpacerItem,
)

from core.base_page import BasePage
from core.dropdown_bar import DropdownBar
from pages.file_management_platforms import default_platform, sync_platform_dropdowns
from pages.doc_man import DocManWidget
from services.inspection_business_db_adapter import (
    create_inspection_project,
    list_inspection_findings,
    list_inspection_projects,
    replace_inspection_findings,
    soft_delete_inspection_project,
    update_inspection_project,
)
from services.file_db_adapter import DOC_MAN_MODULE_CODE, soft_delete_files_by_prefix

# ✅ 直接复用 ConstructionDocsWidget 的文件夹布局样式
from pages.construction_docs_widget import ConstructionDocsWidget


# ----------------------------------------------------------------------
# 小工具：可点击的 QLabel，用于面包屑“首页”
# ----------------------------------------------------------------------
class LinkLabel(QLabel):
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class AddPeriodicInspectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新增定期检测")
        self.setModal(True)
        self.resize(420, 220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.name_edit = QLineEdit(self)
        self.description_edit = QLineEdit(self)
        self.description_edit.setPlaceholderText("请输入项目描述")
        self.year_edit = QLineEdit(self)
        self.year_edit.setPlaceholderText("例如：2025")

        form.addRow("检测名称", self.name_edit)
        form.addRow("描述", self.description_edit)
        form.addRow("年份", self.year_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.button(QDialogButtonBox.Ok).setText("确定")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept_if_valid(self):
        name = self.name_edit.text().strip()
        year = self.year_edit.text().strip()
        if not name:
            QMessageBox.information(self, "提示", "请先填写名称。")
            return
        if not year:
            QMessageBox.information(self, "提示", "请先填写年份。")
            return
        self.accept()

    def get_values(self) -> dict[str, str]:
        return {
            "project_name": self.name_edit.text().strip(),
            "summary_text": self.description_edit.text().strip(),
            "project_year": self.year_edit.text().strip(),
        }


class AddSpecialEventInspectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新增特殊事件检测")
        self.setModal(True)
        self.resize(420, 220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.name_edit = QLineEdit(self)
        self.description_edit = QLineEdit(self)
        self.description_edit.setPlaceholderText("请输入事件描述")
        self.year_edit = QLineEdit(self)
        self.year_edit.setPlaceholderText("例如：2025")

        form.addRow("事件名称", self.name_edit)
        form.addRow("描述", self.description_edit)
        form.addRow("年份", self.year_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.button(QDialogButtonBox.Ok).setText("确定")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept_if_valid(self):
        name = self.name_edit.text().strip()
        year = self.year_edit.text().strip()
        if not name:
            QMessageBox.information(self, "提示", "请先填写事件名称。")
            return
        if not year:
            QMessageBox.information(self, "提示", "请先填写年份。")
            return
        self.accept()

    def get_values(self) -> dict[str, str]:
        return {
            "project_name": self.name_edit.text().strip(),
            "summary_text": self.description_edit.text().strip(),
            "project_year": self.year_edit.text().strip(),
        }


class InspectionProjectEditDialog(QDialog):
    def __init__(
        self,
        *,
        title_text: str,
        project_name: str = "",
        project_year: str = "",
        summary_text: str = "",
        parent=None,
        ):
        super().__init__(parent)
        self.setWindowTitle(title_text)
        self.resize(520, 220)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)
        self.name_edit = QLineEdit(self)
        self.name_edit.setText(project_name)
        self.summary_edit = QLineEdit(self)
        self.summary_edit.setText(summary_text or "")
        self.summary_edit.setPlaceholderText("请输入项目描述")
        self.year_edit = QLineEdit(self)
        self.year_edit.setText(project_year)
        form.addRow("项目名称", self.name_edit)
        form.addRow("描述", self.summary_edit)
        form.addRow("年份", self.year_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.button(QDialogButtonBox.Ok).setText("保存")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept_if_valid(self):
        if not self.name_edit.text().strip():
            QMessageBox.information(self, "提示", "项目名称不能为空。")
            return
        self.accept()

    def get_values(self) -> dict[str, str]:
        return {
            "project_name": self.name_edit.text().strip(),
            "project_year": self.year_edit.text().strip(),
            "summary_text": self.summary_edit.text().strip(),
        }


class InspectionFindingDialog(QDialog):
    def __init__(
        self,
        *,
        title_text: str,
        item_code: str = "",
        risk_level: str = "",
        conclusion: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title_text)
        self.resize(420, 260)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)
        self.item_code_edit = QLineEdit(self)
        self.item_code_edit.setText(item_code)
        self.risk_level_edit = QLineEdit(self)
        self.risk_level_edit.setText(risk_level)
        form.addRow("节点/构件", self.item_code_edit)
        form.addRow("风险等级", self.risk_level_edit)
        layout.addLayout(form)

        self.conclusion_edit = QTextEdit(self)
        self.conclusion_edit.setPlaceholderText("请输入结论")
        self.conclusion_edit.setPlainText(conclusion or "")
        layout.addWidget(self.conclusion_edit, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.button(QDialogButtonBox.Ok).setText("保存")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept_if_valid(self):
        if not self.item_code_edit.text().strip():
            QMessageBox.information(self, "提示", "节点/构件不能为空。")
            return
        self.accept()

    def get_values(self) -> dict[str, str]:
        return {
            "item_code": self.item_code_edit.text().strip(),
            "risk_level": self.risk_level_edit.text().strip(),
            "conclusion": self.conclusion_edit.toPlainText().strip(),
        }


# ----------------------------------------------------------------------
# ✅ 首页文件夹入口：直接复用 ConstructionDocsWidget 的文件夹布局 UI
# ----------------------------------------------------------------------
class _HomeFoldersWidget(ConstructionDocsWidget):
    folderSelected = pyqtSignal(str)

    def _build_folder_tree(self) -> Dict:
        """
        首页
        ├─ 完工检测
        ├─ 第1次检测
        ├─ 第N次检测
        └─ 历史抽检记录

        这里不进入 ConstructionDocsWidget 自带的 file_view，
        只用于“文件夹入口”。点击后抛出 folderSelected 信号。
        """
        return {
            "完工检测": {"type": "folder", "children": {}},
            "定期检测1-N": {"type": "folder", "children": {}},
            "特殊事件检测（台风、碰撞等）": {"type": "folder", "children": {}},
        }

    def _build_demo_file_records(self) -> Dict[str, List[Dict]]:
        return {}

    def _on_folder_clicked(self, folder_name: str):
        # 直接发信号给外部页面处理（保持你原来的 _switch_to 逻辑）
        name_to_key = {
            "完工检测": "complete",
            "定期检测1-N": "periodic",
            "特殊事件检测（台风、碰撞等）": "history_sampling",
        }
        self.folderSelected.emit(name_to_key.get(folder_name, "home"))


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

    PERIODIC_FILE_COL_INDEX = 0
    PERIODIC_FILE_COL_NAME = 1
    PERIODIC_FILE_COL_MTIME = 2
    PERIODIC_FILE_COL_UPLOAD = 3
    PERIODIC_FILE_COL_DOWNLOAD = 4
    PERIODIC_FILE_COL_REMARK = 5

    def __init__(self, parent=None):
        # ✅ 删除 BasePage 顶部标题“历史检测及结论”：不给标题文本
        super().__init__("", parent)
        self.breadcrumb_font_ratio = 0.015
        self.facility_code = ""

        # 当前所在“文件夹”
        self.current_folder_key = "home"

        # 各文件夹每一行上传的真实路径：
        # {folder_key: {row_index: file_path}}
        self.file_paths: Dict[str, Dict[int, str]] = {}

        # 预设每个文件夹的表格数据
        self.folder_rows = self._build_folder_rows()
        self.periodic_demo_data = self._build_periodic_demo_data()
        self.special_event_demo_data = self._build_special_event_demo_data()
        self.doc_man_configs = self._build_doc_man_configs()
        self.doc_man_records = self._build_doc_man_records()
        self._loading_periodic_findings = False
        self._loading_special_event_findings = False

        # 资源路径（小文件夹图标）
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.folder_icon_path = os.path.join(project_root, "pict", "wenjian.png")

        self._build_ui()
        self._reload_database_backed_data()

        # ✅ 兜底隐藏 BasePage 的标题控件（不同实现命名可能不同）
        self._hide_basepage_title_if_any()

    # ✅ 兜底：隐藏 BasePage 可能创建的标题控件，避免占高度
    def _hide_basepage_title_if_any(self):
        for attr in ("title_label", "lbl_title", "label_title", "page_title_label", "header_label"):
            w = getattr(self, attr, None)
            if w is not None:
                try:
                    w.setVisible(False)
                    w.setFixedHeight(0)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # 数据定义
    # ------------------------------------------------------------------
    def _build_folder_rows(self) -> Dict[str, List[Dict]]:
        """定义 4 个文件夹显示的行内容。"""

        complete_rows = [
            {"category": "检测策略报告", "format": "word/pdf"},
            {"category": "节点风险评估表", "format": "excel/pdf"},
            {"category": "节点检验计划表", "format": "excel/pdf"},
            {"category": "构件风险评估表", "format": "excel/pdf"},
            {"category": "构件检验计划表", "format": "excel/pdf"},
            {"category": "节点构件检验计划位置", "format": "dwg/pdf"},
        ]

        first_rows = [
            {"category": "检测策略报告", "format": "word/pdf"},
            {"category": "节点风险评估表", "format": "excel/pdf"},
            {"category": "节点检验计划表", "format": "excel/pdf"},
            {"category": "构件风险评估表", "format": "excel/pdf"},
            {"category": "构件检验计划表", "format": "excel/pdf"},
            {"category": "节点构件检验计划位置", "format": "dwg/pdf"},
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
            "periodic": list(first_rows),
            "history_sampling": history_rows,
        }

    def _reload_database_backed_data(self):
        facility_code = (self.facility_code or default_platform()["facility_code"]).strip()
        self.periodic_demo_data = self._build_project_view_models(
            list_inspection_projects(facility_code, "periodic"),
            file_title_suffix="文件",
            record_title_suffix="抽检记录",
        )
        self.special_event_demo_data = self._build_project_view_models(
            list_inspection_projects(facility_code, "special_event"),
            file_title_suffix="文件",
            record_title_suffix="检测记录",
        )
        if hasattr(self, "periodic_overview_table"):
            self._refresh_periodic_overview_table(selected_row=0 if self.periodic_demo_data else None)
        if hasattr(self, "special_event_overview_table"):
            self._refresh_special_event_overview_table(selected_row=0 if self.special_event_demo_data else None)

    @staticmethod
    def _build_project_view_models(rows: List[Dict], *, file_title_suffix: str, record_title_suffix: str) -> List[Dict]:
        items: List[Dict] = []
        for index, row in enumerate(rows, start=1):
            title = row.get("project_name") or ""
            year = row.get("project_year") or row.get("event_date") or ""
            summary_text = row.get("summary_text") or ""
            items.append(
                {
                    "id": row.get("id"),
                    "index": index,
                    "title": title,
                    "summary_text": summary_text,
                    "year": year,
                    "file_section_title": f"{title}{file_title_suffix}" if title else file_title_suffix,
                    "sampling_section_title": f"{title}{record_title_suffix}" if title else record_title_suffix,
                    "record_section_title": f"{title}{record_title_suffix}" if title else record_title_suffix,
                }
            )
        return items

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------
    def _build_ui(self):
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        # ✅ 顶格更贴近“文件管理”效果：把 spacing 从 8 改为 0（不改逻辑，仅 UI）
        self.main_layout.setSpacing(8)

        # ---------- 顶部 DropdownBar ----------
        fields = [
            {"key": "branch", "label": "分公司", "options": ["渤江分公司"], "default": "渤江分公司"},
            {"key": "op_company", "label": "作业公司", "options": ["文昌油田群作业公司"], "default": "文昌油田群作业公司"},
            {"key": "oilfield", "label": "油气田", "options": ["文昌19-1油田"], "default": "文昌19-1油田"},
            {"key": "facility_code", "label": "设施编码", "options": ["WC19-1WHPC"], "default": "WC19-1WHPC"},
            {"key": "facility_name", "label": "设施名称", "options": ["文昌19-1WHPC井口平台"], "default": "文昌19-1WHPC井口平台"},
            {"key": "facility_type", "label": "设施类型", "options": ["平台"], "default": "平台"},
            {"key": "category", "label": "分类", "options": ["井口平台"], "default": "井口平台"},
            {"key": "start_time", "label": "投产时间", "options": ["2013-07-15"], "default": "2013-07-15"},
            {"key": "design_life", "label": "设计年限", "options": ["15"], "default": "15"},
        ]
        platform_defaults = default_platform()
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
        self.pages["periodic"] = self._build_periodic_page()
        self.pages["first"] = self._build_folder_table_page("第1次检测", "first")
        self.pages["nth"] = self._build_folder_table_page("第N次检测", "nth")
        self.pages["history_sampling"] = self._build_history_sampling_page()

        for key in ["home", "complete", "periodic", "first", "nth", "history_sampling"]:
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
        bar.setObjectName("PathBar")
        bar.setFixedHeight(40)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(6)

        # 小文件夹图标 (深蓝底)
        self.path_icon_label = QLabel(bar)
        self.path_icon_label.setFixedSize(24, 24)
        self.path_icon_label.setAlignment(Qt.AlignCenter)
        self.path_icon_label.setObjectName("PathIcon")

        pix = QPixmap(self.folder_icon_path)
        if not pix.isNull():
            pix = pix.scaled(18, 18, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.path_icon_label.setPixmap(pix)

        layout.addWidget(self.path_icon_label)

        # “首页”
        self.lbl_home_link = LinkLabel("首页", bar)
        self.lbl_home_link.setObjectName("Breadcrumb")
        self.lbl_home_link.clicked.connect(lambda: self._switch_to("home"))
        layout.addWidget(self.lbl_home_link)

        # 分隔符 >
        self.lbl_sep = QLabel(" >", bar)
        self.lbl_sep.setObjectName("BreadcrumbArrow")
        layout.addWidget(self.lbl_sep)

        # 第二级标题：完工检测 / 第1次检测 / 第N次检测 / 历史抽检记录
        self.lbl_second = QLabel("", bar)
        self.lbl_second.setObjectName("BreadcrumbCurrent")
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
                "periodic": "定期检测1-N",
                "first": "第1次检测",
                "nth": "第N次检测",
                "history_sampling": "特殊事件检测（台风、碰撞等）",
            }
            self.lbl_second.setText(name_map.get(self.current_folder_key, ""))

    # ------------------------------------------------------------------
    # 首页：四个文件夹
    # ------------------------------------------------------------------
    def _build_home_page(self) -> QWidget:
        # ✅ 这里保持“首页是 stack 的一个 page”的结构不变
        page = QWidget(self.stack)
        layout = QVBoxLayout(page)

        # ✅ 让它更像 ConstructionDocsWidget 的首页：顶格、由其内部控制间距
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ✅ 直接复用 ConstructionDocsWidget 的文件夹布局 UI
        home_folders = _HomeFoldersWidget(page)
        home_folders.folderSelected.connect(lambda k: self._switch_to(k))
        layout.addWidget(home_folders)

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

        if folder_key in self.doc_man_configs:
            doc_widget = DocManWidget(self._get_doc_man_upload_dir, page)
            doc_widget.set_context(
                [folder_key],
                self.doc_man_records[folder_key],
                self.doc_man_configs[folder_key],
                facility_code=self.facility_code,
                hide_empty_templates=True,
                db_list_mode=True,
            )
            layout.addWidget(doc_widget)
            return page

        table = self._create_table_for_folder(folder_key)
        layout.addWidget(table)

        return page

    def _build_periodic_page(self) -> QWidget:
        page = QWidget(self.stack)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 10, 0, 18)
        layout.setSpacing(14)

        self.periodic_overview_table = QTableWidget(len(self.periodic_demo_data), 4, page)
        self.periodic_overview_table.setObjectName("PeriodicOverviewTable")
        self.periodic_overview_table.setHorizontalHeaderLabels(["序号", "项目名称", "描述", "年份"])
        self.periodic_overview_table.verticalHeader().setVisible(False)
        self.periodic_overview_table.setAlternatingRowColors(False)
        self.periodic_overview_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.periodic_overview_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.periodic_overview_table.verticalHeader().setDefaultSectionSize(42)
        self.periodic_overview_table.setShowGrid(True)
        self.periodic_overview_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.periodic_overview_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.periodic_overview_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.periodic_overview_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.periodic_overview_table.setColumnWidth(0, 92)
        self.periodic_overview_table.setColumnWidth(3, 138)
        self.periodic_overview_table.setMinimumHeight(182)

        for row, item in enumerate(self.periodic_demo_data):
            index_item = QTableWidgetItem(str(item["index"]))
            index_item.setTextAlignment(Qt.AlignCenter)
            index_item.setFlags(index_item.flags() & ~Qt.ItemIsEditable)
            self.periodic_overview_table.setItem(row, 0, index_item)

            title_item = QTableWidgetItem(item["title"])
            title_item.setTextAlignment(Qt.AlignCenter)
            title_item.setFlags(title_item.flags() & ~Qt.ItemIsEditable)
            self.periodic_overview_table.setItem(row, 1, title_item)

            summary_item = QTableWidgetItem(item.get("summary_text", ""))
            summary_item.setTextAlignment(Qt.AlignCenter)
            summary_item.setFlags(summary_item.flags() & ~Qt.ItemIsEditable)
            self.periodic_overview_table.setItem(row, 2, summary_item)

            year_item = QTableWidgetItem(item["year"])
            year_item.setTextAlignment(Qt.AlignCenter)
            year_item.setFlags(year_item.flags() & ~Qt.ItemIsEditable)
            self.periodic_overview_table.setItem(row, 3, year_item)

        self.periodic_overview_table.itemSelectionChanged.connect(self._on_periodic_project_changed)
        layout.addWidget(self.periodic_overview_table, 0)

        periodic_action_row = QHBoxLayout()
        periodic_action_row.setContentsMargins(0, 0, 0, 0)
        periodic_action_row.addStretch()
        self.periodic_add_btn = QPushButton("新增检测", page)
        self.periodic_add_btn.setObjectName("OverviewActionButton")
        self.periodic_add_btn.clicked.connect(self._add_periodic_project)
        periodic_action_row.addWidget(self.periodic_add_btn, 0, Qt.AlignRight)
        self.periodic_edit_btn = QPushButton("ç¼–è¾‘æ£€æµ‹", page)
        self.periodic_edit_btn.setObjectName("OverviewActionButton")
        self.periodic_edit_btn.clicked.connect(self._edit_periodic_project)
        self.periodic_edit_btn.setText("编辑检测")
        periodic_action_row.addWidget(self.periodic_edit_btn, 0, Qt.AlignRight)
        self.periodic_delete_btn = QPushButton("åˆ é™¤æ£€æµ‹", page)
        self.periodic_delete_btn.setObjectName("OverviewActionButton")
        self.periodic_delete_btn.clicked.connect(self._delete_periodic_project)
        self.periodic_delete_btn.setText("删除检测")
        periodic_action_row.addWidget(self.periodic_delete_btn, 0, Qt.AlignRight)
        layout.addLayout(periodic_action_row)

        self.periodic_files_title = QLabel("第一次检测文件", page)
        self.periodic_files_title.setObjectName("PeriodicSectionBanner")
        layout.addWidget(self.periodic_files_title, 0)

        self.periodic_files_table = QTableWidget(0, 6, page)
        self.periodic_files_table.setObjectName("PeriodicFilesTable")
        self.periodic_files_table.setHorizontalHeaderLabels(["序号", "文件名", "修改时间", "上传", "下载", "备注"])
        self.periodic_files_table.verticalHeader().setVisible(False)
        self.periodic_files_table.setAlternatingRowColors(False)
        self.periodic_files_table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.periodic_files_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.periodic_files_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.periodic_files_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.periodic_files_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.periodic_files_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.periodic_files_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.periodic_files_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.periodic_files_table.setMinimumHeight(220)
        self.periodic_files_table.cellClicked.connect(self._on_periodic_file_cell_clicked)
        layout.addWidget(self.periodic_files_table, 0)
        self.periodic_files_table.hide()
        self.periodic_files_widget = DocManWidget(self._get_doc_man_upload_dir, page)
        layout.addWidget(self.periodic_files_widget, 0)

        self.periodic_sampling_title = QLabel("第一次抽检记录", page)
        self.periodic_sampling_title.setObjectName("PeriodicSectionBanner")
        layout.addWidget(self.periodic_sampling_title, 0)

        periodic_sampling_action_row = QHBoxLayout()
        periodic_sampling_action_row.setContentsMargins(0, 0, 0, 0)
        periodic_sampling_action_row.addStretch()
        self.periodic_sampling_add_btn = QPushButton("新增记录", page)
        self.periodic_sampling_add_btn.setObjectName("OverviewActionButton")
        self.periodic_sampling_add_btn.clicked.connect(self._add_periodic_finding)
        periodic_sampling_action_row.addWidget(self.periodic_sampling_add_btn, 0, Qt.AlignRight)
        self.periodic_sampling_delete_btn = QPushButton("删除记录", page)
        self.periodic_sampling_delete_btn.setObjectName("OverviewActionButton")
        self.periodic_sampling_delete_btn.clicked.connect(self._delete_periodic_finding)
        periodic_sampling_action_row.addWidget(self.periodic_sampling_delete_btn, 0, Qt.AlignRight)
        self.periodic_sampling_edit_btn = QPushButton("ç¼–è¾‘è®°å½•", page)
        self.periodic_sampling_edit_btn.setObjectName("OverviewActionButton")
        self.periodic_sampling_edit_btn.clicked.connect(self._edit_periodic_finding)
        self.periodic_sampling_edit_btn.setText("编辑记录")
        periodic_sampling_action_row.addWidget(self.periodic_sampling_edit_btn, 0, Qt.AlignRight)
        layout.addLayout(periodic_sampling_action_row)

        self.periodic_sampling_table = QTableWidget(0, 3, page)
        self.periodic_sampling_table.setObjectName("PeriodicSamplingTable")
        self.periodic_sampling_table.setHorizontalHeaderLabels(["节点号", "检验等级", "检验结论"])
        self.periodic_sampling_table.verticalHeader().setVisible(False)
        self.periodic_sampling_table.setAlternatingRowColors(False)
        self.periodic_sampling_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.periodic_sampling_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.periodic_sampling_table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked)
        self.periodic_sampling_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.periodic_sampling_table.setMinimumHeight(190)
        self.periodic_sampling_table.itemChanged.connect(self._on_periodic_sampling_item_changed)
        layout.addWidget(self.periodic_sampling_table, 1)

        if self.periodic_demo_data:
            self.periodic_overview_table.selectRow(0)
            self._refresh_periodic_detail(0)

        return page

    # ------------------------------------------------------------------
    # 历史抽检记录：表格 + 蓝底说明
    # ------------------------------------------------------------------
    def _build_history_sampling_page(self) -> QWidget:
        page = QWidget(self.stack)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 10, 0, 18)
        layout.setSpacing(14)

        self.special_event_overview_table = QTableWidget(len(self.special_event_demo_data), 4, page)
        self.special_event_overview_table.setObjectName("SpecialEventOverviewTable")
        self.special_event_overview_table.setHorizontalHeaderLabels(["序号", "事件名称", "描述", "年份"])
        self.special_event_overview_table.verticalHeader().setVisible(False)
        self.special_event_overview_table.setAlternatingRowColors(False)
        self.special_event_overview_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.special_event_overview_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.special_event_overview_table.verticalHeader().setDefaultSectionSize(42)
        self.special_event_overview_table.setShowGrid(True)
        self.special_event_overview_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.special_event_overview_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.special_event_overview_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.special_event_overview_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.special_event_overview_table.setColumnWidth(0, 92)
        self.special_event_overview_table.setColumnWidth(3, 138)
        self.special_event_overview_table.setMinimumHeight(182)

        for row, item in enumerate(self.special_event_demo_data):
            index_item = QTableWidgetItem(str(item["index"]))
            index_item.setTextAlignment(Qt.AlignCenter)
            index_item.setFlags(index_item.flags() & ~Qt.ItemIsEditable)
            self.special_event_overview_table.setItem(row, 0, index_item)

            title_item = QTableWidgetItem(item["title"])
            title_item.setTextAlignment(Qt.AlignCenter)
            title_item.setFlags(title_item.flags() & ~Qt.ItemIsEditable)
            self.special_event_overview_table.setItem(row, 1, title_item)

            summary_item = QTableWidgetItem(item.get("summary_text", ""))
            summary_item.setTextAlignment(Qt.AlignCenter)
            summary_item.setFlags(summary_item.flags() & ~Qt.ItemIsEditable)
            self.special_event_overview_table.setItem(row, 2, summary_item)

            year_item = QTableWidgetItem(item["year"])
            year_item.setTextAlignment(Qt.AlignCenter)
            year_item.setFlags(year_item.flags() & ~Qt.ItemIsEditable)
            self.special_event_overview_table.setItem(row, 3, year_item)

        self.special_event_overview_table.itemSelectionChanged.connect(self._on_special_event_changed)
        layout.addWidget(self.special_event_overview_table, 0)

        special_event_action_row = QHBoxLayout()
        special_event_action_row.setContentsMargins(0, 0, 0, 0)
        special_event_action_row.addStretch()
        self.special_event_add_btn = QPushButton("新增检测", page)
        self.special_event_add_btn.setObjectName("OverviewActionButton")
        self.special_event_add_btn.clicked.connect(self._add_special_event)
        special_event_action_row.addWidget(self.special_event_add_btn, 0, Qt.AlignRight)
        self.special_event_edit_btn = QPushButton("ç¼–è¾‘æ£€æµ‹", page)
        self.special_event_edit_btn.setObjectName("OverviewActionButton")
        self.special_event_edit_btn.clicked.connect(self._edit_special_event_project)
        self.special_event_edit_btn.setText("编辑检测")
        special_event_action_row.addWidget(self.special_event_edit_btn, 0, Qt.AlignRight)
        self.special_event_delete_btn = QPushButton("åˆ é™¤æ£€æµ‹", page)
        self.special_event_delete_btn.setObjectName("OverviewActionButton")
        self.special_event_delete_btn.clicked.connect(self._delete_special_event_project)
        self.special_event_delete_btn.setText("删除检测")
        special_event_action_row.addWidget(self.special_event_delete_btn, 0, Qt.AlignRight)
        layout.addLayout(special_event_action_row)

        self.special_event_files_title = QLabel("台风损伤检测", page)
        self.special_event_files_title.setObjectName("PeriodicSectionBanner")
        layout.addWidget(self.special_event_files_title, 0)

        self.special_event_files_table = QTableWidget(0, 6, page)
        self.special_event_files_table.setObjectName("SpecialEventFilesTable")
        self.special_event_files_table.setHorizontalHeaderLabels(["序号", "文件名", "修改时间", "上传", "下载", "备注"])
        self.special_event_files_table.verticalHeader().setVisible(False)
        self.special_event_files_table.setAlternatingRowColors(False)
        self.special_event_files_table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.special_event_files_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.special_event_files_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.special_event_files_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.special_event_files_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.special_event_files_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.special_event_files_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.special_event_files_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.special_event_files_table.setMinimumHeight(220)
        self.special_event_files_table.cellClicked.connect(self._on_special_event_file_cell_clicked)
        layout.addWidget(self.special_event_files_table, 0)
        self.special_event_files_table.hide()
        self.special_event_files_widget = DocManWidget(self._get_doc_man_upload_dir, page)
        layout.addWidget(self.special_event_files_widget, 0)

        self.special_event_records_title = QLabel("台风损伤检测记录", page)
        self.special_event_records_title.setObjectName("PeriodicSectionBanner")
        layout.addWidget(self.special_event_records_title, 0)

        special_event_records_action_row = QHBoxLayout()
        special_event_records_action_row.setContentsMargins(0, 0, 0, 0)
        special_event_records_action_row.addStretch()
        self.special_event_records_add_btn = QPushButton("新增记录", page)
        self.special_event_records_add_btn.setObjectName("OverviewActionButton")
        self.special_event_records_add_btn.clicked.connect(self._add_special_event_finding)
        special_event_records_action_row.addWidget(self.special_event_records_add_btn, 0, Qt.AlignRight)
        self.special_event_records_delete_btn = QPushButton("删除记录", page)
        self.special_event_records_delete_btn.setObjectName("OverviewActionButton")
        self.special_event_records_delete_btn.clicked.connect(self._delete_special_event_finding)
        special_event_records_action_row.addWidget(self.special_event_records_delete_btn, 0, Qt.AlignRight)
        self.special_event_records_edit_btn = QPushButton("ç¼–è¾‘è®°å½•", page)
        self.special_event_records_edit_btn.setObjectName("OverviewActionButton")
        self.special_event_records_edit_btn.clicked.connect(self._edit_special_event_finding)
        self.special_event_records_edit_btn.setText("编辑记录")
        special_event_records_action_row.addWidget(self.special_event_records_edit_btn, 0, Qt.AlignRight)
        layout.addLayout(special_event_records_action_row)

        self.special_event_records_table = QTableWidget(0, 3, page)
        self.special_event_records_table.setObjectName("SpecialEventRecordsTable")
        self.special_event_records_table.setHorizontalHeaderLabels(["节点号", "检验等级", "检验结论"])
        self.special_event_records_table.verticalHeader().setVisible(False)
        self.special_event_records_table.setAlternatingRowColors(False)
        self.special_event_records_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.special_event_records_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.special_event_records_table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked)
        self.special_event_records_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.special_event_records_table.setMinimumHeight(190)
        self.special_event_records_table.itemChanged.connect(self._on_special_event_record_item_changed)
        layout.addWidget(self.special_event_records_table, 1)

        if self.special_event_demo_data:
            self.special_event_overview_table.selectRow(0)
            self._refresh_special_event_detail(0)

        return page

    def _create_periodic_demo_entry(self, title: str, year: str) -> Dict:
        return {
            "index": len(self.periodic_demo_data) + 1,
            "title": title,
            "year": year,
            "file_section_title": f"{title}文件",
            "sampling_section_title": f"{title}抽检记录",
            "files": [
                {"name": f"{title}报告.pdf", "mtime": f"{year}/06/18", "remark": "演示文件"},
                {"name": f"{title}原始记录.xlsx", "mtime": f"{year}/06/20", "remark": "演示文件"},
                {"name": f"{title}照片资料.zip", "mtime": f"{year}/06/22", "remark": "演示文件"},
            ],
            "sampling": [
                {"node": "A1X2", "level": "III", "conclusion": "演示结论，建议跟踪观察"},
                {"node": "L002", "level": "II", "conclusion": "演示结论，状态良好"},
                {"node": "XG030", "level": "III", "conclusion": "演示结论，局部复核"},
            ],
        }

    def _create_special_event_demo_entry(self, title: str, year: str) -> Dict:
        return {
            "index": len(self.special_event_demo_data) + 1,
            "title": title,
            "year": year,
            "file_section_title": title,
            "record_section_title": f"{title}记录",
            "files": [
                {"name": f"{title}报告.pdf", "mtime": f"{year}/09/08", "remark": "演示文件"},
                {"name": f"{title}照片资料.zip", "mtime": f"{year}/09/10", "remark": "演示文件"},
                {"name": f"{title}处理建议.docx", "mtime": f"{year}/09/12", "remark": "演示文件"},
            ],
            "records": [
                {"node": "A1X2", "level": "IV", "conclusion": "演示结论，建议专项复查"},
                {"node": "L002", "level": "II", "conclusion": "演示结论，状态可控"},
                {"node": "XG030", "level": "III", "conclusion": "演示结论，建议补充检测"},
            ],
        }

    def _add_periodic_project(self):
        dialog = AddPeriodicInspectionDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return

        values = dialog.get_values()
        create_inspection_project(
            facility_code=(self.facility_code or default_platform()["facility_code"]).strip(),
            project_type="periodic",
            project_name=values["project_name"],
            project_year=values["project_year"],
            summary_text=values["summary_text"],
        )
        self._reload_database_backed_data()

    def _add_special_event(self):
        dialog = AddSpecialEventInspectionDialog(self)
        if dialog.exec_() != QDialog.Accepted:
            return

        values = dialog.get_values()
        create_inspection_project(
            facility_code=(self.facility_code or default_platform()["facility_code"]).strip(),
            project_type="special_event",
            project_name=values["project_name"],
            project_year=values["project_year"],
            summary_text=values["summary_text"],
        )
        self._reload_database_backed_data()

    def _on_periodic_project_changed(self):
        row = self.periodic_overview_table.currentRow()
        if row < 0 and self.periodic_overview_table.rowCount():
            row = 0
        self._refresh_periodic_detail(row)

    def _populate_periodic_sampling_table(self, row: int):
        project_id = self.periodic_demo_data[row].get("id")
        sampling_rows = list_inspection_findings(project_id) if project_id else []
        self._loading_periodic_findings = True
        self.periodic_sampling_table.clearContents()
        self.periodic_sampling_table.setRowCount(len(sampling_rows))

        for sampling_row, sampling_info in enumerate(sampling_rows):
            for col, value in enumerate(
                (
                    sampling_info.get("item_code", ""),
                    sampling_info.get("risk_level", ""),
                    sampling_info.get("conclusion", ""),
                )
            ):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignCenter)
                self.periodic_sampling_table.setItem(sampling_row, col, item)
        self._loading_periodic_findings = False

    @staticmethod
    def _collect_findings_from_table(table: QTableWidget) -> list[dict]:
        rows: list[dict] = []
        for row in range(table.rowCount()):
            values = []
            for col in range(3):
                item = table.item(row, col)
                values.append(item.text().strip() if item else "")
            if any(values):
                rows.append(
                    {
                        "item_code": values[0],
                        "risk_level": values[1],
                        "conclusion": values[2],
                    }
                )
        return rows

    def _save_periodic_findings(self):
        row = self.periodic_overview_table.currentRow()
        if row < 0 or row >= len(self.periodic_demo_data):
            return
        project_id = self.periodic_demo_data[row].get("id")
        if not project_id:
            return
        replace_inspection_findings(project_id, self._collect_findings_from_table(self.periodic_sampling_table))

    def _save_special_event_findings(self):
        row = self.special_event_overview_table.currentRow()
        if row < 0 or row >= len(self.special_event_demo_data):
            return
        project_id = self.special_event_demo_data[row].get("id")
        if not project_id:
            return
        replace_inspection_findings(project_id, self._collect_findings_from_table(self.special_event_records_table))

    def _add_periodic_finding(self):
        row = self.periodic_overview_table.currentRow()
        if row < 0 or row >= len(self.periodic_demo_data):
            return
        self._loading_periodic_findings = True
        new_row = self.periodic_sampling_table.rowCount()
        self.periodic_sampling_table.insertRow(new_row)
        for col in range(3):
            item = QTableWidgetItem("")
            item.setTextAlignment(Qt.AlignCenter)
            self.periodic_sampling_table.setItem(new_row, col, item)
        self._loading_periodic_findings = False
        self._save_periodic_findings()

    def _delete_periodic_finding(self):
        row = self.periodic_sampling_table.currentRow()
        if row < 0:
            return
        self._loading_periodic_findings = True
        self.periodic_sampling_table.removeRow(row)
        self._loading_periodic_findings = False
        self._save_periodic_findings()

    def _on_periodic_sampling_item_changed(self, item: QTableWidgetItem):
        if self._loading_periodic_findings:
            return
        self._save_periodic_findings()

    def _on_special_event_changed(self):
        row = self.special_event_overview_table.currentRow()
        if row < 0 and self.special_event_overview_table.rowCount():
            row = 0
        self._refresh_special_event_detail(row)

    def _populate_special_event_records_table(self, row: int):
        project_id = self.special_event_demo_data[row].get("id")
        records = list_inspection_findings(project_id) if project_id else []
        self._loading_special_event_findings = True
        self.special_event_records_table.clearContents()
        self.special_event_records_table.setRowCount(len(records))

        for record_row, record_info in enumerate(records):
            for col, value in enumerate(
                (
                    record_info.get("item_code", ""),
                    record_info.get("risk_level", ""),
                    record_info.get("conclusion", ""),
                )
            ):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignCenter)
                self.special_event_records_table.setItem(record_row, col, item)
        self._loading_special_event_findings = False

    def _add_special_event_finding(self):
        row = self.special_event_overview_table.currentRow()
        if row < 0 or row >= len(self.special_event_demo_data):
            return
        self._loading_special_event_findings = True
        new_row = self.special_event_records_table.rowCount()
        self.special_event_records_table.insertRow(new_row)
        for col in range(3):
            item = QTableWidgetItem("")
            item.setTextAlignment(Qt.AlignCenter)
            self.special_event_records_table.setItem(new_row, col, item)
        self._loading_special_event_findings = False
        self._save_special_event_findings()

    def _delete_special_event_finding(self):
        row = self.special_event_records_table.currentRow()
        if row < 0:
            return
        self._loading_special_event_findings = True
        self.special_event_records_table.removeRow(row)
        self._loading_special_event_findings = False
        self._save_special_event_findings()

    def _selected_periodic_project(self) -> dict | None:
        row = self.periodic_overview_table.currentRow()
        if row < 0 or row >= len(self.periodic_demo_data):
            return None
        return self.periodic_demo_data[row]

    def _selected_special_event_project(self) -> dict | None:
        row = self.special_event_overview_table.currentRow()
        if row < 0 or row >= len(self.special_event_demo_data):
            return None
        return self.special_event_demo_data[row]

    def _project_file_key(self, project_type: str, project: dict | None, fallback_row: int) -> str:
        prefix = "periodic" if project_type == "periodic" else "special_event"
        if project and project.get("id"):
            return f"{prefix}_project_{int(project['id'])}"
        return f"{prefix}_row_{max(int(fallback_row), 0)}"

    def _on_special_event_record_item_changed(self, item: QTableWidgetItem):
        if self._loading_special_event_findings:
            return
        self._save_special_event_findings()

    def _on_periodic_file_cell_clicked(self, row: int, col: int):
        project_index = self.periodic_overview_table.currentRow()
        if project_index < 0:
            return

        project = self.periodic_demo_data[project_index] if project_index < len(self.periodic_demo_data) else None
        file_key = self._project_file_key("periodic", project, project_index)
        if col == self.PERIODIC_FILE_COL_UPLOAD:
            self._handle_periodic_upload(file_key, row)
        elif col == self.PERIODIC_FILE_COL_DOWNLOAD:
            self._handle_periodic_download(file_key, row)

    def _on_special_event_file_cell_clicked(self, row: int, col: int):
        event_index = self.special_event_overview_table.currentRow()
        if event_index < 0:
            return

        event = self.special_event_demo_data[event_index] if event_index < len(self.special_event_demo_data) else None
        file_key = self._project_file_key("special_event", event, event_index)
        if col == self.PERIODIC_FILE_COL_UPLOAD:
            self._handle_special_event_upload(file_key, row)
        elif col == self.PERIODIC_FILE_COL_DOWNLOAD:
            self._handle_special_event_download(file_key, row)

    def _handle_periodic_upload(self, file_key: str, row: int):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择文件上传",
            "",
            "所有文件 (*);;文档 (*.pdf *.doc *.docx *.xls *.xlsx *.dwg)",
        )
        if not file_path:
            return

        upload_root = self._get_upload_root()
        target_dir = os.path.join(upload_root, file_key)
        os.makedirs(target_dir, exist_ok=True)

        base_name = os.path.basename(file_path)
        target_path = os.path.join(target_dir, base_name)
        root, ext = os.path.splitext(target_path)
        suffix = 1
        while os.path.exists(target_path):
            target_path = f"{root} ({suffix}){ext}"
            suffix += 1

        try:
            shutil.copy2(file_path, target_path)
        except Exception as e:
            QMessageBox.critical(self, "上传失败", f"复制文件失败：{e}")
            return

        self.file_paths.setdefault(file_key, {})[row] = target_path
        now_str = QDateTime.currentDateTime().toString("yyyy/M/d")
        self.periodic_files_table.item(row, self.PERIODIC_FILE_COL_MTIME).setText(now_str)
        self.periodic_files_table.item(row, self.PERIODIC_FILE_COL_NAME).setText(base_name)
        QMessageBox.information(self, "上传成功", "文件上传成功。")

    def _handle_periodic_download(self, file_key: str, row: int):
        path = self.file_paths.get(file_key, {}).get(row)
        if not path or not os.path.exists(path):
            QMessageBox.information(self, "提示", "该行尚未上传真实文件，当前展示的是演示文件名。")
            return

        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _handle_special_event_upload(self, file_key: str, row: int):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择文件上传",
            "",
            "所有文件 (*);;文档 (*.pdf *.doc *.docx *.xls *.xlsx *.dwg)",
        )
        if not file_path:
            return

        upload_root = self._get_upload_root()
        target_dir = os.path.join(upload_root, file_key)
        os.makedirs(target_dir, exist_ok=True)

        base_name = os.path.basename(file_path)
        target_path = os.path.join(target_dir, base_name)
        root, ext = os.path.splitext(target_path)
        suffix = 1
        while os.path.exists(target_path):
            target_path = f"{root} ({suffix}){ext}"
            suffix += 1

        try:
            shutil.copy2(file_path, target_path)
        except Exception as e:
            QMessageBox.critical(self, "上传失败", f"复制文件失败：{e}")
            return

        self.file_paths.setdefault(file_key, {})[row] = target_path
        now_str = QDateTime.currentDateTime().toString("yyyy/M/d")
        self.special_event_files_table.item(row, self.PERIODIC_FILE_COL_MTIME).setText(now_str)
        self.special_event_files_table.item(row, self.PERIODIC_FILE_COL_NAME).setText(base_name)
        QMessageBox.information(self, "上传成功", "文件上传成功。")

    def _handle_special_event_download(self, file_key: str, row: int):
        path = self.file_paths.get(file_key, {}).get(row)
        if not path or not os.path.exists(path):
            QMessageBox.information(self, "提示", "该行尚未上传真实文件，当前展示的是演示文件名。")
            return

        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    # ------------------------------------------------------------------
    # 构造单个文件夹的表格
    # ------------------------------------------------------------------
    def _build_doc_man_configs(self) -> Dict[str, List[str]]:
        return {
            "complete": [
                "检测策略报告",
                "节点风险评估表",
                "节点检验计划表",
                "构件风险评估表",
                "构件检验计划表",
                "节点构件检验计划位置",
            ],
        }

    def _build_doc_man_records(self) -> Dict[str, List[Dict]]:
        records: Dict[str, List[Dict]] = {}
        for folder_key, categories in self.doc_man_configs.items():
            records[folder_key] = [
                {
                    "index": idx + 1,
                    "checked": False,
                    "category": category,
                    "fmt": "",
                    "mtime": "",
                    "path": "",
                    "remark": "",
                }
                for idx, category in enumerate(categories)
            ]
        return records

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
        facility = (self.facility_code or default_platform()["facility_code"]).strip()
        return os.path.join(project_root, "upload", "history_inspection", facility)

    def _get_doc_man_upload_dir(self, path_segments: List[str]) -> str:
        target_dir = os.path.join(self._get_upload_root(), *path_segments)
        os.makedirs(target_dir, exist_ok=True)
        return target_dir

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

    def set_facility_code(self, code: str):
        self.facility_code = (code or "").strip()
        self._reload_database_backed_data()
        if self.current_folder_key == "periodic" and hasattr(self, "periodic_overview_table"):
            row = self.periodic_overview_table.currentRow()
            if row >= 0:
                self._refresh_periodic_detail(row)
        elif self.current_folder_key == "history_sampling" and hasattr(self, "special_event_overview_table"):
            row = self.special_event_overview_table.currentRow()
            if row >= 0:
                self._refresh_special_event_detail(row)

    def _switch_to(self, folder_key: str):
        """切换到指定子页面。"""
        self.current_folder_key = folder_key
        widget = self.pages.get(folder_key)
        if widget is not None:
            self.stack.setCurrentWidget(widget)

        # ✅ 关键：首页用 ConstructionDocsWidget 自带的“首页条”，
        # 所以把你原来的面包屑蓝条隐藏，避免出现两条“首页”
        if folder_key == "home":
            self.breadcrumb_bar.setVisible(False)
            self.breadcrumb_bar.setFixedHeight(0)  # 防止仍占高度形成空白
        else:
            self.breadcrumb_bar.setVisible(True)
            self.breadcrumb_bar.setFixedHeight(40)  # 还原高度（你原来是 40）
            self._update_breadcrumb()

    # ------------------------------------------------------------------
    # 数据库优先：覆盖残留 demo/旧表格逻辑
    # ------------------------------------------------------------------
    def _project_storage_segments(self, project_type: str, project: dict | None) -> List[str]:
        root = "定期检测" if project_type == "periodic" else "特殊事件检测"
        if not project or not project.get("id"):
            return [root]
        return [root, f"project_{int(project['id'])}"]

    def _build_periodic_demo_data(self) -> List[Dict]:
        return []

    def _build_special_event_demo_data(self) -> List[Dict]:
        return []

    def _refresh_periodic_overview_table(self, selected_row: int | None = None):
        self.periodic_overview_table.clearContents()
        self.periodic_overview_table.setRowCount(len(self.periodic_demo_data))
        for row, item in enumerate(self.periodic_demo_data):
            item["index"] = row + 1
            values = (
                item["index"],
                item.get("title", ""),
                item.get("summary_text", ""),
                item.get("year", ""),
            )
            for col, value in enumerate(values):
                table_item = QTableWidgetItem(str(value))
                table_item.setTextAlignment(Qt.AlignCenter)
                table_item.setFlags(table_item.flags() & ~Qt.ItemIsEditable)
                self.periodic_overview_table.setItem(row, col, table_item)

        if self.periodic_demo_data:
            row = len(self.periodic_demo_data) - 1 if selected_row is None else max(0, min(selected_row, len(self.periodic_demo_data) - 1))
            self.periodic_overview_table.selectRow(row)
            self._refresh_periodic_detail(row)
            return

        self.periodic_files_title.setText("定期检测文件")
        self.periodic_sampling_title.setText("定期检测记录")
        self.periodic_files_widget.set_context(
            ["定期检测"],
            [],
            ["检测文档", "图纸", "Excel", "CAD", "其他"],
            facility_code=self.facility_code,
            hide_empty_templates=True,
            db_list_mode=True,
        )
        self.periodic_sampling_table.clearContents()
        self.periodic_sampling_table.setRowCount(0)

    def _refresh_special_event_overview_table(self, selected_row: int | None = None):
        self.special_event_overview_table.clearContents()
        self.special_event_overview_table.setRowCount(len(self.special_event_demo_data))
        for row, item in enumerate(self.special_event_demo_data):
            item["index"] = row + 1
            values = (
                item["index"],
                item.get("title", ""),
                item.get("summary_text", ""),
                item.get("year", ""),
            )
            for col, value in enumerate(values):
                table_item = QTableWidgetItem(str(value))
                table_item.setTextAlignment(Qt.AlignCenter)
                table_item.setFlags(table_item.flags() & ~Qt.ItemIsEditable)
                self.special_event_overview_table.setItem(row, col, table_item)

        if self.special_event_demo_data:
            row = len(self.special_event_demo_data) - 1 if selected_row is None else max(0, min(selected_row, len(self.special_event_demo_data) - 1))
            self.special_event_overview_table.selectRow(row)
            self._refresh_special_event_detail(row)
            return

        self.special_event_files_title.setText("特殊事件检测文件")
        self.special_event_records_title.setText("特殊事件检测记录")
        self.special_event_files_widget.set_context(
            ["特殊事件检测"],
            [],
            ["检测文档", "图纸", "Excel", "CAD", "其他"],
            facility_code=self.facility_code,
            hide_empty_templates=True,
            db_list_mode=True,
        )
        self.special_event_records_table.clearContents()
        self.special_event_records_table.setRowCount(0)

    def _refresh_periodic_detail(self, row: int):
        if row < 0 or row >= len(self.periodic_demo_data):
            return
        project = self.periodic_demo_data[row]
        self.periodic_files_title.setText(project.get("file_section_title") or "定期检测文件")
        self.periodic_sampling_title.setText(project.get("sampling_section_title") or "定期检测记录")
        self._populate_periodic_files_table(row)
        self._populate_periodic_sampling_table(row)

    def _populate_periodic_files_table(self, row: int):
        project = self.periodic_demo_data[row]
        self.periodic_files_widget.set_context(
            self._project_storage_segments("periodic", project),
            [],
            ["检测文档", "图纸", "Excel", "CAD", "其他"],
            facility_code=self.facility_code,
            hide_empty_templates=True,
            db_list_mode=True,
        )

    def _refresh_special_event_detail(self, row: int):
        if row < 0 or row >= len(self.special_event_demo_data):
            return
        event = self.special_event_demo_data[row]
        self.special_event_files_title.setText(event.get("file_section_title") or "特殊事件检测文件")
        self.special_event_records_title.setText(event.get("record_section_title") or "特殊事件检测记录")
        self._populate_special_event_files_table(row)
        self._populate_special_event_records_table(row)

    def _populate_special_event_files_table(self, row: int):
        event = self.special_event_demo_data[row]
        self.special_event_files_widget.set_context(
            self._project_storage_segments("special_event", event),
            [],
            ["检测文档", "图纸", "Excel", "CAD", "其他"],
            facility_code=self.facility_code,
            hide_empty_templates=True,
            db_list_mode=True,
        )

    def _edit_periodic_project(self):
        project = self._selected_periodic_project()
        if not project or not project.get("id"):
            QMessageBox.information(self, "提示", "请先选择一条定期检测项目。")
            return
        dialog = InspectionProjectEditDialog(
            title_text="编辑定期检测",
            project_name=project.get("title", ""),
            summary_text=project.get("summary_text", ""),
            project_year=project.get("year", ""),
            parent=self,
        )
        if dialog.exec_() != QDialog.Accepted:
            return
        values = dialog.get_values()
        update_inspection_project(
            int(project["id"]),
            project_name=values["project_name"],
            project_year=values["project_year"],
            summary_text=values["summary_text"],
        )
        self._reload_database_backed_data()

    def _delete_periodic_project(self):
        project = self._selected_periodic_project()
        if not project or not project.get("id"):
            QMessageBox.information(self, "提示", "请先选择一条定期检测项目。")
            return
        reply = QMessageBox.question(
            self,
            "删除检测",
            f"确认删除定期检测项目“{project.get('title', '')}”吗？相关文件会一并隐藏。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        soft_delete_files_by_prefix(
            module_code=DOC_MAN_MODULE_CODE,
            logical_path_prefix="/".join(self._project_storage_segments("periodic", project)),
            facility_code=self.facility_code,
        )
        soft_delete_inspection_project(int(project["id"]))
        self._reload_database_backed_data()

    def _edit_special_event_project(self):
        project = self._selected_special_event_project()
        if not project or not project.get("id"):
            QMessageBox.information(self, "提示", "请先选择一条特殊事件检测项目。")
            return
        dialog = InspectionProjectEditDialog(
            title_text="编辑特殊事件检测",
            project_name=project.get("title", ""),
            summary_text=project.get("summary_text", ""),
            project_year=project.get("year", ""),
            parent=self,
        )
        if dialog.exec_() != QDialog.Accepted:
            return
        values = dialog.get_values()
        update_inspection_project(
            int(project["id"]),
            project_name=values["project_name"],
            project_year=values["project_year"],
            summary_text=values["summary_text"],
        )
        self._reload_database_backed_data()

    def _delete_special_event_project(self):
        project = self._selected_special_event_project()
        if not project or not project.get("id"):
            QMessageBox.information(self, "提示", "请先选择一条特殊事件检测项目。")
            return
        reply = QMessageBox.question(
            self,
            "删除检测",
            f"确认删除特殊事件检测项目“{project.get('title', '')}”吗？相关文件会一并隐藏。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        soft_delete_files_by_prefix(
            module_code=DOC_MAN_MODULE_CODE,
            logical_path_prefix="/".join(self._project_storage_segments("special_event", project)),
            facility_code=self.facility_code,
        )
        soft_delete_inspection_project(int(project["id"]))
        self._reload_database_backed_data()

    def _edit_periodic_finding(self):
        project = self._selected_periodic_project()
        row = self.periodic_sampling_table.currentRow()
        if not project or row < 0:
            QMessageBox.information(self, "提示", "请先选择一条定期检测记录。")
            return
        values = []
        for col in range(3):
            item = self.periodic_sampling_table.item(row, col)
            values.append(item.text().strip() if item else "")
        dialog = InspectionFindingDialog(
            title_text="编辑定期检测记录",
            item_code=values[0],
            risk_level=values[1],
            conclusion=values[2],
            parent=self,
        )
        if dialog.exec_() != QDialog.Accepted:
            return
        result = dialog.get_values()
        self._loading_periodic_findings = True
        for col, value in enumerate((result["item_code"], result["risk_level"], result["conclusion"])):
            item = self.periodic_sampling_table.item(row, col) or QTableWidgetItem("")
            item.setTextAlignment(Qt.AlignCenter)
            item.setText(value)
            self.periodic_sampling_table.setItem(row, col, item)
        self._loading_periodic_findings = False
        self._save_periodic_findings()

    def _edit_special_event_finding(self):
        project = self._selected_special_event_project()
        row = self.special_event_records_table.currentRow()
        if not project or row < 0:
            QMessageBox.information(self, "提示", "请先选择一条特殊事件检测记录。")
            return
        values = []
        for col in range(3):
            item = self.special_event_records_table.item(row, col)
            values.append(item.text().strip() if item else "")
        dialog = InspectionFindingDialog(
            title_text="编辑特殊事件检测记录",
            item_code=values[0],
            risk_level=values[1],
            conclusion=values[2],
            parent=self,
        )
        if dialog.exec_() != QDialog.Accepted:
            return
        result = dialog.get_values()
        self._loading_special_event_findings = True
        for col, value in enumerate((result["item_code"], result["risk_level"], result["conclusion"])):
            item = self.special_event_records_table.item(row, col) or QTableWidgetItem("")
            item.setTextAlignment(Qt.AlignCenter)
            item.setText(value)
            self.special_event_records_table.setItem(row, col, item)
        self._loading_special_event_findings = False
        self._save_special_event_findings()

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

            /* 面包屑样式与 ConstructionDocsWidget 保持一致 */
            QFrame#PathBar {
                background-color: #006bb3;
            }
            QLabel#PathIcon {
                background-color: #004a87;
                border-radius: 3px;
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

            /* 文件夹按钮 */
            QToolButton#FolderButton {
                border: none;
                background: transparent;
                font-size: 14pt;
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
                padding: 8px 8px;
                border: 1px solid #d0d7e2;
                font-weight: 500;
                font-size: 14px;
            }
            QTableWidget::item {
                padding: 6px 8px;
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
            QLabel#SectionBanner {
                min-height: 34px;
                padding: 0 18px;
                background-color: #d91f11;
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
                border-radius: 4px;
            }
            QLabel#PeriodicSectionBanner {
                min-height: 34px;
                padding: 0 18px;
                background-color: #0f5ea5;
                color: #ffffff;
                font-size: 14px;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton#OverviewActionButton {
                min-height: 32px;
                padding: 0 16px;
                border: 1px solid #0f5ea5;
                border-radius: 6px;
                background-color: #ffffff;
                color: #0f5ea5;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton#OverviewActionButton:hover {
                background-color: #eaf4ff;
            }
            """
        )
        self._update_breadcrumb_font_scale()

    def _update_breadcrumb_font_scale(self):
        if not hasattr(self, "lbl_home_link"):
            return

        font_size = max(11.0, min(20.0, self.width() * self.breadcrumb_font_ratio - 2.0))
        for widget in (self.lbl_home_link, self.lbl_sep, self.lbl_second):
            font = widget.font()
            font.setPointSizeF(font_size)
            widget.setFont(font)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_breadcrumb_font_scale()
