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
    QGraphicsBlurEffect,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from core.auth import AuthError, AuthService, UserSession
from pages.register_dialog import RegisterDialog


class LoginDialog(QDialog):
    SETTINGS_ORG = "Shiyou"
    SETTINGS_APP = "PlatformLoadManager"
    CONTROL_WIDTH = 328
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
        self.resize(620, 430)
        self.setMinimumSize(620, 430)
        self.setObjectName("LoginDialog")
        self.setStyleSheet(self._dialog_style())

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.stage = QFrame(self)
        self.stage.setObjectName("LoginStage")
        main_layout.addWidget(self.stage)

        self.bg_label = QLabel(self.stage)
        self.bg_label.setObjectName("LoginBg")
        self.bg_label.setAlignment(Qt.AlignCenter)
        blur = QGraphicsBlurEffect(self.bg_label)
        blur.setBlurRadius(2.2)
        self.bg_label.setGraphicsEffect(blur)

        self.mask_label = QLabel(self.stage)
        self.mask_label.setObjectName("LoginMask")

        card = QFrame(self.stage)
        card.setObjectName("AuthCard")
        card.setFixedWidth(520)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 30, 36, 30)
        card_layout.setSpacing(14)

        self.card = card

        title = QLabel("海上平台结构载荷管理系统", self)
        title.setObjectName("AuthTitle")
        title.setAlignment(Qt.AlignCenter)
        title.setMinimumHeight(42)
        card_layout.addWidget(title)
        card_layout.addSpacing(12)

        form_layout = QVBoxLayout()
        form_layout.setSpacing(12)

        self.user_edit = QLineEdit(self)
        self.user_edit.setPlaceholderText("用户名")
        self._setup_glass_input(self.user_edit, "user")
        self._setup_username_history()
        form_layout.addWidget(self.user_edit, 0, Qt.AlignCenter)

        self.pwd_edit = QLineEdit(self)
        self.pwd_edit.setPlaceholderText("密码")
        self.pwd_edit.setEchoMode(QLineEdit.Password)
        self.pwd_edit.returnPressed.connect(self._on_login_clicked)
        self._setup_glass_input(self.pwd_edit, "lock")
        form_layout.addWidget(self.pwd_edit, 0, Qt.AlignCenter)

        self.remember_chk = QCheckBox("记住密码", self)
        self.remember_chk.setObjectName("RememberCheck")
        remember_layout = QHBoxLayout()
        remember_layout.setContentsMargins(60, 0, 60, 0)
        remember_layout.addWidget(self.remember_chk, 0, Qt.AlignLeft)
        remember_layout.addStretch(1)
        form_layout.addLayout(remember_layout)
        card_layout.addLayout(form_layout)

        self.login_btn = QPushButton("登录", self)
        self.login_btn.setObjectName("PrimaryButton")
        self.login_btn.setFixedWidth(self.CONTROL_WIDTH)
        self.login_btn.setGraphicsEffect(self._button_shadow())
        self.register_btn = QPushButton("注册", self)
        self.register_btn.setObjectName("TextLinkButton")
        self.cancel_btn = QPushButton("取消", self)
        self.cancel_btn.setObjectName("TextLinkButton")
        self.login_btn.clicked.connect(self._on_login_clicked)
        self.register_btn.clicked.connect(self._on_register_clicked)
        self.cancel_btn.clicked.connect(self.reject)
        card_layout.addWidget(self.login_btn, 0, Qt.AlignCenter)

        link_layout = QHBoxLayout()
        link_layout.setContentsMargins(96, 0, 96, 0)
        link_layout.addWidget(self.register_btn, 0, Qt.AlignLeft)
        link_layout.addStretch(1)
        link_layout.addWidget(self.cancel_btn, 0, Qt.AlignRight)
        card_layout.addLayout(link_layout)

        self._load_remembered_credentials()
        self.card.adjustSize()
        self._refresh_background()

    def _setup_glass_input(self, edit: QLineEdit, icon_kind: str) -> None:
        edit.setObjectName("GlassInput")
        edit.setFixedWidth(self.CONTROL_WIDTH)
        edit.addAction(self._line_icon(icon_kind), QLineEdit.LeadingPosition)
        edit.setTextMargins(8, 0, 0, 0)

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
        pen = QPen(QColor(255, 255, 255, 230), 1.8)
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
        self.bg_label.setGeometry(-12, -12, stage_width + 24, stage_height + 24)
        if hasattr(self, "mask_label"):
            self.mask_label.setGeometry(0, 0, stage_width, stage_height)
        bg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pict", "home_bg.png")
        if os.path.exists(bg_path):
            pixmap = QPixmap(bg_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(self.bg_label.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                x = max(0, (scaled.width() - self.bg_label.width()) // 2)
                y = max(0, (scaled.height() - self.bg_label.height()) // 2)
                self.bg_label.setPixmap(scaled.copy(x, y, self.bg_label.width(), self.bg_label.height()))
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
            QFrame#LoginStage { background-color: #004a80; }
            QLabel#LoginMask { background-color: rgba(30, 58, 104, 28); }
            QFrame#AuthCard {
                background-color: rgba(255, 255, 255, 0);
                border: none;
            }
            QLabel#AuthTitle {
                color: #17324D;
                font-size: 28px;
                font-weight: 700;
                letter-spacing: 1px;
                padding: 4px 0;
            }
            QLineEdit#GlassInput {
                min-width: 328px;
                max-width: 328px;
                min-height: 40px;
                border: 1px solid rgba(255, 255, 255, 76);
                border-radius: 20px;
                padding: 0 18px 0 8px;
                background-color: rgba(255, 255, 255, 105);
                color: #12304A;
                font-size: 16px;
            }
            QLineEdit#GlassInput:focus {
                border: 1px solid rgba(255, 255, 255, 150);
                background-color: rgba(255, 255, 255, 130);
            }
            QCheckBox#RememberCheck {
                color: rgba(255, 255, 255, 225);
                font-size: 15px;
                spacing: 8px;
                padding-left: 4px;
            }
            QCheckBox#RememberCheck::indicator {
                width: 13px;
                height: 13px;
                border-radius: 7px;
                background-color: rgba(255, 255, 255, 220);
                border: 1px solid rgba(255, 255, 255, 160);
            }
            QCheckBox#RememberCheck::indicator:checked {
                background-color: #1f5ad7;
                border: 1px solid #88a9ff;
            }
            QPushButton {
                min-height: 36px;
                border-radius: 18px;
                padding: 0 16px;
                font-size: 16px;
            }
            QPushButton#PrimaryButton {
                min-width: 328px;
                max-width: 328px;
                background-color: #1f5ad7;
                color: white;
                border: none;
                font-weight: 700;
            }
            QPushButton#PrimaryButton:hover { background-color: #356ef0; }
            QPushButton#TextLinkButton {
                min-height: 24px;
                background-color: transparent;
                color: rgba(255,255,255,230);
                border: none;
                padding: 0 4px;
                font-size: 15px;
            }
            QPushButton#TextLinkButton:hover { color: #ffffff; text-decoration: underline; }
            QPushButton#GhostButton { background-color: rgba(255,255,255,0.58); color: #42566b; border: 1px solid rgba(255,255,255,0.36); }
            QPushButton#GhostButton:hover { background-color: rgba(255,255,255,0.78); }
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
        if dlg.exec_() == dlg.Accepted and dlg.registered_username:
            self.user_edit.setText(dlg.registered_username)
            self.pwd_edit.clear()
            self.pwd_edit.setFocus()
