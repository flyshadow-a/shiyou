# -*- coding: utf-8 -*-
# pages/login_dialog.py
from __future__ import annotations

import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QFrame,
    QVBoxLayout,
)

from core.auth import AuthError, AuthService, UserSession
from pages.register_dialog import RegisterDialog


class LoginDialog(QDialog):
    def __init__(self, parent=None, auth_service: AuthService | None = None):
        super().__init__(parent)
        self.auth_service = auth_service or AuthService()
        self.session: UserSession | None = None
        self.username = ""
        self.setWindowTitle("登录")
        self.setWindowModality(Qt.WindowModal)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._build_ui()

    def _build_ui(self) -> None:
        self.resize(620, 430)
        self.setObjectName("LoginDialog")
        self.setStyleSheet(self._dialog_style())

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.bg_label = QLabel(self)
        self.bg_label.setObjectName("LoginBg")
        self.bg_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.bg_label)

        card = QFrame(self.bg_label)
        card.setObjectName("AuthCard")
        card.setFixedWidth(390)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(34, 30, 34, 30)
        card_layout.setSpacing(16)

        self.card = card

        title = QLabel("用户登录", self)
        title.setObjectName("AuthTitle")
        title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title)

        subtitle = QLabel("海上平台结构载荷管理系统", self)
        subtitle.setObjectName("AuthSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(subtitle)

        form_layout = QVBoxLayout()
        form_layout.setSpacing(14)

        self.user_edit = QLineEdit(self)
        self.user_edit.setPlaceholderText("请输入用户名")
        form_layout.addWidget(self.user_edit)

        pwd_layout = QHBoxLayout()
        pwd_layout.setSpacing(8)
        self.pwd_edit = QLineEdit(self)
        self.pwd_edit.setPlaceholderText("请输入密码")
        self.pwd_edit.setEchoMode(QLineEdit.Password)
        self.pwd_edit.returnPressed.connect(self._on_login_clicked)
        self.toggle_pwd_btn = QPushButton("显示", self)
        self.toggle_pwd_btn.setObjectName("GhostButton")
        self.toggle_pwd_btn.setFixedWidth(58)
        self.toggle_pwd_btn.clicked.connect(lambda: self._toggle_password(self.pwd_edit, self.toggle_pwd_btn))
        pwd_layout.addWidget(self.pwd_edit)
        pwd_layout.addWidget(self.toggle_pwd_btn)
        form_layout.addLayout(pwd_layout)
        card_layout.addLayout(form_layout)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        self.login_btn = QPushButton("登录", self)
        self.login_btn.setObjectName("PrimaryButton")
        self.register_btn = QPushButton("注册", self)
        self.register_btn.setObjectName("SecondaryButton")
        self.cancel_btn = QPushButton("取消", self)
        self.cancel_btn.setObjectName("GhostButton")
        self.login_btn.clicked.connect(self._on_login_clicked)
        self.register_btn.clicked.connect(self._on_register_clicked)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.login_btn)
        btn_layout.addWidget(self.register_btn)
        btn_layout.addWidget(self.cancel_btn)
        card_layout.addLayout(btn_layout)

        self.card.adjustSize()
        self._refresh_background()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_background()

    def _refresh_background(self) -> None:
        if not hasattr(self, "bg_label"):
            return
        self.bg_label.setFixedSize(self.size())
        bg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pict", "home_bg.png")
        if os.path.exists(bg_path):
            pixmap = QPixmap(bg_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                x = max(0, (scaled.width() - self.width()) // 2)
                y = max(0, (scaled.height() - self.height()) // 2)
                self.bg_label.setPixmap(scaled.copy(x, y, self.width(), self.height()))
        if hasattr(self, "card"):
            self.card.move((self.width() - self.card.width()) // 2, (self.height() - self.card.height()) // 2)

    @staticmethod
    def _toggle_password(edit: QLineEdit, button: QPushButton) -> None:
        if edit.echoMode() == QLineEdit.Password:
            edit.setEchoMode(QLineEdit.Normal)
            button.setText("隐藏")
        else:
            edit.setEchoMode(QLineEdit.Password)
            button.setText("显示")

    @staticmethod
    def _dialog_style() -> str:
        return """
            QDialog#LoginDialog { background-color: #004a80; }
            QFrame#AuthCard {
                background-color: rgba(255, 255, 255, 205);
                border: 1px solid rgba(255, 255, 255, 150);
                border-radius: 24px;
            }
            QLabel#AuthTitle {
                color: #17324d;
                font-size: 24px;
                font-weight: 800;
            }
            QLabel#AuthSubtitle {
                color: #526579;
                font-size: 13px;
                padding-bottom: 8px;
            }
            QLineEdit {
                min-height: 38px;
                border: 1px solid #c9d7e6;
                border-radius: 12px;
                padding: 0 14px;
                background-color: #f8fbff;
                color: #172536;
                font-size: 14px;
            }
            QLineEdit:focus { border: 1px solid #1f78c8; background-color: #ffffff; }
            QPushButton {
                min-height: 36px;
                border-radius: 12px;
                padding: 0 16px;
                font-size: 14px;
            }
            QPushButton#PrimaryButton { background-color: #006bb3; color: white; border: none; font-weight: 700; }
            QPushButton#PrimaryButton:hover { background-color: #0782d4; }
            QPushButton#SecondaryButton { background-color: #eaf4ff; color: #075f9f; border: 1px solid #bcd8f2; }
            QPushButton#SecondaryButton:hover { background-color: #d9ecff; }
            QPushButton#GhostButton { background-color: rgba(255,255,255,0.72); color: #42566b; border: 1px solid #d4dfeb; }
            QPushButton#GhostButton:hover { background-color: #ffffff; }
        """

    def _on_login_clicked(self) -> None:
        try:
            session = self.auth_service.authenticate_user(
                self.user_edit.text(),
                self.pwd_edit.text(),
                client_info="PyQt5 desktop",
            )
        except AuthError as exc:
            QMessageBox.warning(self, "登录失败", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "登录失败", f"登录时发生错误：\n{exc}")
            return

        self.session = session
        self.username = session.display_name or session.username
        self.accept()

    def _on_register_clicked(self) -> None:
        dlg = RegisterDialog(self.auth_service, self)
        if dlg.exec_() == dlg.Accepted and dlg.registered_username:
            self.user_edit.setText(dlg.registered_username)
            self.pwd_edit.clear()
            self.pwd_edit.setFocus()
