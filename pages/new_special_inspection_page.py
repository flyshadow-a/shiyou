# -*- coding: utf-8 -*-
# pages/new_special_inspection_page.py

import os
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QWidget,
    QLineEdit, QFileDialog, QMessageBox, QScrollArea
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt

from base_page import BasePage
from pages.upgrade_special_inspection_result_page import UpgradeSpecialInspectionResultPage


class NewSpecialInspectionPage(BasePage):
    """
    新增检测策略打开的页面：
    - 右侧：黑底模型图（仅一个，不重复创建）
    - 左侧：上半（结构模型信息 + 设置倒塌分析结果文件）
           下半（用户设置：风险等级参数 + 按钮）
    - 整体支持滚轮滚动（ScrollArea）
    """

    def __init__(self, facility_code: str, parent=None):
        self.facility_code = facility_code
        self._risk_updated = False
        super().__init__(f"{facility_code}特检策略", parent)
        self._build_ui()

    def _build_ui(self):
        # 整页浅蓝灰背景
        self.setStyleSheet("""
            QWidget { background: #e6eef7; }
            QFrame#Card {
                background: #e6eef7;
                border: 1px solid #c7d2e3;
            }
            QLabel#SectionTitle {
                font-weight: bold;
                color: #2b2b2b;
            }
            QLabel#RedSectionTitle {
                font-weight: bold;
                color: #d10000;
            }
            QPushButton#ActionBtn {
                background: #00a0d6;
                color: white;
                border: 1px solid #007aa3;
                border-radius: 4px;
                padding: 4px 12px;
                min-height: 26px;
            }
            QPushButton#ActionBtn:hover { background: #00b6f2; }

            QPushButton#BigBlueBtn {
                background: #00a0d6;
                color: black;
                border: 1px solid #0a5f7a;
                border-radius: 6px;
                min-height: 46px;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton#BigBlueBtn:hover { background: #00b6f2; }

            QTableWidget {
                background: #f7fbff;
                gridline-color: #7b8798;
                border: 1px solid #7b8798;
            }
            QHeaderView::section {
                background: #d9e6f5;
                border: 1px solid #7b8798;
                padding: 4px 6px;
                font-weight: bold;
            }
            QLineEdit {
                background: white;
                border: 1px solid #c7d2e3;
                padding: 4px 6px;
            }
        """)

        # ===== 关键：用 ScrollArea 包裹“中间主要内容”，滚轮可下滑查看下半部分 =====
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        self.main_layout.addWidget(scroll, 1)

        container = QWidget()
        scroll.setWidget(container)

        # 依旧是：左（内容） + 右（黑底模型图）
        content = QFrame()
        content.setObjectName("Card")
        lay = QHBoxLayout(content)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(12)

        left = self._build_left_panel()     # 上半 + 下半都在这里
        right = self._build_right_panel()   # 黑底模型图（只创建一次）

        lay.addWidget(left, 3)
        lay.addWidget(right, 2)

        root = QVBoxLayout(container)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(content)

    # ---------------- 左侧：上下拼接 ----------------
    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        v = QVBoxLayout(panel)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)

        # 上半部分：你原来 new_special_inspection_page 的内容
        v.addWidget(self._build_model_info_block(), 0)
        v.addWidget(self._build_analysis_files_block(), 0)

        # 下半部分：按你新截图增加的“用户设置/风险等级参数”
        v.addWidget(self._build_risk_level_settings_block(), 0)

        v.addStretch(1)
        return panel

    # ---------------- 上半：结构模型信息 ----------------
    def _build_model_info_block(self) -> QFrame:
        block = QFrame()
        block_lay = QVBoxLayout(block)
        block_lay.setContentsMargins(0, 0, 0, 0)
        block_lay.setSpacing(6)

        title_row = QHBoxLayout()
        title = QLabel("结构模型信息")
        title.setObjectName("SectionTitle")

        btn_find = QPushButton("查找节点")
        btn_find.setObjectName("ActionBtn")
        btn_find.clicked.connect(self._on_find_nodes)

        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(btn_find)
        block_lay.addLayout(title_row)

        # 参数表（两列：项目/值）
        param_table = QTableWidget(4, 2)
        param_table.setHorizontalHeaderLabels(["项目", "值"])
        param_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        param_table.verticalHeader().setVisible(False)
        param_table.setFixedHeight(160)

        params = [
            ("构件直线夹角容许误差（度）", "15"),
            ("腿柱管节点撑杆最小管径（mm）", "509"),
            ("工作点高度 Z(m)", "10"),
            ("腿柱数量", "4"),
        ]
        for r, (k, val) in enumerate(params):
            item_k = QTableWidgetItem(k)
            item_v = QTableWidgetItem(val)
            item_k.setTextAlignment(Qt.AlignCenter)
            item_v.setTextAlignment(Qt.AlignCenter)
            param_table.setItem(r, 0, item_k)
            param_table.setItem(r, 1, item_v)

        block_lay.addWidget(param_table)

        # 坐标表（示例）
        coord_table = QTableWidget(5, 3)
        coord_table.setHorizontalHeaderLabels(["柱腿工作点坐标", "X坐标（m）", "Y坐标（m）"])
        coord_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        coord_table.verticalHeader().setVisible(False)
        coord_table.setFixedHeight(190)

        coords = [
            (1, -10, -8),
            (2, -10,  8),
            (3,  10, -8),
            (4,  10,  8),
            (5, "",  ""),
        ]
        for r, (idx, x, y) in enumerate(coords):
            for c, val in enumerate([idx, x, y]):
                it = QTableWidgetItem(str(val))
                it.setTextAlignment(Qt.AlignCenter)
                coord_table.setItem(r, c, it)

        block_lay.addWidget(coord_table)
        return block

    # ---------------- 上半：场分析结果文件 ----------------
    def _build_analysis_files_block(self) -> QFrame:
        block = QFrame()
        block_lay = QVBoxLayout(block)
        block_lay.setContentsMargins(0, 0, 0, 0)
        block_lay.setSpacing(6)

        title_row = QHBoxLayout()
        title = QLabel("设置倒塌分析结果文件")
        title.setObjectName("SectionTitle")

        btn_extract = QPushButton("提取分析")
        btn_extract.setObjectName("ActionBtn")
        btn_extract.clicked.connect(self._on_extract_analysis)

        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(btn_extract)
        block_lay.addLayout(title_row)

        self.files_table = QTableWidget(8, 2)
        self.files_table.setHorizontalHeaderLabels(["序号", "路径"])
        self.files_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.files_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.files_table.verticalHeader().setVisible(False)
        self.files_table.setMinimumHeight(260)

        demo_paths = [
            r"D:\SACS\Strategy\test file\1\clplog",
            r"D:\SACS\Strategy\test file\2\clplog",
            r"D:\SACS\Strategy\test file\3\clplog",
            r"D:\SACS\Strategy\test file\4\clplog",
            r"D:\SACS\Strategy\test file\5\clplog",
            r"D:\SACS\Strategy\test file\6\clplog",
            r"D:\SACS\Strategy\test file\7\clplog",
            r"D:\SACS\Strategy\test file\8\clplog",
        ]
        for i in range(8):
            idx = QTableWidgetItem(str(i + 1))
            path = QTableWidgetItem(demo_paths[i])
            idx.setTextAlignment(Qt.AlignCenter)
            path.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            self.files_table.setItem(i, 0, idx)
            self.files_table.setItem(i, 1, path)

        block_lay.addWidget(self.files_table, 1)

        # 疲劳分析结果文件选择
        bottom_row = QHBoxLayout()
        bottom_row.addWidget(QLabel("设置疲劳分析结果文件："))

        self.result_path_edit = QLineEdit()
        self.result_path_edit.setPlaceholderText("请选择 *.wit 或其它结果文件")
        bottom_row.addWidget(self.result_path_edit, 1)

        btn_browse = QPushButton("选择文件")
        btn_browse.clicked.connect(self._browse_result_file)
        bottom_row.addWidget(btn_browse)

        block_lay.addLayout(bottom_row)
        return block

    # ---------------- 下半：风险等级参数（新增） ----------------
    def _build_risk_level_settings_block(self) -> QFrame:
        block = QFrame()
        v = QVBoxLayout(block)
        v.setContentsMargins(0, 8, 0, 0)
        v.setSpacing(10)

        # 红色标题（对应截图“设置等级参数”）
        title = QLabel("设置等级参数")
        title.setObjectName("RedSectionTitle")
        v.addWidget(title)

        table = QTableWidget(7, 3)
        table.setHorizontalHeaderLabels(["项目", "等级/值", "说明"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)

        # 行内容（按你图的结构填示例）
        rows = [
            ("生命安全等级", "S-2", "有人可撤离——有人员居住的平台，在极端情况下人员可以实施撤离的情况。"),
            ("失效后果等级", "C-3", "低后果——所有井口包含功能齐全的SSSV，在平台失效时，生产系统可以自行运转而不受影响。这些平台可以支持不依托平台的生产，平台仅包含低输量的内部管道，仅含有工艺库存。"),
            ("平台整体暴露等级", "L-2", ""),
            ("平台海域", "中国南海", ""),
            ("A", "0.272", ""),
            ("B", "0.158", ""),
            ("已服役时间（年）", "12", ""),
        ]

        for r, (k, val, desc) in enumerate(rows):
            it0 = QTableWidgetItem(k)
            it1 = QTableWidgetItem(val)
            it2 = QTableWidgetItem(desc)

            it0.setTextAlignment(Qt.AlignCenter)
            it1.setTextAlignment(Qt.AlignCenter)
            it2.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)

            # 描述列允许换行
            it2.setFlags(it2.flags() | Qt.ItemIsSelectable)
            table.setItem(r, 0, it0)
            table.setItem(r, 1, it1)
            table.setItem(r, 2, it2)

        # 让前两行更高，容纳长描述
        table.setRowHeight(0, 70)
        table.setRowHeight(1, 90)

        # “平台整体暴露等级 L-2”黄色高亮（对应截图）
        highlight = table.item(2, 1)
        if highlight:
            highlight.setBackground(Qt.yellow)
            highlight.setForeground(Qt.black)
            highlight.setTextAlignment(Qt.AlignCenter)

        table.setMinimumHeight(260)
        v.addWidget(table)

        # 两个大按钮（对应截图：更新风险等级 / 查看结果）
        btn_row = QVBoxLayout()
        btn_row.setSpacing(12)

        btn_update = QPushButton("更新风险等级")
        btn_update.setObjectName("BigBlueBtn")
        btn_update.setFixedWidth(300)
        btn_update.clicked.connect(self._on_update_risk_level)

        btn_view = QPushButton("查看结果")
        btn_view.setObjectName("BigBlueBtn")
        btn_view.setFixedWidth(300)
        btn_view.clicked.connect(self._on_view_result)

        btn_row.addWidget(btn_update, 0, Qt.AlignLeft)
        btn_row.addWidget(btn_view, 0, Qt.AlignLeft)

        v.addLayout(btn_row)

        return block

    # ---------------- 右侧：黑底模型图（只保留一个） ----------------
    def _build_right_panel(self) -> QFrame:
        panel = QFrame()
        v = QVBoxLayout(panel)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        title = QLabel("结构模型示意")
        title.setObjectName("SectionTitle")
        v.addWidget(title)

        img_frame = QFrame()
        img_frame.setStyleSheet("background: black; border: 1px solid #c7d2e3;")
        img_lay = QVBoxLayout(img_frame)
        img_lay.setContentsMargins(6, 6, 6, 6)

        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignCenter)
        self.img_label.setStyleSheet("color: #9ca3af;")
        self.img_label.setText("（这里显示平台结构图/模型截图）")
        img_lay.addWidget(self.img_label, 1)

        # 可选：自动加载 pict/platform.png（你可以改成真实图片名）
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidate = os.path.join(project_root, "pict", "platform.png")
        if os.path.exists(candidate):
            pix = QPixmap(candidate)
            if not pix.isNull():
                self.img_label.setPixmap(pix.scaled(650, 650, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        v.addWidget(img_frame, 1)
        return panel

    # ---------------- actions ----------------
    def _on_find_nodes(self):
        QMessageBox.information(self, "查找节点", f"这里执行：根据 {self.facility_code} 的模型/参数查找节点（待接算法）。")

    def _on_extract_analysis(self):
        QMessageBox.information(self, "提取分析", "这里执行：读取场分析结果文件并提取分析结果（待接算法/外部程序）。")

    def _browse_result_file(self):
        fp, _ = QFileDialog.getOpenFileName(self, "选择疲劳分析结果文件", "", "结果文件 (*.wit *.csv *.txt);;所有文件 (*.*)")
        if fp:
            self.result_path_edit.setText(fp)

    def _on_update_risk_level(self):
        # 这里你以后接算法，更新完就标记一下
        self._risk_updated = True
        QMessageBox.information(self, "更新风险等级", "已完成风险等级更新（示例）。")

    def _on_view_result(self):
        if not self._risk_updated:
            QMessageBox.information(self, "提示", "请先点击“更新风险等级”，再查看结果。")
            return

        mw = self.window()  # ✅比 self.parent() 稳定

        # ✅这里判断/调用你 main.py 里真实存在的方法名
        if mw is not None and hasattr(mw, "open_upgrade_special_inspection_result_tab"):
            mw.open_upgrade_special_inspection_result_tab(self.facility_code)
            return

        # 兜底：直接加tab
        if mw is not None and hasattr(mw, "tab_widget"):
            page = UpgradeSpecialInspectionResultPage(self.facility_code, mw)
            idx = mw.tab_widget.addTab(page, f"{self.facility_code}更新风险结果")
            mw.tab_widget.setCurrentIndex(idx)
            return

        QMessageBox.warning(self, "错误", "未找到 MainWindow/tab_widget，无法打开结果页。")

