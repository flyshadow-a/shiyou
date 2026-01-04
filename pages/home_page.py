# -*- coding: utf-8 -*-
# pages/home_page.py

import os
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QResizeEvent
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy


class HomePage(QWidget):
    """
    应用启动后的首页：
    - 右侧只显示一张适应区域并保持纵横比的背景图片
    - 窗口变大图片也变大，但避免初始化/布局动画导致“自己一点点放大”的视觉效果（resize 防抖）
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._original_pixmap = None

        # resize 防抖：尺寸频繁变化时不立刻缩放，等稳定后再缩放一次
        self._pending_size = None
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._apply_resize)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.bg_label = QLabel(self)
        # ✅ 设置图片背后的背景色（HomePage + Label）
        self.setStyleSheet("background-color: #004a80;")
        self.bg_label.setStyleSheet("background-color: #004a80;")

        self.bg_label.setAlignment(Qt.AlignCenter)

        # 关键：不要让 pixmap 的 sizeHint 反过来影响布局/窗口尺寸（容易造成“自己变大”的连锁）
        self.bg_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.bg_label.setMinimumSize(0, 0)

        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        img_path = os.path.join(project_root, "pict", "home_bg.png")

        if os.path.exists(img_path):
            self._original_pixmap = QPixmap(img_path)
        else:
            self.bg_label.setText(f"首页背景图片缺失:\n{img_path}")
            self.bg_label.setStyleSheet("QLabel { font-size: 20px; color: red; }")

        layout.addWidget(self.bg_label)

        # 初次进入时也走防抖更新，避免启动阶段连续 resize 造成“缓慢放大”
        self._pending_size = self.size()
        self._resize_timer.start(0)

    def resizeEvent(self, event: QResizeEvent):
        if self._original_pixmap and not self._original_pixmap.isNull():
            target_size = self.size()

            # ✅ 1) 先按“覆盖铺满”缩放（可能超出目标尺寸）
            if target_size.width() > 0 and target_size.height() > 0:
                scaled = self._original_pixmap.scaled(
                    target_size,
                    Qt.KeepAspectRatioByExpanding,
                    Qt.SmoothTransformation
                )

            # ✅ 2) 再居中裁剪成目标尺寸（关键：去掉白边）
            x = max(0, (scaled.width() - target_size.width()) // 2)
            y = max(0, (scaled.height() - target_size.height()) // 2)
            cropped = scaled.copy(x, y, target_size.width(), target_size.height())

            self.bg_label.setPixmap(cropped)

        super().resizeEvent(event)

    def _apply_resize(self):
        if not self._original_pixmap or self._original_pixmap.isNull():
            return

        # 以 label 的真实尺寸为准，更不容易露边
        target_size = self.bg_label.size()
        if target_size.width() <= 0 or target_size.height() <= 0:
            return

        scaled = self._original_pixmap.scaled(
            target_size,
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation
        )

        x = max(0, (scaled.width() - target_size.width()) // 2)
        y = max(0, (scaled.height() - target_size.height()) // 2)
        cropped = scaled.copy(x, y, target_size.width(), target_size.height())

        self.bg_label.setPixmap(cropped)

