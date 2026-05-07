# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from shiyou_db.config import AppSettings, load_settings
from shiyou_db.database import Base, build_engine
from shiyou_db.models import AuthLoginLog, AuthRole, AuthUser
from shiyou_db.service import DEFAULT_AUTH_ROLES

PASSWORD_ALGO = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 260000
SALT_BYTES = 16


class AuthError(Exception):
    """可直接展示给用户的认证错误。"""


@dataclass(frozen=True)
class UserSession:
    user_id: int
    username: str
    display_name: str
    role_code: str
    role_name: str
    employee_no: str = ""
    branch_company: str = ""
    operation_company: str = ""
    phone: str = ""
    email: str = ""

    @property
    def display_label(self) -> str:
        name = self.display_name or self.username
        return f"{name}（{self.role_name}）" if self.role_name else name


def hash_password(password: str) -> str:
    salt = secrets.token_hex(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("ascii"),
        PASSWORD_ITERATIONS,
    ).hex()
    return f"{PASSWORD_ALGO}${PASSWORD_ITERATIONS}${salt}${digest}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, iterations_text, salt, expected = encoded.split("$", 3)
        if algo != PASSWORD_ALGO:
            return False
        iterations = int(iterations_text)
    except (ValueError, TypeError):
        return False

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("ascii"),
        iterations,
    ).hex()
    return hmac.compare_digest(digest, expected)


class AuthService:
    def __init__(self, settings: AppSettings | None = None):
        self.settings = settings or load_settings()
        self.engine = build_engine(self.settings)
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        Base.metadata.create_all(self.engine)
        self._seed_roles()

    def _seed_roles(self) -> None:
        with self.session_factory() as session:
            existing = {item.code: item for item in session.execute(select(AuthRole)).scalars().all()}
            changed = False
            for index, item in enumerate(DEFAULT_AUTH_ROLES, start=1):
                row = existing.get(item["code"])
                sort_order = index * 10
                if row is None:
                    session.add(
                        AuthRole(
                            code=item["code"],
                            name=item["name"],
                            description=item.get("description"),
                            sort_order=sort_order,
                            is_active=True,
                        )
                    )
                    changed = True
                elif row.name != item["name"] or row.description != item.get("description") or row.sort_order != sort_order:
                    row.name = item["name"]
                    row.description = item.get("description")
                    row.sort_order = sort_order
                    changed = True
            if changed:
                session.commit()

    def register_user(
        self,
        *,
        username: str,
        password: str,
        confirm_password: str,
        display_name: str = "",
        employee_no: str = "",
        branch_company: str = "",
        operation_company: str = "",
        phone: str = "",
        email: str = "",
    ) -> None:
        username = username.strip()
        password = password.strip()
        confirm_password = confirm_password.strip()
        if not username:
            raise AuthError("用户名不能为空。")
        if len(password) < 6:
            raise AuthError("密码长度至少 6 位。")
        if password != confirm_password:
            raise AuthError("两次输入的密码不一致。")

        with self.session_factory() as session:
            exists = session.execute(select(AuthUser).where(AuthUser.username == username)).scalar_one_or_none()
            if exists is not None:
                raise AuthError("用户名已存在，请更换用户名。")

            user = AuthUser(
                username=username,
                display_name=display_name.strip() or username,
                employee_no=employee_no.strip() or None,
                branch_company=branch_company.strip() or None,
                operation_company=operation_company.strip() or None,
                phone=phone.strip() or None,
                email=email.strip() or None,
                role_code="engineer",
                password_hash=hash_password(password),
                password_algo=PASSWORD_ALGO,
                password_updated_at=datetime.utcnow(),
                is_active=True,
                is_deleted=False,
            )
            session.add(user)
            session.commit()

    def authenticate_user(self, username: str, password: str, *, client_info: str = "") -> UserSession:
        username = username.strip()
        password = password.strip()
        if not username or not password:
            raise AuthError("请输入用户名和密码。")

        with self.session_factory() as session:
            user = session.execute(select(AuthUser).where(AuthUser.username == username)).scalar_one_or_none()
            if user is None or user.is_deleted:
                self._add_login_log(session, None, username, False, "invalid_credentials", client_info)
                session.commit()
                raise AuthError("用户名或密码错误。")
            if not user.is_active:
                self._add_login_log(session, user, username, False, "user_disabled", client_info)
                session.commit()
                raise AuthError("账号已禁用，请联系管理员。")
            if not verify_password(password, user.password_hash):
                self._add_login_log(session, user, username, False, "invalid_credentials", client_info)
                session.commit()
                raise AuthError("用户名或密码错误。")

            user.last_login_at = datetime.utcnow()
            self._add_login_log(session, user, username, True, None, client_info)
            session.commit()
            role = user.role
            return UserSession(
                user_id=int(user.id),
                username=user.username,
                display_name=user.display_name or user.username,
                role_code=user.role_code,
                role_name=role.name if role is not None else user.role_code,
                employee_no=user.employee_no or "",
                branch_company=user.branch_company or "",
                operation_company=user.operation_company or "",
                phone=user.phone or "",
                email=user.email or "",
            )

    @staticmethod
    def _add_login_log(session, user: AuthUser | None, username: str, success: bool, failure_reason: str | None, client_info: str) -> None:
        session.add(
            AuthLoginLog(
                user_id=user.id if user is not None else None,
                username=username,
                success=success,
                failure_reason=failure_reason,
                client_info=client_info.strip() or None,
            )
        )
