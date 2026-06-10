# -*- coding: utf-8 -*-
# pages/login_dialog.py
from __future__ import annotations

import os

from PyQt5.QtCore import QSettings, QStringListModel, Qt
from PyQt5.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (
    QCheckBox,
    QCompleter,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from core.auth import AuthError, AuthService, UserSession
from core.dialog_utils import exec_dialog_safely
from pages.register_dialog import RegisterDialog


class LoginDialog(QDialog):
    SETTINGS_ORG = "Shiyou"
    SETTINGS_APP = "PlatformLoadManager"
    CONTROL_WIDTH = 280
    LOGIN_BUTTON_WIDTH = 280
    _session_remember_password = False
    _session_username = ""
    _session_password = ""

    def __init__(self, parent=None, auth_service: AuthService | None = None):
        super().__init__(parent)
        self.auth_service = auth_service or AuthService()
        self.settings = QSettings(self.SETTINGS_ORG, self.SETTINGS_APP)
        self.session: UserSession | None = None
        self.username = ""
        self.setWindowTitle("登录")
        self.setWindowModality(Qt.WindowModal)
        self.setWindowFlags(
            (self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
        )
        self._build_ui()

    def _build_ui(self) -> None:
        self.resize(760, 560)
        self.setMinimumSize(760, 560)
        self.setObjectName("LoginDialog")
        self.setStyleSheet(self._dialog_style())

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(60, 40, 60, 40)
        main_layout.setSpacing(0)

        self.stage = QFrame(self)
        self.stage.setObjectName("LoginStage")
        main_layout.addWidget(self.stage)

        self.bg_label = QLabel(self)
        self.bg_label.setObjectName("LoginBg")
        self.bg_label.setAlignment(Qt.AlignCenter)
        self.bg_label.lower()

        card = QFrame(self.stage)
        card.setObjectName("AuthCard")
        card.setFixedWidth(400)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 24, 28, 24)
        card_layout.setSpacing(12)

        self.card = card

        title = QLabel("海上平台结构载荷管理系统", self)
        title.setObjectName("AuthTitle")
        title.setAlignment(Qt.AlignCenter)
        title.setMinimumHeight(36)
        card_layout.addWidget(title)
        card_layout.addSpacing(8)

        form_layout = QVBoxLayout()
        form_layout.setSpacing(10)

        self.user_edit = QLineEdit(self)
        self.user_edit.setPlaceholderText("请输入用户名/工号")
        self._setup_glass_input(self.user_edit, "user")
        self._setup_username_history()
        form_layout.addWidget(self.user_edit, 0, Qt.AlignCenter)

        self.pwd_edit = QLineEdit(self)
        self.pwd_edit.setPlaceholderText("请输入密码")
        self.pwd_edit.setEchoMode(QLineEdit.Password)
        self.pwd_edit.returnPressed.connect(self._on_login_clicked)
        self._setup_glass_input(self.pwd_edit, "lock")
        form_layout.addWidget(self.pwd_edit, 0, Qt.AlignCenter)

        self.remember_chk = QCheckBox("记住密码", self)
        self.remember_chk.setObjectName("RememberCheck")
        remember_layout = QHBoxLayout()
        remember_layout.setContentsMargins(10, 0, 10, 0)
        remember_layout.addWidget(self.remember_chk, 0, Qt.AlignLeft)
        remember_layout.addStretch(1)
        form_layout.addLayout(remember_layout)
        card_layout.addLayout(form_layout)

        self.login_btn = QPushButton("登录", self)
        self.login_btn.setObjectName("PrimaryButton")
        self.login_btn.setFixedWidth(self.LOGIN_BUTTON_WIDTH)
        self.login_btn.setGraphicsEffect(self._button_shadow())
        self.register_btn = QPushButton("注册账号", self)
        self.register_btn.setObjectName("TextLinkButton")
        self.cancel_btn = QPushButton("退出", self)
        self.cancel_btn.setObjectName("TextLinkButton")
        self.login_btn.clicked.connect(self._on_login_clicked)
        self.register_btn.clicked.connect(self._on_register_clicked)
        self.cancel_btn.clicked.connect(self.reject)
        card_layout.addWidget(self.login_btn, 0, Qt.AlignCenter)

        link_layout = QHBoxLayout()
        link_layout.setContentsMargins(0, 0, 0, 0)
        link_layout.setSpacing(18)
        link_layout.addStretch(1)
        link_layout.addWidget(self.register_btn)
        link_layout.addWidget(self.cancel_btn)
        link_layout.addStretch(1)
        card_layout.addLayout(link_layout)

        self._load_remembered_credentials()
        self._bind_return_focus_chain([self.user_edit, self.pwd_edit])
        self.card.adjustSize()
        self._refresh_background()
        self.bg_label.lower()

    def _setup_glass_input(self, edit: QLineEdit, icon_kind: str) -> None:
        edit.setObjectName("GlassInput")
        edit.setFixedWidth(self.CONTROL_WIDTH)
        edit.setFixedHeight(32)
        edit.addAction(self._line_icon(icon_kind), QLineEdit.LeadingPosition)
        edit.setTextMargins(10, 0, 0, 0)

    def _setup_username_history(self) -> None:
        usernames = self._load_username_history()
        if not usernames:
            return
        model = QStringListModel(usernames, self)
        completer = QCompleter(model, self.user_edit)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        self.user_edit.setCompleter(completer)

    def _load_username_history(self) -> list[str]:
        value = self.settings.value("login/history_usernames", [], type=list)
        return [str(item).strip() for item in value if str(item).strip()]

    def _save_username_history(self, username: str) -> None:
        username = username.strip()
        if not username:
            return
        usernames = [item for item in self._load_username_history() if item != username]
        usernames.insert(0, username)
        self.settings.setValue("login/history_usernames", usernames[:8])

    @staticmethod
    def _button_shadow() -> QGraphicsDropShadowEffect:
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(14)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(14, 54, 150, 110))
        return shadow

    @staticmethod
    def _line_icon(kind: str) -> QIcon:
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        pen = QPen(QColor(58, 72, 92, 255), 1.8)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)

        if kind == "lock":
            painter.drawRoundedRect(7, 10, 10, 8, 2, 2)
            painter.drawArc(8, 5, 8, 10, 0, 180 * 16)
            painter.drawLine(12, 14, 12, 16)
        else:
            painter.drawEllipse(9, 5, 6, 6)
            painter.drawArc(6, 11, 12, 10, 20 * 16, 140 * 16)

        painter.end()
        return QIcon(pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_background()

    def _refresh_background(self) -> None:
        if not hasattr(self, "bg_label"):
            return
        stage_width = self.stage.width() if hasattr(self, "stage") else self.width()
        stage_height = self.stage.height() if hasattr(self, "stage") else self.height()
        self.bg_label.setGeometry(0, 0, self.width(), self.height())
        bg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pict", "home_bg.png")
        if os.path.exists(bg_path):
            pixmap = QPixmap(bg_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                x = max(0, (scaled.width() - self.width()) // 2)
                y = max(0, (scaled.height() - self.height()) // 2)
                self.bg_label.setPixmap(scaled.copy(x, y, self.width(), self.height()))
        if hasattr(self, "card"):
            self.card.move((stage_width - self.card.width()) // 2, (stage_height - self.card.height()) // 2)

    def _load_remembered_credentials(self) -> None:
        if not self._session_remember_password:
            return
        self.user_edit.setText(self._session_username)
        self.pwd_edit.setText(self._session_password)
        self.remember_chk.setChecked(True)

    def _save_remembered_credentials(self) -> None:
        if self.remember_chk.isChecked():
            LoginDialog._session_remember_password = True
            LoginDialog._session_username = self.user_edit.text().strip()
            LoginDialog._session_password = self.pwd_edit.text()
        else:
            LoginDialog._session_remember_password = False
            LoginDialog._session_username = ""
            LoginDialog._session_password = ""

    def _bind_return_focus_chain(self, edits: list[QLineEdit]) -> None:
        for current, nxt in zip(edits, edits[1:]):
            current.returnPressed.connect(nxt.setFocus)

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
            QFrame#LoginStage { background-color: transparent; }
            QFrame#AuthCard {
                background-color: rgba(255, 255, 255, 230);
                border: none;
                border-radius: 15px;
            }
            QLabel#AuthTitle {
                color: #17324D;
                font-size: 20px;
                font-weight: 700;
                padding: 4px 0 6px 0;
            }
            QLineEdit#GlassInput {
                min-width: 280px;
                max-width: 280px;
                min-height: 32px;
                max-height: 32px;
                border: 1px solid #DCDFE6;
                border-radius: 8px;
                padding: 0 16px 0 10px;
                background-color: #ffffff;
                color: #12304A;
                font-size: 16px;
            }
            QLineEdit#GlassInput:focus {
                border: 2px solid #409EFF;
                background-color: #ffffff;
            }
            QCheckBox#RememberCheck {
                color: #606266;
                font-size: 14px;
                spacing: 8px;
                padding-left: 4px;
            }
            QCheckBox#RememberCheck::indicator {
                width: 13px;
                height: 13px;
                border-radius: 7px;
                background-color: #ffffff;
                border: 1px solid #DCDFE6;
            }
            QCheckBox#RememberCheck::indicator:checked {
                background-color: #2D5CF6;
                border: 1px solid #2D5CF6;
            }
            QPushButton {
                min-height: 36px;
                border-radius: 6px;
                padding: 0 16px;
                font-size: 16px;
            }
            QPushButton#PrimaryButton {
                min-width: 280px;
                max-width: 280px;
                background-color: #2D5CF6;
                color: white;
                border: none;
                font-weight: 700;
            }
            QPushButton#PrimaryButton:hover { background-color: #4A74F7; }
            QPushButton#TextLinkButton {
                min-height: 24px;
                background-color: transparent;
                color: #606266;
                border: none;
                padding: 0 4px;
                font-size: 14px;
            }
            QPushButton#TextLinkButton:hover { color: #2D5CF6; text-decoration: underline; }
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
        self._save_username_history(self.user_edit.text())
        self._save_remembered_credentials()
        self.accept()

    def _on_register_clicked(self) -> None:
        dlg = RegisterDialog(self.auth_service, self)
        if exec_dialog_safely(dlg, title="注册窗口错误", context="注册窗口", parent=self) == dlg.Accepted and dlg.registered_username:
            self.user_edit.setText(dlg.registered_username)
            self.pwd_edit.clear()
            self.pwd_edit.setFocus()
