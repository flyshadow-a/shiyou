# -*- coding: utf-8 -*-
# hover_tip_table.py
"""
可复用组件：HoverTipTable
- 仅当单元格文本在当前列宽下被截断时，鼠标悬停显示完整内容 Tooltip
"""

from PyQt5.QtCore import QEvent
from PyQt5.QtGui import QFontMetrics
from PyQt5.QtWidgets import QTableWidget, QToolTip


class HoverTipTable(QTableWidget):
    """只在“内容显示不全（被截断）”时显示 Tooltip 的表格。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMouseTracking(True)

    def viewportEvent(self, event):
        if event.type() == QEvent.ToolTip:
            pos = event.pos()
            item = self.itemAt(pos)
            if item is None:
                QToolTip.hideText()
                return True

            text = item.text()
            if not text:
                QToolTip.hideText()
                return True

            rect = self.visualItemRect(item)
            # 估算单元格可用宽度（减去一点 padding）
            avail = max(0, rect.width() - 10)

            fm = QFontMetrics(item.font())
            lines = text.splitlines() or [text]
            text_w = max(fm.horizontalAdvance(line) for line in lines)

            # 仅当文本宽度超过可用宽度时显示 Tooltip
            if text_w > avail:
                QToolTip.showText(event.globalPos(), text, self)
            else:
                QToolTip.hideText()
            return True

        return super().viewportEvent(event)
