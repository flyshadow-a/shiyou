# dropdown_bar.py
from typing import List, Dict, Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QFontDatabase, QFontMetrics
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QGridLayout, QLabel, QComboBox, QSizePolicy
)


WINDOWS_SONGTI_FONT_CANDIDATES = [
    "SimSun",
    "NSimSun",
    "宋体",
    "Microsoft YaHei UI",
    "Microsoft YaHei",
]


def _pick_windows_compatible_zh_font() -> str:
    """优先宋体，回退到 Win 常见中文字体，兼容 Win10/Win11。"""
    families = {name.lower(): name for name in QFontDatabase().families()}
    for name in WINDOWS_SONGTI_FONT_CANDIDATES:
        hit = families.get(name.lower())
        if hit:
            return hit
    return QFont().defaultFamily()


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

        self._font_family = _pick_windows_compatible_zh_font()
        self._header_font = QFont(self._font_family, 12)
        self._header_font.setBold(True)
        self._combo_font = QFont(self._font_family, 12)
        self._header_min_height = self._calc_control_min_height(self._header_font, base=32, extra=8)
        self._combo_min_height = self._calc_control_min_height(self._combo_font, base=34, extra=10)

        self._init_ui(fields)

    @staticmethod
    def _calc_control_min_height(font: QFont, base: int, extra: int) -> int:
        """按字体动态计算控件高度，避免高 DPI 下被裁切。"""
        fm = QFontMetrics(font)
        return max(base, min(44, fm.height() + extra))

    @staticmethod
    def _parse_stretch(raw_value: object, default: int) -> int:
        if isinstance(raw_value, bool):
            value = int(raw_value)
        elif isinstance(raw_value, (int, float, str)):
            try:
                value = int(raw_value)
            except (TypeError, ValueError):
                value = default
        else:
            value = default
        return max(0, value)

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

            QLabel[class="DropdownHeader"] {
                background-color: #0090d0;
                color: #ffffff;
                padding: 7px 6px;
                font-weight: bold;
                border: none;
            }

            QComboBox {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                min-width: 100px;
                padding: 4px 6px;
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
            expand = bool(field.get("expand", True))
            default_stretch = 1 if expand else 0
            stretch = self._parse_stretch(field.get("stretch", default_stretch), default_stretch)

            # ------ 行 0：蓝色表头 ------
            lbl = QLabel(label_text)
            lbl.setObjectName("DropdownHeader")
            lbl.setProperty("class", "DropdownHeader")
            lbl.setFont(self._header_font)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setSizePolicy(QSizePolicy.Expanding if expand else QSizePolicy.Minimum, QSizePolicy.Fixed)
            lbl.setMinimumHeight(self._header_min_height)
            grid.addWidget(lbl, 0, col)

            # ------ 行 1：白色下拉框 ------
            combo = QComboBox()
            combo.addItems(options)
            combo.setFont(self._combo_font)
            combo.setSizePolicy(QSizePolicy.Expanding if expand else QSizePolicy.Minimum, QSizePolicy.Fixed)
            combo.setMinimumHeight(self._combo_min_height)
            combo.setProperty("compactMode", not expand)

            view = combo.view()
            if view is not None:
                view.setFont(self._combo_font)

            # 默认选中
            if default_value:
                idx = combo.findText(default_value)
                if idx >= 0:
                    combo.setCurrentIndex(idx)

            # 下拉变化 -> 发射 signal
            if key:
                combo.currentTextChanged.connect(lambda text, k=key, cb=combo: self._on_combo_changed(k, cb, text))

            self._update_combo_display_metrics(combo, compact=(not expand))
            combo.setToolTip(combo.currentText())

            grid.addWidget(combo, 1, col)
            grid.setColumnStretch(col, stretch)

            if key:
                self._combos[key] = combo

    def _on_combo_changed(self, key: str, combo: QComboBox, text: str):
        combo.setToolTip(text)
        self.valueChanged.emit(key, text)

    def _update_combo_display_metrics(self, combo: QComboBox, compact: bool = False):
        fm = QFontMetrics(combo.font())
        texts = [combo.itemText(i) for i in range(combo.count())]
        max_px = max((fm.horizontalAdvance(t) for t in texts), default=0)
        max_chars = max((len(t) for t in texts), default=0)

        if max_chars > 0:
            max_len = 24 if compact else 30
            combo.setMinimumContentsLength(min(max(max_chars, 8), max_len))
        combo.setSizeAdjustPolicy(
            QComboBox.AdjustToContents if compact else QComboBox.AdjustToMinimumContentsLengthWithIcon
        )

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

    def set_options(self, key: str, options: List[str], default: str = ""):
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
        compact = bool(cb.property("compactMode"))
        self._update_combo_display_metrics(cb, compact=compact)
        cb.setToolTip(cb.currentText())
        cb.blockSignals(False)

    def get_combo(self, key: str) -> Optional[QComboBox]:
        """如果你要自己连信号/改样式，可以拿到底层 QComboBox。"""
        return self._combos.get(key)
