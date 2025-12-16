# dropdown_bar.py
from typing import List, Dict, Optional

from PyQt5.QtCore import Qt, pyqtSignal
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
                padding: 4px 6px;
                font-weight: bold;
                border: none;
            }

            QComboBox {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                min-width: 90px;
                padding: 2px 4px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 16px;
            }
        """)

        # 每个 field 一列：上 label，下 combobox
        for col, field in enumerate(fields):
            key: str = field.get("key", "")
            label_text: str = field.get("label", "")
            options: List[str] = field.get("options") or []
            default_value: Optional[str] = field.get("default")

            # ------ 行 0：蓝色表头 ------
            lbl = QLabel(label_text)
            lbl.setObjectName("DropdownHeader")
            lbl.setProperty("class", "DropdownHeader")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            grid.addWidget(lbl, 0, col)

            # ------ 行 1：白色下拉框 ------
            combo = QComboBox()
            combo.addItems(options)
            combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            # 默认选中
            if default_value:
                idx = combo.findText(default_value)
                if idx >= 0:
                    combo.setCurrentIndex(idx)

            # 下拉变化 -> 发射 signal
            if key:
                combo.currentTextChanged.connect(
                    lambda text, k=key: self.valueChanged.emit(k, text)
                )

            grid.addWidget(combo, 1, col)
            grid.setColumnStretch(col, 1)  # 所有列等比分配宽度

            if key:
                self._combos[key] = combo

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
        cb.blockSignals(False)

    def get_combo(self, key: str) -> Optional[QComboBox]:
        """如果你要自己连信号/改样式，可以拿到底层 QComboBox。"""
        return self._combos.get(key)
