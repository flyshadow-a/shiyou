# -*- coding: utf-8 -*-
# pages/construction_docs_page.py

import os

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget,
    QLabel,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QMessageBox,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
)
from core.base_page import BasePage
from pages.document_library_widget import DocumentLibraryWidget
from pages.file_management_filter_search_bar import FileManagementFilterSearchBar
from pages.file_management_platforms import (
    apply_platform_defaults_to_fields,
    default_platform,
    sync_platform_dropdowns,
)
from shiyou_db.document_code_parser import OTHER_FILE_CLASS_NAMES, parse_document_code_from_name
from pages.file_management_header import build_platform_description
from services.inspection_business_db_adapter import load_facility_profile, save_facility_profile


class PlatformDescriptionDialog(QDialog):
    def __init__(self, description_text: str, parent=None):
        super().__init__(parent)
        self.setObjectName("PlatformDescriptionDialog")
        self.setWindowTitle("编辑平台描述")
        self.resize(640, 360)
        self.setModal(True)
        self.setStyleSheet(
            """
            QDialog#PlatformDescriptionDialog {
                background-color: #ffffff;
            }
            QDialog#PlatformDescriptionDialog QTextEdit {
                border: 1px solid #d1d5db;
                border-radius: 8px;
                padding: 10px 12px;
                font-size: 12pt;
                color: #1f2937;
                background-color: #ffffff;
            }
            QDialog#PlatformDescriptionDialog QTextEdit:focus {
                border: 1px solid #1677c5;
            }
            QDialog#PlatformDescriptionDialog QPushButton {
                min-height: 34px;
                padding: 0 18px;
                border-radius: 6px;
                font-size: 12pt;
                font-weight: 600;
            }
            QDialog#PlatformDescriptionDialog QPushButton#DialogPrimaryButton {
                border: none;
                background-color: #1677c5;
                color: #ffffff;
            }
            QDialog#PlatformDescriptionDialog QPushButton#DialogPrimaryButton:hover {
                background-color: #2186d4;
            }
            QDialog#PlatformDescriptionDialog QPushButton#DialogSecondaryButton {
                border: 1px solid #1677c5;
                background-color: #ffffff;
                color: #1677c5;
            }
            QDialog#PlatformDescriptionDialog QPushButton#DialogSecondaryButton:hover {
                background-color: #eaf4ff;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.editor = QTextEdit(self)
        self.editor.setPlaceholderText("请输入平台描述")
        self.editor.setPlainText(description_text or "")
        self.editor.setMinimumHeight(220)
        layout.addWidget(self.editor, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        ok_button = buttons.button(QDialogButtonBox.Ok)
        cancel_button = buttons.button(QDialogButtonBox.Cancel)
        ok_button.setText("保存")
        cancel_button.setText("取消")
        ok_button.setObjectName("DialogPrimaryButton")
        cancel_button.setObjectName("DialogSecondaryButton")
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

    _STRUCTURAL_FOLDERS = {
        "SPC": "规格书",
        "RPT": "报告",
        "DWG": "图纸",
        "MAL": "料单",
        "BOD": "设计基础",
    }
    _GENERAL_FOLDERS = {
        "DWG": "图纸",
        "SPC": "规格书",
        "RPT": "报告",
    }
    _STAGE_BY_CODE = {
        "DD": "详细设计",
        "AB": "完工",
        "MD(DD)": "详细设计",
    }

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
        self._initial_profile = dict(profile_defaults)
        apply_platform_defaults_to_fields(fields, profile_defaults)
        self.filter_search_bar = FileManagementFilterSearchBar(fields, self)
        self.dropdown_bar = self.filter_search_bar.dropdown_bar
        self.filter_search_bar.searchRequested.connect(self._search_documents)
        self.main_layout.addWidget(self.filter_search_bar, 0)

        self.content_scroll = QScrollArea(self)
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setFrameShape(QFrame.NoFrame)
        self.content_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.main_layout.addWidget(self.content_scroll, 1)

        content_widget = QWidget(self.content_scroll)
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)
        self.content_scroll.setWidget(content_widget)

        self.docs_widget = DocumentLibraryWidget(
            self._build_document_sections(),
            module_code="doc_man",
            show_description=True,
            upload_path_resolver=self._resolve_design_upload_target,
            parent=content_widget,
        )
        content_layout.addWidget(self.docs_widget)

        # 3) 监听筛选条件变化（保留）
        self.filter_search_bar.valueChanged.connect(self.on_filter_changed)
        self.docs_widget.navigationStateChanged.connect(self._set_dropdown_visible)
        self.docs_widget.descriptionEditRequested.connect(self._edit_platform_description)
        self._sync_platform_ui()

    def _search_documents(self, code: str = "", name: str = ""):
        if not hasattr(self, "docs_widget"):
            return
        self.docs_widget.search_all_documents(code, name)

    def _build_document_sections(self) -> list[dict]:
        structural = [
            ("规格书", "规格书", "详细设计/完工阶段结构专业规格书，支持标准编码自动识别。"),
            ("报告", "报告", "结构专业分析报告、校核报告、检测策略报告等。"),
            ("图纸", "图纸", "结构专业设计图纸，文件名可按 DD-DWG-平台(模块)-ST-图号 自动解析。"),
            ("料单", "材料清单", "结构专业材料清单。"),
            ("设计基础", "设计基础数据", "结构专业设计基础数据。"),
        ]
        general = [
            ("图纸", "图纸", "总体专业图纸，文件名可按 DD-DWG-平台-GE-图号 自动解析。"),
            ("规格书", "规格书", "总体专业规格书。"),
            ("报告", "报告", "总体专业报告。"),
        ]

        sections: list[dict] = []
        structural_categories = [category for _name, category, _hint in structural]
        general_categories = [category for _name, category, _hint in general]
        all_categories = list(
            dict.fromkeys(
                [
                    *structural_categories,
                    *general_categories,
                    "未分类/其他",
                    *OTHER_FILE_CLASS_NAMES,
                    "其他",
                ]
            )
        )
        for stage in ("详细设计", "完工"):
            sections.append(
                {
                    "label": stage,
                    "tree_path": [stage],
                    "path_segments": [stage],
                    "categories": all_categories,
                    "hint": f"{stage}阶段全部设计文件，包含结构、总体及其他专业子目录文件。",
                    "display_profile": "design",
                }
            )
            sections.append(
                {
                    "label": f"{stage} / 结构(ST)",
                    "tree_path": [stage, "结构(ST)"],
                    "path_segments": [stage, "结构(ST)"],
                    "categories": [*structural_categories, "其他"],
                    "hint": f"{stage}阶段结构专业全部文件，包含规格书、报告、图纸、料单和设计基础数据。",
                    "display_profile": "design",
                }
            )
            for name, category, hint in structural:
                sections.append(
                    {
                        "label": f"{stage} / 结构(ST) / {name}",
                        "tree_path": [stage, "结构(ST)", name],
                        "path_segments": [stage, "结构(ST)", name],
                        "categories": [category, "其他"],
                        "hint": hint,
                        "display_profile": "design",
                    }
                )
            sections.append(
                {
                    "label": f"{stage} / 总体(GE)",
                    "tree_path": [stage, "总体(GE)"],
                    "path_segments": [stage, "总体(GE)"],
                    "categories": [*general_categories, "其他"],
                    "hint": f"{stage}阶段总体专业全部文件，包含图纸、规格书和报告。",
                    "display_profile": "design",
                }
            )
            for name, category, hint in general:
                sections.append(
                    {
                        "label": f"{stage} / 总体(GE) / {name}",
                        "tree_path": [stage, "总体(GE)", name],
                        "path_segments": [stage, "总体(GE)", name],
                        "categories": [category, "其他"],
                        "hint": hint,
                        "display_profile": "design",
                    }
                )
            sections.append(
                {
                    "label": f"{stage} / 其他",
                    "tree_path": [stage, "其他"],
                    "path_segments": [stage, "其他"],
                    "categories": ["未分类/其他", *OTHER_FILE_CLASS_NAMES, "其他"],
                    "hint": "无法按标准编码自动归类的文件先放入其他，后续可在表格中手动维护类别。",
                    "display_profile": "design",
                }
            )
        return sections

    def _resolve_design_upload_target(self, item: dict, current_path: list[str], category: str) -> dict:
        meta = dict(item.get("meta") or {})
        if not meta:
            meta = parse_document_code_from_name(os.path.basename(str(item.get("path") or "")))

        stage = self._stage_name_from_meta(meta, current_path)
        discipline = str(meta.get("discipline_code") or "").strip().upper()
        file_class = str(meta.get("file_class_code") or "").strip().upper()
        is_unclassified = str(meta.get("recognition_status") or "").strip() == "unclassified"
        category_name = "" if is_unclassified else str(meta.get("file_class_name") or category or "").strip()

        if discipline == "ST":
            folder = self._STRUCTURAL_FOLDERS.get(file_class)
            if folder:
                return {
                    "path_segments": [stage, "结构(ST)", folder],
                    "category": category_name or folder,
                }

        if discipline == "GE":
            folder = self._GENERAL_FOLDERS.get(file_class)
            if folder:
                return {
                    "path_segments": [stage, "总体(GE)", folder],
                    "category": category_name or folder,
                }

        return {
            "path_segments": [stage, "其他"],
            "category": category_name or "未分类/其他",
        }

    def _stage_name_from_meta(self, meta: dict, current_path: list[str]) -> str:
        stage_code = str(meta.get("design_stage_code") or "").strip().upper()
        if stage_code in self._STAGE_BY_CODE:
            return self._STAGE_BY_CODE[stage_code]
        for part in current_path:
            if part in {"详细设计", "完工"}:
                return part
        return "详细设计"

    def on_filter_changed(self, key: str, value: str):
        self._sync_platform_ui(changed_key=key)

    def _sync_platform_ui(self, changed_key: str | None = None):
        platform = sync_platform_dropdowns(self.dropdown_bar, changed_key=changed_key)
        initial_profile = getattr(self, "_initial_profile", None)
        if (
            changed_key is None
            and isinstance(initial_profile, dict)
            and initial_profile.get("facility_code") == platform["facility_code"]
        ):
            profile = initial_profile
            self._initial_profile = None
        else:
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
        values = self.dropdown_bar.get_all_values()
        values["facility_code"] = profile["facility_code"]
        values["facility_name"] = profile["facility_name"]
        generated_description = build_platform_description(values)
        description_text = profile.get("description_text") or generated_description
        platform_name = values.get("facility_name", "")
        self.docs_widget.set_facility_code(profile["facility_code"])
        self.docs_widget.set_platform_name(platform_name)
        self.docs_widget.set_platform_description(description_text)
        self._refresh_edit_description_button_visibility()
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
        self._refresh_edit_description_button_visibility(show_top_level=visible)

    def _refresh_edit_description_button_visibility(self, show_top_level: bool | None = None):
        if not hasattr(self, "docs_widget"):
            return

        if show_top_level is None:
            show_top_level = True
        has_description = bool(getattr(self.docs_widget, "platform_description", "").strip())
        self.docs_widget.set_description_edit_visible(bool(show_top_level and has_description))
