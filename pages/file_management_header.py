from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QHBoxLayout, QLabel


class CurrentPlatformBanner(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("CurrentPlatformBanner")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(10)

        layout.addStretch(1)

        self.prefix_label = QLabel("\u5f53\u524d\u9009\u4e2d\u5e73\u53f0", self)
        self.prefix_label.setObjectName("CurrentPlatformPrefix")
        self.prefix_label.setAlignment(Qt.AlignCenter)

        self.platform_label = QLabel("--", self)
        self.platform_label.setObjectName("CurrentPlatformValue")
        self.platform_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.prefix_label, 0, Qt.AlignCenter)
        layout.addWidget(self.platform_label, 0, Qt.AlignCenter)
        layout.addStretch(1)

        self.setStyleSheet(
            """
            QFrame#CurrentPlatformBanner {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #e8f5ff,
                    stop: 0.5 #f6fbff,
                    stop: 1 #e8f5ff
                );
                border: 1px solid #b6daf7;
                border-radius: 12px;
            }
            QLabel#CurrentPlatformPrefix {
                color: #2b5d88;
                font-size: 14px;
                font-weight: 600;
                padding: 2px 0;
            }
            QLabel#CurrentPlatformValue {
                color: #0f5ea5;
                font-size: 18px;
                font-weight: 700;
                padding: 2px 0;
            }
            """
        )

    def set_platform_name(self, name: str):
        self.platform_label.setText(name or "--")


def build_platform_description(values: dict) -> str:
    facility_name = values.get("facility_name") or "\u5f53\u524d\u5e73\u53f0"
    oilfield = values.get("field") or values.get("oilfield") or ""
    facility_type = values.get("facility_type") or ""
    category = values.get("category") or ""
    facility_code = values.get("facility_code") or ""
    start_time = values.get("start_time") or ""
    design_life = values.get("design_years") or values.get("design_life") or ""

    fragments = []
    if oilfield:
        fragments.append(f"\u6240\u5c5e\u6cb9\u6c14\u7530\u4e3a{oilfield}")
    if facility_type and category:
        fragments.append(f"\u5e73\u53f0\u7c7b\u578b\u4e3a{facility_type}\uff0c\u5206\u7c7b\u4e3a{category}")
    elif facility_type:
        fragments.append(f"\u5e73\u53f0\u7c7b\u578b\u4e3a{facility_type}")
    elif category:
        fragments.append(f"\u5e73\u53f0\u5206\u7c7b\u4e3a{category}")
    if facility_code:
        fragments.append(f"\u5e73\u53f0\u7f16\u53f7\u4e3a{facility_code}")
    if start_time:
        fragments.append(f"\u6295\u4ea7\u65f6\u95f4\u4e3a{start_time}")
    if design_life:
        fragments.append(f"\u8bbe\u8ba1\u5e74\u9650\u4e3a{design_life}\u5e74")

    if not fragments:
        return f"{facility_name}\uff0c\u5f53\u524d\u5df2\u9009\u4e2d\u4e3a\u6587\u4ef6\u7ba1\u7406\u5bf9\u8c61\u3002"
    return f"{facility_name}\uff0c" + "\uff1b".join(fragments) + "\u3002"
