# -*- coding: utf-8 -*-
# pages/construction_docs_page.py

from PyQt5.QtWidgets import (
    QWidget,
    QLabel,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)
from base_page import BasePage
from dropdown_bar import DropdownBar
from pages.construction_docs_widget import ConstructionDocsWidget
from pages.file_management_platforms import default_platform, sync_platform_dropdowns
from pages.file_management_header import build_platform_description
from inspection_business_db_adapter import load_facility_profile, save_facility_profile


class PlatformDescriptionDialog(QDialog):
    def __init__(self, description_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑平台描述")
        self.resize(640, 360)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.editor = QTextEdit(self)
        self.editor.setPlaceholderText("请输入平台描述")
        self.editor.setPlainText(description_text or "")
        layout.addWidget(self.editor, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.button(QDialogButtonBox.Ok).setText("保存")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_value(self) -> str:
        return self.editor.toPlainText().strip()


class ConstructionDocsPage(BasePage):
    """
    建设阶段完工文件 页面：
    - 上方：可复用的条件筛选下拉条（DropdownBar）
    - 下方：建设阶段完工文件内容区域（ConstructionDocsWidget）
    """

    def __init__(self, parent=None):
        # ✅ 1) 传空标题：避免 BasePage 顶部显示“建设阶段完工文件”
        super().__init__("", parent)
        self._build_ui()

        # ✅ 2) 兜底：如果 BasePage 仍然有标题 QLabel，就把它隐藏
        self._hide_base_title_if_any()

    def _hide_base_title_if_any(self):
        """
        兼容不同 BasePage 写法：尽量把顶部标题控件隐藏掉
        （不会影响其它控件）
        """
        # 常见写法：BasePage 里有某个 label 成员
        for attr in ("title_label", "lbl_title", "label_title", "page_title_label"):
            w = getattr(self, attr, None)
            if isinstance(w, QLabel):
                w.hide()

        # 兜底：如果 BasePage 给标题设置了 objectName，也可能通过 findChild 找到
        for obj_name in ("PageTitle", "pageTitle", "titleLabel", "lblTitle"):
            w = self.findChild(QLabel, obj_name)
            if w:
                w.hide()

    def _build_ui(self):
        # 0) 页面整体间距（保持你原来的逻辑即可）
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(8)

        # 1) 顶部筛选下拉条（可复用组件）
        fields = [
            {"key": "division",      "label": "分公司",   "options": ["渤江分公司"]},
            {"key": "company",       "label": "作业公司", "options": ["文昌油田群作业公司"]},
            {"key": "field",         "label": "油气田",   "options": ["文昌19-1油田"]},
            {"key": "facility_code", "label": "设施编码", "options": ["WC19-1WHPC"]},
            {"key": "facility_name", "label": "设施名称", "options": ["文昌19-1WHPC井口平台"]},
            {"key": "facility_type", "label": "设施类型", "options": ["平台"]},
            {"key": "category",      "label": "分类",     "options": ["井口平台"]},
            {"key": "start_time",    "label": "投产时间", "options": ["2013-07-15"]},
            {"key": "design_years",  "label": "设计年限", "options": ["15"]},
        ]

        platform_defaults = default_platform()
        profile_defaults = load_facility_profile(
            platform_defaults["facility_code"],
            defaults={
                "branch": platform_defaults["branch"],
                "op_company": platform_defaults["op_company"],
                "oilfield": platform_defaults["oilfield"],
                "facility_code": platform_defaults["facility_code"],
                "facility_name": platform_defaults["facility_name"],
                "facility_type": platform_defaults["facility_type"],
                "category": platform_defaults["category"],
                "start_time": platform_defaults["start_time"],
                "design_life": platform_defaults["design_life"],
            },
        )
        field_map = {item["key"]: item for item in fields}
        field_map["division"]["options"] = [profile_defaults["branch"]]
        field_map["division"]["default"] = profile_defaults["branch"]
        field_map["company"]["options"] = [profile_defaults["op_company"]]
        field_map["company"]["default"] = profile_defaults["op_company"]
        field_map["field"]["options"] = [profile_defaults["oilfield"]]
        field_map["field"]["default"] = profile_defaults["oilfield"]
        field_map["facility_code"]["options"] = ["WC19-1D", "WC9-7"]
        field_map["facility_code"]["default"] = profile_defaults["facility_code"]
        field_map["facility_name"]["options"] = ["WC19-1D平台", "WC9-7平台"]
        field_map["facility_name"]["default"] = profile_defaults["facility_name"]
        field_map["facility_type"]["options"] = [profile_defaults["facility_type"]]
        field_map["facility_type"]["default"] = profile_defaults["facility_type"]
        field_map["category"]["options"] = [profile_defaults["category"]]
        field_map["category"]["default"] = profile_defaults["category"]
        field_map["start_time"]["options"] = [profile_defaults["start_time"]]
        field_map["start_time"]["default"] = profile_defaults["start_time"]
        field_map["design_years"]["options"] = [profile_defaults["design_life"]]
        field_map["design_years"]["default"] = profile_defaults["design_life"]
        self.dropdown_bar = DropdownBar(fields, self)
        self.main_layout.addWidget(self.dropdown_bar, 0)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.addStretch()
        self.btn_edit_description = QPushButton("编辑平台描述", self)
        self.btn_edit_description.clicked.connect(self._edit_platform_description)
        action_row.addWidget(self.btn_edit_description)
        self.btn_reset_description = QPushButton("恢复默认描述", self)
        self.btn_reset_description.clicked.connect(self._reset_platform_description)
        action_row.addWidget(self.btn_reset_description)
        self.main_layout.addLayout(action_row)

        # ✅ 2) 关键：不要再额外包一层 HomeCard/HomeHeaderBar
        #    直接使用 ConstructionDocsWidget 自己那套“首页 + 文件夹UI”
        self.docs_widget = ConstructionDocsWidget(self, show_platform_description=True)
        self.main_layout.addWidget(self.docs_widget, 1)

        # 3) 监听筛选条件变化（保留）
        self.dropdown_bar.valueChanged.connect(self.on_filter_changed)
        self.docs_widget.navigationStateChanged.connect(self._set_dropdown_visible)
        self._sync_platform_ui()

    def on_filter_changed(self, key: str, value: str):
        print(f"[ConstructionDocsPage] filter changed: {key} -> {value}")
        self._sync_platform_ui(changed_key=key)

    def _sync_platform_ui(self, changed_key: str | None = None):
        platform = sync_platform_dropdowns(self.dropdown_bar, changed_key=changed_key)
        profile = load_facility_profile(
            platform["facility_code"],
            defaults={
                "branch": platform["branch"],
                "op_company": platform["op_company"],
                "oilfield": platform["oilfield"],
                "facility_code": platform["facility_code"],
                "facility_name": platform["facility_name"],
                "facility_type": platform["facility_type"],
                "category": platform["category"],
                "start_time": platform["start_time"],
                "design_life": platform["design_life"],
            },
        )
        self.dropdown_bar.set_options("division", [profile["branch"]], profile["branch"])
        self.dropdown_bar.set_options("company", [profile["op_company"]], profile["op_company"])
        self.dropdown_bar.set_options("field", [profile["oilfield"]], profile["oilfield"])
        self.dropdown_bar.set_options("facility_type", [profile["facility_type"]], profile["facility_type"])
        self.dropdown_bar.set_options("category", [profile["category"]], profile["category"])
        self.dropdown_bar.set_options("start_time", [profile["start_time"]], profile["start_time"])
        self.dropdown_bar.set_options("design_years", [profile["design_life"]], profile["design_life"])
        values = self.dropdown_bar.get_all_values()
        values["facility_code"] = profile["facility_code"]
        values["facility_name"] = profile["facility_name"]
        generated_description = build_platform_description(values)
        description_text = profile.get("description_text") or generated_description
        save_facility_profile(
            profile["facility_code"],
            {
                "facility_name": values.get("facility_name"),
                "branch": values.get("division"),
                "op_company": values.get("company"),
                "oilfield": values.get("field"),
                "facility_type": values.get("facility_type"),
                "category": values.get("category"),
                "start_time": values.get("start_time"),
                "design_life": values.get("design_years"),
                "description_text": description_text,
            },
        )
        platform_name = values.get("facility_name", "")
        self.docs_widget.set_facility_code(profile["facility_code"])
        self.docs_widget.set_platform_name(platform_name)
        self.docs_widget.set_platform_description(description_text)
        window = self.window()
        if hasattr(window, "set_current_platform_name"):
            window.set_current_platform_name(platform_name)

    def _save_current_profile(self, *, description_text: str | None = None):
        values = self.dropdown_bar.get_all_values()
        facility_code = values.get("facility_code") or default_platform()["facility_code"]
        if description_text is None:
            description_text = build_platform_description(values)
        save_facility_profile(
            facility_code,
            {
                "facility_name": values.get("facility_name"),
                "branch": values.get("division"),
                "op_company": values.get("company"),
                "oilfield": values.get("field"),
                "facility_type": values.get("facility_type"),
                "category": values.get("category"),
                "start_time": values.get("start_time"),
                "design_life": values.get("design_years"),
                "description_text": description_text,
            },
        )
        self.docs_widget.set_platform_description(description_text)

    def _edit_platform_description(self):
        values = self.dropdown_bar.get_all_values()
        profile = load_facility_profile(values.get("facility_code") or default_platform()["facility_code"])
        initial = profile.get("description_text") or build_platform_description(values)
        dialog = PlatformDescriptionDialog(initial, self)
        if dialog.exec_() != QDialog.Accepted:
            return
        text = dialog.get_value()
        if not text:
            QMessageBox.information(self, "提示", "平台描述不能为空。")
            return
        self._save_current_profile(description_text=text)

    def _reset_platform_description(self):
        values = self.dropdown_bar.get_all_values()
        generated = build_platform_description(values)
        self._save_current_profile(description_text=generated)
        QMessageBox.information(self, "提示", "已恢复默认平台描述。")

    def get_current_platform_name(self):
        return self.dropdown_bar.get_value("facility_name")

    def _set_dropdown_visible(self, visible: bool):
        self.dropdown_bar.setVisible(visible)
        self.dropdown_bar.setFixedHeight(self.dropdown_bar.sizeHint().height() if visible else 0)
