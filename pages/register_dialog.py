# -*- coding: utf-8 -*-
from __future__ import annotations

import os

from PyQt5.QtCore import QRegExp, Qt
from PyQt5.QtGui import QPixmap, QRegExpValidator
from PyQt5.QtWidgets import (
    QDialog,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from core.auth import AuthError, AuthService


class RegisterDialog(QDialog):
    def __init__(self, auth_service: AuthService, parent=None):
        super().__init__(parent)
        self.auth_service = auth_service
        self.registered_username = ""
        self.setWindowTitle("注册")
        self.setWindowModality(Qt.WindowModal)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._build_ui()

    def _build_ui(self) -> None:
        self.resize(680, 620)
        self.setObjectName("RegisterDialog")
        self.setStyleSheet(self._dialog_style())

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.bg_label = QLabel(self)
        self.bg_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.bg_label)

        card = QFrame(self.bg_label)
        card.setObjectName("AuthCard")
        card.setFixedWidth(500)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(34, 28, 34, 28)
        card_layout.setSpacing(14)
        self.card = card

        title = QLabel("注册工程师账号", self)
        title.setObjectName("AuthTitle")
        title.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(title)

        hint = QLabel("当前开放注册角色：工程师", self)
        hint.setObjectName("AuthSubtitle")
        hint.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(hint)

        form = QFormLayout()
        form.setSpacing(11)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.username_edit = QLineEdit(self)
        self.password_edit = QLineEdit(self)
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.confirm_password_edit = QLineEdit(self)
        self.confirm_password_edit.setEchoMode(QLineEdit.Password)
        self.display_name_edit = QLineEdit(self)
        self.employee_no_edit = QLineEdit(self)
        self.branch_company_edit = QLineEdit(self)
        self.operation_company_edit = QLineEdit(self)
        self.phone_edit = QLineEdit(self)
        self.phone_edit.setMaxLength(11)
        self.phone_edit.setValidator(QRegExpValidator(QRegExp(r"\d{0,11}"), self.phone_edit))
        self.phone_edit.setPlaceholderText("请输入 11 位数字手机号")
        self.email_edit = QLineEdit(self)

        form.addRow("用户名：", self.username_edit)
        form.addRow("密码：", self._password_row(self.password_edit, "toggle_pwd_btn"))
        form.addRow("确认密码：", self._password_row(self.confirm_password_edit, "toggle_confirm_pwd_btn"))
        form.addRow("姓名：", self.display_name_edit)
        form.addRow("工号：", self.employee_no_edit)
        form.addRow("分公司：", self.branch_company_edit)
        form.addRow("作业公司：", self.operation_company_edit)
        form.addRow("电话：", self.phone_edit)
        form.addRow("邮箱：", self.email_edit)
        card_layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        self.submit_btn = QPushButton("注册", self)
        self.submit_btn.setObjectName("PrimaryButton")
        self.cancel_btn = QPushButton("取消", self)
        self.cancel_btn.setObjectName("GhostButton")
        self.submit_btn.clicked.connect(self._on_register_clicked)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.submit_btn)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addStretch(1)
        card_layout.addLayout(btn_layout)

        self.card.adjustSize()
        self._refresh_background()

    def _password_row(self, edit: QLineEdit, attr_name: str) -> QFrame:
        row = QFrame(self)
        row.setObjectName("PasswordRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        button = QPushButton("显示", self)
        button.setObjectName("GhostButton")
        button.setFixedWidth(58)
        button.clicked.connect(lambda: self._toggle_password(edit, button))
        setattr(self, attr_name, button)
        layout.addWidget(edit)
        layout.addWidget(button)
        return row

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
            QDialog#RegisterDialog { background-color: #004a80; }
            QFrame#AuthCard {
                background-color: rgba(255, 255, 255, 205);
                border: 1px solid rgba(255, 255, 255, 150);
                border-radius: 24px;
            }
            QLabel#AuthTitle { color: #17324d; font-size: 23px; font-weight: 800; }
            QLabel#AuthSubtitle { color: #526579; font-size: 13px; padding-bottom: 4px; }
            QLabel { color: #263d55; font-size: 14px; }
            QLineEdit {
                min-height: 36px;
                border: 1px solid #c9d7e6;
                border-radius: 12px;
                padding: 0 13px;
                background-color: #f8fbff;
                color: #172536;
                font-size: 14px;
            }
            QLineEdit:focus { border: 1px solid #1f78c8; background-color: #ffffff; }
            QFrame#PasswordRow { border: none; background: transparent; }
            QPushButton {
                min-height: 34px;
                border-radius: 12px;
                padding: 0 16px;
                font-size: 14px;
            }
            QPushButton#PrimaryButton { background-color: #006bb3; color: white; border: none; font-weight: 700; }
            QPushButton#PrimaryButton:hover { background-color: #0782d4; }
            QPushButton#GhostButton { background-color: rgba(255,255,255,0.72); color: #42566b; border: 1px solid #d4dfeb; }
            QPushButton#GhostButton:hover { background-color: #ffffff; }
        """

    def _on_register_clicked(self) -> None:
        try:
            self.auth_service.register_user(
                username=self.username_edit.text(),
                password=self.password_edit.text(),
                confirm_password=self.confirm_password_edit.text(),
                display_name=self.display_name_edit.text(),
                employee_no=self.employee_no_edit.text(),
                branch_company=self.branch_company_edit.text(),
                operation_company=self.operation_company_edit.text(),
                phone=self.phone_edit.text(),
                email=self.email_edit.text(),
            )
        except AuthError as exc:
            QMessageBox.warning(self, "注册失败", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "注册失败", f"注册账号时发生错误：\n{exc}")
            return

        self.registered_username = self.username_edit.text().strip()
        QMessageBox.information(self, "注册成功", "注册成功，请使用新账号登录。")
        self.accept()
