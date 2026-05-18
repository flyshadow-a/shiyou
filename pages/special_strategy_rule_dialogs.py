from __future__ import annotations

from typing import Any, Iterable, Sequence

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


RULE_MODE_JOINT_CLASSIFICATION = "joint_classification"
RULE_MODE_MEMBER_CLASSIFICATION = "member_classification"
RULE_MODE_MEMBER_EXCLUSION = "member_exclusion"
RULE_MODE_JOINT_EXCLUSION = "joint_exclusion"

_PATTERN_LENGTH = 4
_ALLOWED_PATTERN_CHARS = set("*0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def normalize_code_pattern(value: Any) -> str:
    text = str(value or "").strip().upper()
    chars = [ch for ch in text if ch in _ALLOWED_PATTERN_CHARS]
    chars = chars[:_PATTERN_LENGTH]
    while len(chars) < _PATTERN_LENGTH:
        chars.append("*")
    return "".join(chars)


def is_active_code_pattern(pattern: Any) -> bool:
    return normalize_code_pattern(pattern) != "****"


def code_matches_pattern(code: Any, pattern: Any) -> bool:
    code_text = str(code or "").strip().upper()
    pattern_text = normalize_code_pattern(pattern)
    if len(code_text) != _PATTERN_LENGTH or not is_active_code_pattern(pattern_text):
        return False
    return all(p == "*" or p == c for c, p in zip(code_text, pattern_text))


def member_matches_pattern(joint_a: Any, joint_b: Any, pattern: dict[str, Any]) -> bool:
    a_pattern = normalize_code_pattern(pattern.get("a"))
    b_pattern = normalize_code_pattern(pattern.get("b"))
    if not (is_active_code_pattern(a_pattern) or is_active_code_pattern(b_pattern)):
        return False
    forward = code_matches_pattern(joint_a, a_pattern) and code_matches_pattern(joint_b, b_pattern)
    reverse = code_matches_pattern(joint_a, b_pattern) and code_matches_pattern(joint_b, a_pattern)
    return forward or reverse


def normalize_rule_overrides(raw: Any) -> dict[str, Any]:
    payload = raw if isinstance(raw, dict) else {}

    def _node_patterns(items: Any) -> list[str]:
        out: list[str] = []
        for item in items or []:
            pattern = normalize_code_pattern(item)
            if is_active_code_pattern(pattern) and pattern not in out:
                out.append(pattern)
        return out

    def _member_patterns(items: Any) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for item in items or []:
            if not isinstance(item, dict):
                continue
            a_pattern = normalize_code_pattern(item.get("a"))
            b_pattern = normalize_code_pattern(item.get("b"))
            if not (is_active_code_pattern(a_pattern) or is_active_code_pattern(b_pattern)):
                continue
            key = tuple(sorted((a_pattern, b_pattern)))
            if key in seen:
                continue
            seen.add(key)
            out.append({"a": a_pattern, "b": b_pattern})
        return out

    joint_cls_raw = payload.get("joint_classification") or {}
    member_cls_raw = payload.get("member_classification") or {}
    return {
        "joint_classification": {
            "leg_joint": _node_patterns(joint_cls_raw.get("leg_joint")),
            "x_joint": _node_patterns(joint_cls_raw.get("x_joint")),
        },
        "member_classification": {
            "leg": _member_patterns(member_cls_raw.get("leg")),
            "x_brace": _member_patterns(member_cls_raw.get("x_brace")),
        },
        "member_exclusions": _member_patterns(payload.get("member_exclusions")),
        "joint_exclusions": _node_patterns(payload.get("joint_exclusions")),
    }


class SpecialStrategyRuleDialog(QDialog):
    _MODE_META = {
        RULE_MODE_JOINT_CLASSIFICATION: {
            "title": "新增节点分类修正",
            "hint": "主腿节点与 X 撑节点分别录入。每 4 个字符组成一条编号规则，全 * 行仅作占位，不参与匹配。",
        },
        RULE_MODE_MEMBER_CLASSIFICATION: {
            "title": "新增构件分类修正",
            "hint": "主腿构件与 X 撑构件分别录入。构件按无向匹配，A-B 与 B-A 视为同一构件。",
        },
        RULE_MODE_MEMBER_EXCLUSION: {
            "title": "剔除不考虑构件修正",
            "hint": "按节点 A / 节点 B 成对录入要剔除的构件规则。全 * 行仅作占位，不参与匹配。",
        },
        RULE_MODE_JOINT_EXCLUSION: {
            "title": "剔除不考虑节点修正",
            "hint": "录入要从后续节点预测与节点策略结果中剔除的节点编号规则。",
        },
    }

    def __init__(
        self,
        mode: str,
        initial_rules: dict[str, Any] | None,
        *,
        joint_ids: Sequence[str] | None = None,
        member_pairs: Sequence[tuple[str, str]] | None = None,
        preview_available: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)
        if mode not in self._MODE_META:
            raise ValueError(f"unsupported rule dialog mode: {mode}")

        self.mode = mode
        self._rules = normalize_rule_overrides(initial_rules)
        self._joint_ids = [str(x or "").strip() for x in (joint_ids or []) if str(x or "").strip()]
        self._member_pairs = [
            (str(a or "").strip(), str(b or "").strip())
            for a, b in (member_pairs or [])
            if str(a or "").strip() and str(b or "").strip()
        ]
        self._preview_available = bool(preview_available)
        self._updating = False
        self._result_rules: dict[str, Any] | None = None

        meta = self._MODE_META[mode]
        self.setWindowTitle(str(meta["title"]))
        self.setObjectName("SpecialStrategyRuleDialog")
        self.setModal(True)
        self.setStyleSheet(self._dialog_style())
        self.resize(760, 690 if mode == RULE_MODE_MEMBER_CLASSIFICATION else 500)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(14)

        title = QLabel(str(meta["title"]), self)
        title.setObjectName("RuleDialogTitle")
        root.addWidget(title)

        hint = QLabel(str(meta["hint"]), self)
        hint.setWordWrap(True)
        hint.setObjectName("RuleDialogHint")
        root.addWidget(hint)

        if mode == RULE_MODE_JOINT_CLASSIFICATION:
            self._build_joint_classification_ui(root)
        elif mode == RULE_MODE_MEMBER_CLASSIFICATION:
            self._build_member_classification_ui(root)
        elif mode == RULE_MODE_MEMBER_EXCLUSION:
            self._build_member_exclusion_ui(root)
        else:
            self._build_joint_exclusion_ui(root)

        self.preview_label = QLabel(self)
        self.preview_label.setWordWrap(True)
        self.preview_label.setObjectName("RulePreviewLabel")
        root.addWidget(self.preview_label)

        note = QLabel("输入说明：支持字母、数字和 *；规则优先级为 剔除规则 > 人工分类修正 > VBA 自动分类 > Other。", self)
        note.setWordWrap(True)
        note.setObjectName("RuleDialogNote")
        root.addWidget(note)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.cancel_button = QPushButton("取消", self)
        self.cancel_button.setObjectName("RuleSecondaryButton")
        self.cancel_button.clicked.connect(self.reject)
        button_row.addWidget(self.cancel_button)
        self.confirm_button = QPushButton("确认", self)
        self.confirm_button.setObjectName("RulePrimaryButton")
        self.confirm_button.clicked.connect(self._on_accept)
        button_row.addWidget(self.confirm_button)
        root.addLayout(button_row)

        self._refresh_preview()

    @property
    def result_rules(self) -> dict[str, Any]:
        return self._result_rules or normalize_rule_overrides(self._rules)

    def _dialog_style(self) -> str:
        return """
            QDialog#SpecialStrategyRuleDialog {
                background-color: #f6f8fb;
            }
            QLabel#RuleDialogTitle {
                color: #172033;
                font-size: 18pt;
                font-weight: 700;
            }
            QLabel#RuleDialogHint {
                color: #475569;
                font-size: 11pt;
                line-height: 1.35;
            }
            QLabel#RuleSectionTitle {
                color: #1f2937;
                font-size: 13pt;
                font-weight: 700;
            }
            QLabel#RulePreviewLabel {
                color: #0f172a;
                background-color: #edf5ff;
                border: 1px solid #cfe3fb;
                border-radius: 8px;
                padding: 9px 12px;
                font-size: 11pt;
            }
            QLabel#RuleDialogNote {
                color: #64748b;
                font-size: 10pt;
            }
            QFrame#RuleSectionFrame {
                background-color: #ffffff;
                border: 1px solid #dbe4f0;
                border-radius: 10px;
            }
            QPushButton#RuleAddButton {
                min-width: 78px;
                min-height: 28px;
                padding: 0 10px;
                color: #1677c5;
                background-color: #ffffff;
                border: 1px solid #b8d7ef;
                border-radius: 6px;
                font-size: 11pt;
            }
            QPushButton#RuleAddButton:hover {
                background-color: #edf6ff;
            }
            QPushButton#RulePrimaryButton,
            QPushButton#RuleSecondaryButton {
                min-width: 88px;
                min-height: 34px;
                padding: 0 16px;
                border-radius: 6px;
                font-size: 12pt;
                font-weight: 600;
            }
            QPushButton#RulePrimaryButton {
                color: #ffffff;
                background-color: #1677c5;
                border: none;
            }
            QPushButton#RulePrimaryButton:hover {
                background-color: #2186d4;
            }
            QPushButton#RuleSecondaryButton {
                color: #1677c5;
                background-color: #ffffff;
                border: 1px solid #1677c5;
            }
            QPushButton#RuleSecondaryButton:hover {
                background-color: #edf6ff;
            }
        """

    def _table_style(self) -> str:
        return """
            QTableWidget {
                background: #ffffff;
                gridline-color: #d4deeb;
                border: 1px solid #ccd8e6;
                border-radius: 8px;
                font-size: 14pt;
                selection-background-color: #dbeafe;
                selection-color: #111827;
            }
            QTableWidget::item {
                padding: 2px;
            }
        """

    def _new_pattern_table(self, columns: int, row_count: int) -> QTableWidget:
        table = QTableWidget(row_count, columns, self)
        table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
        )
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.horizontalHeader().setVisible(False)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setDefaultSectionSize(56)
        table.verticalHeader().setDefaultSectionSize(40)
        table.setStyleSheet(self._table_style())
        table.itemChanged.connect(lambda item, current=table: self._on_item_changed(current, item))
        self._fit_table_height(table)
        return table

    def _readonly_item(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        item.setBackground(QColor("#eef5fc"))
        item.setForeground(QColor("#1f2937"))
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        return item

    def _editable_item(self, text: str = "*") -> QTableWidgetItem:
        item = QTableWidgetItem(normalize_code_pattern(text)[0])
        item.setTextAlignment(Qt.AlignCenter)
        return item

    def _fit_table_height(self, table: QTableWidget) -> None:
        row_height = table.verticalHeader().defaultSectionSize()
        table.setFixedHeight(table.rowCount() * row_height + 4)

    def _set_preview_color(self, color: str) -> None:
        self.preview_label.setStyleSheet(f"color: {color};")

    def _set_pattern_row(self, table: QTableWidget, row: int, start_col: int, pattern: str) -> None:
        normalized = normalize_code_pattern(pattern)
        for offset, ch in enumerate(normalized):
            table.setItem(row, start_col + offset, self._editable_item(ch))

    def _append_empty_member_row(self, table: QTableWidget) -> None:
        row = table.rowCount()
        table.insertRow(row)
        for col in range(8):
            table.setItem(row, col, self._editable_item("*"))
        self._fit_table_height(table)
        self._refresh_preview()

    def _append_empty_node_row(self, table: QTableWidget, *, dual: bool) -> None:
        row = table.rowCount()
        table.insertRow(row)
        for col in range(8 if dual else 4):
            table.setItem(row, col, self._editable_item("*"))
        self._fit_table_height(table)
        self._refresh_preview()

    def _add_row_button(self, text: str, callback) -> QPushButton:
        button = QPushButton(text, self)
        button.clicked.connect(callback)
        button.setObjectName("RuleAddButton")
        return button

    def _new_section(self, title: str = "", add_callback=None) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame(self)
        frame.setObjectName("RuleSectionFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)

        if title or add_callback is not None:
            header_row = QHBoxLayout()
            header_row.setContentsMargins(0, 0, 0, 0)
            if title:
                title_label = QLabel(title, frame)
                title_label.setObjectName("RuleSectionTitle")
                header_row.addWidget(title_label)
            header_row.addStretch(1)
            if add_callback is not None:
                header_row.addWidget(self._add_row_button("新增一行", add_callback))
            layout.addLayout(header_row)

        return frame, layout

    def _build_joint_classification_ui(self, root: QVBoxLayout) -> None:
        leg_rules = list(self._rules["joint_classification"]["leg_joint"])
        x_rules = list(self._rules["joint_classification"]["x_joint"])
        data_rows = max(3, len(leg_rules), len(x_rules))
        table = self._new_pattern_table(8, data_rows + 1)
        table.setSpan(0, 0, 1, 4)
        table.setSpan(0, 4, 1, 4)
        table.setItem(0, 0, self._readonly_item("主腿节点编号"))
        table.setItem(0, 4, self._readonly_item("X撑节点编号"))
        for idx in range(data_rows):
            self._set_pattern_row(table, idx + 1, 0, leg_rules[idx] if idx < len(leg_rules) else "****")
            self._set_pattern_row(table, idx + 1, 4, x_rules[idx] if idx < len(x_rules) else "****")
        self.joint_classification_table = table
        frame, layout = self._new_section(
            add_callback=lambda: self._append_empty_node_row(self.joint_classification_table, dual=True),
        )
        layout.addWidget(table)
        root.addWidget(frame)

    def _build_member_table_section(
        self,
        root: QVBoxLayout,
        *,
        title: str,
        patterns: Sequence[dict[str, str]],
        attr_name: str,
    ) -> None:
        data_rows = max(3, len(patterns))
        table = self._new_pattern_table(8, data_rows + 1)
        table.setSpan(0, 0, 1, 4)
        table.setSpan(0, 4, 1, 4)
        table.setItem(0, 0, self._readonly_item("节点A编号"))
        table.setItem(0, 4, self._readonly_item("节点B编号"))
        for idx in range(data_rows):
            pattern = patterns[idx] if idx < len(patterns) else {"a": "****", "b": "****"}
            self._set_pattern_row(table, idx + 1, 0, str(pattern.get("a", "****")))
            self._set_pattern_row(table, idx + 1, 4, str(pattern.get("b", "****")))
        setattr(self, attr_name, table)
        frame, layout = self._new_section(
            title,
            add_callback=lambda current=table: self._append_empty_member_row(current),
        )
        layout.addWidget(table)
        root.addWidget(frame)

    def _build_member_classification_ui(self, root: QVBoxLayout) -> None:
        self._build_member_table_section(
            root,
            title="主腿构件",
            patterns=self._rules["member_classification"]["leg"],
            attr_name="leg_member_table",
        )
        self._build_member_table_section(
            root,
            title="X撑构件",
            patterns=self._rules["member_classification"]["x_brace"],
            attr_name="x_member_table",
        )

    def _build_member_exclusion_ui(self, root: QVBoxLayout) -> None:
        self._build_member_table_section(
            root,
            title="",
            patterns=self._rules["member_exclusions"],
            attr_name="member_exclusion_table",
        )

    def _build_joint_exclusion_ui(self, root: QVBoxLayout) -> None:
        rules = list(self._rules["joint_exclusions"])
        data_rows = max(3, len(rules))
        table = self._new_pattern_table(4, data_rows + 1)
        table.setSpan(0, 0, 1, 4)
        table.setItem(0, 0, self._readonly_item("节点编号"))
        for idx in range(data_rows):
            self._set_pattern_row(table, idx + 1, 0, rules[idx] if idx < len(rules) else "****")
        self.joint_exclusion_table = table
        frame, layout = self._new_section(
            add_callback=lambda: self._append_empty_node_row(self.joint_exclusion_table, dual=False),
        )
        layout.addWidget(table)
        root.addWidget(frame)

    def _on_item_changed(self, table: QTableWidget, item: QTableWidgetItem) -> None:
        if self._updating or item.row() == 0 or not hasattr(self, "preview_label"):
            return
        self._updating = True
        try:
            text = str(item.text() or "").strip().upper()
            ch = next((char for char in text if char in _ALLOWED_PATTERN_CHARS), "*")
            item.setText(ch)
            item.setTextAlignment(Qt.AlignCenter)
        finally:
            self._updating = False
        self._refresh_preview()

    def _row_pattern(self, table: QTableWidget, row: int, start_col: int) -> str:
        chars: list[str] = []
        for col in range(start_col, start_col + 4):
            item = table.item(row, col)
            chars.append(str(item.text() if item is not None else "*").strip().upper()[:1] or "*")
        return normalize_code_pattern("".join(chars))

    def _collect_joint_classification_rules(self) -> tuple[list[str], list[str]]:
        leg_rules: list[str] = []
        x_rules: list[str] = []
        for row in range(1, self.joint_classification_table.rowCount()):
            leg = self._row_pattern(self.joint_classification_table, row, 0)
            x_joint = self._row_pattern(self.joint_classification_table, row, 4)
            if is_active_code_pattern(leg) and leg not in leg_rules:
                leg_rules.append(leg)
            if is_active_code_pattern(x_joint) and x_joint not in x_rules:
                x_rules.append(x_joint)
        return leg_rules, x_rules

    def _collect_member_table_rules(self, table: QTableWidget) -> list[dict[str, str]]:
        rules: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for row in range(1, table.rowCount()):
            a_pattern = self._row_pattern(table, row, 0)
            b_pattern = self._row_pattern(table, row, 4)
            if not (is_active_code_pattern(a_pattern) or is_active_code_pattern(b_pattern)):
                continue
            key = tuple(sorted((a_pattern, b_pattern)))
            if key in seen:
                continue
            seen.add(key)
            rules.append({"a": a_pattern, "b": b_pattern})
        return rules

    def _collect_joint_exclusion_rules(self) -> list[str]:
        rules: list[str] = []
        for row in range(1, self.joint_exclusion_table.rowCount()):
            pattern = self._row_pattern(self.joint_exclusion_table, row, 0)
            if is_active_code_pattern(pattern) and pattern not in rules:
                rules.append(pattern)
        return rules

    def _rules_from_tables(self) -> dict[str, Any]:
        rules = normalize_rule_overrides(self._rules)
        if self.mode == RULE_MODE_JOINT_CLASSIFICATION:
            leg_rules, x_rules = self._collect_joint_classification_rules()
            rules["joint_classification"] = {
                "leg_joint": leg_rules,
                "x_joint": x_rules,
            }
        elif self.mode == RULE_MODE_MEMBER_CLASSIFICATION:
            rules["member_classification"] = {
                "leg": self._collect_member_table_rules(self.leg_member_table),
                "x_brace": self._collect_member_table_rules(self.x_member_table),
            }
        elif self.mode == RULE_MODE_MEMBER_EXCLUSION:
            rules["member_exclusions"] = self._collect_member_table_rules(self.member_exclusion_table)
        else:
            rules["joint_exclusions"] = self._collect_joint_exclusion_rules()
        return normalize_rule_overrides(rules)

    def _matched_joint_ids(self, patterns: Iterable[str]) -> set[str]:
        pattern_list = list(patterns)
        return {
            joint
            for joint in self._joint_ids
            if any(code_matches_pattern(joint, pattern) for pattern in pattern_list)
        }

    def _matched_member_pairs(self, patterns: Iterable[dict[str, str]]) -> set[tuple[str, str]]:
        pattern_list = list(patterns)
        out: set[tuple[str, str]] = set()
        for joint_a, joint_b in self._member_pairs:
            if any(member_matches_pattern(joint_a, joint_b, pattern) for pattern in pattern_list):
                out.add(tuple(sorted((joint_a, joint_b))))
        return out

    def _refresh_preview(self) -> None:
        rules = self._rules_from_tables()
        if not self._preview_available:
            self.preview_label.setText("命中数量预览：当前未读取到结构模型，暂无法预览。")
            self._set_preview_color("#b45309")
            return

        if self.mode == RULE_MODE_JOINT_CLASSIFICATION:
            leg_hits = self._matched_joint_ids(rules["joint_classification"]["leg_joint"])
            x_hits = self._matched_joint_ids(rules["joint_classification"]["x_joint"])
            conflicts = leg_hits & x_hits
            self.preview_label.setText(
                f"命中数量预览：主腿节点 {len(leg_hits)}，X 撑节点 {len(x_hits)}，冲突 {len(conflicts)}。"
            )
            color = "#b91c1c" if conflicts else "#0f172a"
        elif self.mode == RULE_MODE_MEMBER_CLASSIFICATION:
            leg_hits = self._matched_member_pairs(rules["member_classification"]["leg"])
            x_hits = self._matched_member_pairs(rules["member_classification"]["x_brace"])
            conflicts = leg_hits & x_hits
            self.preview_label.setText(
                f"命中数量预览：主腿构件 {len(leg_hits)}，X 撑构件 {len(x_hits)}，冲突 {len(conflicts)}。"
            )
            color = "#b91c1c" if conflicts else "#0f172a"
        elif self.mode == RULE_MODE_MEMBER_EXCLUSION:
            hits = self._matched_member_pairs(rules["member_exclusions"])
            self.preview_label.setText(f"命中数量预览：剔除构件 {len(hits)}。")
            color = "#0f172a"
        else:
            hits = self._matched_joint_ids(rules["joint_exclusions"])
            self.preview_label.setText(f"命中数量预览：剔除节点 {len(hits)}。")
            color = "#0f172a"
        self._set_preview_color(color)

    def _on_accept(self) -> None:
        rules = self._rules_from_tables()
        if self.mode == RULE_MODE_JOINT_CLASSIFICATION:
            leg_hits = self._matched_joint_ids(rules["joint_classification"]["leg_joint"])
            x_hits = self._matched_joint_ids(rules["joint_classification"]["x_joint"])
            conflict_count = len(leg_hits & x_hits)
        elif self.mode == RULE_MODE_MEMBER_CLASSIFICATION:
            leg_hits = self._matched_member_pairs(rules["member_classification"]["leg"])
            x_hits = self._matched_member_pairs(rules["member_classification"]["x_brace"])
            conflict_count = len(leg_hits & x_hits)
        else:
            conflict_count = 0

        if conflict_count > 0:
            reply = QMessageBox.question(
                self,
                "规则冲突确认",
                f"当前规则存在 {conflict_count} 条分类冲突，系统将按“主腿优先于 X 撑”处理。\n仍要继续吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        self._result_rules = rules
        self.accept()
