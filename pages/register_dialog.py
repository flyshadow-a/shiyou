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
    CARD_WIDTH = 480
    CONTROL_WIDTH = 280
    ACTION_BUTTON_WIDTH = 120

    def __init__(self, auth_service: AuthService, parent=None):
        super().__init__(parent)
        self.auth_service = auth_service
        self.registered_username = ""
        self.setWindowTitle("注册")
        self.setWindowModality(Qt.WindowModal)
        self.setWindowFlags(
            (self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
        )
        self._build_ui()

    def _build_ui(self) -> None:
        self.resize(780, 620)
        self.setMinimumSize(780, 620)
        self.setObjectName("RegisterDialog")
        self.setStyleSheet(self._dialog_style())

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.bg_label = QLabel(self)
        self.bg_label.setObjectName("RegisterBg")
        self.bg_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.bg_label)

        card = QFrame(self.bg_label)
        card.setObjectName("AuthCard")
        card.setFixedWidth(self.CARD_WIDTH)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 24, 28, 24)
        card_layout.setSpacing(14)
        self.card = card

        title = QLabel("注册工程师账号", self)
        title.setObjectName("AuthTitle")
        title.setAlignment(Qt.AlignCenter)
        title.setMinimumHeight(36)
        card_layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFormAlignment(Qt.AlignCenter)
        form.setHorizontalSpacing(14)
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

        for edit in (
            self.username_edit,
            self.password_edit,
            self.confirm_password_edit,
            self.display_name_edit,
            self.employee_no_edit,
            self.branch_company_edit,
            self.operation_company_edit,
            self.phone_edit,
            self.email_edit,
        ):
            edit.setObjectName("GlassInput")
            edit.setFixedWidth(self.CONTROL_WIDTH)

        self.username_edit.setPlaceholderText("请输入用户名")
        self.password_edit.setPlaceholderText("请输入密码")
        self.confirm_password_edit.setPlaceholderText("请再次输入密码")
        self.display_name_edit.setPlaceholderText("请输入姓名")
        self.employee_no_edit.setPlaceholderText("请输入工号")
        self.branch_company_edit.setPlaceholderText("请输入分公司")
        self.operation_company_edit.setPlaceholderText("请输入作业公司")
        self.email_edit.setPlaceholderText("请输入邮箱")

        form.addRow("用户名：", self.username_edit)
        form.addRow("密码：", self.password_edit)
        form.addRow("确认密码：", self.confirm_password_edit)
        form.addRow("姓名：", self.display_name_edit)
        form.addRow("工号：", self.employee_no_edit)
        form.addRow("分公司：", self.branch_company_edit)
        form.addRow("作业公司：", self.operation_company_edit)
        form.addRow("电话：", self.phone_edit)
        form.addRow("邮箱：", self.email_edit)
        card_layout.addLayout(form)

        self.submit_btn = QPushButton("注册", self)
        self.submit_btn.setObjectName("PrimaryButton")
        self.submit_btn.setFixedWidth(self.ACTION_BUTTON_WIDTH)
        self.cancel_btn = QPushButton("取消", self)
        self.cancel_btn.setObjectName("SecondaryButton")
        self.cancel_btn.setFixedWidth(self.ACTION_BUTTON_WIDTH)
        self.submit_btn.clicked.connect(self._on_register_clicked)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 4, 0, 0)
        btn_layout.setSpacing(16)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.submit_btn)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addStretch(1)
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
    def _dialog_style() -> str:
        return """
            QDialog#RegisterDialog { background-color: #004a80; }
            QFrame#AuthCard {
                background-color: rgba(255, 255, 255, 230);
                border: none;
                border-radius: 15px;
            }
            QLabel#AuthTitle {
                color: #17324D;
                font-size: 24px;
                font-weight: 700;
                padding: 4px 0 8px 0;
            }
            QLabel { color: #0F2A44; font-size: 15px; font-weight: 700; }
            QLineEdit#GlassInput {
                min-width: 280px;
                max-width: 280px;
                min-height: 36px;
                border: 1px solid rgba(160, 175, 195, 180);
                border-radius: 8px;
                padding: 0 16px;
                background-color: #ffffff;
                color: #12304A;
                font-size: 16px;
            }
            QLineEdit#GlassInput:focus {
                border: 1px solid #7ba4d6;
                background-color: #ffffff;
            }
            QPushButton {
                min-height: 36px;
                border-radius: 8px;
                padding: 0 16px;
                font-size: 16px;
            }
            QPushButton#PrimaryButton {
                min-width: 120px;
                max-width: 120px;
                background-color: #1f5ad7;
                color: white;
                border: none;
                font-weight: 700;
            }
            QPushButton#PrimaryButton:hover { background-color: #356ef0; }
            QPushButton#SecondaryButton {
                min-width: 120px;
                max-width: 120px;
                background-color: #eef3f9;
                color: #17324D;
                border: 1px solid #d4deea;
                font-weight: 700;
            }
            QPushButton#SecondaryButton:hover { background-color: #dde8f4; }
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
