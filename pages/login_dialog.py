# -*- coding: utf-8 -*-
# pages/login_dialog.py

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox
)


class LoginDialog(QDialog):
    """
    登录对话框，单独成文件，逻辑简单清晰：
    - 用户名：工程师1
    - 密码：123456
    其它用户名密码直接提示失败。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("登录")
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        self.resize(420, 260)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 30, 40, 30)
        main_layout.setSpacing(20)

        # 顶部人形图标（用大号文字代替也可以）
        icon_label = QLabel("👤", self)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_font = icon_label.font()
        icon_font.setPointSize(32)
        icon_label.setFont(icon_font)
        main_layout.addWidget(icon_label)

        # 表单区域
        form_layout = QVBoxLayout()
        form_layout.setSpacing(12)

        # 用户名
        user_layout = QHBoxLayout()
        user_layout.addWidget(QLabel("用户名：", self))
        self.user_edit = QLineEdit(self)
        user_layout.addWidget(self.user_edit)
        form_layout.addLayout(user_layout)

        # 密码
        pwd_layout = QHBoxLayout()
        pwd_layout.addWidget(QLabel("密  码：", self))
        self.pwd_edit = QLineEdit(self)
        self.pwd_edit.setEchoMode(QLineEdit.Password)
        pwd_layout.addWidget(self.pwd_edit)
        form_layout.addLayout(pwd_layout)

        main_layout.addLayout(form_layout)

        # 登录按钮
        self.login_btn = QPushButton("登录", self)
        self.login_btn.setFixedWidth(120)
        self.login_btn.clicked.connect(self._on_login_clicked)
        main_layout.addWidget(self.login_btn, alignment=Qt.AlignCenter)

    # -------------------------------------------------
    #  登录逻辑
    # -------------------------------------------------
    def _on_login_clicked(self):
        username = self.user_edit.text().strip()
        password = self.pwd_edit.text().strip()

        if username == "工程师1" and password == "123456":
            self.accept()  # 由主窗口处理登录成功后的跳转
        else:
            QMessageBox.warning(self, "登录失败", "用户名或密码错误！")
