from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes

from .config import AppSettings, load_settings


RESOURCETYPE_DISK = 0x00000001
ERROR_ALREADY_ASSIGNED = 85
ERROR_DEVICE_ALREADY_REMEMBERED = 1202
ERROR_SESSION_CREDENTIAL_CONFLICT = 1219

_CONNECTED_KEYS: set[tuple[str, str]] = set()


class NETRESOURCEW(ctypes.Structure):
    _fields_ = [
        ("dwScope", wintypes.DWORD),
        ("dwType", wintypes.DWORD),
        ("dwDisplayType", wintypes.DWORD),
        ("dwUsage", wintypes.DWORD),
        ("lpLocalName", wintypes.LPWSTR),
        ("lpRemoteName", wintypes.LPWSTR),
        ("lpComment", wintypes.LPWSTR),
        ("lpProvider", wintypes.LPWSTR),
    ]


def _is_unc_path(path: str) -> bool:
    text = str(path or "").replace("/", "\\").strip()
    return text.startswith("\\\\")


def unc_share_root(path: str) -> str:
    text = str(path or "").replace("/", "\\").strip()
    if not _is_unc_path(text):
        return ""
    parts = [part for part in text.strip("\\").split("\\") if part]
    if len(parts) < 2:
        return ""
    return f"\\\\{parts[0]}\\{parts[1]}"


def _format_windows_error(code: int) -> str:
    try:
        return ctypes.FormatError(int(code)).strip()
    except Exception:
        return f"Windows error {code}"


def _cancel_connection(remote_name: str) -> None:
    mpr = ctypes.WinDLL("mpr")
    mpr.WNetCancelConnection2W.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.BOOL]
    mpr.WNetCancelConnection2W.restype = wintypes.DWORD
    mpr.WNetCancelConnection2W(remote_name, 0, True)


def connect_storage_share(
    unc_path: str,
    *,
    username: str = "",
    password: str = "",
    force_reconnect: bool = False,
) -> tuple[bool, str]:
    if os.name != "nt":
        return False, "自动连接共享目录仅支持 Windows 客户端。"

    remote_name = unc_share_root(unc_path)
    if not remote_name:
        return False, f"共享目录路径不是有效 UNC 路径：{unc_path}"

    user = str(username or "").strip()
    key = (remote_name.lower(), user.lower())
    if key in _CONNECTED_KEYS:
        return True, ""

    if force_reconnect:
        _cancel_connection(remote_name)

    resource = NETRESOURCEW()
    resource.dwType = RESOURCETYPE_DISK
    resource.lpRemoteName = remote_name

    mpr = ctypes.WinDLL("mpr")
    mpr.WNetAddConnection2W.argtypes = [
        ctypes.POINTER(NETRESOURCEW),
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
    ]
    mpr.WNetAddConnection2W.restype = wintypes.DWORD

    result = int(
        mpr.WNetAddConnection2W(
            ctypes.byref(resource),
            str(password or "") or None,
            user or None,
            0,
        )
    )
    if result in (0, ERROR_ALREADY_ASSIGNED, ERROR_DEVICE_ALREADY_REMEMBERED):
        _CONNECTED_KEYS.add(key)
        return True, ""
    if result == ERROR_SESSION_CREDENTIAL_CONFLICT:
        return (
            False,
            f"共享目录 {remote_name} 已使用其他账号连接。"
            "请在配置中设置 storage_share.force_reconnect=true，或关闭占用该共享的连接后重启程序。",
        )
    return False, f"连接共享目录失败：{remote_name}\n{_format_windows_error(result)}"


def ensure_storage_share_connected(settings: AppSettings) -> tuple[bool, str]:
    share = settings.storage_share
    if not share.auto_connect:
        return True, ""

    unc_path = str(share.unc_path or settings.storage_root or "").strip()
    if not _is_unc_path(unc_path):
        return True, ""

    return connect_storage_share(
        unc_path,
        username=share.username,
        password=share.password,
        force_reconnect=share.force_reconnect,
    )


def ensure_configured_storage_share_connected(config_path: str | None = None) -> tuple[bool, str]:
    if os.name != "nt" or "--report-image-export-worker" in sys.argv:
        return True, ""
    settings = load_settings(config_path)
    return ensure_storage_share_connected(settings)
