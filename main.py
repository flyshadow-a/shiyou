# -*- coding: utf-8 -*-
# main.py

import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QTabWidget, QLabel, QLineEdit,
    QPushButton, QSplitter, QFrame
)
from PyQt5.QtCore import Qt

from nav_config import NAV_CONFIG
from PyQt5.QtGui import QPixmap
from PyQt5.QtGui import QPixmap, QIcon
import os


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("海上平台结构载荷管理系统")
        # 默认窗口大小（可以按需要改）
        self.resize(1280, 720)

        self.nav_tree = None     # 左侧导航树
        self.nav_search = None        # 左侧导航里的搜索框   ← 新增
        self.nav_container = None     # 搜索框+树 的容器     ← 新增
        self.tab_widget = None        # 右侧 tab 区域（多个页面）
        self.search_edit = None       # 顶部搜索框

        # 记录“菜单路径 -> 页面 widget”的映射，用来避免重复开同一个页面
        self.page_tab_map = {}

        self.init_ui()

    # ================== 整体 UI ================== #
    def init_ui(self):
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        # 1. 头部
        header = self.create_header()
        # 头部高度基本固定，下面的内容区域占主导
        central_layout.addWidget(header, 1)

        # 2. 中部：左侧导航面板（搜索框+树） + 右侧 tab 页面

        # ---- 左侧：导航面板 ----
        self.nav_container = QFrame()
        self.nav_container.setMinimumWidth(200)
        self.nav_container.setStyleSheet("""
            QFrame#NavContainer {
                background-color: #1f2d3d;
            }
        """)
        self.nav_container.setObjectName("NavContainer")

        nav_layout = QVBoxLayout(self.nav_container)
        nav_layout.setContentsMargins(6, 6, 6, 6)
        nav_layout.setSpacing(4)

        # 顶部搜索框（和每一行菜单同宽）
        self.nav_search = QLineEdit()
        self.nav_search.setPlaceholderText("搜索菜单")
        self.nav_search.setClearButtonEnabled(True)
        self.nav_search.setFixedHeight(26)
        self.nav_search.setStyleSheet("""
            QLineEdit {
                background-color: #1a2533;
                border: 1px solid #314155;
                border-radius: 3px;
                padding-left: 6px;
                color: #b0bccd;            /* 暗淡文字 */
            }
            QLineEdit:focus {
                background-color: #ffffff; /* 亮起 */
                border: 1px solid #3a8ee6;
                color: #000000;
            }
        """)
        nav_layout.addWidget(self.nav_search)

        # 树菜单本体
        self.nav_tree = QTreeWidget()
        self.nav_tree.setHeaderHidden(True)
        self.nav_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #1f2d3d;
                color: #f0f0f0;
                border: none;
            }
            QTreeWidget::item {
                height: 24px;
            }
            QTreeWidget::item:selected {
                background-color: #3a8ee6;
            }
        """)
        nav_layout.addWidget(self.nav_tree, 1)

        # ---- 右侧：tab 控件 ----
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.tabCloseRequested.connect(self.on_tab_close_requested)
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: #e5eef7;
            }
            QTabBar::tab {
                height: 28px;
                padding: 4px 16px;
            }
        """)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.nav_container)   # ← 现在加的是容器
        splitter.addWidget(self.tab_widget)
        # 左:右 = 1:4 大致比例
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        central_layout.addWidget(splitter, 9)
        self.setCentralWidget(central)

        # 构建左侧导航树（只创建页面对象，不立即加入 tab）
        self.build_nav_tree()

        # 信号连接
        self.nav_tree.itemClicked.connect(self.on_nav_item_clicked)
        # 左侧导航搜索：输入时过滤树
        if self.nav_search is not None:
            self.nav_search.textChanged.connect(self.filter_nav_tree)
        if self.search_edit is not None:
            self.search_edit.textChanged.connect(self.filter_nav_tree)

        # 打开第一个叶子菜单对应的页面作为默认页面
        self.open_first_leaf_page()

    # ================== 头部 ================== #
    def create_header(self) -> QWidget:
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background-color: #004a80;
                color: white;
            }
            QLineEdit {
                background-color: white;
                border-radius: 4px;
                padding: 2px 6px;
            }
            QPushButton {
                background-color: #006bb3;
                border: none;
                color: white;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0088e8;
            }
        """)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(10)
        # ====== 新增：logo ======
        # ====== logo 区域 ======
        logo_label = QLabel()

        # 使用脚本所在目录作为基准，避免 IDE 工作目录不一致的问题
        base_dir = os.path.dirname(os.path.abspath(__file__))
        # 假设 logo 文件就放在 main.py 同目录，名字叫 logo.png
        logo_path = os.path.join(base_dir, "pict/logo.png")

        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(28, 28, Qt.KeepAspectRatio,
                                       Qt.SmoothTransformation)
                logo_label.setPixmap(pixmap)
            else:
                # 图片格式不支持或损坏，可以给一点文字提示方便排查
                logo_label.setText("X")
        else:
            # 路径不对的情况下也给个占位，免得你以为没加成功
            logo_label.setText(" ")
        logo_label.setFixedSize(30, 30)
        # =======================

        title = QLabel("海上平台结构载荷管理系统")
        title.setStyleSheet("font-size:18px; font-weight:bold;")

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("菜单搜索：支持菜单名称、路径")
        self.search_edit.setMaximumWidth(320)

        user_label = QLabel("工程师1")
        btn_settings = QPushButton("设置")
        btn_notice = QPushButton("通知")

        layout.addWidget(logo_label)
        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(self.search_edit)
        layout.addStretch()
        layout.addWidget(user_label)
        layout.addWidget(btn_settings)
        layout.addWidget(btn_notice)

        return header

    # ================== 构建导航树 ================== #
    def build_nav_tree(self):
        """
        只负责建立左侧树结构，并为每个“叶子菜单”创建对应的页面实例，
        存在 item 的 UserRole 数据里；真正打开页面是在点击时添加到 tab。
        """
        self.nav_tree.clear()
        self.page_tab_map.clear()

        def add_nodes(config_list, parent_item=None, parent_path: str = ""):
            for node in config_list:
                text = node.get("text", "未命名")
                # 生成一个唯一的路径 key，例如 "平台载荷管理/平台信息/油气田信息"
                path = f"{parent_path}/{text}" if parent_path else text

                item = QTreeWidgetItem([text])
                if parent_item is None:
                    self.nav_tree.addTopLevelItem(item)
                else:
                    parent_item.addChild(item)

                # 保存路径 key，后面用来在 page_tab_map 里查找
                item.setData(0, Qt.UserRole + 1, path)

                # build_nav_tree 里，存类，而不是实例
                page_cls = node.get("page")
                if page_cls is not None:
                    item.setData(0, Qt.UserRole, page_cls)

                children = node.get("children")
                if children:
                    add_nodes(children, item, path)

        add_nodes(NAV_CONFIG)
        self.nav_tree.expandAll()

    # ================== 默认打开第一个页面 ================== #
    def open_first_leaf_page(self):
        first_leaf = None

        def dfs_find_leaf(item):
            nonlocal first_leaf
            if first_leaf is not None:
                return
            if item.data(0, Qt.UserRole) is not None:
                first_leaf = item
                return
            for i in range(item.childCount()):
                dfs_find_leaf(item.child(i))

        for i in range(self.nav_tree.topLevelItemCount()):
            dfs_find_leaf(self.nav_tree.topLevelItem(i))
            if first_leaf is not None:
                break

        if first_leaf is not None:
            self.open_page_for_item(first_leaf)
            self.nav_tree.setCurrentItem(first_leaf)

    # ================== 打开/激活页面 ================== #
    def open_page_for_item(self, item: QTreeWidgetItem):
        page_cls = item.data(0, Qt.UserRole)
        if page_cls is None:
            return

        path = item.data(0, Qt.UserRole + 1)
        text = item.text(0)

        # 已打开：直接激活
        if path in self.page_tab_map:
            widget = self.page_tab_map[path]
            index = self.tab_widget.indexOf(widget)
            if index != -1:
                self.tab_widget.setCurrentIndex(index)
                return

        # 未打开：新建一个页面
        page = page_cls(self)
        index = self.tab_widget.addTab(page, text)
        self.page_tab_map[path] = page
        self.tab_widget.setCurrentIndex(index)

    # ================== 左侧导航点击 ================== #
    def on_nav_item_clicked(self, item: QTreeWidgetItem, column: int):
        page = item.data(0, Qt.UserRole)
        if page is not None:
            # 叶子节点：打开/激活页面
            self.open_page_for_item(item)
        else:
            # 分组节点：展开 / 收起
            item.setExpanded(not item.isExpanded())

    # ================== 关闭 tab ================== #
    def on_tab_close_requested(self, index: int):
        widget = self.tab_widget.widget(index)
        if widget is None:
            return

        # 从映射表里移除对应的路径 key
        remove_keys = []
        for key, w in self.page_tab_map.items():
            if w is widget:
                remove_keys.append(key)
        for key in remove_keys:
            self.page_tab_map.pop(key, None)

        self.tab_widget.removeTab(index)
        widget.deleteLater()

    # ================== 导航搜索过滤（可选） ================== #
    def filter_nav_tree(self, text: str):
        text = text.strip().lower()
        for i in range(self.nav_tree.topLevelItemCount()):
            item = self.nav_tree.topLevelItem(i)
            self._filter_nav_item(item, text)

    def filter_nav_tree(self, text: str):
        text = text.strip().lower()
        for i in range(self.nav_tree.topLevelItemCount()):
            item = self.nav_tree.topLevelItem(i)
            self._filter_nav_item(item, text)

    def _filter_nav_item(self, item: QTreeWidgetItem, text: str) -> bool:
        """
        递归过滤导航树节点，返回该节点（或其子节点）是否匹配搜索关键字。
        """
        if not text:
            # 没有搜索关键字：全部显示
            item.setHidden(False)
            for i in range(item.childCount()):
                self._filter_nav_item(item.child(i), text)
            return True

        self_match = text in item.text(0).lower()
        child_match = False
        for i in range(item.childCount()):
            child = item.child(i)
            if self._filter_nav_item(child, text):
                child_match = True

        visible = self_match or child_match
        item.setHidden(not visible)
        if text and child_match:
            item.setExpanded(True)
        return visible


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
