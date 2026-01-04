# -*- coding: utf-8 -*-
# main.py

import sys
import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QTabWidget, QStackedWidget, QLabel, QLineEdit,
    QPushButton, QSplitter, QFrame
)

from nav_config import NAV_CONFIG

# 业务页面 / 对话框
from pages.new_special_inspection_page import NewSpecialInspectionPage
from pages.upgrade_special_inspection_result_page import UpgradeSpecialInspectionResultPage
from pages.home_page import HomePage
from pages.personal_center_page import PersonalCenterPage
from pages.login_dialog import LoginDialog
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QHeaderView
from PyQt5.QtWidgets import QStatusBar






class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("海上平台结构载荷管理系统")
        self.resize(1280, 720)

        # 左侧导航相关
        self.nav_tree: QTreeWidget | None = None
        self.nav_search: QLineEdit | None = None
        self.nav_container: QFrame | None = None

        # 右侧：功能 Tab 区域
        self.tab_widget: QTabWidget | None = None

        # 右侧：占位首页 + Tab 区域（Stack）
        self.right_stack: QStackedWidget | None = None
        self.home_page: QWidget | None = None

        # 头部搜索框
        self.search_edit: QLineEdit | None = None

        # 记录“菜单路径 -> 页面 widget”的映射
        self.page_tab_map: dict[str, QWidget] = {}

        # 登录状态
        self.logged_in: bool = False
        self.current_user: str = ""
        self.user_label: QLabel | None = None
        self.btn_login: QPushButton | None = None

        self.init_ui()

    # ================== 整体 UI ================== #
    def init_ui(self):
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        # 1. 头部
        header = self.create_header()
        central_layout.addWidget(header, 1)

        # 2. 中部：左侧导航面板（搜索框+树） + 右侧内容区

        # ---- 左侧：导航面板 ----
        self.nav_container = QFrame()
        self.nav_container.setObjectName("NavContainer")
        self.nav_container.setMinimumWidth(200)
        self.nav_container.setStyleSheet("""
            QFrame#NavContainer {
                background-color: #004a80;
            }
        """)

        nav_layout = QVBoxLayout(self.nav_container)
        nav_layout.setContentsMargins(6, 6, 6, 6)
        nav_layout.setSpacing(4)

        # 顶部搜索框
        self.nav_search = QLineEdit()
        self.nav_search.setPlaceholderText("菜单搜索：支持菜单名称、路径")
        self.nav_search.setClearButtonEnabled(True)
        self.nav_search.setFixedHeight(26)
        self.nav_search.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255,255,255,0.10);
                border: 1px solid rgba(255,255,255,0.35);
                border-radius: 4px;
                padding-left: 8px;
                color: #ffffff;
            }
            QLineEdit:focus {
                background-color: rgba(255,255,255,0.18);
                border: 1px solid rgba(255,255,255,0.65);
                color: #ffffff;
            }
        """)
        nav_layout.addWidget(self.nav_search)

        # 树菜单本体
        self.nav_tree = QTreeWidget()
        self.nav_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.nav_tree.setTextElideMode(Qt.ElideRight)
        self.nav_tree.setHeaderHidden(True)
        self.nav_tree.setStyleSheet("""
        QTreeWidget {
            background-color: #004a80;
            color: #ffffff;
            border: none;
        }
        QTreeWidget::viewport { background-color: #004a80; }

        QTreeWidget::item { height: 26px; }

        /* 鼠标悬停可以保留淡淡高亮（可选） */
        QTreeWidget::item:hover { background-color: rgba(255,255,255,0.10); }

        /* ✅ 选中：背景保持不变，只改文字颜色为红 */
        QTreeWidget::item:selected {
            background: transparent;
            color: #ff3b30;        /* 红色，你也可以换成 #ff0000 */
        }

        /* ✅ 防止失焦时又变回去 */
        QTreeWidget::item:selected:!active {
            background: transparent;
            color: #ff3b30;
        }
        QTreeWidget::item:focus {
            outline: none;
        }
        QTreeWidget::focus {
            outline: none;
        }
        """)
        nav_layout.addWidget(self.nav_tree, 1)

        # ---- 右侧：占位首页 + tab 控件（不把首页放进 Tab） ----
        self.home_page = HomePage(self)

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.tabCloseRequested.connect(self.on_tab_close_requested)
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: #ffffff;
            }
            QTabBar::tab {
                height: 28px;
                padding: 4px 16px;
            }
        """)

        # 用 Stack 把“首页背景图”与“多标签页”分离
        self.right_stack = QStackedWidget()
        self.right_stack.addWidget(self.home_page)   # index 0: 首页背景
        self.right_stack.addWidget(self.tab_widget)  # index 1: 功能页面 Tabs
        self.right_stack.setCurrentWidget(self.home_page)

        self.nav_container.setMaximumWidth(360)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.nav_container)
        splitter.addWidget(self.right_stack)
        splitter.setStretchFactor(0, 1)   # 左:右 = 1:3
        splitter.setStretchFactor(1, 5)

        central_layout.addWidget(splitter, 9)
        self.setCentralWidget(central)

        # ===== 底部状态栏（蓝色）=====
        status = QStatusBar(self)
        status.setSizeGripEnabled(False)
        status.setFixedHeight(52)  # 高度你可调：44~60
        status.setStyleSheet("""
        QStatusBar {
            background-color: #004a80;
            color: white;
            border-top: 2px solid #0a5f98;
        }
        QStatusBar::item { border: none; }
        """)

        lbl = QLabel("状态栏")
        lbl.setStyleSheet("""
        QLabel {
            color: white;
            background: rgba(255,255,255,0.10);
            border: 1px solid rgba(255,255,255,0.45);
            border-radius: 10px;
            padding: 10px 22px;
            margin-left: 14px;
            font-size: 16px;
            font-weight: bold;
        }
        """)

        status.addWidget(lbl)  # 左侧
        self.setStatusBar(status)

        splitter.setSizes([300, 1000])
        QTimer.singleShot(0, lambda: splitter.setSizes([300, max(1, self.width() - 300)]))

        # 构建左侧导航树
        self.build_nav_tree()

        self.nav_tree.header().setSectionResizeMode(0, QHeaderView.Fixed)
        self.nav_tree.setColumnWidth(0, 260)  # 左侧文字显示宽度（调这个就行）
        self.nav_tree.setTextElideMode(Qt.ElideRight)  # 太长就…省略号
        self.nav_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # 信号连接
        self.nav_tree.itemClicked.connect(self.on_nav_item_clicked)
        if self.nav_search is not None:
            self.nav_search.textChanged.connect(self.filter_nav_tree)
        if self.search_edit is not None:
            self.search_edit.textChanged.connect(self.filter_nav_tree)

        # 默认显示首页背景（不在 Tab 栏显示“首页”）
        self.open_home_tab()

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

        # logo
        logo_label = QLabel()
        base_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(base_dir, "pict", "logo.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(28, 28, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                logo_label.setPixmap(pixmap)
        logo_label.setFixedSize(30, 30)

        title = QLabel("海上平台结构载荷管理系统")
        title.setStyleSheet("font-size:18px; font-weight:bold;")

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("菜单搜索：支持菜单名称、路径")
        self.search_edit.setMaximumWidth(320)

        # 用户 + 登录按钮
        self.user_label = QLabel("未登录")
        self.btn_login = QPushButton("登录/注销")
        self.btn_login.clicked.connect(self.on_login_logout)

        btn_settings = QPushButton("设置")
        btn_notice = QPushButton("通知")
        btn_lang = QPushButton("语言")

        layout.addWidget(logo_label)
        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(self.search_edit)
        layout.addStretch()
        layout.addWidget(self.user_label)
        layout.addWidget(self.btn_login)
        layout.addWidget(btn_settings)
        layout.addWidget(btn_notice)
        layout.addWidget(btn_lang)

        return header

    # ================== 构建导航树 ================== #
    def build_nav_tree(self):
        self.nav_tree.clear()
        self.page_tab_map.clear()

        def add_nodes(config_list, parent_item=None, parent_path: str = ""):
            for node in config_list:
                text = node.get("text", "未命名")
                path = f"{parent_path}/{text}" if parent_path else text

                item = QTreeWidgetItem([text])
                if parent_item is None:
                    self.nav_tree.addTopLevelItem(item)
                else:
                    parent_item.addChild(item)

                # 保存路径 key
                item.setData(0, Qt.UserRole + 1, path)

                # 叶子菜单：存页面类
                page_cls = node.get("page")
                if page_cls is not None:
                    item.setData(0, Qt.UserRole, page_cls)

                children = node.get("children")
                if children:
                    add_nodes(children, item, path)

        add_nodes(NAV_CONFIG)

        self.nav_tree.expandAll()
        self.nav_tree.expandToDepth(0)

    # ================== 首页显示（不进入 Tab） ================== #
    def open_home_tab(self):
        """显示首页背景（不在 Tab 栏出现“首页”标签）。"""
        if self.right_stack is None or self.home_page is None:
            return
        self.right_stack.setCurrentWidget(self.home_page)

    # ================== 默认打开第一个菜单页（备用，不再默认调用） ================== #
    def open_first_leaf_page(self):
        first_leaf = None

        def dfs_find_leaf(item: QTreeWidgetItem):
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

        # 打开任何功能页面时，切换到 Tab 区域
        if self.right_stack is not None and self.tab_widget is not None:
            self.right_stack.setCurrentWidget(self.tab_widget)

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
        page_cls = item.data(0, Qt.UserRole)
        if page_cls is not None:
            self.open_page_for_item(item)
        else:
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

        # 如果所有功能页都关了，回到首页背景
        if self.tab_widget.count() == 0:
            self.open_home_tab()

    # ================== 导航搜索过滤 ================== #
    def filter_nav_tree(self, text: str):
        text = text.strip().lower()
        for i in range(self.nav_tree.topLevelItemCount()):
            item = self.nav_tree.topLevelItem(i)
            self._filter_nav_item(item, text)

    def _filter_nav_item(self, item: QTreeWidgetItem, text: str) -> bool:
        if not text:
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

    # ================== 登录 / 注销 ================== #
    def on_login_logout(self):
        if not self.logged_in:
            # ---- 登录 ----
            dlg = LoginDialog(self)
            result = dlg.exec_()
            if result == dlg.Accepted:
                # LoginDialog 内部已做用户名/密码校验
                username = getattr(dlg, "username", "工程师1")
                self.logged_in = True
                self.current_user = username
                self.user_label.setText(username)
                self.btn_login.setText("注销")
                self.open_personal_center_page()

                # ✅ 登录只弹框 + 更新状态，不强制跳转页面
        else:
            # ---- 注销 ----
            self.logged_in = False
            self.current_user = ""
            self.user_label.setText("未登录")
            self.btn_login.setText("登录/注销")
            # 注销后回到首页背景
            self.open_home_tab()

    def open_personal_center_page(self):
        """
        在左侧树中寻找“个人中心”节点并打开；
        如果 nav_config 里没有，就直接创建一个 Tab。
        """
        # 切换到 Tab 区域
        if self.right_stack is not None and self.tab_widget is not None:
            self.right_stack.setCurrentWidget(self.tab_widget)

        target_item = None

        def dfs(item: QTreeWidgetItem):
            nonlocal target_item
            if target_item is not None:
                return
            if item.text(0) == "个人中心" and item.data(0, Qt.UserRole) is not None:
                target_item = item
                return
            for i in range(item.childCount()):
                dfs(item.child(i))

        for i in range(self.nav_tree.topLevelItemCount()):
            dfs(self.nav_tree.topLevelItem(i))
            if target_item is not None:
                break

        if target_item is not None:
            self.nav_tree.setCurrentItem(target_item)
            self.open_page_for_item(target_item)
        else:
            # 兜底：没有在树里配置时，手动开一个 Tab
            page = PersonalCenterPage(self)
            index = self.tab_widget.addTab(page, "个人中心")
            self.tab_widget.setCurrentIndex(index)

    # ================== 业务：新增特检策略 ================== #
    def open_new_special_strategy_tab(self, facility_code: str):
        # 切换到 Tab 区域
        if self.right_stack is not None and self.tab_widget is not None:
            self.right_stack.setCurrentWidget(self.tab_widget)

        tab_title = f"{facility_code} - 特检策略"
        page = NewSpecialInspectionPage(facility_code, self)
        index = self.tab_widget.addTab(page, tab_title)
        self.tab_widget.setTabIcon(index, QIcon('./pict/logo.png'))
        self.tab_widget.setCurrentIndex(index)

    # ================== 业务：风险更新结果 ================== #
    def open_upgrade_special_inspection_result_tab(self, facility_code: str):
        # 切换到 Tab 区域
        if self.right_stack is not None and self.tab_widget is not None:
            self.right_stack.setCurrentWidget(self.tab_widget)

        tab_title = f"{facility_code}更新风险结果"
        page = UpgradeSpecialInspectionResultPage(facility_code, self)
        index = self.tab_widget.addTab(page, tab_title)
        self.tab_widget.setCurrentIndex(index)

    # 供子页面调用，关闭当前 Tab
    def close_current_tab(self):
        current_index = self.tab_widget.currentIndex()
        if current_index >= 0:
            self.on_tab_close_requested(current_index)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
