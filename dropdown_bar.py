# dropdown_bar.py
from typing import List, Dict, Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFontMetrics
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QGridLayout, QLabel, QComboBox, QSizePolicy
)


class DropdownBar(QFrame):
    """
    一排蓝色标题 + 一排白色下拉框，可在各页面复用。
    这版使用 2 行 N 列的 GridLayout，保证“表头”和“下拉框”一一对齐。
    """

    # 任意一个下拉框改变时发信号：key, new_text
    valueChanged = pyqtSignal(str, str)

    def __init__(self, fields: List[Dict], parent=None):
        """
        :param fields: 列表，每个元素:
            {
              "key": "division",          # 唯一键，用于 get/set
              "label": "分公司",          # 表头文字
              "options": ["渤江分公司"],   # 选项列表
              "default": "渤江分公司"      # 可选，默认值
            }
        """
        super().__init__(parent)
        self.setObjectName("DropdownBar")

        # key -> QComboBox
        self._combos: Dict[str, QComboBox] = {}

        self._init_ui(fields)

    # ---------------- UI 构建 ---------------- #
    def _init_ui(self, fields: List[Dict]):
        """使用 2 行 N 列的 GridLayout，0 行放 label，1 行放 combobox。"""
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(1)   # 列之间的细缝
        grid.setVerticalSpacing(0)
        outer_layout.addLayout(grid)

        # 统一样式
        self.setStyleSheet("""
            QFrame#DropdownBar {
                background-color: #0090d0;
            }

            QLabel.DropdownHeader {
                background-color: #0090d0;
                color: #ffffff;
                padding: 7px 6px;
                font-weight: bold;
                font-size: 15px;
                border: none;
            }

            QComboBox {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                min-width: 100px;
                min-height: 32px;
                padding: 4px 6px;
                font-size: 14px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 18px;
            }
        """)

        # 每个 field 一列：上 label，下 combobox
        for col, field in enumerate(fields):
            key: str = field.get("key", "")
            label_text: str = field.get("label", "")
            options: List[str] = field.get("options") or []
            default_value: Optional[str] = field.get("default")
            stretch = max(1, int(field.get("stretch", 1) or 1))

            # ------ 行 0：蓝色表头 ------
            lbl = QLabel(label_text)
            lbl.setObjectName("DropdownHeader")
            lbl.setProperty("class", "DropdownHeader")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            lbl.setMinimumHeight(32)
            grid.addWidget(lbl, 0, col)

            # ------ 行 1：白色下拉框 ------
            combo = QComboBox()
            combo.addItems(options)
            combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            combo.setMinimumHeight(34)

            # 默认选中
            if default_value:
                idx = combo.findText(default_value)
                if idx >= 0:
                    combo.setCurrentIndex(idx)

            # 下拉变化 -> 发射 signal
            if key:
                combo.currentTextChanged.connect(lambda text, k=key, cb=combo: self._on_combo_changed(k, cb, text))

            self._update_combo_display_metrics(combo)
            combo.setToolTip(combo.currentText())

            grid.addWidget(combo, 1, col)
            grid.setColumnStretch(col, stretch)

            if key:
                self._combos[key] = combo

    def _on_combo_changed(self, key: str, combo: QComboBox, text: str):
        combo.setToolTip(text)
        self.valueChanged.emit(key, text)

    def _update_combo_display_metrics(self, combo: QComboBox):
        fm = QFontMetrics(combo.font())
        texts = [combo.itemText(i) for i in range(combo.count())]
        max_px = max((fm.horizontalAdvance(t) for t in texts), default=0)
        max_chars = max((len(t) for t in texts), default=0)

        if max_chars > 0:
            combo.setMinimumContentsLength(min(max(max_chars, 8), 30))
        combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)

        view = combo.view()
        if view is not None and max_px > 0:
            popup_width = max_px + 42
            view.setMinimumWidth(max(view.minimumWidth(), popup_width))

    # ---------------- 对外接口：取值/设值 ---------------- #
    def get_value(self, key: str) -> str:
        """获取某个字段当前选中的文本。"""
        cb = self._combos.get(key)
        if cb is None:
            return ""
        return cb.currentText()

    def set_value(self, key: str, value: str):
        """设置某个字段当前选中项。"""
        cb = self._combos.get(key)
        if cb is None:
            return
        idx = cb.findText(value)
        if idx >= 0:
            cb.setCurrentIndex(idx)

    def get_all_values(self) -> Dict[str, str]:
        """一次性获取全部字段当前的值。"""
        return {k: cb.currentText() for k, cb in self._combos.items()}

    def set_options(self, key: str, options: List[str], default: str = None):
        """更新某个字段的选项列表，并可选设置一个默认值。"""
        cb = self._combos.get(key)
        if cb is None:
            return
        cb.blockSignals(True)
        cb.clear()
        cb.addItems(options)
        if default:
            idx = cb.findText(default)
            if idx >= 0:
                cb.setCurrentIndex(idx)
        self._update_combo_display_metrics(cb)
        cb.setToolTip(cb.currentText())
        cb.blockSignals(False)

    def get_combo(self, key: str) -> Optional[QComboBox]:
        """如果你要自己连信号/改样式，可以拿到底层 QComboBox。"""
        return self._combos.get(key)
