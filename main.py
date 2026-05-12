# -*- coding: utf-8 -*-
# main.py

import sys
import os
import ctypes

from vtkmodules.vtkCommonCore import vtkObject, vtkLogger

# 关闭 VTK 全局 warning/error 显示
vtkObject.GlobalWarningDisplayOff()
# 关闭写到 stderr 的 VTK 日志
vtkLogger.SetStderrVerbosity(vtkLogger.VERBOSITY_OFF)

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QIcon, QFont, QFontDatabase, QColor, QBrush
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QTabWidget, QStackedWidget, QLabel, QLineEdit,
    QPushButton, QSplitter, QFrame, QMessageBox
)

from core.auth import AuthService, UserSession
from pages.nav_config import NAV_CONFIG

# 业务页面 / 对话框
from pages.new_special_inspection_page import NewSpecialInspectionPage
from pages.upgrade_special_inspection_result_page import UpgradeSpecialInspectionResultPage
from pages.home_page import HomePage
from pages.personal_center_page import PersonalCenterPage
from pages.login_dialog import LoginDialog
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QHeaderView
from PyQt5.QtWidgets import QStatusBar


# ==========================================
WINDOWS_SONGTI_FONT_CANDIDATES = [
    "SimSun",
    "NSimSun",
    "宋体",
    "Microsoft YaHei UI",
    "Microsoft YaHei",
]
WINDOWS_APP_USER_MODEL_ID = "shiyou.platform.load.management"


def pick_windows_compatible_zh_font() -> str:
    """优先宋体，回退到 Windows 常见中文字体（Win10/Win11）。"""
    families = {name.lower(): name for name in QFontDatabase().families()}
    for name in WINDOWS_SONGTI_FONT_CANDIDATES:
        hit = families.get(name.lower())
        if hit:
            return hit
    return QFont().defaultFamily()


# ==========================================
def get_resource_path(relative_path):
    """
    获取资源的绝对路径。
    开发环境：使用当前文件所在目录 + 相对路径
    打包环境：使用 sys._MEIPASS + 相对路径
    """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 打包后的临时解压目录
        base_path = sys._MEIPASS
    else:
        # 开发环境：使用当前 main.py 所在的目录
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)

# ==========================================

def get_external_path(relative_path):
    if getattr(sys, 'frozen', False):
        #如果是打包后的 exe，使用 exe 所在的真实目录
        base_path = os.path.dirname(sys.executable)
    else:
        # 开发环境
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# ==========================================


def load_app_icon() -> QIcon:
    for relative_path in ("logo.ico", os.path.join("pict", "logo.png")):
        icon_path = get_resource_path(relative_path)
        if not os.path.exists(icon_path):
            continue
        icon = QIcon(icon_path)
        if not icon.isNull():
            return icon
    return QIcon()


def set_windows_app_user_model_id() -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(WINDOWS_APP_USER_MODEL_ID)
    except Exception:
        pass


# ==========================================


def maybe_run_auxiliary_worker() -> int | None:
    worker_flag = "--report-image-export-worker"
    if worker_flag not in sys.argv:
        return None

    filtered_argv = [sys.argv[0], *[arg for arg in sys.argv[1:] if arg != worker_flag]]
    original_argv = list(sys.argv)
    try:
        sys.argv = filtered_argv
        from services.report_image_batch_export_process import main as export_worker_main

        return int(export_worker_main())
    finally:
        sys.argv = original_argv


# ==========================================

