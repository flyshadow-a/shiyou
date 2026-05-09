# -*- coding: utf-8 -*-
from __future__ import annotations

import os

from PyQt5.QtCore import QRegExp, Qt
from PyQt5.QtGui import QColor, QPixmap, QRegExpValidator
from PyQt5.QtWidgets import (
    QDialog,
    QFrame,
    QFormLayout,
    QGraphicsBlurEffect,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from core.auth import AuthError, AuthService


class RegisterDialog(QDialog):
    CONTROL_WIDTH = 328

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

        self.stage = QFrame(self)
        self.stage.setObjectName("RegisterStage")
        main_layout.addWidget(self.stage)

        self.bg_label = QLabel(self.stage)
        self.bg_label.setObjectName("RegisterBg")
        self.bg_label.setAlignment(Qt.AlignCenter)
        blur = QGraphicsBlurEffect(self.bg_label)
        blur.setBlurRadius(2.2)
        self.bg_label.setGraphicsEffect(blur)

        self.mask_label = QLabel(self.stage)
        self.mask_label.setObjectName("RegisterMask")

        card = QFrame(self.stage)
        card.setObjectName("AuthCard")
        card.setFixedWidth(720)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(36, 30, 36, 30)
        card_layout.setSpacing(12)
        self.card = card

        title = QLabel("注册工程师账号", self)
        title.setObjectName("AuthTitle")
        title.setAlignment(Qt.AlignCenter)
        title.setMinimumHeight(40)
        card_layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFormAlignment(Qt.AlignCenter)
        form.setHorizontalSpacing(12)
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
        self.submit_btn.setFixedWidth(self.CONTROL_WIDTH)
        self.submit_btn.setGraphicsEffect(self._button_shadow())
        self.cancel_btn = QPushButton("取消", self)
        self.cancel_btn.setObjectName("TextLinkButton")
        self.submit_btn.clicked.connect(self._on_register_clicked)
        self.cancel_btn.clicked.connect(self.reject)
        card_layout.addWidget(self.submit_btn, 0, Qt.AlignCenter)

        link_layout = QHBoxLayout()
        link_layout.setContentsMargins(0, 0, 0, 0)
        link_layout.addStretch(1)
        link_layout.addWidget(self.cancel_btn, 0, Qt.AlignCenter)
        link_layout.addStretch(1)
        card_layout.addLayout(link_layout)

        self.card.adjustSize()
        self._refresh_background()

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

    @staticmethod
    def _button_shadow() -> QGraphicsDropShadowEffect:
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(14)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(14, 54, 150, 110))
        return shadow

    @staticmethod
    def _dialog_style() -> str:
        return """
            QDialog#RegisterDialog { background-color: #004a80; }
            QFrame#RegisterStage { background-color: #004a80; }
            QLabel#RegisterMask { background-color: rgba(30, 58, 104, 28); }
            QFrame#AuthCard {
                background-color: rgba(255, 255, 255, 0);
                border: none;
            }
            QLabel#AuthTitle {
                color: #17324D;
                font-size: 26px;
                font-weight: 700;
                letter-spacing: 1px;
                padding: 4px 0;
            }
            QLabel { color: #0F2A44; font-size: 16px; font-weight: 700; }
            QLineEdit#GlassInput {
                min-width: 328px;
                max-width: 328px;
                min-height: 36px;
                border: 1px solid rgba(255, 255, 255, 76);
                border-radius: 18px;
                padding: 0 16px;
                background-color: rgba(255, 255, 255, 105);
                color: #12304A;
                font-size: 16px;
            }
            QLineEdit#GlassInput:focus {
                border: 1px solid rgba(255, 255, 255, 150);
                background-color: rgba(255, 255, 255, 130);
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
