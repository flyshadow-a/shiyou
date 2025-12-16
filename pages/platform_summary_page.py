# -*- coding: utf-8 -*-
# pages/platform_summary_page.py

import os
import shutil
import datetime

from typing import List


from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QFileDialog, QMessageBox, QWidget,
    QScrollArea,  QSizePolicy,     # ← 新增
)

from base_page import BasePage

# 尝试导入 pandas，用于 Excel 读写；如果没有安装，会在导入/导出时给出提示
try:
    import pandas as pd
except ImportError:
    pd = None


class PlatformSummaryPage(BasePage):
    """
    平台信息 - 汇总信息页面

    左侧：平台列表（可编辑、增删行）
        列包含：分公司、作业公司、油气田、设施编号、设施名称、设施类型、投产时间、设计年限

    右侧：
        顶部按钮：保存、导入Excel、导出Excel、导出模板
        中间：油田分布图（pict/youtianfenbu.png）
    """

    def __init__(self, parent: QWidget = None):
        super().__init__("平台汇总信息", parent)

        # 列名定义，导入/导出也按这个顺序处理
        self.columns: List[str] = [
            "分公司",
            "作业公司",
            "油气田",
            "设施编号",
            "设施名称",
        ]

        # 项目根目录 & 图片路径
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.map_image_path = os.path.join(self.project_root, "pict", "youtianfenbu.png")

        self._build_ui()

    # ------------------------------------------------------------------ #
    # UI 构建
    # ------------------------------------------------------------------ #
    def _build_ui(self):
        root = QFrame()
        root.setObjectName("PlatformSummaryRoot")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)

        # 样式
        self.setStyleSheet("""
            QFrame#PlatformSummaryRoot {
                background-color: #f3f4f6;
            }

            QFrame#TablePanel, QFrame#RightPanel {
                background-color: #ffffff;
                border-radius: 8px;
                border: 1px solid #d0d7e2;
            }

            QFrame#MapFrame {
                background-color: #eef6ff;
                border-radius: 24px;
                border: 3px solid #4caf50;
            }

            QTableWidget {
                background-color: #ffffff;
                gridline-color: #e0e0e0;
                border: none;
            }
            QHeaderView::section {
                background-color: #e5e7eb;
                color: #111827;
                padding: 4px 6px;
                border: 0px;
                border-right: 1px solid #d1d5db;
                font-weight: bold;
            }

            QPushButton {
                min-height: 26px;
                padding: 4px 10px;
                border-radius: 4px;
                border: 1px solid #c0c4cc;
                background-color: #ffffff;
            }
            QPushButton:hover {
                background-color: #f2f6ff;
            }

            QPushButton.PrimaryButton {
                background-color: #0090d0;
                color: #ffffff;
                border-color: #0090d0;
            }
            QPushButton.PrimaryButton:hover {
                background-color: #00a4f2;
            }
        """)

        # ============ 左侧：表格区 ============ #
        table_panel = QFrame()
        table_panel.setObjectName("TablePanel")
        table_layout = QVBoxLayout(table_panel)
        table_layout.setContentsMargins(10, 10, 10, 10)
        table_layout.setSpacing(8)

        # 表格
        self.table = QTableWidget(0, len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(
            self.table.DoubleClicked |
            self.table.SelectedClicked |
            self.table.EditKeyPressed
        )
        table_layout.addWidget(self.table)

        # 表格底部：新增 / 删除
        table_btn_layout = QHBoxLayout()
        table_btn_layout.setContentsMargins(0, 0, 0, 0)
        table_btn_layout.setSpacing(8)

        self.btn_add_row = QPushButton("新增行")
        self.btn_del_row = QPushButton("删除选中行")

        self.btn_add_row.clicked.connect(self.add_empty_row)
        self.btn_del_row.clicked.connect(self.remove_selected_rows)

        table_btn_layout.addWidget(self.btn_add_row)
        table_btn_layout.addWidget(self.btn_del_row)
        table_btn_layout.addStretch()

        table_layout.addLayout(table_btn_layout)

        # ============ 右侧：按钮 + 地图 ============ #
        right_panel = QFrame()
        right_panel.setObjectName("RightPanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(10)

        # 顶部按钮区
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(8)

        self.btn_save = QPushButton("保存")
        self.btn_save.setProperty("class", "PrimaryButton")
        self.btn_save.setObjectName("")

        self.btn_import = QPushButton("导入Excel")
        self.btn_export = QPushButton("导出Excel")
        self.btn_export_tpl = QPushButton("导出模板")

        self.btn_save.clicked.connect(self.on_save_clicked)
        self.btn_import.clicked.connect(self.on_import_clicked)
        self.btn_export.clicked.connect(self.on_export_clicked)
        self.btn_export_tpl.clicked.connect(self.on_export_template_clicked)

        btn_bar.addWidget(self.btn_save)
        btn_bar.addSpacing(10)
        btn_bar.addWidget(self.btn_import)
        btn_bar.addWidget(self.btn_export)
        btn_bar.addWidget(self.btn_export_tpl)
        btn_bar.addStretch()

        right_layout.addLayout(btn_bar)

        # 中间：油田分布图
        map_frame = QFrame()
        map_frame.setObjectName("MapFrame")
        map_layout = QVBoxLayout(map_frame)
        map_layout.setContentsMargins(10, 10, 10, 10)

        self.map_label = QLabel()
        self.map_label.setAlignment(Qt.AlignCenter)

        # 图片在 label 区域内自适应缩放
        self.map_label.setScaledContents(True)

        # 关键：忽略原始 sizeHint，避免按原图尺寸把右侧撑爆
        self.map_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

        # 再给一个最大高度，防止窗口很大时图片无限变大
        self.map_label.setMaximumHeight(500)   # 觉得还大就改小一点，比如 400


        self._load_map_image()

        map_layout.addWidget(self.map_label)
        right_layout.addWidget(map_frame, 1)

        # 两侧加入根布局
        # 用滚动区域包住左侧表格面板
        table_scroll = QScrollArea()
        table_scroll.setWidgetResizable(True)
        table_scroll.setFrameShape(QFrame.NoFrame)
        table_scroll.setWidget(table_panel)

        # 让左侧优先扩展，右侧保持正常
        table_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        root_layout.addWidget(table_scroll)
        root_layout.addWidget(right_panel)

        # 明确设置左右 6 : 4 的宽度比例
        root_layout.setStretch(0, 6)   # 左：表格
        root_layout.setStretch(1, 4)   # 右：地图


        self.main_layout.addWidget(root)

    # ------------------------------------------------------------------ #
    # 地图加载
    # ------------------------------------------------------------------ #

    def _get_upload_root(self) -> str:
        """
        Excel 上传文件的根目录：
        项目根目录 / upload / platform_summary

        比如:
        D:/pyproject/pythonProject4/upload/platform_summary
        """
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        root = os.path.join(project_root, "upload", "platform_summary")
        os.makedirs(root, exist_ok=True)
        return root

    def _load_map_image(self):
        if os.path.exists(self.map_image_path):
            pix = QPixmap(self.map_image_path)
            if not pix.isNull():
                # 给一个初始大小，后面会自动跟随布局拉伸
                self.map_label.setPixmap(pix)
        else:
            self.map_label.setText("找不到图片：youtianfenbu.png")

    # ------------------------------------------------------------------ #
    # 表格增删行
    # ------------------------------------------------------------------ #
    def add_empty_row(self):
        """在表格末尾新增一空行."""
        row = self.table.rowCount()
        self.table.insertRow(row)
        # 默认每个单元格给一个 QTableWidgetItem，方便直接编辑
        for col in range(self.table.columnCount()):
            item = QTableWidgetItem("")
            self.table.setItem(row, col, item)

    def remove_selected_rows(self):
        """删除当前选中的行（可多选）."""
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return
        # 从后往前删，避免索引混乱
        rows = sorted([idx.row() for idx in selected], reverse=True)
        for r in rows:
            self.table.removeRow(r)

    # ------------------------------------------------------------------ #
    # Excel 导入 / 导出
    # ------------------------------------------------------------------ #
    def _ensure_pandas(self) -> bool:
        """检查是否安装 pandas，没有的话给提示。"""
        if pd is None:
            QMessageBox.warning(
                self,
                "缺少依赖",
                "当前导入/导出 Excel 需要安装 pandas 库：\n\n"
                "    pip install pandas openpyxl\n"
            )
            return False
        return True

    def on_import_clicked(self):
        """从 Excel 导入平台汇总数据，并把 Excel 复制到 upload 目录下。"""
        if not self._ensure_pandas():
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择要导入的 Excel 文件",
            "",
            "Excel 文件 (*.xls *.xlsx)"
        )
        if not file_path:
            return

        # 根据扩展名选择 engine（.xlsx -> openpyxl, .xls -> xlrd）
        ext = os.path.splitext(file_path)[1].lower()
        engine = None
        if ext == ".xlsx":
            engine = "openpyxl"
        elif ext == ".xls":
            engine = "xlrd"

        try:
            if engine:
                df = pd.read_excel(file_path, engine=engine)
            else:
                df = pd.read_excel(file_path)
        except Exception as e:
            QMessageBox.critical(self, "导入失败", f"读取 Excel 失败：\n{e}")
            return

        # 如果没有任何数据行，直接提示
        if df is None or df.shape[0] == 0:
            QMessageBox.information(self, "导入完成", "Excel 中没有数据行（仅表头或为空）。")
            return

        # ---- 将 Excel 文件复制到 upload 目录 ----
        try:
            upload_root = self._get_upload_root()

            # 按日期再分一层目录，比如 20241211
            date_str = datetime.date.today().strftime("%Y%m%d")
            target_dir = os.path.join(upload_root, date_str)
            os.makedirs(target_dir, exist_ok=True)

            basename = os.path.basename(file_path)
            # 也可以加个时间戳避免重名
            time_str = datetime.datetime.now().strftime("%H%M%S")
            new_name = f"{time_str}_{basename}"
            saved_path = os.path.join(target_dir, new_name)

            shutil.copy2(file_path, saved_path)
        except Exception as e:
            # 复制失败不影响表格显示，只给个提示
            QMessageBox.warning(self, "提示", f"Excel 文件复制到 upload 目录失败：\n{e}")
            saved_path = None

        # ---- 将 df 写入左侧表格 ----
        # 只保留我们关心的列；如果缺列就补空列
        data_cols = []
        for col in self.columns:
            if col in df.columns:
                data_cols.append(col)
            else:
                df[col] = ""
                data_cols.append(col)

        df = df[data_cols]

        # 填表
        self.table.setRowCount(0)
        self.table.clearContents()
        for _, row in df.iterrows():
            r = self.table.rowCount()
            self.table.insertRow(r)
            for c, col_name in enumerate(self.columns):
                value = row.get(col_name, "")
                # 处理 NaN
                text = "" if pd.isna(value) else str(value)
                item = QTableWidgetItem(text)
                self.table.setItem(r, c, item)

        msg = f"已从文件导入 {len(df)} 条记录。"
        if saved_path:
            msg += f"\n\n源文件已保存到：\n{saved_path}"

        QMessageBox.information(self, "导入完成", msg)


    def on_export_clicked(self):
        """将当前表格内容导出为 Excel."""
        if not self._ensure_pandas():
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出 Excel 文件",
            "平台汇总信息.xlsx",
            "Excel 文件 (*.xlsx)"
        )
        if not file_path:
            return

        # 收集当前表格数据
        data = {col: [] for col in self.columns}
        rows = self.table.rowCount()
        for r in range(rows):
            for c, col_name in enumerate(self.columns):
                item = self.table.item(r, c)
                text = item.text() if item is not None else ""
                data[col_name].append(text)

        try:
            df = pd.DataFrame(data)
            df.to_excel(file_path, index=False)
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"写入 Excel 失败：\n{e}")
            return

        QMessageBox.information(self, "导出完成", f"已导出 {rows} 条记录到：\n{file_path}")

    def on_export_template_clicked(self):
        """导出一个只包含表头的 Excel 模板，方便其他系统按模板导出数据."""
        if not self._ensure_pandas():
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出 Excel 模板",
            "平台汇总信息模板.xlsx",
            "Excel 文件 (*.xlsx)"
        )
        if not file_path:
            return

        try:
            df = pd.DataFrame(columns=self.columns)
            df.to_excel(file_path, index=False)
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"写入 Excel 失败：\n{e}")
            return

        QMessageBox.information(self, "导出完成", f"模板已导出到：\n{file_path}")

    # ------------------------------------------------------------------ #
    # 保存按钮（写接口占位，后续可接数据库或接口）
    # ------------------------------------------------------------------ #
    def on_save_clicked(self):
        """
        保存当前表格内容。

        这里暂时只做一个提示，真正接数据库 / 接口时，可以在这里把数据打包提交。
        """
        rows = self.table.rowCount()
        QMessageBox.information(
            self,
            "保存",
            f"当前共有 {rows} 条平台记录。\n\n"
            "后续可以在 on_save_clicked 中对接后端接口或写入数据库。"
        )