class MainWindow(QMainWindow):
    def __init__(self, auth_service: AuthService, session: UserSession | None = None):
        super().__init__()
        self.auth_service = auth_service
        self.session: UserSession | None = session
        self.setWindowTitle("海上平台结构载荷管理系统")
        app_icon = load_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)
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


        # 记录“菜单路径 -> 页面 widget”的映射
        self.page_tab_map: dict[str, QWidget] = {}

        # 登录状态
        self.logged_in: bool = session is not None
        self.current_user: str = (session.display_name or session.username) if session is not None else ""
        self.user_label: QLabel | None = None
        self.btn_login: QPushButton | None = None
        self.current_platform_label: QLabel | None = None
        self.current_platform_font_ratio: float = 0.0125
        self.init_ui()

    def require_login(self) -> bool:
        if self.logged_in and self.session is not None:
            return True
        dlg = LoginDialog(auth_service=self.auth_service)
        if dlg.exec_() == dlg.Accepted and dlg.session is not None:
            self._apply_login_session(dlg.session)
            return True
        return False

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
        self.nav_search.setFixedHeight(32)
        self.nav_search.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255,255,255,0.10);
                border: 1px solid rgba(255,255,255,0.35);
                border-radius: 4px;
                padding-left: 10px;
                color: #ffffff;
                font-size: 15px;
            }
            QLineEdit:focus {
                background-color: rgba(255,255,255,0.18);
                border: 1px solid rgba(255,255,255,0.65);
                color: #ffffff;
            }
        """)
        nav_search_font = QFont(self.nav_search.font())
        nav_search_font.setPixelSize(15)
        self.nav_search.setFont(nav_search_font)
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
            font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
            font-size: 12pt;
        }
        QTreeWidget::viewport { background-color: #004a80; }

        QTreeWidget::item { height: 36px; }
        QTreeWidget::item:disabled { color: #9ca3af; }

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
        nav_tree_font = QFont(self.nav_tree.font())
        nav_tree_font.setFamily(pick_windows_compatible_zh_font())
        nav_tree_font.setPointSize(12)
        self.nav_tree.setFont(nav_tree_font)
        nav_layout.addWidget(self.nav_tree, 1)

        # ---- 右侧：占位首页 + tab 控件（不把首页放进 Tab） ----
        self.home_page = HomePage(self)

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.tabCloseRequested.connect(self.on_tab_close_requested)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: #ffffff;
            }
            QTabBar::tab {
                height: 42px;
                padding: 6px 20px;
                font-size: 12pt;
                font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
                font-weight: 600;
                color: #1f2937;
                background: #f4f4f4;
                border: 1px solid #d1d5db;
                border-bottom: none;
                margin-right: 1px;
            }
            QTabBar::tab:hover:!selected {
                background: #eef6ff;
            }
            QTabBar::tab:selected {
                color: #004a80;
                background: #dcefff;
                border-color: #9ec8ef;
            }
            QTabBar::tab:selected:!active {
                color: #004a80;
                background: #dcefff;
                border-color: #9ec8ef;
            }
        """)
        tab_font = QFont(self.tab_widget.tabBar().font())
        tab_font.setFamily(pick_windows_compatible_zh_font())
        tab_font.setPointSize(12)
        tab_font.setBold(True)
        self.tab_widget.tabBar().setFont(tab_font)

        # 用 Stack 把“首页背景图”与“多标签页”分离
        self.right_stack = QStackedWidget()
        self.right_stack.addWidget(self.home_page)   # index 0: 首页背景
        self.right_stack.addWidget(self.tab_widget)  # index 1: 功能页面 Tabs
        self.right_stack.setCurrentWidget(self.home_page)
        self.set_current_platform_name("")
        self._update_header_font_scale()

        self.nav_container.setMaximumWidth(380)

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

        self.setStatusBar(status)

        splitter.setSizes([300, 1000])
        QTimer.singleShot(0, lambda: splitter.setSizes([300, max(1, self.width() - 300)]))

        # 构建左侧导航树
        self.build_nav_tree()

        self.nav_tree.header().setSectionResizeMode(0, QHeaderView.Fixed)
        self.nav_tree.setColumnWidth(0, 280)  # 左侧文字显示宽度（调这个就行）
        self.nav_tree.setTextElideMode(Qt.ElideRight)  # 太长就…省略号
        self.nav_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # 信号连接
        self.nav_tree.itemClicked.connect(self.on_nav_item_clicked)
        if self.nav_search is not None:
            self.nav_search.textChanged.connect(self.filter_nav_tree)


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
        logo_path = get_resource_path(os.path.join("pict", "logo.png"))
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(42, 42, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                logo_label.setPixmap(pixmap)
        logo_label.setFixedSize(44, 44)

        title = QLabel("海上平台结构载荷管理系统")
        title.setStyleSheet("font-size: 12pt; font-weight: 800;")
        self.current_platform_label = QLabel("--")
        self.current_platform_label.setAlignment(Qt.AlignCenter)
        self.current_platform_label.setStyleSheet("""
            QLabel {
                color: #eaf6ff;
                background-color: rgba(255,255,255,0.08);
                border: 1px solid rgba(255,255,255,0.18);
                border-radius: 14px;
                padding: 8px 18px;
                font-weight: bold;
                min-width: 320px;
            }
        """)
        self.current_platform_label.setText("")
        self.current_platform_label.hide()

        # 用户 + 登录按钮
        self.user_label = QLabel(self.session.display_label if self.session is not None else "未登录")
        self.btn_login = QPushButton("退出" if self.logged_in else "登录/退出")
        self.btn_login.clicked.connect(self.on_login_logout)

        layout.addWidget(logo_label)
        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(self.current_platform_label, 0, Qt.AlignCenter)
        layout.addStretch()
        layout.addWidget(self.user_label)
        layout.addWidget(self.btn_login)

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
                item_font = QFont(self.nav_tree.font())
                if parent_item is None:
                    item_font.setBold(True)
                else:
                    item_font.setBold(False)
                item.setFont(0, item_font)
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

                if node.get("disabled"):
                    item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                    item.setForeground(0, QBrush(QColor("#9ca3af")))

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
        if self.current_platform_label is not None:
            self.current_platform_label.hide()
            self.current_platform_label.setText("")

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
        if not self.logged_in or self.session is None:
            dlg = LoginDialog(self, auth_service=self.auth_service)
            if dlg.exec_() == dlg.Accepted and dlg.session is not None:
                self._apply_login_session(dlg.session)
            else:
                return

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
            setattr(widget, "_nav_path", path)
            index = self.tab_widget.indexOf(widget)
            if index != -1:
                self.tab_widget.setCurrentIndex(index)
                self._sync_current_platform_from_widget(widget)
                return

        # 未打开：新建一个页面
        page = page_cls(self)
        setattr(page, "_nav_path", path)
        index = self.tab_widget.addTab(page, text)
        self.page_tab_map[path] = page
        self.tab_widget.setCurrentIndex(index)
        self._sync_current_platform_from_widget(page)

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
        else:
            self._sync_current_platform_from_widget(self.tab_widget.currentWidget())

    # ================== 导航搜索过滤 ================== #
    def filter_nav_tree(self, text: str):
        text = text.strip().lower()
        for i in range(self.nav_tree.topLevelItemCount()):
            item = self.nav_tree.topLevelItem(i)
            self._filter_nav_item(item, text)

    def on_tab_changed(self, index: int):
        if self.tab_widget is None or index < 0:
            self.set_current_platform_name("")
            return
        self._sync_current_platform_from_widget(self.tab_widget.widget(index))

    def set_current_platform_name(self, name: str):
        if self.current_platform_label is None:
            return

        active_widget = self._get_active_content_widget()
        if not self._is_file_management_widget(active_widget):
            self.current_platform_label.hide()
            self.current_platform_label.setText("")
            return

        text = name.strip() if name else ""
        self.current_platform_label.setText(text)
        self._update_header_font_scale()
        self._refresh_platform_header_visibility()

    def _update_header_font_scale(self):
        if self.current_platform_label is None:
            return

        font_size = max(11.0, min(20.0, self.width() * self.current_platform_font_ratio))
        font = self.current_platform_label.font()
        font.setPointSizeF(font_size)
        self.current_platform_label.setFont(font)

    def _is_file_management_widget(self, widget: QWidget | None) -> bool:
        if widget is None:
            return False

        if widget.__class__.__name__ in {
            "ConstructionDocsPage",
            "HistoryRebuildFilesPage",
            "HistoryEventsInspectionPage",
            "ModelFilesPage",
        }:
            return True

        path = getattr(widget, "_nav_path", "")
        return isinstance(path, str) and path.startswith("文件管理")

    def _get_active_content_widget(self) -> QWidget | None:
        if self.right_stack is None or self.tab_widget is None:
            return None
        if self.right_stack.currentWidget() is not self.tab_widget:
            return None
        return self.tab_widget.currentWidget()

    def _refresh_platform_header_visibility(self):
        if self.current_platform_label is None:
            return

        active_widget = self._get_active_content_widget()
        label_text = self.current_platform_label.text().strip()
        if self._is_file_management_widget(active_widget) and label_text:
            self.current_platform_label.show()
            return

        self.current_platform_label.hide()
        self.current_platform_label.setText("")

    def _sync_current_platform_from_widget(self, widget: QWidget | None):
        active_widget = self._get_active_content_widget()
        if active_widget is not None:
            widget = active_widget

        if widget is None or not self._is_file_management_widget(widget):
            if self.current_platform_label is not None:
                self.current_platform_label.hide()
                self.current_platform_label.setText("")
            return

        getter = getattr(widget, "get_current_platform_name", None)
        if callable(getter):
            try:
                self.set_current_platform_name(getter())
                return
            except Exception:
                pass

        self.set_current_platform_name("")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_header_font_scale()

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
            dlg = LoginDialog(self, auth_service=self.auth_service)
            if dlg.exec_() == dlg.Accepted and dlg.session is not None:
                self._apply_login_session(dlg.session)
                self.open_personal_center_page()
            return

        if QMessageBox.question(self, "确认退出", "确定要退出当前账号吗？") != QMessageBox.Yes:
            return
        self._clear_open_tabs()
        self.logged_in = False
        self.current_user = ""
        self.session = None
        self.user_label.setText("未登录")
        self.btn_login.setText("登录/退出")
        self.open_home_tab()
        self.hide()

        dlg = LoginDialog(auth_service=self.auth_service)
        if dlg.exec_() == dlg.Accepted and dlg.session is not None:
            self._apply_login_session(dlg.session)
            self.show()
            self.open_personal_center_page()
        else:
            self.close()

    def _apply_login_session(self, session: UserSession):
        self.session = session
        self.logged_in = True
        self.current_user = session.display_name or session.username
        self.user_label.setText(session.display_label)
        self.btn_login.setText("退出")

    def _clear_open_tabs(self):
        if self.tab_widget is None:
            return
        while self.tab_widget.count() > 0:
            widget = self.tab_widget.widget(0)
            self.tab_widget.removeTab(0)
            if widget is not None:
                widget.deleteLater()
        self.page_tab_map.clear()

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
            self._sync_current_platform_from_widget(page)

    # ================== 业务：新增特检策略 ================== #
    def open_new_special_strategy_tab(self, facility_code: str):
        # 切换到 Tab 区域
        if self.right_stack is not None and self.tab_widget is not None:
            self.right_stack.setCurrentWidget(self.tab_widget)

        tab_title = f"{facility_code} - 特检策略"
        page = NewSpecialInspectionPage(facility_code, self)
        if hasattr(page, "strategy_calculated"):
            page.strategy_calculated.connect(self._on_special_strategy_calculated)
        index = self.tab_widget.addTab(page, tab_title)
        # self.tab_widget.setTabIcon(index, QIcon('./pict/logo.png'))
        self.tab_widget.setCurrentIndex(index)
        self._sync_current_platform_from_widget(page)

    # ================== 业务：风险更新结果 ================== #
    def open_upgrade_special_inspection_result_tab(self, facility_code: str, run_id: int | None = None):
        # 切换到 Tab 区域
        if self.right_stack is not None and self.tab_widget is not None:
            self.right_stack.setCurrentWidget(self.tab_widget)

        tab_title = f"{facility_code}更新风险结果"
        page = UpgradeSpecialInspectionResultPage(facility_code, self, run_id=run_id)
        index = self.tab_widget.addTab(page, tab_title)
        self.tab_widget.setCurrentIndex(index)
        self._sync_current_platform_from_widget(page)

    # 供子页面调用，关闭当前 Tab
    def _on_special_strategy_calculated(self, facility_code: str, run_id: object = None):
        for widget in self.page_tab_map.values():
            if widget.__class__.__name__ != "SpecialInspectionStrategy":
                continue
            refresh = getattr(widget, "refresh_runtime_summary", None)
            if callable(refresh):
                refresh(facility_code=facility_code, run_id=run_id, sync_dropdown=True)

    def close_current_tab(self):
        current_index = self.tab_widget.currentIndex()
        if current_index >= 0:
            self.on_tab_close_requested(current_index)


def main():
    set_windows_app_user_model_id()
    # 开启高 DPI 自动缩放
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    # 开启高 DPI 图片自适应
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    # 新机器上 PyVista/VTK 的 OpenGL 上下文不稳定时，优先走软件渲染，
    # 避免打开含 3D 预览的页面时直接导致整个进程退出。
    QApplication.setAttribute(Qt.AA_UseSoftwareOpenGL, True)
    # 针对某些 Qt 版本的额外环境变量配置
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    os.environ.setdefault("QT_OPENGL", "software")

    app = QApplication(sys.argv)
    app_icon = load_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)
    try:
        auth_service = AuthService()
    except Exception as exc:
        QMessageBox.critical(None, "数据库连接失败", f"初始化用户认证服务失败：\n{exc}")
        sys.exit(1)

    login_dialog = LoginDialog(auth_service=auth_service)
    if not app_icon.isNull():
        login_dialog.setWindowIcon(app_icon)
    if login_dialog.exec_() != login_dialog.Accepted or login_dialog.session is None:
        sys.exit(0)

    window = MainWindow(auth_service, login_dialog.session)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    worker_exit_code = maybe_run_auxiliary_worker()
    if worker_exit_code is not None:
        sys.exit(worker_exit_code)
    main()
