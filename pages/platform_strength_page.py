# -*- coding: utf-8 -*-
# pages/platform_strength_page.py

import os
import re

import numpy as np
import pyvista as pv
from pyvistaqt import QtInteractor

from typing import Any, Dict, List, Tuple, Optional

from PyQt5.QtCore import QObject, Qt, QRectF, QEvent, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPen
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QTableWidget,
    QTableWidgetItem,
    QSizePolicy,
    QWidget,
    QLineEdit,
    QScrollArea,
    QGraphicsView,
    QGraphicsScene, QMessageBox, QPushButton, QHeaderView, QSlider, QDialog,
    QApplication,
    QProgressDialog,
    QToolTip,
)

from core.app_paths import first_existing_path
from core.base_page import BasePage
from core.dropdown_bar import DropdownBar
from core.table_clipboard import TableClipboardController
from feasibility_analysis_services.oilfield_env_service import (
    get_env_profile_id,
    load_platform_strength_marine_items,
    load_platform_strength_pile_items,
    load_platform_strength_splash_items,
    replace_platform_strength_marine_items,
    replace_platform_strength_pile_items,
    replace_platform_strength_splash_items,
)
from services.inspection_business_db_adapter import load_facility_profile
from pages.feasibility_assessment_page import FeasibilityAssessmentPage
from pages.file_management_platforms import default_platform, sync_platform_dropdowns
from services.file_db_adapter import (
    FileBackendError,
    is_file_db_configured,
    list_files_by_prefix,
    resolve_storage_path,
)
from services.platform_strength_db import (
    load_horizontal_levels,
    load_structure_model_info,
    save_horizontal_levels,
    save_structure_model_info,
)
from services.platform_strength_quick_assessment import run_quick_assessment_preparation

from pages.sacs_import_service import import_model_bundle_to_db

# 远程客户端：用于从 FastAPI 服务端下载数据库中登记的模型/海况文件到本地缓存。
# 注意：如果当前运行环境没有 client_api，页面仍可回退到原本的本地/数据库路径逻辑。
try:
    from client_api.api_client import ApiClient
except Exception:  # pragma: no cover - 兼容未接入客户端 API 的旧环境
    ApiClient = None

from shiyou_db.runtime_db import get_mysql_url
from shiyou_db.config import get_storage_root
from services.special_strategy_image_service import build_strategy_image_path, save_strategy_image_record

from collections import Counter

from pages.sacs_storage_service import (
    get_job_runtime_dir,
)

try:
    from vtkmodules.vtkCommonCore import vtkLogger, vtkObject

    vtkObject.GlobalWarningDisplayOff()
    if hasattr(vtkLogger, "SetStderrVerbosity") and hasattr(vtkLogger, "VERBOSITY_OFF"):
        vtkLogger.SetStderrVerbosity(vtkLogger.VERBOSITY_OFF)
except Exception:
    pass


def read_lines_with_fallback(file_path: str) -> List[str]:
    encodings = ["utf-8", "utf-8-sig", "gb18030", "gbk", "latin-1"]
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                return f.readlines()
        except UnicodeDecodeError:
            continue
        except Exception:
            break
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.readlines()


def parse_sacs_full_robust_file(filepath: str) -> tuple[dict[str, list[float]], list[tuple[str, str, str]], dict[str, float]]:
    nodes: dict[str, list[float]] = {}
    members: list[tuple[str, str, str]] = []
    groups_od: dict[str, float] = {}

    for line in read_lines_with_fallback(filepath):
        if line.startswith("GRUP"):
            gid = line[5:8].strip()
            try:
                od_str = line[14:24].strip()
                od = float(od_str) if od_str else 0.0
                groups_od[gid] = od
            except Exception:
                groups_od[gid] = 0.0

        elif line.startswith("JOINT"):
            try:
                nid = line[6:10].strip()
                x = float(line[11:18].strip())
                y = float(line[18:25].strip())
                z = float(line[25:32].strip())
                nodes[nid] = [x, y, z]
            except Exception:
                continue

        elif line.startswith("MEMBER"):
            try:
                na = line[7:11].strip()
                nb = line[11:15].strip()
                gid = line[15:18].strip()
                members.append((na, nb, gid))
            except Exception:
                continue

    return nodes, members, groups_od


def classify_sacs_model_joints(
    nodes: dict[str, list[float]],
    members: list[tuple[str, str, str]],
    groups_od: dict[str, float],
    target_z: float = 8.5,
) -> tuple[list[list[float]], list[list[float]]]:
    graph = {nid: [] for nid in nodes}
    node_to_max_od = {nid: 0.0 for nid in nodes}

    for na, nb, gid in members:
        if na in nodes and nb in nodes:
            od = groups_od.get(gid, 0.0)
            node_to_max_od[na] = max(node_to_max_od[na], od)
            node_to_max_od[nb] = max(node_to_max_od[nb], od)
            graph[na].append(nb)
            graph[nb].append(na)

    tolerance = 1.0
    elevation_nodes = {
        nid: od for nid, od in node_to_max_od.items()
        if abs(nodes[nid][2] - target_z) < tolerance
    }

    leg_joints: list[list[float]] = []
    tubular_joints: list[list[float]] = []

    if elevation_nodes:
        local_max_od = max(elevation_nodes.values())
        for nid in elevation_nodes:
            if node_to_max_od[nid] >= local_max_od * 0.95:
                leg_joints.append(nodes[nid])

    for nid, neighbors in graph.items():
        if len(neighbors) >= 3:
            tubular_joints.append(nodes[nid])

    return leg_joints, tubular_joints


def parse_mud_level_from_sacinp_file(file_path: str) -> Optional[str]:
    """从 SACS INP 文件读取 LDOPT 卡片的泥面高程字段。"""
    for line in read_lines_with_fallback(file_path):
        if line.upper().startswith("LDOPT"):
            if len(line) >= 40:
                val_str = line[32:40].strip()
                try:
                    val_float = float(val_str)
                    return f"{val_float:.3f}"
                except ValueError:
                    pass
    return None


def _model_db_row_time(row: dict[str, Any]) -> float:
    for key in ("source_modified_at", "uploaded_at", "updated_at"):
        value = row.get(key)
        if hasattr(value, "timestamp"):
            try:
                return float(value.timestamp())
            except Exception:
                pass
    return 0.0


def _model_row_logical_path(row: dict[str, Any]) -> str:
    return str(row.get("logical_path") or "").replace("\\", "/").strip().strip("/")


def _model_row_storage_path(row: dict[str, Any]) -> str:
    try:
        path = resolve_storage_path(row)
    except Exception:
        path = str(row.get("storage_path") or "").strip()
    path = os.path.normpath(str(path or "").strip())
    return path if path and os.path.exists(path) else ""


def _sacinp_name_score_for_preview(file_name: str) -> int:
    name = (file_name or "").strip().lower()
    if not name:
        return 0

    stem, ext = os.path.splitext(name)
    if stem == "sacinp" and ext == ".jknew":
        return 1200
    if stem == "sacinp" and ext == ".m1":
        return 100
    if stem.startswith("sacinp"):
        return 300
    if ext == ".sacinp":
        return 220
    tokens = [t for t in re.split(r"[^a-z0-9]+", stem) if t]
    if "sacinp" in tokens:
        return 160
    return 0


def _file_has_model_signature_for_preview(file_path: str) -> bool:
    markers_joint = False
    markers_member = False
    try:
        lines = read_lines_with_fallback(file_path)
    except Exception:
        return False
    for raw in lines:
        line = raw.strip().upper()
        if not line:
            continue
        if line.startswith("JOINT"):
            markers_joint = True
        elif line.startswith("MEMBER"):
            markers_member = True
        if markers_joint and markers_member:
            return True
    return False


def _query_model_file_rows_for_preview(facility_code: str, prefixes: list[str]) -> list[dict[str, Any]]:
    if not is_file_db_configured():
        return []

    rows: list[dict[str, Any]] = []
    seen_ids = set()
    code = (facility_code or "").strip() or None

    for prefix in prefixes:
        try:
            current_rows = list_files_by_prefix(
                module_code="model_files",
                logical_path_prefix=prefix,
                facility_code=code,
            )
        except FileBackendError:
            current_rows = []
        except Exception:
            current_rows = []

        if not current_rows:
            try:
                current_rows = list_files_by_prefix(
                    module_code="model_files",
                    logical_path_prefix=prefix,
                    facility_code=None,
                )
            except Exception:
                current_rows = []

        for row in current_rows:
            row_id = row.get("id")
            sig = row_id if row_id is not None else (
                str(row.get("stored_name") or ""),
                str(row.get("storage_path") or ""),
                _model_row_logical_path(row),
            )
            if sig in seen_ids:
                continue
            seen_ids.add(sig)
            rows.append(dict(row))

    return rows


def _find_current_model_file_from_db_for_preview(facility_code: str) -> str:
    code = (facility_code or "").strip()
    if not code:
        return ""

    prefixes = [
        f"{code}/当前模型/结构模型",
        f"{code}/当前模型/结构模型/用户上传",
    ]

    candidates: list[tuple[int, float, str]] = []
    for row in _query_model_file_rows_for_preview(code, prefixes):
        path = _model_row_storage_path(row)
        if not path:
            continue

        name = os.path.basename(path)
        name_score = _sacinp_name_score_for_preview(name)
        if name_score <= 0:
            continue
        if name.lower().startswith("seainp"):
            continue
        if not _file_has_model_signature_for_preview(path):
            continue

        logical = _model_row_logical_path(row)
        path_low = path.lower()
        score = name_score
        if "当前模型" in logical:
            score += 300
        if "结构模型" in logical:
            score += 220
        if "用户上传" in logical:
            score += 50
        if "海况" in logical:
            score -= 500
        if code.lower() in path_low:
            score += 80
        if path_low.endswith("sacinp.jknew"):
            score += 800
        if path_low.endswith("sacinp.m1"):
            score -= 600

        candidates.append((score, _model_db_row_time(row), path))

    if not candidates:
        return ""

    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][2]


def _find_best_inp_file_for_preview(facility_code: str, model_files_root: str, upload_dir: str) -> str:
    roots = [model_files_root, upload_dir]
    code = (facility_code or "").strip().lower()
    if not code:
        return ""

    candidates: list[tuple[int, float, str]] = []
    seen = set()
    for root in roots:
        if not os.path.isdir(root):
            continue

        for dir_path, _, file_names in os.walk(root):
            for fn in file_names:
                name_score = _sacinp_name_score_for_preview(fn)
                if name_score <= 0:
                    continue

                full = os.path.normpath(os.path.join(dir_path, fn))
                if full in seen:
                    continue
                seen.add(full)

                name_low = fn.lower()
                path_low = full.lower()
                score = 0
                if code not in path_low:
                    continue
                if code in name_low:
                    score += 200
                if "model_files" in path_low:
                    score += 60
                if ("静力" in full) or ("static" in path_low):
                    score += 25
                if "demo_platform_jacket" in name_low:
                    score -= 200
                if path_low.endswith("sacinp.jknew"):
                    score += 800
                if path_low.endswith("sacinp.m1"):
                    score -= 400
                if "当前模型" in path_low:
                    score += 300
                if not _file_has_model_signature_for_preview(full):
                    continue

                score += name_score + 120
                try:
                    mtime = os.path.getmtime(full)
                except OSError:
                    mtime = 0.0
                candidates.append((score, mtime, full))

    if not candidates:
        return ""

    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return candidates[0][2]


def _client_cache_root_for_preview() -> str:
    root = os.path.join(os.getcwd(), ".client_cache", "model_files")
    os.makedirs(root, exist_ok=True)
    return os.path.normpath(root)


def _is_local_accessible_file_for_preview(path: object) -> bool:
    text = os.path.normpath(str(path or "").strip())
    return bool(text and os.path.isfile(text))


def _cached_remote_model_file_for_preview(facility_code: str, cached_path: str = "") -> str:
    code = str(facility_code or "").strip()
    candidates = [
        os.path.normpath(str(cached_path or "").strip()),
        os.path.join(_client_cache_root_for_preview(), code, "sacinp_from_server") if code else "",
    ]
    for candidate in candidates:
        if _is_local_accessible_file_for_preview(candidate):
            return candidate
    return ""


def _download_latest_model_from_server_for_preview(
    facility_code: str,
    *,
    force: bool = False,
    cached_path: str = "",
) -> str:
    code = str(facility_code or "").strip()
    if not code or ApiClient is None:
        return ""

    if not force:
        cached = _cached_remote_model_file_for_preview(code, cached_path)
        if cached:
            return cached

    try:
        local_path = ApiClient().download_latest_model_file(code)
        local_path = os.path.normpath(str(local_path or ""))
        if _is_local_accessible_file_for_preview(local_path):
            return local_path
    except Exception as exc:
        print("[PlatformStrengthPage] worker download latest model failed:", exc)
    return ""


def resolve_model_preview_file(payload: dict[str, Any]) -> str:
    facility_code = str(payload.get("facility_code") or "").strip()
    if not facility_code:
        return ""

    if bool(payload.get("allow_remote", True)):
        remote_model = _download_latest_model_from_server_for_preview(
            facility_code,
            force=bool(payload.get("force_remote")),
            cached_path=str(payload.get("cached_remote_model_path") or ""),
        )
        if remote_model:
            return remote_model

    db_model = _find_current_model_file_from_db_for_preview(facility_code)
    if db_model:
        return db_model

    runtime_dir = os.path.normpath(get_job_runtime_dir(facility_code))
    for candidate in (
        os.path.join(runtime_dir, "sacinp.JKnew"),
        os.path.join(runtime_dir, "sacinp.M1"),
    ):
        if os.path.exists(candidate):
            return candidate

    return _find_best_inp_file_for_preview(
        facility_code,
        str(payload.get("model_files_root") or "").strip(),
        str(payload.get("upload_dir") or "").strip(),
    )


def load_model_preview_payload(payload: dict[str, Any]) -> dict[str, Any]:
    raw_path = str(payload.get("path") or "").strip()
    file_path = os.path.normpath(raw_path) if raw_path else ""
    if not file_path:
        file_path = resolve_model_preview_file(payload)
    target_z = float(payload.get("target_z") or 9.1)
    if not file_path:
        return {
            "seq": payload.get("seq"),
            "path": "",
            "target_z": target_z,
            "nodes": {},
            "members": [],
            "groups_od": {},
            "leg_joints": [],
            "tubular_joints": [],
            "mud_level": None,
        }
    nodes, members, groups_od = parse_sacs_full_robust_file(file_path)
    leg_joints, tubular_joints = classify_sacs_model_joints(nodes, members, groups_od, target_z=target_z)
    return {
        "seq": payload.get("seq"),
        "path": file_path,
        "target_z": target_z,
        "nodes": nodes,
        "members": members,
        "groups_od": groups_od,
        "leg_joints": leg_joints,
        "tubular_joints": tubular_joints,
        "mud_level": parse_mud_level_from_sacinp_file(file_path),
    }


class QuickAssessmentPreparationWorker(QObject):
    finished = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, payload: dict[str, Any]):
        super().__init__()
        self._payload = dict(payload)

    def run(self) -> None:
        try:
            self.finished.emit(run_quick_assessment_preparation(self._payload))
        except Exception as exc:
            self.failed.emit(str(exc))


class StrengthEnvLoadWorker(QObject):
    finished = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, payload: dict[str, Any]):
        super().__init__()
        self._payload = dict(payload)

    def run(self) -> None:
        try:
            self.finished.emit(load_strength_env_payload(self._payload))
        except Exception as exc:
            self.failed.emit(str(exc))


class ModelPreviewLoadWorker(QObject):
    finished = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, payload: dict[str, Any]):
        super().__init__()
        self._payload = dict(payload)

    def run(self) -> None:
        try:
            self.finished.emit(load_model_preview_payload(self._payload))
        except Exception as exc:
            self.failed.emit(str(exc))


def load_strength_env_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Load structure-strength environment data without touching Qt widgets."""
    branch = str(payload.get("branch") or "").strip()
    op_company = str(payload.get("op_company") or "").strip()
    oilfield = str(payload.get("oilfield") or "").strip()
    facility_code = str(payload.get("facility_code") or "").strip()
    mysql_url = str(payload.get("mysql_url") or "").strip()

    result: dict[str, Any] = {
        "seq": payload.get("seq"),
        "branch": branch,
        "op_company": op_company,
        "oilfield": oilfield,
        "facility_code": facility_code,
        "profile_id": None,
        "splash_items": [],
        "pile_items": [],
        "marine_items": [],
        "structure_model_info": None,
        "horizontal_levels": [],
    }
    if not (branch and op_company and oilfield and facility_code):
        return result

    profile_id = get_env_profile_id(
        branch=branch,
        op_company=op_company,
        oilfield=oilfield,
        create_if_missing=False,
    )
    if not profile_id:
        return result

    result["profile_id"] = int(profile_id)
    result["splash_items"] = load_platform_strength_splash_items(
        int(profile_id),
        facility_code,
        mysql_url=mysql_url or None,
    )
    result["pile_items"] = load_platform_strength_pile_items(
        int(profile_id),
        facility_code,
        mysql_url=mysql_url or None,
    )
    result["marine_items"] = load_platform_strength_marine_items(
        int(profile_id),
        facility_code,
        mysql_url=mysql_url or None,
    )
    if mysql_url:
        result["structure_model_info"] = load_structure_model_info(
            mysql_url,
            profile_id=int(profile_id),
            facility_code=facility_code,
        )
        result["horizontal_levels"] = load_horizontal_levels(
            mysql_url,
            profile_id=int(profile_id),
            facility_code=facility_code,
        )
    return result


class PyVistaSacsView(QFrame):
    COLOR_SCHEME = {
        "background": "white",
        "main_structure": "#E9D012",   # 原结构：暖黄色
        "leg_joint": "#B22222",        # 主腿节点：深红
        "tubular_joint": "#2A7F9E",    # 核心管节点：湖蓝
    }

    def __init__(self, parent=None):
        super().__init__(parent)

        self._vtk_closed = False
        self._loaded_path = ""
        self._nodes = {}
        self._members = []
        self._groups_od = {}

        self._last_pan_x = 0
        self._last_pan_y = 0

        self._initial_camera_position = None
        self._initial_camera_focal_point = None
        self._initial_camera_up = None
        self._initial_parallel_scale = None

        self._slider_h = None
        self._slider_v = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.plotter = QtInteractor(self)
        self.plotter.installEventFilter(self)
        layout.addWidget(self.plotter)

        self.plotter.set_background(self.COLOR_SCHEME["background"])
        self.plotter.add_axes()

    def _plotter_ready(self) -> bool:
        return (not getattr(self, "_vtk_closed", False)) and getattr(self, "plotter", None) is not None

    def _safe_render(self) -> bool:
        if not self._plotter_ready():
            return False
        try:
            self.plotter.render()
            return True
        except Exception:
            return False

    def _can_export_current_view(self) -> bool:
        if not self._plotter_ready():
            return False
        try:
            return bool(self.isVisible() and self.plotter.isVisible())
        except Exception:
            return False

    def cleanup_vtk(self) -> None:
        if getattr(self, "_vtk_closed", False):
            return
        self._vtk_closed = True
        plotter = getattr(self, "plotter", None)
        if plotter is None:
            return
        try:
            plotter.removeEventFilter(self)
        except Exception:
            pass
        try:
            plotter.clear()
        except Exception:
            pass
        try:
            render_window = plotter.GetRenderWindow()
            if render_window is not None:
                render_window.Finalize()
        except Exception:
            pass
        try:
            plotter.close()
        except Exception:
            pass

    def closeEvent(self, event):
        self.cleanup_vtk()
        super().closeEvent(event)

    def deleteLater(self):
        self.cleanup_vtk()
        super().deleteLater()

    def clear_view(self, message: str = ""):
        if not self._plotter_ready():
            return
        try:
            self.plotter.clear()
            self.plotter.set_background(self.COLOR_SCHEME["background"])
            self.plotter.add_axes()
            if message:
                self.plotter.add_text(message, position="upper_left", font_size=10)
        except Exception:
            pass

    def eventFilter(self, obj, event):
        if obj is self.plotter and event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.RightButton:
                self.reset_to_initial_view()
                return True
        return super().eventFilter(obj, event)

    def reset_to_initial_view(self):
        if self._initial_camera_position is None:
            return

        cam = self.plotter.camera
        cam.position = self._initial_camera_position
        cam.focal_point = self._initial_camera_focal_point
        cam.up = self._initial_camera_up

        try:
            cam.parallel_scale = self._initial_parallel_scale
        except Exception:
            pass

        # 重置平移状态
        self.reset_pan_state()

        # 同步重置滑动条位置
        if self._slider_h is not None:
            self._slider_h.blockSignals(True)
            self._slider_h.setValue(0)
            self._slider_h.blockSignals(False)

        if self._slider_v is not None:
            self._slider_v.blockSignals(True)
            self._slider_v.setValue(0)
            self._slider_v.blockSignals(False)

        self._safe_render()

    def load_inp(self, file_path: str, target_z: float = 9.1):
        payload = load_model_preview_payload({"path": file_path, "target_z": target_z})
        self.apply_model_preview_payload(payload)

    def apply_model_preview_payload(self, payload: dict[str, Any]) -> None:
        self._loaded_path = str(payload.get("path") or "")
        self._nodes = dict(payload.get("nodes") or {})
        self._members = list(payload.get("members") or [])
        self._groups_od = dict(payload.get("groups_od") or {})

        if not self._nodes or not self._members:
            self.clear_view("未解析到有效的 SACS JOINT/MEMBER 数据")
            return

        self.render_structure(
            self._nodes,
            self._members,
            list(payload.get("leg_joints") or []),
            list(payload.get("tubular_joints") or []),
        )

    def parse_sacs_full_robust(self, filepath):
        return parse_sacs_full_robust_file(filepath)

    def _get_shared_preferred_model_file(self, facility_code: str) -> str:
        code = (facility_code or "").strip()
        if not code:
            return ""

        # 仅作为兜底预览：新流程不再读取 sacs_jobs/<平台>/source。
        runtime_dir = os.path.normpath(get_job_runtime_dir(code))
        candidates = [
            os.path.join(runtime_dir, "sacinp.M1"),
            os.path.join(runtime_dir, "sacinp.JKnew"),
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return ""

    def _resolve_preview_model_file(self, facility_code: str) -> str:
        shared = self._get_shared_preferred_model_file(facility_code)
        if shared:
            return shared
        return self._find_best_inp_file(facility_code)
    def apply_pdf_logic_diagnostic(self, nodes, members, groups_od, target_z=8.5):
        return classify_sacs_model_joints(nodes, members, groups_od, target_z=target_z)

    def render_structure(self, nodes, members, leg_joints, tubular_joints):
        """渲染当前模型。

        按最新需求：
        - 不再区分 Main Structure / Leg Joint / Tubular Joint 的颜色与点位标注；
        - 整个模型统一用黄色绘制；
        - 保留坐标轴与相机行为不变。
        """
        if not self._plotter_ready():
            return

        try:
            self.plotter.clear()
            self.plotter.set_background(self.COLOR_SCHEME["background"])
        except Exception:
            return

        node_list = list(nodes.keys())
        id_map = {nid: i for i, nid in enumerate(node_list)}
        points = np.array([nodes[nid] for nid in node_list], dtype=float)

        if len(points) == 0:
            self.clear_view("没有可显示的节点")
            return

        lines = []
        for na, nb, _ in members:
            if na in id_map and nb in id_map:
                lines.extend([2, id_map[na], id_map[nb]])

        mesh = pv.PolyData(points)
        if lines:
            mesh.lines = np.array(lines)

        try:
            structure = mesh.tube(radius=0.12, n_sides=8)
            self.plotter.add_mesh(
                structure,
                color=self.COLOR_SCHEME["main_structure"],
                opacity=0.90,
                label="Structure",
            )
        except Exception:
            self.plotter.add_mesh(
                mesh,
                color=self.COLOR_SCHEME["main_structure"],
                line_width=1.2,
                opacity=0.95,
                label="Structure",
            )

        self.plotter.add_axes()
        self.plotter.reset_camera()

        cam = self.plotter.camera
        self._initial_camera_position = tuple(cam.position)
        self._initial_camera_focal_point = tuple(cam.focal_point)
        self._initial_camera_up = tuple(cam.up)

        try:
            self._initial_parallel_scale = cam.parallel_scale
        except Exception:
            self._initial_parallel_scale = None

        self._safe_render()

    def export_current_view(self, output_path: str, width: int = 3200, height: int = 3200, scale: int = 4) -> str:
        """导出当前三维视图为高清 PNG，页面显示尺寸不变。"""
        output = os.path.normpath(str(output_path or "").strip())
        if not output or not self._can_export_current_view():
            return ""
        folder = os.path.dirname(output)
        if folder:
            os.makedirs(folder, exist_ok=True)

        width = max(int(width or 3200), 1200)
        height = max(int(height or 3200), 1200)
        scale = max(int(scale or 1), 1)

        if not self._safe_render():
            return ""

        try:
            self.plotter.screenshot(output, scale=scale)
        except TypeError:
            try:
                self.plotter.screenshot(output, window_size=(width, height))
            except TypeError:
                old_size = None
                try:
                    old_size = tuple(getattr(self.plotter, "window_size", ()) or ())
                except Exception:
                    old_size = None
                try:
                    try:
                        self.plotter.window_size = [width, height]
                    except Exception:
                        pass
                    self._safe_render()
                    self.plotter.screenshot(output)
                finally:
                    if old_size and len(old_size) == 2:
                        try:
                            self.plotter.window_size = list(old_size)
                            self._safe_render()
                        except Exception:
                            pass
        except Exception:
            try:
                self.plotter.screenshot(output)
            except Exception:
                return ""

        return output if os.path.exists(output) else ""

    def pan_view(self, x_value: int, y_value: int):
        dx_slider = x_value - self._last_pan_x
        dy_slider = y_value - self._last_pan_y

        self._last_pan_x = x_value
        self._last_pan_y = y_value

        if dx_slider == 0 and dy_slider == 0:
            return

        if not self._plotter_ready():
            return

        cam = self.plotter.camera

        pos = np.array(cam.position, dtype=float)
        focal = np.array(cam.focal_point, dtype=float)
        up = np.array(cam.up, dtype=float)

        forward = focal - pos
        dist = np.linalg.norm(forward)
        if dist < 1e-9:
            return
        forward = forward / dist

        up = up / (np.linalg.norm(up) + 1e-12)
        right = np.cross(forward, up)
        right_norm = np.linalg.norm(right)
        if right_norm < 1e-9:
            return
        right = right / right_norm

        true_up = np.cross(right, forward)
        true_up = true_up / (np.linalg.norm(true_up) + 1e-12)

        # 用当前相机距离控制平移步长，放大后也不会一下子跳太远
        step = max(dist * 0.02, 0.5)

        shift = right * (dx_slider * step) + true_up * (dy_slider * step)

        cam.position = tuple(pos + shift)
        cam.focal_point = tuple(focal + shift)

        self._safe_render()

    def reset_pan_state(self):
        self._last_pan_x = 0
        self._last_pan_y = 0

    def bind_sliders(self, slider_h, slider_v):
        self._slider_h = slider_h
        self._slider_v = slider_v

    def _read_lines_with_fallback(self, file_path: str) -> List[str]:
        encodings = ["utf-8", "utf-8-sig", "gb18030", "gbk", "latin-1"]
        for enc in encodings:
            try:
                with open(file_path, "r", encoding=enc) as f:
                    return f.readlines()
            except UnicodeDecodeError:
                continue
            except Exception:
                break
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.readlines()

class PlatformStrengthPage(BasePage):
    """结构强度 -> 平台强度页面。"""

    TOP_FIELDS: List[Tuple[str, str]] = [
        ("分公司", "湛江分公司"),
        ("作业公司", "文昌油田群作业公司"),
        ("油气田", "文昌19-1油田"),
        ("设施编码", "WC19-1WHPC"),
        ("设施名称", "文昌19-1WHPC井口平台"),
        ("设施类型", "平台"),
        ("分类", "井口平台"),
        ("投产时间", "2013-07-15"),
        ("设计年限", "15"),
    ]

    KEY_TO_FIELD: Dict[str, str] = {
        "branch": "分公司",
        "op_company": "作业公司",
        "oilfield": "油气田",
        "facility_code": "设施编码",
        "facility_name": "设施名称",
        "facility_type": "设施类型",
        "category": "分类",
        "start_time": "投产时间",
        "design_life": "设计年限",
    }
    FIELD_TO_KEY: Dict[str, str] = {v: k for k, v in KEY_TO_FIELD.items()}
    TOP_KEY_ORDER: List[str] = [
        "branch", "op_company", "oilfield", "facility_code", "facility_name",
        "facility_type", "category", "start_time", "design_life",
    ]

    @staticmethod
    def _songti_small_four_font(bold: bool = False) -> QFont:
        font = QFont("SimSun")
        font.setPointSize(12)
        font.setBold(bold)
        return font

    def __init__(self, main_window, parent=None):
        if parent is None:
            parent = main_window
        super().__init__("", parent)
        self.main_window = main_window

        self.data_dir = first_existing_path("data")
        self.upload_dir = first_existing_path("upload")
        self.model_files_root = first_existing_path("upload", "model_files")

        # 远程服务端文件缓存：
        # 结构强度页面在客户端运行时，不能直接访问服务端 D:/shiyou_file_storage。
        # 因此通过 /api/files/download/latest-model 和 /api/files/download/latest-sea
        # 下载到 .client_cache 后再交给 PyVista/SACS 解析显示。
        self._remote_model_file_cache: Dict[str, str] = {}
        self._remote_sea_file_cache: Dict[str, str] = {}

        self._model_signature_cache: Dict[str, Tuple[float, bool]] = {}
        self._default_splash_items: List[Dict] = []
        self._default_pile_items: List[Dict] = []
        self._default_marine_items: List[Dict] = []

        # 水平层高程改为数据库驱动：主页面只显示数据库中保存的高程；
        # 节点数量限制只在“水平层高程-更新到数据库”弹窗中使用。
        self._horizontal_level_threshold = 40
        self._horizontal_levels: List[Tuple[float, int, bool]] = []

        # 三维总图：打开结构强度页后自动保存；避免重复/过期导出。
        self._overall_export_seq = 0
        self._last_saved_overall_image_key = ""
        self._is_closing = False
        self._quick_assessment_thread: QThread | None = None
        self._quick_assessment_worker: QuickAssessmentPreparationWorker | None = None
        self._quick_assessment_progress: QProgressDialog | None = None
        self._quick_assessment_context: dict[str, Any] = {}
        self._strength_env_thread: QThread | None = None
        self._strength_env_worker: StrengthEnvLoadWorker | None = None
        self._strength_env_jobs: list[tuple[QThread, StrengthEnvLoadWorker]] = []
        self._strength_env_load_seq = 0
        self._model_autoload_seq = 0
        self._model_preview_thread: QThread | None = None
        self._model_preview_worker: ModelPreviewLoadWorker | None = None
        self._model_preview_jobs: list[tuple[QThread, ModelPreviewLoadWorker]] = []
        self._model_preview_load_seq = 0

        self._build_ui()
        self._capture_default_strength_env_tables()
        self._schedule_initial_page_load()

    # ---------------- 顶部下拉 ----------------
    def _normalize_top_value(self, value: object) -> str:
        txt = "" if value is None else str(value).strip()
        if (not txt) or (txt.lower() == "nan"):
            return ""
        if txt.endswith(".0") and txt[:-2].isdigit():
            return txt[:-2]
        return txt

    def _load_top_records_from_excel(self) -> List[Dict[str, str]]:
        if (not self._excel_loaded) or (not hasattr(self._excel_provider, "df")):
            return []

        df = self._excel_provider.df
        if df is None:
            return []

        fields = [f for f, _ in self.TOP_FIELDS]
        resolved: Dict[str, str] = {}
        for field in fields:
            col = self._excel_provider._resolve_col(field) if hasattr(self._excel_provider, "_resolve_col") else None
            if not col:
                return []
            resolved[field] = col

        rows: List[Dict[str, str]] = []
        seen = set()
        for _, row in df.iterrows():
            rec: Dict[str, str] = {}
            for field, col in resolved.items():
                raw = self._excel_provider._clean(row[col]) if hasattr(self._excel_provider, "_clean") else row[col]
                rec[field] = self._normalize_top_value(raw)

            if not any(rec.get(k) for k in ("分公司", "作业公司", "油气田", "设施编码", "设施名称")):
                continue

            sig = tuple(rec.get(f, "") for f in fields)
            if sig in seen:
                continue
            seen.add(sig)
            rows.append(rec)

        return rows

    def _unique_record_values(self, records: List[Dict[str, str]], field: str) -> List[str]:
        out: List[str] = []
        seen = set()
        for rec in records:
            v = self._normalize_top_value(rec.get(field, ""))
            if (not v) or (v in seen):
                continue
            seen.add(v)
            out.append(v)
        return out

    def _pick_option(self, options: List[str], preferred: str = "") -> str:
        p = self._normalize_top_value(preferred)
        if p and p in options:
            return p
        return options[0] if options else ""

    def _mock_top_options(self, field: str, default: str) -> List[str]:
        options_map = {
            "分公司": ["湛江分公司", "深圳分公司", "上海分公司", "海南分公司", "天津分公司"],
            "作业公司": ["文昌油田群作业公司", "涠洲作业公司", "珠江作业公司", "渤海作业公司"],
            "油气田": ["文昌19-1油田", "文昌19-2油田", "涠洲油田", "珠江口油田"],
            "设施编码": ["WC19-1WHPC", "WC19-2WHPC", "WC9-7DPP", "WC19-1DPPA"],
            "设施名称": ["文昌19-1WHPC井口平台", "文昌19-2WHPC井口平台", "WC9-7DPP井口平台"],
            "设施类型": ["平台", "导管架", "浮式"],
            "分类": ["井口平台", "生产平台", "生活平台"],
            "投产时间": ["2013-07-15", "2008-06-26", "2010-03-10"],
            "设计年限": ["10", "15", "20", "25", "30"],
        }
        opts = options_map.get(field, [default])
        return opts if default in opts else [default] + opts

    def _build_top_dropdown_fields(self) -> List[Dict]:
        platform_defaults = default_platform()
        profile = load_facility_profile(platform_defaults["facility_code"], defaults=platform_defaults)
        fallback_defaults = {
            "分公司": str(profile.get("branch") or self.TOP_FIELDS[0][1]),
            "作业公司": str(profile.get("op_company") or self.TOP_FIELDS[1][1]),
            "油气田": str(profile.get("oilfield") or self.TOP_FIELDS[2][1]),
            "设施编码": str(profile.get("facility_code") or self.TOP_FIELDS[3][1]),
            "设施名称": str(profile.get("facility_name") or self.TOP_FIELDS[4][1]),
            "设施类型": str(profile.get("facility_type") or self.TOP_FIELDS[5][1]),
            "分类": str(profile.get("category") or self.TOP_FIELDS[6][1]),
            "投产时间": str(profile.get("start_time") or self.TOP_FIELDS[7][1]),
            "设计年限": str(profile.get("design_life") or self.TOP_FIELDS[8][1]),
        }
        stretch_map = {
            "branch": 1,
            "op_company": 2,
            "oilfield": 2,
            "facility_code": 2,
            "facility_name": 3,
            "facility_type": 1,
            "category": 1,
            "start_time": 1,
            "design_life": 1,
        }
        fields: List[Dict] = []
        for key in self.TOP_KEY_ORDER:
            label = self.KEY_TO_FIELD[key]
            fallback = fallback_defaults.get(label, "")
            opts = [fallback] if fallback else []
            default = fallback
            fields.append({
                "key": key,
                "label": label,
                "options": opts,
                "default": default,
                "stretch": stretch_map.get(key, 1),
            })

        # 最后一列：操作（下方单元格将替换为“快速评估”按钮）
        fields.append({
            "key": "operation",
            "label": "操作",
            "options": [""],
            "default": "",
            "stretch": 1,
        })
        return fields

    def _embed_operation_button_in_dropdown(self):
        if not hasattr(self, "dropdown_bar"):
            return
        combo = self.dropdown_bar.get_combo("operation")
        if combo is None:
            return

        outer_layout = self.dropdown_bar.layout()
        if outer_layout is None or outer_layout.count() == 0:
            return
        grid = outer_layout.itemAt(0).layout()
        if grid is None:
            return

        idx = grid.indexOf(combo)
        if idx < 0:
            return
        row, col, row_span, col_span = grid.getItemPosition(idx)

        self.evaluate_btn = QPushButton("快速评估")
        self.evaluate_btn.setFont(self._songti_small_four_font(bold=True))
        self.evaluate_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.evaluate_btn.setMinimumHeight(max(32, combo.sizeHint().height()))
        self.evaluate_btn.setStyleSheet("""
            QPushButton {
                background: #f6a24a;
                border: 1px solid #2f3a4a;
                border-radius: 3px;
                padding: 6px 16px;
                font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
                font-size: 12pt;
                font-weight: bold;
            }
            QPushButton:hover { background: #ffb86b; }
            QPushButton:pressed { background: #e68a00; }
        """)
        self.evaluate_btn.clicked.connect(self.on_quick_evaluate)

        grid.removeWidget(combo)
        combo.hide()
        combo.deleteLater()
        if hasattr(self.dropdown_bar, "_combos"):
            self.dropdown_bar._combos.pop("operation", None)

        grid.addWidget(self.evaluate_btn, row, col, row_span, col_span)

    def _sync_platform_ui(self, changed_key: str | None = None):
        if not hasattr(self, "dropdown_bar"):
            return
        platform = sync_platform_dropdowns(self.dropdown_bar, changed_key=changed_key)
        profile = load_facility_profile(
            platform["facility_code"],
            defaults={
                "branch": platform["branch"],
                "op_company": platform["op_company"],
                "oilfield": platform["oilfield"],
                "facility_code": platform["facility_code"],
                "facility_name": platform["facility_name"],
                "facility_type": platform["facility_type"],
                "category": platform["category"],
                "start_time": platform["start_time"],
                "design_life": platform["design_life"],
            },
        )
        if hasattr(self, "tbl_splash") and hasattr(self, "tbl_pile") and hasattr(self, "tbl_marine"):
            self._start_async_strength_env_load()

    def _on_top_key_changed(self, key: str, txt: str):
        if key in {"branch", "op_company", "oilfield", "facility_code", "facility_name"}:
            self._sync_platform_ui(changed_key=key)
            self._schedule_autoload_inp_to_view(force_remote=True)

    def _get_top_value(self, key: str) -> str:
        if not hasattr(self, "dropdown_bar"):
            return ""
        try:
            return (self.dropdown_bar.get_value(key) or "").strip()
        except Exception:
            return ""

    def _safe_int(self, text: str, default: int) -> int:
        try:
            return int(float((text or "").strip()))
        except Exception:
            return default

    def _safe_float(self, text: str, default: float) -> float:
        try:
            return float((text or "").strip())
        except Exception:
            return default

    def _table_text(self, table: QTableWidget, row: int, col: int) -> str:
        item = table.item(row, col)
        if item is None:
            return ""
        return (item.text() or "").strip()

    def _parse_optional_float(self, text: str) -> float | None:
        value = (text or "").strip()
        if not value:
            return None
        return float(value)

    def _format_optional_number(self, value: object) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        if not text:
            return ""
        try:
            number = float(text)
        except Exception:
            return text
        return f"{number:.3f}".rstrip("0").rstrip(".")

    def _set_table_text(self, table: QTableWidget, row: int, col: int, text: str):
        item = table.item(row, col)
        if item is None:
            self._set_center_item(table, row, col, text)
            return
        item.setText(text)

    def _default_marine_layer_items(self) -> List[Dict[str, object]]:
        return [{
            "layer_no": 1,
            "upper_limit_m": None,
            "lower_limit_m": None,
            "thickness_mm": None,
            "density_t_per_m3": None,
            "sort_order": 1,
        }]

    def _marine_layer_count_from_items(self, items: List[Dict]) -> int:
        max_layer_no = 0
        for index, item in enumerate(items or [], start=1):
            try:
                layer_no = int(item.get("layer_no", 0) or 0)
            except Exception:
                layer_no = 0
            max_layer_no = max(max_layer_no, layer_no, index)
        return max(1, max_layer_no)

    def _marine_layer_count(self) -> int:
        if not hasattr(self, "tbl_marine"):
            return len(self._default_marine_layer_items())
        return max(1, self.tbl_marine.columnCount() - 3)

    def _configure_marine_display_table(self, layer_count: int) -> None:
        tbl_marine = self.tbl_marine
        layer_count = max(1, int(layer_count or 1))
        tbl_marine.clearSpans()
        tbl_marine.setColumnCount(3 + layer_count)

        tbl_marine.setSpan(0, 0, 1, 3)
        self._set_center_item(tbl_marine, 0, 0, "层数", editable=False)
        for i in range(layer_count):
            self._set_center_item(tbl_marine, 0, 3 + i, str(i + 1), editable=False)

        tbl_marine.setSpan(1, 0, 2, 2)
        self._set_center_item(tbl_marine, 1, 0, "高度区域", editable=False)
        self._set_center_item(tbl_marine, 1, 2, "上限(m)", editable=False)
        self._set_center_item(tbl_marine, 2, 2, "下限(m)", editable=False)

        tbl_marine.setSpan(3, 0, 1, 2)
        self._set_center_item(tbl_marine, 3, 0, "海生物", editable=False)
        self._set_center_item(tbl_marine, 3, 2, "厚度(mm)", editable=False)

        tbl_marine.setSpan(4, 0, 1, 3)
        tbl_marine.setSpan(4, 3, 1, layer_count)
        self._set_center_item(tbl_marine, 4, 0, "海生物密度（t/m^3）", editable=False)

    def _populate_marine_display_table(self, items: List[Dict]) -> None:
        source_items = items or self._default_marine_items or self._default_marine_layer_items()
        layer_count = self._marine_layer_count_from_items(source_items)
        self._configure_marine_display_table(layer_count)
        by_layer = {
            int(item.get("layer_no", 0) or 0): item
            for item in source_items
            if int(item.get("layer_no", 0) or 0) > 0
        }
        density_text = ""
        for i in range(layer_count):
            layer_no = i + 1
            source = by_layer.get(layer_no, {})
            col = 3 + i
            self._set_table_text(self.tbl_marine, 1, col, self._format_optional_number(source.get("upper_limit_m")))
            self._set_table_text(self.tbl_marine, 2, col, self._format_optional_number(source.get("lower_limit_m")))
            self._set_table_text(self.tbl_marine, 3, col, self._format_optional_number(source.get("thickness_mm")))
            if not density_text:
                density_text = self._format_optional_number(source.get("density_t_per_m3"))
        self._set_table_text(self.tbl_marine, 4, 3, density_text)

    def _collect_marine_items_from_display_table(self) -> List[Dict[str, object]]:
        items: List[Dict[str, object]] = []
        density_text = self._table_text(self.tbl_marine, 4, 3)
        density_value = self._parse_optional_float(density_text)
        for i in range(self._marine_layer_count()):
            col = 3 + i
            items.append({
                "layer_no": i + 1,
                "upper_limit_m": self._parse_optional_float(self._table_text(self.tbl_marine, 1, col)),
                "lower_limit_m": self._parse_optional_float(self._table_text(self.tbl_marine, 2, col)),
                "thickness_mm": self._parse_optional_float(self._table_text(self.tbl_marine, 3, col)),
                "density_t_per_m3": density_value,
                "sort_order": i + 1,
            })
        return items

    def _capture_default_strength_env_tables(self):
        self._default_splash_items = [{
            "upper_limit_m": self._parse_optional_float(self._table_text(self.tbl_splash, 0, 0)),
            "lower_limit_m": self._parse_optional_float(self._table_text(self.tbl_splash, 0, 1)),
            "corrosion_allowance_mm_per_y": self._parse_optional_float(self._table_text(self.tbl_splash, 0, 2)),
        }]
        self._default_pile_items = [{
            "scour_depth_m": self._parse_optional_float(self._table_text(self.tbl_pile, 0, 0)),
            "compressive_capacity_t": self._parse_optional_float(self._table_text(self.tbl_pile, 0, 1)),
            "uplift_capacity_t": self._parse_optional_float(self._table_text(self.tbl_pile, 0, 2)),
            "submerged_weight_t": self._parse_optional_float(self._table_text(self.tbl_pile, 0, 3)),
        }]
        self._default_marine_items = self._collect_marine_items_from_display_table()

    def _apply_splash_items(self, items: List[Dict]):
        source = items[0] if items else (self._default_splash_items[0] if self._default_splash_items else {})
        self._set_table_text(self.tbl_splash, 0, 0, self._format_optional_number(source.get("upper_limit_m")))
        self._set_table_text(self.tbl_splash, 0, 1, self._format_optional_number(source.get("lower_limit_m")))
        self._set_table_text(self.tbl_splash, 0, 2, self._format_optional_number(source.get("corrosion_allowance_mm_per_y")))

    def _apply_pile_items(self, items: List[Dict]):
        source = self._select_pile_display_item(items)
        self._set_table_text(self.tbl_pile, 0, 0, self._format_optional_number(source.get("scour_depth_m")))
        self._set_table_text(self.tbl_pile, 0, 1, self._format_optional_number(source.get("compressive_capacity_t")))
        self._set_table_text(self.tbl_pile, 0, 2, self._format_optional_number(source.get("uplift_capacity_t")))
        self._set_table_text(self.tbl_pile, 0, 3, self._format_optional_number(source.get("submerged_weight_t")))

    def _select_pile_display_item(self, items: List[Dict]) -> Dict:
        valid_items = [
            item for item in (items or [])
            if str(item.get("pile_head_id") or "").strip()
        ]
        for item in valid_items:
            if item.get("is_display_row"):
                return item
        if valid_items:
            return valid_items[-1]
        return self._default_pile_items[0] if self._default_pile_items else {}

    def _apply_marine_items(self, items: List[Dict]):
        self._populate_marine_display_table(items)

    def _schedule_initial_page_load(self) -> None:
        QTimer.singleShot(0, self._start_async_strength_env_load)
        self._schedule_autoload_inp_to_view(delay_ms=600)

    def _schedule_autoload_inp_to_view(self, delay_ms: int = 80, force_remote: bool = False) -> None:
        self._overall_export_seq += 1
        self._model_autoload_seq += 1
        self._model_preview_load_seq += 1
        seq = self._model_autoload_seq
        QTimer.singleShot(
            int(delay_ms),
            lambda s=seq, f=force_remote: self._do_scheduled_autoload_inp_to_view(s, f),
        )

    def _do_scheduled_autoload_inp_to_view(self, seq: int, force_remote: bool = False) -> None:
        if seq != self._model_autoload_seq or getattr(self, "_is_closing", False):
            return
        self._autoload_inp_to_view(force_remote=force_remote)

    def _build_strength_env_payload(self) -> dict[str, Any]:
        self._strength_env_load_seq += 1
        return {
            "seq": self._strength_env_load_seq,
            "branch": self._get_top_value("branch"),
            "op_company": self._get_top_value("op_company"),
            "oilfield": self._get_top_value("oilfield"),
            "facility_code": self._get_top_value("facility_code"),
            "mysql_url": self._get_mysql_url(),
        }

    def _start_async_strength_env_load(self) -> None:
        if getattr(self, "_is_closing", False):
            return
        payload = self._build_strength_env_payload()
        thread = QThread(self)
        worker = StrengthEnvLoadWorker(payload)
        worker.moveToThread(thread)

        self._strength_env_thread = thread
        self._strength_env_worker = worker
        self._strength_env_jobs.append((thread, worker))

        thread.started.connect(worker.run)
        worker.finished.connect(self._on_strength_env_loaded)
        worker.failed.connect(self._on_strength_env_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_strength_env_worker)
        thread.start()

    def _clear_strength_env_worker(self) -> None:
        sender = self.sender()
        if sender is not None:
            self._strength_env_jobs = [
                (thread, worker)
                for thread, worker in self._strength_env_jobs
                if thread is not sender
            ]
        if sender is not None and sender is not self._strength_env_thread:
            return
        self._strength_env_thread = None
        self._strength_env_worker = None

    def _payload_matches_current_strength_context(self, payload: dict[str, Any]) -> bool:
        if payload.get("seq") != self._strength_env_load_seq:
            return False
        return (
            str(payload.get("branch") or "").strip() == self._get_top_value("branch")
            and str(payload.get("op_company") or "").strip() == self._get_top_value("op_company")
            and str(payload.get("oilfield") or "").strip() == self._get_top_value("oilfield")
            and str(payload.get("facility_code") or "").strip() == self._get_top_value("facility_code")
        )

    def _apply_structure_model_info_row(self, row: dict[str, Any] | None) -> None:
        if not row:
            return
        if hasattr(self, "edt_mud_level") and row.get("mud_level_m") not in (None, ""):
            self.edt_mud_level.setText(self._format_optional_number(row.get("mud_level_m")))
        if hasattr(self, "edt_workpoint") and row.get("workpoint_m") not in (None, ""):
            self.edt_workpoint.setText(self._format_optional_number(row.get("workpoint_m")))
        if row.get("level_threshold") not in (None, ""):
            try:
                self._horizontal_level_threshold = int(float(row.get("level_threshold")))
            except Exception:
                self._horizontal_level_threshold = 40

    def _apply_horizontal_level_rows(self, rows: list[dict[str, Any]]) -> None:
        levels: List[Tuple[float, int, bool]] = []
        for row in rows or []:
            z = self._safe_db_float(row.get("z_m"))
            if z is None:
                continue
            try:
                occ = int(row.get("node_count") or 0)
            except Exception:
                occ = 0
            selected = bool(row.get("selected") if row.get("selected") is not None else 1)
            levels.append((z, occ, selected))
        self._horizontal_levels = levels
        self._refresh_layers_table()

    def _on_strength_env_loaded(self, payload: dict) -> None:
        if getattr(self, "_is_closing", False) or not self._payload_matches_current_strength_context(payload):
            return
        self._apply_splash_items(list(payload.get("splash_items") or []))
        self._apply_pile_items(list(payload.get("pile_items") or []))
        self._apply_marine_items(list(payload.get("marine_items") or []))
        self._apply_structure_model_info_row(payload.get("structure_model_info"))
        self._apply_horizontal_level_rows(list(payload.get("horizontal_levels") or []))

    def _on_strength_env_failed(self, error: str) -> None:
        if getattr(self, "_is_closing", False):
            return
        print("[PlatformStrengthPage] async load strength env failed:", error)
        self._apply_splash_items([])
        self._apply_pile_items([])
        self._apply_marine_items([])
        self._horizontal_levels = []
        self._refresh_layers_table()

    def _start_async_model_preview_load(
        self,
        facility_code: str,
        target_z: float,
        model_path: str = "",
        force_remote: bool = False,
    ) -> None:
        if getattr(self, "_is_closing", False):
            return
        self._model_preview_load_seq += 1
        code = str(facility_code or "").strip()
        payload = {
            "seq": self._model_preview_load_seq,
            "facility_code": code,
            "path": os.path.normpath(str(model_path or "").strip()) if model_path else "",
            "target_z": float(target_z or 9.1),
            "model_files_root": self.model_files_root,
            "upload_dir": self.upload_dir,
            "force_remote": bool(force_remote),
            "allow_remote": True,
            "cached_remote_model_path": self._remote_model_file_cache.get(code, ""),
        }
        thread = QThread(self)
        worker = ModelPreviewLoadWorker(payload)
        worker.moveToThread(thread)

        self._model_preview_thread = thread
        self._model_preview_worker = worker
        self._model_preview_jobs.append((thread, worker))

        thread.started.connect(worker.run)
        worker.finished.connect(self._on_model_preview_loaded)
        worker.failed.connect(self._on_model_preview_failed)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_model_preview_worker)
        thread.start()

    def _clear_model_preview_worker(self) -> None:
        sender = self.sender()
        if sender is not None:
            self._model_preview_jobs = [
                (thread, worker)
                for thread, worker in self._model_preview_jobs
                if thread is not sender
            ]
        if sender is not None and sender is not self._model_preview_thread:
            return
        self._model_preview_thread = None
        self._model_preview_worker = None

    def _reset_model_preview_pan_controls(self) -> None:
        if getattr(self, "inp_view", None) is not None:
            self.inp_view.reset_pan_state()

        if hasattr(self, "slider_h"):
            self.slider_h.blockSignals(True)
            self.slider_h.setValue(0)
            self.slider_h.blockSignals(False)

        if hasattr(self, "slider_v"):
            self.slider_v.blockSignals(True)
            self.slider_v.setValue(0)
            self.slider_v.blockSignals(False)

    def _on_model_preview_loaded(self, payload: dict) -> None:
        if getattr(self, "_is_closing", False):
            return
        if payload.get("seq") != self._model_preview_load_seq:
            return
        try:
            if not payload.get("path"):
                self.inp_path_label.setText("未找到可解析的 SACS 结构模型文件")
                self._clear_inp_view_or_placeholder(
                    "未找到可解析的 SACS 结构模型文件\n"
                    "请先上传文件名以 sacinp 开头（或扩展名为 .sacinp）的模型文件"
                )
                self._refresh_layers_table()
                return

            if not self._ensure_inp_view_created():
                return
            self.inp_view.apply_model_preview_payload(payload)
            code = str(payload.get("facility_code") or "").strip()
            path = os.path.normpath(str(payload.get("path") or "").strip())
            if code and path:
                self._remote_model_file_cache[code] = path
            self._reset_model_preview_pan_controls()
            self.inp_path_label.setText(f"当前模型文件：{payload.get('path') or ''}")

            mud_level = payload.get("mud_level")
            if mud_level and hasattr(self, "edt_mud_level"):
                self.edt_mud_level.setText(str(mud_level))

            self._refresh_layers_table()

            try:
                self._schedule_export_overall_model_image(delay_ms=1200)
            except Exception as export_exc:
                print("[PlatformStrengthPage] schedule overall model export failed:", export_exc)
        except Exception as exc:
            self.inp_path_label.setText("模型加载失败")
            self.inp_view.clear_view(f"INP 加载失败：\n{exc}")
            self._refresh_layers_table()

    def _on_model_preview_failed(self, error: str) -> None:
        if getattr(self, "_is_closing", False):
            return
        self.inp_path_label.setText("模型加载失败")
        self._clear_inp_view_or_placeholder(f"INP 加载失败：\n{error}")
        self._refresh_layers_table()

    def _load_strength_env_tables(self):
        branch = self._get_top_value("branch")
        op_company = self._get_top_value("op_company")
        oilfield = self._get_top_value("oilfield")
        facility_code = self._get_top_value("facility_code")

        if not (branch and op_company and oilfield and facility_code):
            self._apply_splash_items([])
            self._apply_pile_items([])
            self._apply_marine_items([])
            return

        try:
            profile_id = get_env_profile_id(
                branch=branch,
                op_company=op_company,
                oilfield=oilfield,
                create_if_missing=False,
            )
            if not profile_id:
                self._apply_splash_items([])
                self._apply_pile_items([])
                self._apply_marine_items([])
                return

            self._apply_splash_items(load_platform_strength_splash_items(profile_id, facility_code))
            self._apply_pile_items(load_platform_strength_pile_items(profile_id, facility_code))
            self._apply_marine_items(load_platform_strength_marine_items(profile_id, facility_code))
            self._load_structure_model_info_from_db(profile_id, facility_code)
            self._load_horizontal_levels_from_db(profile_id, facility_code)
        except Exception:
            self._apply_splash_items([])
            self._apply_pile_items([])
            self._apply_marine_items([])
            self._horizontal_levels = []
            self._refresh_layers_table()

    def _save_strength_env_tables(self) -> tuple[int, int, int]:
        branch = self._get_top_value("branch")
        op_company = self._get_top_value("op_company")
        oilfield = self._get_top_value("oilfield")
        facility_code = self._get_top_value("facility_code")

        if not (branch and op_company and oilfield):
            raise ValueError("缺少分公司/作业公司/油气田信息，无法保存结构强度环境数据。")
        if not facility_code:
            raise ValueError("缺少设施编码，无法保存结构强度环境数据。")

        profile_id = get_env_profile_id(
            branch=branch,
            op_company=op_company,
            oilfield=oilfield,
            create_if_missing=True,
        )
        if not profile_id:
            raise ValueError("未能创建或获取环境主表记录。")

        splash_items = [{
            "upper_limit_m": self._parse_optional_float(self._table_text(self.tbl_splash, 0, 0)),
            "lower_limit_m": self._parse_optional_float(self._table_text(self.tbl_splash, 0, 1)),
            "corrosion_allowance_mm_per_y": self._parse_optional_float(self._table_text(self.tbl_splash, 0, 2)),
            "sort_order": 1,
        }]

        marine_items = self._collect_marine_items_from_display_table()

        replace_platform_strength_splash_items(profile_id, facility_code, splash_items)
        replace_platform_strength_marine_items(profile_id, facility_code, marine_items)
        try:
            self._save_structure_model_info_to_db()
        except Exception as exc:
            print("[PlatformStrengthPage] save structure model info with env tables failed:", exc)
        return len(splash_items), 0, len(marine_items)

    def _current_pile_default_values(self) -> Dict[str, float | None]:
        return {
            "scour_depth_m": self._parse_optional_float(self._table_text(self.tbl_pile, 0, 0)),
            "compressive_capacity_t": self._parse_optional_float(self._table_text(self.tbl_pile, 0, 1)),
            "uplift_capacity_t": self._parse_optional_float(self._table_text(self.tbl_pile, 0, 2)),
            "submerged_weight_t": self._parse_optional_float(self._table_text(self.tbl_pile, 0, 3)),
        }

    def _get_level_threshold(self) -> int:
        """当前用于模型导入/立面划分的水平层阈值。

        主页面不再直接编辑“水平层高程节点数量限制”；
        该值由水平层高程弹窗保存到数据库后同步到这里。
        """
        try:
            return int(getattr(self, "_horizontal_level_threshold", 40) or 40)
        except Exception:
            return 40

    def _get_workpoint_value(self) -> float:
        if not hasattr(self, "edt_workpoint"):
            return 9.1
        return self._safe_float(self.edt_workpoint.text(), 9.1)

    def _get_mysql_url(self) -> str:
        return get_mysql_url()

    def _get_strength_profile_context(self, *, create_if_missing: bool = False) -> tuple[int, str]:
        branch = self._get_top_value("branch")
        op_company = self._get_top_value("op_company")
        oilfield = self._get_top_value("oilfield")
        facility_code = self._get_top_value("facility_code")

        if not (branch and op_company and oilfield):
            raise ValueError("缺少分公司/作业公司/油气田信息，无法更新数据库。")
        if not facility_code:
            raise ValueError("缺少设施编码，无法更新数据库。")

        profile_id = get_env_profile_id(
            branch=branch,
            op_company=op_company,
            oilfield=oilfield,
            create_if_missing=create_if_missing,
        )
        if not profile_id:
            raise ValueError("未能创建或获取环境主表记录。")
        return int(profile_id), facility_code

    def _safe_db_float(self, value) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except Exception:
            return None

    def _load_structure_model_info_from_db(self, profile_id: int | None = None, facility_code: str | None = None) -> None:
        try:
            if profile_id is None or facility_code is None:
                profile_id, facility_code = self._get_strength_profile_context(create_if_missing=False)
            row = load_structure_model_info(
                self._get_mysql_url(),
                profile_id=profile_id,
                facility_code=facility_code,
            )
            if not row:
                return
            if hasattr(self, "edt_mud_level") and row.get("mud_level_m") not in (None, ""):
                self.edt_mud_level.setText(self._format_optional_number(row.get("mud_level_m")))
            if hasattr(self, "edt_workpoint") and row.get("workpoint_m") not in (None, ""):
                self.edt_workpoint.setText(self._format_optional_number(row.get("workpoint_m")))
            if row.get("level_threshold") not in (None, ""):
                try:
                    self._horizontal_level_threshold = int(float(row.get("level_threshold")))
                except Exception:
                    self._horizontal_level_threshold = 40
        except Exception as exc:
            print("[PlatformStrengthPage] load structure model info failed:", exc)

    def _save_structure_model_info_values_to_db(self, mud_level: float | None, workpoint: float | None) -> None:
        profile_id, facility_code = self._get_strength_profile_context(create_if_missing=True)
        threshold = self._get_level_threshold()
        save_structure_model_info(
            self._get_mysql_url(),
            profile_id=profile_id,
            facility_code=facility_code,
            mud_level_m=mud_level,
            workpoint_m=workpoint,
            level_threshold=threshold,
        )

    def _save_structure_model_info_to_db(self) -> None:
        mud_level = self._parse_optional_float(self.edt_mud_level.text() if hasattr(self, "edt_mud_level") else "")
        workpoint = self._parse_optional_float(self.edt_workpoint.text() if hasattr(self, "edt_workpoint") else "")
        self._save_structure_model_info_values_to_db(mud_level, workpoint)

    def _load_horizontal_levels_from_db(self, profile_id: int | None = None, facility_code: str | None = None) -> List[Tuple[float, int, bool]]:
        levels: List[Tuple[float, int, bool]] = []
        try:
            if profile_id is None or facility_code is None:
                profile_id, facility_code = self._get_strength_profile_context(create_if_missing=False)
            rows = load_horizontal_levels(
                self._get_mysql_url(),
                profile_id=profile_id,
                facility_code=facility_code,
            )
            for row in rows:
                z = self._safe_db_float(row.get("z_m"))
                if z is None:
                    continue
                try:
                    occ = int(row.get("node_count") or 0)
                except Exception:
                    occ = 0
                selected = bool(row.get("selected") if row.get("selected") is not None else 1)
                levels.append((z, occ, selected))
        except Exception as exc:
            print("[PlatformStrengthPage] load horizontal levels failed:", exc)
        self._horizontal_levels = levels
        self._refresh_layers_table()
        return levels

    def _save_horizontal_levels_to_db(self, levels: List[Tuple[float, int, bool]], threshold: int) -> None:
        profile_id, facility_code = self._get_strength_profile_context(create_if_missing=True)
        self._horizontal_level_threshold = int(threshold or 40)
        save_horizontal_levels(
            self._get_mysql_url(),
            profile_id=profile_id,
            facility_code=facility_code,
            levels=levels,
            level_threshold=self._horizontal_level_threshold,
            mud_level_m=self._parse_optional_float(self.edt_mud_level.text() if hasattr(self, "edt_mud_level") else ""),
            workpoint_m=self._parse_optional_float(self.edt_workpoint.text() if hasattr(self, "edt_workpoint") else ""),
        )
        self._horizontal_levels = list(levels)
        self._refresh_layers_table()

    def _on_update_structure_model_info_to_db(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("编辑结构模型信息")
        dialog.resize(540, 230)
        root = self._setup_edit_dialog(dialog, "编辑结构模型信息", "泥面高程与工作平面高程将用于模型预览和后续分析，请确认后保存。")
        card, card_layout = self._make_dialog_card(dialog)

        form_table = QTableWidget(2, 3, dialog)
        self._init_table_common(form_table, show_vertical_header=False)
        self._style_dialog_table(form_table)
        form_table.horizontalHeader().setVisible(False)
        form_table.verticalHeader().setVisible(False)
        form_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        form_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        form_table.setColumnWidth(0, 220)
        form_table.setColumnWidth(1, 150)
        form_table.setColumnWidth(2, 60)
        self._set_center_item(form_table, 0, 0, "泥面高程", editable=False)
        self._set_center_item(form_table, 0, 1, self.edt_mud_level.text() if hasattr(self, "edt_mud_level") else "")
        self._set_center_item(form_table, 0, 2, "m", editable=False)
        self._set_center_item(form_table, 1, 0, "工作平面高程Workpoint", editable=False)
        self._set_center_item(form_table, 1, 1, self.edt_workpoint.text() if hasattr(self, "edt_workpoint") else "")
        self._set_center_item(form_table, 1, 2, "m", editable=False)
        for r in range(2):
            form_table.setRowHeight(r, 34)
        form_table.setFixedHeight(78)
        card_layout.addWidget(form_table, 0)
        root.addWidget(card, 0)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        btn_save = QPushButton("确认更新到数据库")
        btn_cancel = QPushButton("取消")
        self._style_dialog_buttons(btn_save, btn_cancel)
        bottom.addWidget(btn_save)
        bottom.addWidget(btn_cancel)
        root.addLayout(bottom)

        def save_dialog() -> None:
            try:
                mud_level = self._parse_optional_float(self._table_text(form_table, 0, 1))
                workpoint = self._parse_optional_float(self._table_text(form_table, 1, 1))
                self._save_structure_model_info_values_to_db(mud_level, workpoint)
                self.edt_mud_level.setText(self._format_optional_number(mud_level))
                self.edt_workpoint.setText(self._format_optional_number(workpoint))
                self._autoload_inp_to_view()
            except Exception as exc:
                QMessageBox.critical(dialog, "更新失败", f"结构模型信息更新到数据库失败：\n{exc}")
                return
            QMessageBox.information(dialog, "更新完成", "结构模型信息已更新到数据库。")
            dialog.accept()

        btn_save.clicked.connect(save_dialog)
        btn_cancel.clicked.connect(dialog.reject)
        dialog.exec_()

    def _on_update_splash_table_to_db(self) -> None:
        self._open_splash_edit_dialog()

    def _on_update_pile_table_to_db(self) -> None:
        self._open_pile_edit_dialog()

    def _on_update_marine_table_to_db(self) -> None:
        self._open_marine_edit_dialog()

    def _replace_splash_items_to_db(self, items: List[Dict[str, object]]) -> None:
        profile_id, facility_code = self._get_strength_profile_context(create_if_missing=True)
        replace_platform_strength_splash_items(profile_id, facility_code, items)

    def _replace_pile_items_to_db(self, items: List[Dict[str, object]]) -> None:
        profile_id, facility_code = self._get_strength_profile_context(create_if_missing=True)
        replace_platform_strength_pile_items(profile_id, facility_code, items)

    def _replace_marine_items_to_db(self, items: List[Dict[str, object]]) -> None:
        profile_id, facility_code = self._get_strength_profile_context(create_if_missing=True)
        replace_platform_strength_marine_items(profile_id, facility_code, items)

    def _setup_edit_dialog(self, dialog: QDialog, title: str, hint: str) -> QVBoxLayout:
        dialog.setStyleSheet("""
            QDialog { background-color: #f5f8fc; }
            QLabel#DialogTitle {
                color: #1d2b3a;
                font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
                font-size: 13pt;
                font-weight: bold;
            }
            QLabel#DialogHint {
                color: #52677a;
                font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
                font-size: 10pt;
            }
            QFrame#DialogCard {
                background-color: #ffffff;
                border: 1px solid #d8e2ef;
                border-radius: 8px;
            }
            QPushButton#PrimaryDialogButton {
                background-color: #168bd0;
                color: #ffffff;
                border: 1px solid #0b5f92;
                border-radius: 5px;
                padding: 6px 18px;
                font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
                font-size: 12pt;
                font-weight: bold;
            }
            QPushButton#PrimaryDialogButton:hover { background-color: #22a3ee; }
            QPushButton#PrimaryDialogButton:pressed { background-color: #0d6ca5; }
            QPushButton#SecondaryDialogButton {
                background-color: #ffffff;
                color: #34495e;
                border: 1px solid #b8c7d9;
                border-radius: 5px;
                padding: 6px 18px;
                font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
                font-size: 12pt;
            }
            QPushButton#SecondaryDialogButton:hover { background-color: #eef4fb; }
        """)
        root = QVBoxLayout(dialog)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        title_label = QLabel(title, dialog)
        title_label.setObjectName("DialogTitle")
        root.addWidget(title_label, 0)

        if hint:
            hint_label = QLabel(hint, dialog)
            hint_label.setObjectName("DialogHint")
            hint_label.setWordWrap(True)
            root.addWidget(hint_label, 0)
        return root

    def _make_dialog_card(self, parent: QWidget) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame(parent)
        card.setObjectName("DialogCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        return card, layout

    def _style_dialog_table(self, table: QTableWidget) -> None:
        table.setStyleSheet(table.styleSheet() + """
            QTableWidget {
                background-color: #ffffff;
                alternate-background-color: #f8fbff;
                border: 1px solid #ccd8e6;
                border-radius: 4px;
                gridline-color: #dce5ef;
                selection-background-color: #dbe9ff;
            }
            QTableWidget::item { padding: 4px; }
            QHeaderView::section {
                background-color: #eaf2fb;
                color: #1d2b3a;
                border: 1px solid #d7e2ef;
                padding: 6px;
            }
        """)

    def _style_dialog_buttons(self, primary: QPushButton, secondary: QPushButton) -> None:
        primary.setObjectName("PrimaryDialogButton")
        secondary.setObjectName("SecondaryDialogButton")
        for btn in (primary, secondary):
            btn.setFont(self._songti_small_four_font(bold=(btn is primary)))
            btn.setMinimumHeight(36)
            btn.setMinimumWidth(120)

    def _style_dialog_tool_button(self, button: QPushButton) -> None:
        button.setObjectName("SecondaryDialogButton")
        button.setFont(self._songti_small_four_font())
        button.setMinimumHeight(32)

    def _open_simple_table_edit_dialog(
        self,
        *,
        title: str,
        source_table: QTableWidget,
        headers: List[str],
        save_callback,
        apply_callback,
        success_message: str,
    ) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(max(560, len(headers) * 170), 190)
        root = self._setup_edit_dialog(dialog, title, "请在下方表格中编辑数据，确认后将保存到数据库并回显到主页面。")
        card, card_layout = self._make_dialog_card(dialog)

        edit_table = QTableWidget(1, len(headers), dialog)
        edit_table.setHorizontalHeaderLabels(headers)
        self._init_table_common(edit_table, show_vertical_header=False)
        self._style_dialog_table(edit_table)
        for c in range(len(headers)):
            self._set_center_item(edit_table, 0, c, self._table_text(source_table, 0, c), editable=True)
        edit_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        edit_table.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        edit_table.setRowHeight(0, 34)
        edit_table.setFixedHeight(edit_table.horizontalHeader().height() + 44)
        card_layout.addWidget(edit_table, 0)
        root.addWidget(card, 0)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        btn_save = QPushButton("确认更新到数据库")
        btn_cancel = QPushButton("取消")
        self._style_dialog_buttons(btn_save, btn_cancel)
        bottom.addWidget(btn_save)
        bottom.addWidget(btn_cancel)
        root.addLayout(bottom)

        def save_dialog() -> None:
            try:
                values = [self._parse_optional_float(self._table_text(edit_table, 0, c)) for c in range(len(headers))]
                items = save_callback(values)
                apply_callback(items)
            except Exception as exc:
                QMessageBox.critical(dialog, "更新失败", f"{title}更新到数据库失败：\n{exc}")
                return
            QMessageBox.information(dialog, "更新完成", success_message)
            dialog.accept()

        btn_save.clicked.connect(save_dialog)
        btn_cancel.clicked.connect(dialog.reject)
        dialog.exec_()

    def _open_splash_edit_dialog(self) -> None:
        def save(values: List[float | None]) -> List[Dict[str, object]]:
            items = [{
                "upper_limit_m": values[0],
                "lower_limit_m": values[1],
                "corrosion_allowance_mm_per_y": values[2],
                "sort_order": 1,
            }]
            self._replace_splash_items_to_db(items)
            return items

        self._open_simple_table_edit_dialog(
            title="编辑飞溅区腐蚀余量",
            source_table=self.tbl_splash,
            headers=["飞溅区上限(m)", "飞溅区下限(m)", "腐蚀余量(mm/y)"],
            save_callback=save,
            apply_callback=self._apply_splash_items,
            success_message="飞溅区腐蚀余量已更新到数据库。",
        )

    def _open_pile_edit_dialog(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("编辑桩基信息")
        dialog.resize(980, 460)
        dialog.setMinimumSize(880, 380)
        root = self._setup_edit_dialog(
            dialog,
            "编辑桩基信息",
            "桩头ID从当前 SACINP 的 JOINT 行 PILEHD 标记读取，也可以手动新增、删除或编辑。",
        )
        card, card_layout = self._make_dialog_card(dialog)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)
        btn_read = QPushButton("读取模型桩头")
        btn_add = QPushButton("新增行")
        btn_del = QPushButton("删除选中行")
        for btn in (btn_read, btn_add, btn_del):
            self._style_dialog_tool_button(btn)
        top.addWidget(btn_read, 0)
        top.addWidget(btn_add, 0)
        top.addWidget(btn_del, 0)
        top.addStretch(1)
        card_layout.addLayout(top)

        headers = ["桩头ID", "基础冲刷(m)", "桩基础抗压承载能力(t)", "桩基础抗拔承载能力(t)", "单根桩泥下自重(t)"]
        edit_table = QTableWidget(0, len(headers), dialog)
        edit_table.setHorizontalHeaderLabels(headers)
        self._init_table_common(edit_table, show_vertical_header=False)
        self._style_dialog_table(edit_table)
        self._install_dialog_table_clipboard(edit_table)
        edit_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        edit_table.verticalHeader().setDefaultSectionSize(34)
        card_layout.addWidget(edit_table, 1)
        root.addWidget(card, 1)

        last_touched_row = {"row": -1}

        def default_values() -> Dict[str, float | None]:
            return self._current_pile_default_values()

        def set_last_touched(row: int) -> None:
            if 0 <= row < edit_table.rowCount():
                last_touched_row["row"] = row

        def append_row(pile_head_id: str = "", values: Dict[str, object] | None = None) -> int:
            values = values or {}
            row = edit_table.rowCount()
            edit_table.insertRow(row)
            edit_table.setRowHeight(row, 34)
            self._set_center_item(edit_table, row, 0, str(pile_head_id or "").upper(), editable=True)
            keys = ["scour_depth_m", "compressive_capacity_t", "uplift_capacity_t", "submerged_weight_t"]
            for col, key in enumerate(keys, start=1):
                self._set_center_item(edit_table, row, col, self._format_optional_number(values.get(key)), editable=True)
            edit_table.setCurrentCell(row, 0)
            set_last_touched(row)
            return row

        def valid_db_rows(rows: List[Dict]) -> List[Dict]:
            return [
                row for row in rows
                if str(row.get("pile_head_id") or "").strip()
            ]

        def fill_initial_rows() -> None:
            try:
                profile_id, facility_code = self._get_strength_profile_context(create_if_missing=False)
                db_rows = valid_db_rows(load_platform_strength_pile_items(profile_id, facility_code))
            except Exception:
                db_rows = []
            edit_table.setRowCount(0)
            if db_rows:
                display_row = 0
                for i, item in enumerate(db_rows):
                    append_row(str(item.get("pile_head_id") or ""), item)
                    if item.get("is_display_row"):
                        display_row = i
                edit_table.setCurrentCell(display_row, 0)
                set_last_touched(display_row)
                return

            heads = self._read_current_model_pile_heads()
            values = default_values()
            if heads:
                for head in heads:
                    append_row(head, values)
            else:
                append_row("", values)
                QMessageBox.information(dialog, "未识别到桩头", "未从 SACINP 中识别到桩头信息，请手动维护。")

        def merge_model_heads() -> None:
            heads = self._read_current_model_pile_heads()
            if not heads:
                QMessageBox.information(dialog, "未识别到桩头", "未从 SACINP 中识别到桩头信息，请手动维护。")
                return
            existing = {
                self._table_text(edit_table, row, 0).upper()
                for row in range(edit_table.rowCount())
                if self._table_text(edit_table, row, 0)
            }
            if edit_table.rowCount() > 0:
                seed = {
                    "scour_depth_m": self._parse_optional_float(self._table_text(edit_table, 0, 1)),
                    "compressive_capacity_t": self._parse_optional_float(self._table_text(edit_table, 0, 2)),
                    "uplift_capacity_t": self._parse_optional_float(self._table_text(edit_table, 0, 3)),
                    "submerged_weight_t": self._parse_optional_float(self._table_text(edit_table, 0, 4)),
                }
            else:
                seed = default_values()
            added = 0
            for head in heads:
                if head in existing:
                    continue
                append_row(head, seed)
                existing.add(head)
                added += 1
            QMessageBox.information(dialog, "读取完成", f"已读取 {len(heads)} 个桩头，新增 {added} 行。")

        def add_empty_row() -> None:
            append_row("")

        def delete_current_row() -> None:
            row = edit_table.currentRow()
            if row < 0 and edit_table.selectedIndexes():
                row = edit_table.selectedIndexes()[0].row()
            if row < 0:
                QMessageBox.information(dialog, "请选择行", "请先选择要删除的桩基信息行。")
                return
            edit_table.removeRow(row)
            if edit_table.rowCount() <= 0:
                append_row("", default_values())
                return
            next_row = min(row, edit_table.rowCount() - 1)
            edit_table.setCurrentCell(next_row, 0)
            set_last_touched(next_row)

        def collect_items() -> tuple[List[Dict[str, object]], int]:
            items: List[Dict[str, object]] = []
            seen = set()
            display_row = last_touched_row["row"]
            if not (0 <= display_row < edit_table.rowCount()):
                display_row = edit_table.currentRow()
            if not (0 <= display_row < edit_table.rowCount()):
                display_row = edit_table.rowCount() - 1

            for row in range(edit_table.rowCount()):
                pile_head_id = self._table_text(edit_table, row, 0).upper()
                row_texts = [self._table_text(edit_table, row, col) for col in range(1, 5)]
                if not pile_head_id and not any(row_texts):
                    raise ValueError("请完整输入承载力和桩身重是数据")
                if not pile_head_id:
                    raise ValueError(f"第 {row + 1} 行桩头ID不能为空。")
                if pile_head_id in seen:
                    raise ValueError(f"桩头ID重复：{pile_head_id}")
                seen.add(pile_head_id)
                values = []
                for col, raw in enumerate(row_texts, start=1):
                    try:
                        values.append(self._parse_optional_float(raw))
                    except Exception:
                        raise ValueError(f"第 {row + 1} 行第 {col + 1} 列不是有效数字：{raw}") from None
                if values[1] is None or values[2] is None or values[3] is None:
                    raise ValueError("请完整输入承载力和桩身重是数据")
                items.append({
                    "pile_head_id": pile_head_id,
                    "scour_depth_m": values[0],
                    "compressive_capacity_t": values[1],
                    "uplift_capacity_t": values[2],
                    "submerged_weight_t": values[3],
                    "is_display_row": row == display_row,
                    "sort_order": row + 1,
                })
            if not items:
                raise ValueError("至少需要保留一条桩基信息。")
            return items, display_row

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        btn_save = QPushButton("确认更新到数据库")
        btn_cancel = QPushButton("取消")
        self._style_dialog_buttons(btn_save, btn_cancel)
        bottom.addWidget(btn_save)
        bottom.addWidget(btn_cancel)
        root.addLayout(bottom)

        def save_dialog() -> None:
            try:
                items, _display_row = collect_items()
                self._replace_pile_items_to_db(items)
                self._apply_pile_items(items)
            except ValueError as exc:
                QMessageBox.warning(dialog, "桩基信息不完整", str(exc))
                return
            except Exception as exc:
                QMessageBox.critical(dialog, "更新失败", f"桩基信息更新到数据库失败：\n{exc}")
                return
            QMessageBox.information(dialog, "更新完成", "桩基信息已更新到数据库。")
            dialog.accept()

        edit_table.currentCellChanged.connect(lambda row, _col, _prev_row, _prev_col: set_last_touched(row))
        edit_table.itemChanged.connect(lambda item: set_last_touched(item.row()) if item is not None else None)
        btn_read.clicked.connect(merge_model_heads)
        btn_add.clicked.connect(add_empty_row)
        btn_del.clicked.connect(delete_current_row)
        btn_save.clicked.connect(save_dialog)
        btn_cancel.clicked.connect(dialog.reject)

        fill_initial_rows()
        dialog.exec_()

    def _install_dialog_table_clipboard(self, table: QTableWidget) -> None:
        table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
        )
        table.setSelectionBehavior(QAbstractItemView.SelectItems)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        table._table_clipboard = TableClipboardController(
            table,
            can_paste_cell=lambda row, col, target=table: self._can_paste_dialog_table_cell(target, row, col),
            on_paste_rows_ignored=lambda count, target=table: self._show_dialog_table_tip(
                target,
                f"粘贴内容超出现有数据区，已忽略 {count} 行。",
            ),
            on_paste_cells_skipped=lambda count, target=table: self._show_dialog_table_tip(
                target,
                f"部分单元格不可粘贴，已跳过 {count} 个单元格。",
            ),
        )

    def _can_paste_dialog_table_cell(self, table: QTableWidget, row: int, col: int) -> bool:
        if not (0 <= row < table.rowCount() and 0 <= col < table.columnCount()):
            return False
        if table.cellWidget(row, col) is not None:
            return False
        item = table.item(row, col)
        if item is None:
            return True
        return bool(item.flags() & Qt.ItemIsEditable)

    def _show_dialog_table_tip(self, table: QTableWidget, message: str) -> None:
        rect = table.viewport().rect()
        pos = table.viewport().mapToGlobal(rect.center())
        QToolTip.showText(pos, message, table, rect, 2500)

    def _open_marine_edit_dialog(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("编辑海生物信息")
        dialog.resize(1120, 420)
        dialog.setMinimumSize(1080, 400)
        root = self._setup_edit_dialog(dialog, "编辑海生物信息", "每一列对应一个海生物层，可分别编辑高度范围、厚度和密度。")
        card, card_layout = self._make_dialog_card(dialog)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addStretch(1)
        btn_add_layer = QPushButton("增加层")
        btn_del_layer = QPushButton("删除选中层")
        btn_read = QPushButton("读取海况文件")
        for btn in (btn_add_layer, btn_del_layer, btn_read):
            self._style_dialog_tool_button(btn)
        top.addWidget(btn_add_layer, 0)
        top.addWidget(btn_del_layer, 0)
        top.addWidget(btn_read, 0)
        card_layout.addLayout(top)

        layer_count = self._marine_layer_count()
        edit_table = QTableWidget(4, layer_count + 1, dialog)
        edit_table.setHorizontalHeaderLabels(["项目"] + [str(i) for i in range(1, layer_count + 1)])
        self._init_table_common(edit_table, show_vertical_header=False)
        self._style_dialog_table(edit_table)
        self._install_dialog_table_clipboard(edit_table)
        labels = ["上限(m)", "下限(m)", "厚度(mm)", "密度(t/m^3)"]
        density = self._table_text(self.tbl_marine, 4, 3)
        for r, label in enumerate(labels):
            self._set_center_item(edit_table, r, 0, label, editable=False)
        for i in range(layer_count):
            source_col = 3 + i
            target_col = 1 + i
            self._set_center_item(edit_table, 0, target_col, self._table_text(self.tbl_marine, 1, source_col))
            self._set_center_item(edit_table, 1, target_col, self._table_text(self.tbl_marine, 2, source_col))
            self._set_center_item(edit_table, 2, target_col, self._table_text(self.tbl_marine, 3, source_col))
            self._set_center_item(edit_table, 3, target_col, density)
        edit_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        edit_table.setColumnWidth(0, 110)
        for r in range(4):
            edit_table.setRowHeight(r, 38)
        edit_table_h = (
            edit_table.horizontalHeader().height()
            + sum(edit_table.rowHeight(r) for r in range(edit_table.rowCount()))
            + edit_table.frameWidth() * 2
            + 8
        )
        edit_table.setFixedHeight(edit_table_h)
        edit_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        edit_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        card_layout.addWidget(edit_table, 0)
        root.addWidget(card, 0)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        btn_save = QPushButton("确认更新到数据库")
        btn_cancel = QPushButton("取消")
        self._style_dialog_buttons(btn_save, btn_cancel)
        bottom.addWidget(btn_save)
        bottom.addWidget(btn_cancel)
        root.addLayout(bottom)

        def refresh_layer_headers() -> None:
            edit_table.setHorizontalHeaderLabels(
                ["项目"] + [str(i) for i in range(1, edit_table.columnCount())]
            )
            edit_table.setColumnWidth(0, 110)

        def ensure_min_layer_column() -> None:
            if edit_table.columnCount() > 1:
                return
            edit_table.setColumnCount(2)
            for row in range(edit_table.rowCount()):
                self._set_center_item(edit_table, row, 1, "")
            refresh_layer_headers()

        def add_layer_column() -> None:
            col = edit_table.columnCount()
            edit_table.insertColumn(col)
            for row in range(edit_table.rowCount()):
                self._set_center_item(edit_table, row, col, "")
            refresh_layer_headers()

        def delete_selected_layer_columns() -> None:
            target_columns = sorted(
                {index.column() for index in edit_table.selectedIndexes() if index.column() > 0},
                reverse=True,
            )
            if not target_columns:
                QMessageBox.information(dialog, "请选择层", "请先选中要删除的海生物层。")
                return
            for col in target_columns:
                if col < edit_table.columnCount():
                    edit_table.removeColumn(col)
            ensure_min_layer_column()
            refresh_layer_headers()
            edit_table.clearSelection()

        def apply_items_to_edit_table(items: List[Dict[str, object]]) -> None:
            layer_count = self._marine_layer_count_from_items(items)
            edit_table.setColumnCount(layer_count + 1)
            refresh_layer_headers()
            for r, label in enumerate(labels):
                self._set_center_item(edit_table, r, 0, label, editable=False)
            by_layer = {
                int(item.get("layer_no", 0) or 0): item
                for item in items
                if int(item.get("layer_no", 0) or 0) > 0
            }
            first_density = ""
            for i in range(layer_count):
                item = by_layer.get(i + 1, {})
                density_text = self._format_optional_number(item.get("density_t_per_m3"))
                if not first_density and density_text:
                    first_density = density_text
                self._set_table_text(edit_table, 0, i + 1, self._format_optional_number(item.get("upper_limit_m")))
                self._set_table_text(edit_table, 1, i + 1, self._format_optional_number(item.get("lower_limit_m")))
                self._set_table_text(edit_table, 2, i + 1, self._format_optional_number(item.get("thickness_mm")))
                self._set_table_text(edit_table, 3, i + 1, density_text)
            if first_density:
                for i in range(layer_count):
                    if not self._table_text(edit_table, 3, i + 1):
                        self._set_table_text(edit_table, 3, i + 1, first_density)

        def read_from_seainp() -> None:
            try:
                sea_file = self._resolve_current_sea_file()
                if not sea_file:
                    QMessageBox.warning(dialog, "读取失败", "未在文件管理保存路径中找到当前设施对应的 SeaInp 海况文件。")
                    return
                items = self._parse_marine_growth_from_seainp(sea_file)
                if not items:
                    QMessageBox.warning(dialog, "读取失败", f"SeaInp 文件中未读取到有效 MGROV 数据：\n{sea_file}")
                    return
                apply_items_to_edit_table(items)
                QMessageBox.information(dialog, "读取完成", f"已从 SeaInp 读取 {len(items)} 层海生物信息。\n{sea_file}")
            except Exception as exc:
                QMessageBox.critical(dialog, "读取失败", f"SeaInp 海生物信息读取失败：\n{exc}")

        def save_dialog() -> None:
            try:
                items = []
                first_density = None
                for i in range(max(0, edit_table.columnCount() - 1)):
                    col = 1 + i
                    density_value = self._parse_optional_float(self._table_text(edit_table, 3, col))
                    if first_density is None and density_value is not None:
                        first_density = density_value
                    items.append({
                        "layer_no": i + 1,
                        "upper_limit_m": self._parse_optional_float(self._table_text(edit_table, 0, col)),
                        "lower_limit_m": self._parse_optional_float(self._table_text(edit_table, 1, col)),
                        "thickness_mm": self._parse_optional_float(self._table_text(edit_table, 2, col)),
                        "density_t_per_m3": density_value,
                        "sort_order": i + 1,
                    })
                if first_density is not None:
                    for item in items:
                        if item.get("density_t_per_m3") is None:
                            item["density_t_per_m3"] = first_density
                self._replace_marine_items_to_db(items)
                self._apply_marine_items(items)
            except Exception as exc:
                QMessageBox.critical(dialog, "更新失败", f"海生物信息更新到数据库失败：\n{exc}")
                return
            QMessageBox.information(dialog, "更新完成", "海生物信息已更新到数据库。")
            dialog.accept()

        btn_read.clicked.connect(read_from_seainp)
        btn_add_layer.clicked.connect(add_layer_column)
        btn_del_layer.clicked.connect(delete_selected_layer_columns)
        btn_save.clicked.connect(save_dialog)
        btn_cancel.clicked.connect(dialog.reject)
        dialog.exec_()

    def _save_splash_table_to_db(self) -> None:
        profile_id, facility_code = self._get_strength_profile_context(create_if_missing=True)
        items = [{
            "upper_limit_m": self._parse_optional_float(self._table_text(self.tbl_splash, 0, 0)),
            "lower_limit_m": self._parse_optional_float(self._table_text(self.tbl_splash, 0, 1)),
            "corrosion_allowance_mm_per_y": self._parse_optional_float(self._table_text(self.tbl_splash, 0, 2)),
            "sort_order": 1,
        }]
        replace_platform_strength_splash_items(profile_id, facility_code, items)

    def _save_pile_table_to_db(self) -> None:
        raise ValueError("桩基信息必须通过编辑弹窗按桩头ID更新到数据库。")

    def _save_marine_table_to_db(self) -> None:
        profile_id, facility_code = self._get_strength_profile_context(create_if_missing=True)
        items = self._collect_marine_items_from_display_table()
        replace_platform_strength_marine_items(profile_id, facility_code, items)

    def _on_update_horizontal_levels_to_db(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("更新水平层高程")
        dialog.resize(900, 390)
        root = self._setup_edit_dialog(
            dialog,
            "编辑水平层高程",
            "先输入节点数量限制并点击“自动更新水平高程”，也可以手动新增、删除或编辑 Z(m)，确认后保存到数据库并回显。",
        )
        card, card_layout = self._make_dialog_card(dialog)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)
        lbl = QLabel("水平层高程节点数量限制：")
        lbl.setFont(self._songti_small_four_font(bold=True))
        lbl.setStyleSheet("color:#1d2b3a;")
        edit_threshold = QLineEdit(str(self._get_level_threshold()))
        edit_threshold.setFont(self._songti_small_four_font())
        edit_threshold.setStyleSheet("background:#ffffff; border:1px solid #b8c7d9; border-radius:4px; padding:4px 6px;")
        edit_threshold.setFixedWidth(120)
        btn_auto = QPushButton("自动更新水平高程")
        btn_add = QPushButton("新增高程列")
        btn_del = QPushButton("删除选中列")
        for btn in (btn_auto, btn_add, btn_del):
            self._style_dialog_tool_button(btn)
        top.addWidget(lbl, 0)
        top.addWidget(edit_threshold, 0)
        top.addSpacing(10)
        top.addWidget(btn_auto, 0)
        top.addWidget(btn_add, 0)
        top.addWidget(btn_del, 0)
        top.addStretch(1)
        card_layout.addLayout(top)

        edit_table = QTableWidget(1, 1, dialog)
        edit_table.setHorizontalHeaderLabels(["编号"])
        self._init_table_common(edit_table, show_vertical_header=False)
        self._style_dialog_table(edit_table)
        edit_table.setEditTriggers(QAbstractItemView.DoubleClicked)
        edit_table.setStyleSheet(edit_table.styleSheet() + """
            QTableWidget::item:selected {
                background-color: #dbeafe;
            }
        """)
        edit_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        edit_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        edit_table.setSelectionBehavior(QAbstractItemView.SelectColumns)
        edit_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        edit_table.setRowHeight(0, 34)
        self._set_center_item(edit_table, 0, 0, "Z(m)", editable=False)
        card_layout.addWidget(edit_table, 1)
        root.addWidget(card, 1)

        def refresh_column_headers() -> None:
            edit_table.setHorizontalHeaderLabels(
                ["编号"] + [str(c) for c in range(1, edit_table.columnCount())]
            )

        def fill_table(levels: List[Tuple[float, int, bool]]):
            col_count = max(1, len(levels) + 1)
            edit_table.setColumnCount(col_count)
            edit_table.setHorizontalHeaderLabels(["编号"] + [str(i) for i in range(1, col_count)])
            self._set_center_item(edit_table, 0, 0, "Z(m)", editable=False)
            for i, (z, _occ, _selected) in enumerate(levels, start=1):
                z_text = f"{float(z):.3f}".rstrip("0").rstrip(".")
                self._set_center_item(edit_table, 0, i, z_text, editable=True)
            edit_table.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
            edit_table.setColumnWidth(0, 96)
            for c in range(1, col_count):
                edit_table.setColumnWidth(c, 88)

        current_levels = list(getattr(self, "_horizontal_levels", []) or [])
        if current_levels:
            fill_table(current_levels)
        else:
            fill_table([])

        auto_node_counts: dict[float, int] = {round(float(z), 3): int(occ or 0) for z, occ, _ in current_levels}

        def auto_update():
            nonlocal auto_node_counts
            threshold = self._safe_int(edit_threshold.text(), 40)
            edit_threshold.setText(str(threshold))
            levels = self._compute_horizontal_levels_by_threshold(threshold)
            auto_node_counts = {round(float(z), 3): int(occ or 0) for z, occ, _ in levels}
            fill_table(levels)

        def add_column():
            c = edit_table.columnCount()
            edit_table.insertColumn(c)
            self._set_center_item(edit_table, 0, c, "", editable=True)
            edit_table.setColumnWidth(c, 88)
            refresh_column_headers()

        def delete_selected_columns():
            target_columns = sorted(
                {index.column() for index in edit_table.selectedIndexes() if index.column() > 0},
                reverse=True,
            )
            if not target_columns:
                QMessageBox.information(dialog, "请选择列", "请先选中要删除的高程列。")
                return
            for col in target_columns:
                if col < edit_table.columnCount():
                    edit_table.removeColumn(col)
            refresh_column_headers()
            edit_table.clearSelection()

        btn_auto.clicked.connect(auto_update)
        btn_add.clicked.connect(add_column)
        btn_del.clicked.connect(delete_selected_columns)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        btn_save = QPushButton("确认更新到数据库")
        btn_cancel = QPushButton("取消")
        self._style_dialog_buttons(btn_save, btn_cancel)
        bottom.addWidget(btn_save)
        bottom.addWidget(btn_cancel)
        root.addLayout(bottom)

        def save_dialog():
            levels: List[Tuple[float, int, bool]] = []
            seen = set()
            for c in range(1, edit_table.columnCount()):
                item = edit_table.item(0, c)
                raw = (item.text() if item else "").strip()
                if not raw:
                    continue
                try:
                    z = float(raw)
                except Exception:
                    QMessageBox.warning(dialog, "格式错误", f"第 {c} 列 Z(m) 不是有效数字：{raw}")
                    return
                key = round(z, 3)
                if key in seen:
                    continue
                seen.add(key)
                levels.append((z, auto_node_counts.get(key, 0), True))

            levels.sort(key=lambda x: x[0], reverse=True)
            threshold = self._safe_int(edit_threshold.text(), 40)
            try:
                self._save_horizontal_levels_to_db(levels, threshold)
            except Exception as exc:
                QMessageBox.critical(dialog, "保存失败", f"水平层高程保存到数据库失败：\n{exc}")
                return
            QMessageBox.information(dialog, "保存完成", "水平层高程已保存到数据库。")
            dialog.accept()

        btn_save.clicked.connect(save_dialog)
        btn_cancel.clicked.connect(dialog.reject)
        dialog.exec_()

    @staticmethod
    def _db_row_time(row: Dict[str, Any]) -> float:
        for key in ("source_modified_at", "uploaded_at", "updated_at"):
            value = row.get(key)
            if hasattr(value, "timestamp"):
                try:
                    return float(value.timestamp())
                except Exception:
                    pass
        return 0.0

    @staticmethod
    def _row_logical_path(row: Dict[str, Any]) -> str:
        return str(row.get("logical_path") or "").replace("\\", "/").strip().strip("/")

    def _row_storage_path(self, row: Dict[str, Any]) -> str:
        try:
            path = resolve_storage_path(row)
        except Exception:
            path = str(row.get("storage_path") or "").strip()
        path = os.path.normpath(str(path or "").strip())
        return path if path and os.path.exists(path) else ""

    def _query_model_file_rows(self, facility_code: str, prefixes: List[str]) -> List[Dict[str, Any]]:
        if not is_file_db_configured():
            return []

        rows: List[Dict[str, Any]] = []
        seen_ids = set()
        code = (facility_code or "").strip() or None

        for prefix in prefixes:
            try:
                current_rows = list_files_by_prefix(
                    module_code="model_files",
                    logical_path_prefix=prefix,
                    facility_code=code,
                )
            except FileBackendError:
                current_rows = []
            except Exception:
                current_rows = []

            # 如果 facility_code 过滤没有返回，兼容没有写 facility_code 的旧记录
            if not current_rows:
                try:
                    current_rows = list_files_by_prefix(
                        module_code="model_files",
                        logical_path_prefix=prefix,
                        facility_code=None,
                    )
                except Exception:
                    current_rows = []

            for row in current_rows:
                row_id = row.get("id")
                sig = row_id if row_id is not None else (
                    str(row.get("stored_name") or ""),
                    str(row.get("storage_path") or ""),
                    self._row_logical_path(row),
                )
                if sig in seen_ids:
                    continue
                seen_ids.add(sig)
                rows.append(dict(row))

        return rows

    def _find_current_model_file_from_db(self, facility_code: str) -> str:
        code = (facility_code or "").strip()
        if not code:
            return ""

        prefixes = [
            f"{code}/当前模型/结构模型",
            f"{code}/当前模型/结构模型/用户上传",
        ]

        candidates: List[Tuple[int, float, str]] = []
        for row in self._query_model_file_rows(code, prefixes):
            path = self._row_storage_path(row)
            if not path:
                continue

            name = os.path.basename(path)
            name_score = self._sacinp_name_score(name)
            if name_score <= 0:
                continue

            # seainp 属于海况文件，不作为结构模型
            if name.lower().startswith("seainp"):
                continue

            if not self._file_has_model_signature(path):
                continue

            logical = self._row_logical_path(row)
            logical_low = logical.lower()
            score = name_score
            if "当前模型" in logical:
                score += 300
            if "结构模型" in logical:
                score += 220
            if "用户上传" in logical:
                score += 50
            if "海况" in logical:
                score -= 500
            if code.lower() in path.lower():
                score += 80
            if path.lower().endswith("sacinp.jknew"):
                score += 800
            if path.lower().endswith("sacinp.m1"):
                score -= 600

            candidates.append((score, self._db_row_time(row), path))

        if not candidates:
            return ""

        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return candidates[0][2]

    def _find_current_sea_file_from_db(self, facility_code: str) -> str:
        code = (facility_code or "").strip()
        if not code:
            return ""

        prefixes = [
            f"{code}/当前模型/结构模型/海况",
            f"{code}/当前模型/结构模型",
        ]

        candidates: List[Tuple[int, float, str]] = []
        for row in self._query_model_file_rows(code, prefixes):
            path = self._row_storage_path(row)
            if not path:
                continue

            name = os.path.basename(path).lower()
            if not name.startswith("seainp"):
                continue

            logical = self._row_logical_path(row)
            score = 100
            if "海况" in logical:
                score += 500
            if "当前模型" in logical:
                score += 120
            if "结构模型" in logical:
                score += 80
            if "用户上传" in logical:
                score += 30
            if code.lower() in path.lower():
                score += 50

            candidates.append((score, self._db_row_time(row), path))

        if not candidates:
            return ""

        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return candidates[0][2]

    def _client_cache_root(self) -> str:
        """客户端本地缓存目录。

        这里只保存从服务端下载来的临时预览/分析输入文件，
        不改变服务端数据库和文件存储中的原始文件。
        """
        root = os.path.join(os.getcwd(), ".client_cache", "model_files")
        os.makedirs(root, exist_ok=True)
        return os.path.normpath(root)

    def _is_local_accessible_file(self, path: object) -> bool:
        text = os.path.normpath(str(path or "").strip())
        return bool(text and os.path.isfile(text))

    def _get_api_client(self):
        if ApiClient is None:
            return None
        try:
            return ApiClient()
        except Exception as exc:
            print("[PlatformStrengthPage] create ApiClient failed:", exc)
            return None

    def _download_latest_model_from_server(self, facility_code: str, force: bool = False) -> str:
        """从 FastAPI 服务端下载当前设施最新 sacinp 模型文件到客户端缓存。

        服务端侧已经通过 /api/files/latest-model 从 MySQL 文件记录中找到
        D:/shiyou_file_storage 下的真实文件；客户端只拿下载后的本地缓存路径。
        """
        code = (facility_code or "").strip()
        if not code:
            return ""

        cached = os.path.normpath(str(self._remote_model_file_cache.get(code, "") or ""))
        if (not force) and self._is_local_accessible_file(cached):
            return cached

        api = self._get_api_client()
        if api is None:
            return ""

        try:
            cache_dir = os.path.join(self._client_cache_root(), code)
            os.makedirs(cache_dir, exist_ok=True)
            # ApiClient.download_latest_model_file 会从 /api/files/download/latest-model 下载。
            local_path = api.download_latest_model_file(code)
            local_path = os.path.normpath(str(local_path or ""))
            if self._is_local_accessible_file(local_path):
                self._remote_model_file_cache[code] = local_path
                print("[PlatformStrengthPage] remote model downloaded:", local_path)
                return local_path
        except Exception as exc:
            print("[PlatformStrengthPage] download latest model from server failed:", exc)
        return ""

    def _download_latest_sea_from_server(self, facility_code: str, force: bool = False) -> str:
        """从 FastAPI 服务端下载当前设施最新 SeaInp 文件到客户端缓存。"""
        code = (facility_code or "").strip()
        if not code:
            return ""

        cached = os.path.normpath(str(self._remote_sea_file_cache.get(code, "") or ""))
        if (not force) and self._is_local_accessible_file(cached):
            return cached

        api = self._get_api_client()
        if api is None:
            return ""

        try:
            local_path = api.download_latest_sea_file(code)
            local_path = os.path.normpath(str(local_path or ""))
            if self._is_local_accessible_file(local_path):
                self._remote_sea_file_cache[code] = local_path
                print("[PlatformStrengthPage] remote sea downloaded:", local_path)
                return local_path
        except Exception as exc:
            # 部分平台没有 seainp，不能影响结构模型显示。
            print("[PlatformStrengthPage] download latest sea from server failed:", exc)
        return ""

    def _get_shared_current_model_file(self, facility_code: str, force_remote: bool = False) -> str:
        code = (facility_code or "").strip()
        if not code:
            return ""

        # 1) C/S 新流程：优先从 FastAPI 服务端下载。
        #    服务端通过 MySQL 文件记录和 storage_root 定位真实 sacinp，
        #    客户端只使用下载后的 .client_cache 本地路径。
        remote_model = self._download_latest_model_from_server(code, force=force_remote)
        if remote_model:
            return remote_model

        # 2) 兼容本机单机/旧流程：如果客户端刚好能访问数据库中的 storage_path，继续可用。
        db_model = self._find_current_model_file_from_db(code)
        if db_model:
            return db_model

        # 3) 兜底：只查新流程运行目录，不再查旧 sacs_jobs/<平台>/source。
        runtime_dir = os.path.normpath(get_job_runtime_dir(code))
        candidates = [
            os.path.join(runtime_dir, "sacinp.JKnew"),
            os.path.join(runtime_dir, "sacinp.M1"),
        ]

        for p in candidates:
            if os.path.exists(p):
                return p
        return ""

    def _resolve_current_preview_model_file(self, facility_code: str, force_remote: bool = False) -> str:
        shared = self._get_shared_current_model_file(facility_code, force_remote=force_remote)
        if shared:
            return shared
        return self._find_best_inp_file(facility_code)

    def _find_matching_sea_file(self, model_path: str, facility_code: str = "") -> Optional[str]:
        code = (facility_code or "").strip()

        # 1) C/S 新流程：优先从服务端下载数据库中登记的 SeaInp 文件。
        remote_sea = self._download_latest_sea_from_server(code)
        if remote_sea:
            return remote_sea

        # 2) 兼容本机单机/旧流程：直接使用数据库 storage_path。
        db_sea = self._find_current_sea_file_from_db(code)
        if db_sea:
            return db_sea

        # 3) 兜底：如果海况文件与结构模型同目录，仍可自动识别。
        if not model_path:
            return None

        folder = os.path.dirname(model_path)
        if not os.path.isdir(folder):
            return None

        candidates = []
        for fn in os.listdir(folder):
            low = fn.lower()
            if low.startswith("seainp"):
                full = os.path.join(folder, fn)
                try:
                    mtime = os.path.getmtime(full)
                except OSError:
                    mtime = 0.0
                candidates.append((mtime, full))

        if not candidates:
            return None

        candidates.sort(reverse=True)
        return candidates[0][1]

    def _prepare_current_model_job(self, model_path: str, facility_code: str) -> str:
        mysql_url = self._get_mysql_url()
        job_name = facility_code

        workpoint = self._get_workpoint_value()
        level_threshold = self._get_level_threshold()
        sea_file = self._find_matching_sea_file(model_path, facility_code)

        import_model_bundle_to_db(
            mysql_url=mysql_url,
            job_name=job_name,
            model_file=model_path,
            sea_file=sea_file,
            workpoint=workpoint,
            level_threshold=level_threshold,
            overwrite_job=True,
        )

        return job_name

    def _compute_horizontal_levels_by_threshold(self, threshold: int) -> List[Tuple[float, int, bool]]:
        """根据模型节点和阈值自动计算水平层高程。"""
        nodes = getattr(self.inp_view, "_nodes", {}) if hasattr(self, "inp_view") else {}
        if not nodes:
            return []

        threshold = int(threshold or 40)
        counter = Counter()
        for coord in nodes.values():
            if coord is None or len(coord) < 3:
                continue
            z = coord[2]
            if z is None:
                continue
            z_key = round(float(z), 3)
            counter[z_key] += 1

        levels = [(z, occ, True) for z, occ in counter.items() if occ > threshold]
        levels.sort(key=lambda x: x[0], reverse=True)
        return levels

    def _compute_horizontal_levels(self) -> List[Tuple[float, int, bool]]:
        """返回当前页面显示的水平层高程。

        主页面的水平层高程来自数据库，不再由主页面的节点数量限制实时驱动。
        """
        levels = list(getattr(self, "_horizontal_levels", []) or [])
        if levels:
            return levels

        # 兜底：如果内存状态丢失，从当前表格读取一遍。
        out: List[Tuple[float, int, bool]] = []
        if hasattr(self, "tbl_layers"):
            for c in range(1, self.tbl_layers.columnCount()):
                item = self.tbl_layers.item(0, c)
                raw = (item.text() if item else "").strip()
                if not raw:
                    continue
                try:
                    out.append((float(raw), 0, True))
                except Exception:
                    continue
        out.sort(key=lambda x: x[0], reverse=True)
        self._horizontal_levels = out
        return out

    def _refresh_layers_table(self):
        if not hasattr(self, "tbl_layers"):
            return

        levels = list(getattr(self, "_horizontal_levels", []) or [])
        col_count = max(1, len(levels) + 1)
        self.tbl_layers.setColumnCount(col_count)

        headers = ["编号"] + [str(i) for i in range(1, col_count)]
        self.tbl_layers.setHorizontalHeaderLabels(headers)

        self._set_center_item(self.tbl_layers, 0, 0, "Z(m)", editable=False)
        for c in range(1, col_count):
            self._set_center_item(self.tbl_layers, 0, c, "")

        for i, (z, _occ, _selected) in enumerate(levels, start=1):
            z_text = f"{float(z):.3f}".rstrip("0").rstrip(".")
            self._set_center_item(self.tbl_layers, 0, i, z_text, editable=False)

        self.tbl_layers.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        first_col_width = 95
        base_data_width = 78
        self.tbl_layers.setColumnWidth(0, first_col_width)

        data_cols = col_count - 1
        if data_cols > 0:
            available_width = self.tbl_layers.viewport().width() - first_col_width - 4
            if data_cols * base_data_width <= available_width and available_width > 0:
                auto_width = max(base_data_width, available_width // data_cols)
                for c in range(1, col_count):
                    self.tbl_layers.setColumnWidth(c, auto_width)
            else:
                for c in range(1, col_count):
                    self.tbl_layers.setColumnWidth(c, base_data_width)

        self.tbl_layers.viewport().update()

    # ---------------- UI ----------------
    def _build_ui(self):
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(8)

        top_wrap = QWidget(self)
        top_layout = QHBoxLayout(top_wrap)
        top_layout.setContentsMargins(8, 8, 8, 0)
        top_layout.setSpacing(0)

        self.dropdown_bar = DropdownBar(self._build_top_dropdown_fields(), parent=self)
        self.dropdown_bar.valueChanged.connect(self._on_top_key_changed)
        self._sync_platform_ui()
        top_layout.addWidget(self.dropdown_bar, 1)
        self._embed_operation_button_in_dropdown()

        self.main_layout.addWidget(top_wrap, 0)

        center = QWidget(self)
        center_layout = QHBoxLayout(center)
        center_layout.setContentsMargins(8, 0, 8, 8)
        center_layout.setSpacing(12)
        self.main_layout.addWidget(center, 1)

        # 左侧加滚动容器：小分辨率时自动滚动，不截断
        left_scroll = QScrollArea(center)
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        left_frame = QFrame()
        left_frame.setStyleSheet(".QFrame { background:#ffffff; border:1px solid #b9c6d6; }")
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(8, 6, 8, 8)
        left_layout.setSpacing(10)

        struct_box = self._build_structure_model_box()
        splash_box, pile_box, marine_box = self._build_left_tables()
        left_layout.addWidget(struct_box, 0)
        left_layout.addWidget(splash_box, 0)
        left_layout.addWidget(pile_box, 0)
        left_layout.addWidget(marine_box, 1)

        left_scroll.setWidget(left_frame)
        center_layout.addWidget(left_scroll, 7)

        right = self._build_inp_view_panel()
        center_layout.addWidget(right, 4)

        if hasattr(self, "edt_workpoint"):
            self.edt_workpoint.editingFinished.connect(self._autoload_inp_to_view)

    def on_quick_evaluate(self):
        if self._quick_assessment_thread is not None and self._quick_assessment_thread.isRunning():
            QMessageBox.information(self, "提示", "快速评估准备中，请稍候。")
            return

        facility_code = self._get_top_value("facility_code") or "XXXX"
        title = f"{facility_code}平台强度/改造可行性评估"

        # 当前页面动态水平层高程
        levels = self._compute_horizontal_levels()
        elevations = [z for z, occ, selected in levels]

        if not elevations:
            elevations = [27, 23, 18, 7, -12, -34, -58]

        # 当前模型文件
        model_path = self._resolve_current_preview_model_file(facility_code)
        if not model_path:
            QMessageBox.warning(self, "提示", "未找到当前设施对应的 sacinp 模型文件，无法打开评估页。")
            return

        try:
            overall_model_image_path = self._export_overall_model_image(facility_code)
        except Exception as e:
            QMessageBox.critical(self, "总图导出失败", f"导出当前三维总图失败：\n{e}")
            return

        try:
            payload = self._build_quick_assessment_payload(facility_code, model_path)
        except Exception as e:
            QMessageBox.critical(self, "准备失败", f"快速评估准备参数生成失败：\n{e}")
            return

        context = {
            "facility_code": facility_code,
            "title": title,
            "elevations": elevations,
            "overall_model_image_path": overall_model_image_path,
            "env_branch": self._get_top_value("branch"),
            "env_op_company": self._get_top_value("op_company"),
            "env_oilfield": self._get_top_value("oilfield"),
            "mysql_url": payload["mysql_url"],
        }
        self._start_quick_assessment_worker(payload, context)

    def _collect_quick_assessment_splash_items(self) -> List[Dict[str, object]]:
        return [{
            "upper_limit_m": self._parse_optional_float(self._table_text(self.tbl_splash, 0, 0)),
            "lower_limit_m": self._parse_optional_float(self._table_text(self.tbl_splash, 0, 1)),
            "corrosion_allowance_mm_per_y": self._parse_optional_float(self._table_text(self.tbl_splash, 0, 2)),
            "sort_order": 1,
        }]

    def _collect_quick_assessment_marine_items(self) -> List[Dict[str, object]]:
        return self._collect_marine_items_from_display_table()

    def _build_quick_assessment_payload(self, facility_code: str, model_path: str) -> dict[str, Any]:
        return {
            "mysql_url": self._get_mysql_url(),
            "facility_code": facility_code,
            "branch": self._get_top_value("branch"),
            "op_company": self._get_top_value("op_company"),
            "oilfield": self._get_top_value("oilfield"),
            "model_path": model_path,
            "sea_file": self._find_matching_sea_file(model_path, facility_code) or "",
            "workpoint": self._get_workpoint_value(),
            "workpoint_m": self._parse_optional_float(
                self.edt_workpoint.text() if hasattr(self, "edt_workpoint") else ""
            ),
            "mud_level": self._parse_optional_float(
                self.edt_mud_level.text() if hasattr(self, "edt_mud_level") else ""
            ),
            "level_threshold": self._get_level_threshold(),
            "splash_items": self._collect_quick_assessment_splash_items(),
            "marine_items": self._collect_quick_assessment_marine_items(),
        }

    def _start_quick_assessment_worker(self, payload: dict[str, Any], context: dict[str, Any]) -> None:
        progress = QProgressDialog("正在准备快速评估数据，请稍候...", None, 0, 0, self)
        progress.setWindowTitle("快速评估")
        progress.setCancelButton(None)
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.show()
        QApplication.processEvents()

        thread = QThread(self)
        worker = QuickAssessmentPreparationWorker(payload)
        worker.moveToThread(thread)

        self._quick_assessment_context = dict(context)
        self._quick_assessment_progress = progress
        self._quick_assessment_thread = thread
        self._quick_assessment_worker = worker

        thread.started.connect(worker.run)
        worker.finished.connect(self._on_quick_assessment_prepared)
        worker.failed.connect(self._on_quick_assessment_prepare_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(self._cleanup_quick_assessment_worker)
        thread.start()

    def _close_quick_assessment_progress(self) -> None:
        progress = self._quick_assessment_progress
        if progress is not None:
            progress.close()

    def _cleanup_quick_assessment_worker(self) -> None:
        thread = self._quick_assessment_thread
        if thread is not None:
            thread.deleteLater()
        self._quick_assessment_thread = None
        self._quick_assessment_worker = None
        self._quick_assessment_progress = None

    def _on_quick_assessment_prepare_failed(self, error: str) -> None:
        self._close_quick_assessment_progress()
        QMessageBox.critical(self, "模型导入失败", f"导入当前 sacinp 到数据库失败：\n{error}")

    def _on_quick_assessment_prepared(self, result: dict) -> None:
        self._close_quick_assessment_progress()
        context = dict(self._quick_assessment_context)
        facility_code = str(context.get("facility_code") or "XXXX")
        title = str(context.get("title") or f"{facility_code}平台强度/改造可行性评估")
        elevations = list(context.get("elevations") or [])
        overall_model_image_path = str(context.get("overall_model_image_path") or "")
        job_name = str(result.get("job_name") or facility_code)

        mw = self.window()
        if hasattr(mw, "tab_widget"):
            elev_key = ",".join(str(z) for z in elevations)
            key = f"feasibility_assessment::{facility_code}::{elev_key}"
            if hasattr(mw, "page_tab_map") and key in mw.page_tab_map:
                old_page = mw.page_tab_map[key]
                old_idx = mw.tab_widget.indexOf(old_page)
                if old_idx != -1:
                    mw.tab_widget.removeTab(old_idx)
                try:
                    old_page.deleteLater()
                except Exception:
                    pass
                del mw.page_tab_map[key]

            page = FeasibilityAssessmentPage(mw, facility_code, elevations=elevations)
            page.env_branch = str(context.get("env_branch") or "")
            page.env_op_company = str(context.get("env_op_company") or "")
            page.env_oilfield = str(context.get("env_oilfield") or "")
            page.overall_model_image_path = overall_model_image_path

            # 保证保存按钮和后续创建新模型都用同一个 job_name / mysql_url
            page.job_name = job_name
            page.mysql_url = str(context.get("mysql_url") or "")

            page.model_files_root = self.model_files_root

            page.current_model_dir = get_job_runtime_dir(job_name)
            page._refresh_runtime_paths_from_disk()

            idx = mw.tab_widget.addTab(page, title)
            mw.tab_widget.setCurrentIndex(idx)

            if hasattr(mw, "page_tab_map"):
                mw.page_tab_map[key] = page
        else:
            QMessageBox.information(self, "提示", "未检测到主窗口Tab组件，无法打开页面。")

    def _schedule_export_overall_model_image(self, delay_ms: int = 1200):
        """三维图打开并渲染完成后延迟保存，避免刚加载完就截图为空。"""
        if getattr(self, "_is_closing", False):
            return
        facility_code = self._get_top_value("facility_code")
        if not facility_code:
            return

        self._overall_export_seq += 1
        seq = self._overall_export_seq
        QTimer.singleShot(
            int(delay_ms),
            lambda s=seq, code=facility_code: self._do_delayed_export_overall_model_image(s, code),
        )

    def _do_delayed_export_overall_model_image(self, seq: int, facility_code: str):
        if seq != self._overall_export_seq or getattr(self, "_is_closing", False):
            return
        try:
            if not self.isVisible():
                return
        except Exception:
            return
        self._export_overall_model_image(facility_code)

    def _export_overall_model_image(self, facility_code: str, force: bool = False) -> str:
        """保存当前三维总图到统一特检图片目录。"""
        code = (facility_code or "").strip()
        view = getattr(self, "inp_view", None)
        if not code or view is None or getattr(self, "_is_closing", False):
            return ""
        if not force:
            try:
                if not self.isVisible():
                    return ""
            except Exception:
                return ""
        if getattr(view, "_vtk_closed", False):
            return ""

        try:
            image_path = build_strategy_image_path(
                facility_code=code,
                run_id=None,
                page_code="platform_strength_page",
                image_type="overall_model",
                year_label="当前",
                row_name="3d",
            )
            target_path = os.path.normpath(str(image_path))

            model_path = self._resolve_current_preview_model_file(code)
            workpoint = self._get_workpoint_value()
            export_key = f"{code}|{model_path}|{workpoint}"
            if (not force) and export_key == self._last_saved_overall_image_key and os.path.exists(target_path):
                return target_path

            saved_path = view.export_current_view(target_path)
            saved_path = os.path.normpath(str(saved_path or ""))
            if not saved_path or not os.path.exists(saved_path):
                return ""

            try:
                save_strategy_image_record(
                    facility_code=code,
                    run_id=None,
                    page_code="platform_strength_page",
                    image_type="overall_model",
                    year_label="当前",
                    row_name="3d",
                    image_path=saved_path,
                    remark="结构强度/改造可行性评估页面三维总图",
                )
            except Exception as db_exc:
                print("[PlatformStrengthPage] save overall model image record failed:", db_exc)

            self._last_saved_overall_image_key = export_key
            print("[PlatformStrengthPage] overall model image saved:", saved_path)
            return saved_path
        except Exception as exc:
            print("[PlatformStrengthPage] export overall model image failed:", exc)
            return ""

    def _cleanup_inp_view(self) -> None:
        view = getattr(self, "inp_view", None)
        if view is not None and hasattr(view, "cleanup_vtk"):
            try:
                view.cleanup_vtk()
            except Exception:
                pass
        self.inp_view = None

    def hideEvent(self, event):
        self._overall_export_seq += 1
        super().hideEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        if getattr(self, "_is_closing", False):
            return
        view = getattr(self, "inp_view", None)
        loaded_path = ""
        try:
            loaded_path = str(getattr(view, "_loaded_path", "") or "").strip()
        except Exception:
            loaded_path = ""
        if loaded_path and not self._last_saved_overall_image_key:
            self._schedule_export_overall_model_image(delay_ms=600)

    def closeEvent(self, event):
        self._is_closing = True
        self._overall_export_seq += 1
        self._cleanup_inp_view()
        super().closeEvent(event)

    def deleteLater(self):
        self._is_closing = True
        self._overall_export_seq += 1
        self._cleanup_inp_view()
        super().deleteLater()

    def _build_custom_legend(self) -> QWidget:
        w = QWidget(self)
        w.setMinimumHeight(34)
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 2, 4, 2)
        lay.setSpacing(20)

        def make_item(color: str, text: str) -> QWidget:
            item = QWidget(w)
            item_lay = QHBoxLayout(item)
            item_lay.setContentsMargins(0, 0, 0, 0)
            item_lay.setSpacing(8)

            dot = QLabel("●")
            dot.setFixedWidth(24)
            dot.setAlignment(Qt.AlignCenter)
            dot.setStyleSheet(f"color:{color}; font-size:22px; font-weight:bold;")
            lab = QLabel(text)
            lab.setStyleSheet("""
                QLabel {
                    color: #26384d;
                    font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
                    font-size: 12pt;
                    font-weight: bold;
                }
            """)

            item_lay.addWidget(dot, 0)
            item_lay.addWidget(lab, 0)
            return item

        lay.addStretch(1)
        lay.addWidget(make_item("#E9D012", "Structure"), 0)

        return w
    # ---------------- 右侧模型 ----------------
    def _build_inp_view_panel(self) -> QWidget:
        frame = QFrame(self)
        frame.setStyleSheet("QFrame { background: #ffffff; border: 1px solid #b9c6d6; }")

        outer = QVBoxLayout(frame)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(6)

        top_row = QWidget(frame)
        top_lay = QHBoxLayout(top_row)
        top_lay.setContentsMargins(0, 0, 0, 0)
        top_lay.setSpacing(6)

        self.inp_path_label = QLabel("")
        self.inp_path_label.setWordWrap(True)
        self.inp_path_label.setStyleSheet("color:#4a5b70; font-size:12px;")
        top_lay.addWidget(self.inp_path_label, 1)

        self.btn_inp_fullscreen = QPushButton("全屏", frame)
        self.btn_inp_fullscreen.setFixedSize(64, 26)
        self.btn_inp_fullscreen.setCursor(Qt.PointingHandCursor)
        self.btn_inp_fullscreen.setStyleSheet("""
            QPushButton {
                background: #2aa9df;
                color: #ffffff;
                border: 1px solid #1b6f91;
                border-radius: 3px;
                font-size: 10pt;
                font-weight: bold;
            }
            QPushButton:hover { background: #42bce9; }
        """)
        self.btn_inp_fullscreen.clicked.connect(self._open_inp_fullscreen_view)
        top_lay.addWidget(self.btn_inp_fullscreen, 0)
        outer.addWidget(top_row, 0)

        outer.addWidget(self._build_custom_legend(), 0)

        view_row = QHBoxLayout()
        view_row.setContentsMargins(0, 0, 0, 0)
        view_row.setSpacing(6)

        self.inp_view = None
        self.inp_view_container = QFrame(frame)
        self.inp_view_container.setFrameShape(QFrame.NoFrame)
        self.inp_view_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.inp_view_layout = QVBoxLayout(self.inp_view_container)
        self.inp_view_layout.setContentsMargins(0, 0, 0, 0)
        self.inp_view_layout.setSpacing(0)

        self.inp_view_placeholder = QLabel("模型预览正在准备...")
        self.inp_view_placeholder.setAlignment(Qt.AlignCenter)
        self.inp_view_placeholder.setStyleSheet("""
            QLabel {
                color: #5d6f85;
                font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
                font-size: 12pt;
                background: #ffffff;
            }
        """)
        self.inp_view_layout.addWidget(self.inp_view_placeholder, 1)
        view_row.addWidget(self.inp_view_container, 1)

        self.slider_v = QSlider(Qt.Vertical)
        self.slider_v.setRange(-100, 100)
        self.slider_v.setValue(0)
        self.slider_v.valueChanged.connect(
            lambda v: self.inp_view.pan_view(self.slider_h.value(), v)
            if getattr(self, "inp_view", None) is not None else None
        )
        view_row.addWidget(self.slider_v, 0)

        outer.addLayout(view_row, 1)

        self.slider_h = QSlider(Qt.Horizontal)
        self.slider_h.setRange(-100, 100)
        self.slider_h.setValue(0)
        self.slider_h.valueChanged.connect(
            lambda v: self.inp_view.pan_view(v, self.slider_v.value())
            if getattr(self, "inp_view", None) is not None else None
        )
        outer.addWidget(self.slider_h, 0)

        return frame

    def _ensure_inp_view_created(self) -> bool:
        if getattr(self, "_is_closing", False):
            return False
        if getattr(self, "inp_view", None) is not None:
            return True
        if not hasattr(self, "inp_view_layout"):
            return False

        placeholder = getattr(self, "inp_view_placeholder", None)
        if placeholder is not None:
            try:
                self.inp_view_layout.removeWidget(placeholder)
                placeholder.deleteLater()
            except Exception:
                pass
            self.inp_view_placeholder = None

        self.inp_view = PyVistaSacsView(getattr(self, "inp_view_container", self))
        self.inp_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.inp_view_layout.addWidget(self.inp_view, 1)
        if hasattr(self, "slider_h") and hasattr(self, "slider_v"):
            self.inp_view.bind_sliders(self.slider_h, self.slider_v)
        return True

    def _set_inp_view_placeholder_text(self, text: str) -> None:
        placeholder = getattr(self, "inp_view_placeholder", None)
        if placeholder is not None:
            placeholder.setText(text)

    def _clear_inp_view_or_placeholder(self, text: str) -> None:
        view = getattr(self, "inp_view", None)
        if view is not None:
            try:
                view.clear_view(text)
                view._loaded_path = ""
                view._nodes = {}
                view._members = []
                view._groups_od = {}
            except Exception:
                pass
            return
        self._set_inp_view_placeholder_text(text)

    def _open_inp_fullscreen_view(self):
        path = ""
        try:
            view = getattr(self, "inp_view", None)
            path = os.path.normpath(str(getattr(view, "_loaded_path", "") or "").strip())
        except Exception:
            path = ""
        if not path or not os.path.isfile(path):
            facility_code = self._get_top_value("facility_code")
            path = self._resolve_current_preview_model_file(facility_code)
        if not path or not os.path.isfile(path):
            QMessageBox.information(self, "全屏显示", "当前没有可全屏显示的模型文件。")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("结构模型预览 - 全屏")
        dlg.resize(1280, 860)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        top = QWidget(dlg)
        top_lay = QHBoxLayout(top)
        top_lay.setContentsMargins(0, 0, 0, 0)
        top_lay.setSpacing(8)
        title = QLabel("结构模型预览（全屏）", top)
        title.setStyleSheet("font-size:13pt; font-weight:bold; color:#1d2b3a;")
        hint = QLabel("右键或双击恢复初始视图，ESC/关闭按钮退出。", top)
        hint.setStyleSheet("font-size:10pt; color:#5d6f85;")
        btn_close = QPushButton("关闭", top)
        btn_close.setFixedSize(72, 28)
        btn_close.clicked.connect(dlg.close)
        top_lay.addWidget(title, 0)
        top_lay.addWidget(hint, 1)
        top_lay.addWidget(btn_close, 0)
        layout.addWidget(top, 0)

        view_row = QHBoxLayout()
        view_row.setContentsMargins(0, 0, 0, 0)
        view_row.setSpacing(6)
        full_view = PyVistaSacsView(dlg)
        view_row.addWidget(full_view, 1)
        slider_v = QSlider(Qt.Vertical, dlg)
        slider_v.setRange(-100, 100)
        slider_v.setValue(0)
        view_row.addWidget(slider_v, 0)
        layout.addLayout(view_row, 1)

        slider_h = QSlider(Qt.Horizontal, dlg)
        slider_h.setRange(-100, 100)
        slider_h.setValue(0)
        layout.addWidget(slider_h, 0)

        full_view.bind_sliders(slider_h, slider_v)
        slider_h.valueChanged.connect(lambda v: full_view.pan_view(v, slider_v.value()))
        slider_v.valueChanged.connect(lambda v: full_view.pan_view(slider_h.value(), v))
        full_view.load_inp(path, target_z=self._get_workpoint_value())

        dlg.showMaximized()
        try:
            dlg.exec_()
        finally:
            try:
                full_view.cleanup_vtk()
            except Exception:
                pass

    def _sacinp_name_score(self, file_name: str) -> int:
        """按文件名判断是否为 SACS 结构模型文件，并优先原模型 JKnew。"""
        name = (file_name or "").strip().lower()
        if not name:
            return 0

        stem, ext = os.path.splitext(name)

        # 明确优先级：
        # 1) sacinp.JKnew —— 当前原模型
        # 2) 其他 sacinp*
        # 3) sacinp.M1 —— 改造后模型，不应该在平台强度首页优先显示
        if stem == "sacinp" and ext == ".jknew":
            return 1200

        if stem == "sacinp" and ext == ".m1":
            return 100

        if stem.startswith("sacinp"):
            return 300

        if ext == ".sacinp":
            return 220

        tokens = [t for t in re.split(r"[^a-z0-9]+", stem) if t]
        if "sacinp" in tokens:
            return 160

        return 0

    def _scan_model_signature(self, file_path: str) -> bool:
        markers_joint = False
        markers_member = False
        encodings = ["utf-8", "utf-8-sig", "gb18030", "gbk", "latin-1"]

        def _scan(fp) -> bool:
            nonlocal markers_joint, markers_member
            for raw in fp:
                line = raw.strip().upper()
                if not line:
                    continue
                if line.startswith("JOINT"):
                    markers_joint = True
                elif line.startswith("MEMBER"):
                    markers_member = True
                if markers_joint and markers_member:
                    return True
            return False

        for enc in encodings:
            try:
                with open(file_path, "r", encoding=enc) as f:
                    if _scan(f):
                        return True
            except UnicodeDecodeError:
                continue
            except Exception:
                return False

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return _scan(f)
        except Exception:
            return False

    def _file_has_model_signature(self, file_path: str) -> bool:
        try:
            mtime = os.path.getmtime(file_path)
        except OSError:
            return False

        cached = self._model_signature_cache.get(file_path)
        if cached and cached[0] == mtime:
            return cached[1]

        ok = self._scan_model_signature(file_path)
        self._model_signature_cache[file_path] = (mtime, ok)
        return ok

    def _find_best_inp_file(self, facility_code: str) -> str:
        roots = [self.model_files_root, self.upload_dir]
        code = (facility_code or "").strip().lower()
        if not code:
            return ""

        candidates: List[Tuple[int, float, str]] = []
        seen = set()
        for root in roots:
            if not os.path.isdir(root):
                continue

            for dir_path, _, file_names in os.walk(root):
                for fn in file_names:
                    name_score = self._sacinp_name_score(fn)
                    if name_score <= 0:
                        continue

                    full = os.path.normpath(os.path.join(dir_path, fn))
                    if full in seen:
                        continue
                    seen.add(full)

                    name_low = fn.lower()
                    path_low = full.lower()
                    score = 0
                    score = 0

                    if code not in path_low:
                        continue

                    if code in name_low:
                        score += 200

                    if "model_files" in path_low:
                        score += 60

                    if ("静力" in full) or ("static" in path_low):
                        score += 25

                    if "demo_platform_jacket" in name_low:
                        score -= 200

                    # 明确偏向“当前原模型”
                    if path_low.endswith("sacinp.jknew"):
                        score += 800

                    if path_low.endswith("sacinp.m1"):
                        score -= 400

                    if "当前模型" in path_low:
                        score += 300

                    has_signature = self._file_has_model_signature(full)
                    if not has_signature:
                        continue

                    score += name_score
                    score += 120

                    try:
                        mtime = os.path.getmtime(full)
                    except OSError:
                        mtime = 0.0
                    candidates.append((score, mtime, full))

        if not candidates:
            return ""

        candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return candidates[0][2]

    def _parse_mud_level_from_sacinp(self, file_path: str) -> Optional[str]:
        """从 SACS INP 文件读取 LDOPT 卡片的泥面高程字段。"""
        lines = read_lines_with_fallback(file_path)
        for line in lines:
            if line.upper().startswith("LDOPT"):
                # 根据 SACS 固定格式，泥面高程通常在 33-40 列 (index 32-40)
                if len(line) >= 40:
                    val_str = line[32:40].strip()
                    try:
                        val_float = float(val_str)
                        return f"{val_float:.3f}"
                    except ValueError:
                        pass
        return None

    def _parse_pile_heads_from_sacinp(self, file_path: str) -> List[str]:
        """按 SACINP JOINT 固定列读取桩头 ID。"""
        lines = read_lines_with_fallback(file_path)
        pile_heads: List[str] = []
        seen = set()
        for raw_line in lines:
            line = raw_line.rstrip("\r\n")
            if not line.upper().startswith("JOINT"):
                continue
            pile_head_id = line[6:10].strip().upper() if len(line) >= 10 else ""
            marker = line[54:60].strip().upper() if len(line) >= 60 else ""
            if not pile_head_id or marker != "PILEHD":
                continue
            if pile_head_id in seen:
                continue
            seen.add(pile_head_id)
            pile_heads.append(pile_head_id)
        return pile_heads

    def _read_current_model_pile_heads(self) -> List[str]:
        facility_code = self._get_top_value("facility_code")
        model_path = self._get_shared_current_model_file(facility_code) or self._find_best_inp_file(facility_code)
        if not model_path:
            return []
        return self._parse_pile_heads_from_sacinp(model_path)

    def _parse_water_depth_from_ldopt(self, lines: List[str]) -> Optional[float]:
        """从 SeaInp/INP 的 LDOPT 卡片读取水深字段。"""
        for line in lines:
            if not line.upper().startswith("LDOPT"):
                continue
            if len(line) >= 48:
                try:
                    return abs(float(line[40:48].strip()))
                except ValueError:
                    pass
        return None

    @staticmethod
    def _parse_mgrov_number(text: str) -> Optional[float]:
        text = (text or "").strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            pass
        # SACS 中常见 2.5400-4 这类省略 E 的科学计数法。
        if re.match(r"^[+-]?\d+(?:\.\d+)?[+-]\d+$", text):
            match = re.match(r"^([+-]?\d+(?:\.\d+)?)([+-]\d+)$", text)
            if not match:
                return None
            try:
                return float(f"{match.group(1)}e{match.group(2)}")
            except ValueError:
                return None
        return None

    def _parse_mgrov_card(self, line: str) -> Optional[Tuple[float, float, float, Optional[float]]]:
        start_depth = self._parse_mgrov_number(line[8:16] if len(line) >= 16 else "")
        end_depth = self._parse_mgrov_number(line[16:24] if len(line) >= 24 else "")
        thickness = self._parse_mgrov_number(line[24:32] if len(line) >= 32 else "")
        density = self._parse_mgrov_number(line[48:56] if len(line) >= 56 else "")

        # 固定列失败时退回空白切分，兼容非标准间距的 SeaInp。
        if end_depth is None or thickness is None:
            values = line.split()[1:]
            if len(values) >= 5:
                start_depth = self._parse_mgrov_number(values[0])
                end_depth = self._parse_mgrov_number(values[1])
                thickness = self._parse_mgrov_number(values[2])
                density = self._parse_mgrov_number(values[4])
            elif len(values) >= 2:
                start_depth = 0.0
                end_depth = self._parse_mgrov_number(values[0])
                thickness = self._parse_mgrov_number(values[1])
                density = self._parse_mgrov_number(values[3]) if len(values) >= 4 else None

        if end_depth is None or thickness is None:
            return None
        return float(start_depth or 0.0), float(end_depth), float(thickness), density

    def _parse_marine_growth_from_seainp(self, file_path: str) -> List[Dict[str, Any]]:
        """按甲方 MGROV 逻辑读取 SeaInp 海生物信息。

        MGROV 固定列：起始深度、结束深度、厚度、阻力系数、密度。
        使用水深把深度转换为模型高程；厚度按 SeaInp 原值写入表格。
        """
        lines = read_lines_with_fallback(file_path)
        water_depth = self._parse_water_depth_from_ldopt(lines)

        raw_rows: List[Tuple[float, float, float, Optional[float]]] = []
        for raw_line in lines:
            line = raw_line.rstrip("\r\n")
            if not line.upper().startswith("MGROV"):
                continue
            if not line[5:].strip():
                continue
            parsed = self._parse_mgrov_card(line)
            if parsed is None:
                continue
            raw_rows.append(parsed)

        if not raw_rows:
            return []

        if water_depth is None:
            water_depth = max(max(abs(a), abs(b)) for a, b, _t, _d in raw_rows)

        layers: List[Tuple[float, float, float, Optional[float]]] = []
        for depth_a, depth_b, thickness, density in raw_rows:
            elevation_a = -(abs(water_depth) - depth_a)
            elevation_b = -(abs(water_depth) - depth_b)
            if abs(elevation_a) < 1e-9:
                elevation_a = 0.0
            if abs(elevation_b) < 1e-9:
                elevation_b = 0.0
            upper_limit = max(elevation_a, elevation_b)
            lower_limit = min(elevation_a, elevation_b)
            if abs(upper_limit - lower_limit) < 1e-9:
                continue
            layers.append((upper_limit, lower_limit, thickness, density))

        layers.sort(key=lambda row: row[0], reverse=True)

        items: List[Dict[str, Any]] = []
        for layer_no, (upper_limit, lower_limit, thickness_mm, density) in enumerate(layers[:9], start=1):
            items.append({
                "layer_no": layer_no,
                "upper_limit_m": upper_limit,
                "lower_limit_m": lower_limit,
                "thickness_mm": thickness_mm,
                "density_t_per_m3": density,
                "sort_order": layer_no,
            })
        return items

    def _resolve_current_sea_file(self) -> str:
        facility_code = self._get_top_value("facility_code")
        remote_sea = self._download_latest_sea_from_server(facility_code)
        if remote_sea:
            return remote_sea
        return self._find_current_sea_file_from_db(facility_code)

    def _on_read_marine_table_from_seainp(self) -> None:
        try:
            sea_file = self._resolve_current_sea_file()
            if not sea_file:
                QMessageBox.warning(self, "读取失败", "未在文件管理保存路径中找到当前设施对应的 SeaInp 海况文件。")
                return
            items = self._parse_marine_growth_from_seainp(sea_file)
            if not items:
                QMessageBox.warning(self, "读取失败", f"SeaInp 文件中未读取到有效 MGROV 数据：\n{sea_file}")
                return
            self._apply_marine_items(items)
            QMessageBox.information(self, "读取完成", f"已从 SeaInp 读取 {len(items)} 层海生物信息。\n{sea_file}")
        except Exception as exc:
            QMessageBox.critical(self, "读取失败", f"SeaInp 海生物信息读取失败：\n{exc}")

    def _autoload_inp_to_view(self, force_remote: bool = False):
        if not hasattr(self, "inp_path_label"):
            return

        facility_code = self._get_top_value("facility_code")

        try:
            target_z = self._get_workpoint_value()
            self.inp_path_label.setText("正在查找并加载 SACS 结构模型文件...")
            self._start_async_model_preview_load(
                facility_code,
                target_z,
                force_remote=force_remote,
            )

        except Exception as e:
            self.inp_path_label.setText("模型加载失败")
            self._clear_inp_view_or_placeholder(f"INP 加载失败：\n{e}")
            self._refresh_layers_table()

    # ---------------- 左侧表格 ----------------
    def _make_update_db_button(self, text_value: str = "更新到数据库", target_name: str = "") -> QPushButton:
        btn = QPushButton(text_value)
        btn.setFont(self._songti_small_four_font(bold=True))
        btn.setCursor(Qt.PointingHandCursor)
        btn.setMinimumHeight(30)
        btn.setMinimumWidth(max(126, btn.fontMetrics().horizontalAdvance(text_value) + 34))
        if target_name:
            btn.setToolTip(f"将“{target_name}”更新到数据库")
        btn.setStyleSheet("""
            QPushButton {
                background: #168bd0;
                color: #ffffff;
                border: 1px solid #0b5f92;
                border-radius: 4px;
                padding: 4px 12px;
                font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
                font-size: 11pt;
                font-weight: bold;
            }
            QPushButton:hover { background: #22a3ee; }
            QPushButton:pressed { background: #0d6ca5; }
        """)
        return btn

    def _make_update_button_row(self, callback, target_name: str) -> QWidget:
        row = QWidget(self)
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addStretch(1)
        btn = self._make_update_db_button(f"更新{target_name}", target_name)
        btn.clicked.connect(callback)
        lay.addWidget(btn, 0)
        return row

    def _make_marine_button_row(self) -> QWidget:
        row = QWidget(self)
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addStretch(1)

        btn_save = self._make_update_db_button("更新海生物信息", "海生物信息")
        btn_save.clicked.connect(self._on_update_marine_table_to_db)
        lay.addWidget(btn_save, 0)
        return row

    def _build_structure_model_kv_table(self) -> QTableWidget:
        tbl = QTableWidget(2, 3)
        tbl.setFocusPolicy(Qt.NoFocus)
        self._init_table_common(tbl, show_vertical_header=False)

        tbl.horizontalHeader().setVisible(False)
        tbl.verticalHeader().setVisible(False)
        tbl.setWordWrap(False)

        tbl.setColumnWidth(0, 280)
        tbl.setColumnWidth(1, 160)
        tbl.setColumnWidth(2, 70)

        self._set_center_item(tbl, 0, 0, "泥面高程", editable=False)
        self.edt_mud_level = QLineEdit("")  # 初始为空，由模型加载后回填或数据库读取
        self.edt_mud_level.setFont(self._songti_small_four_font())
        self.edt_mud_level.setReadOnly(True)
        tbl.setCellWidget(0, 1, self.edt_mud_level)
        self._set_center_item(tbl, 0, 2, "m", editable=False)

        self._set_center_item(tbl, 1, 0, "工作平面高程Workpoint", editable=False)
        self.edt_workpoint = QLineEdit("")  # 用户输入，初始为空
        self.edt_workpoint.setFont(self._songti_small_four_font())
        self.edt_workpoint.setReadOnly(True)
        tbl.setCellWidget(1, 1, self.edt_workpoint)
        self._set_center_item(tbl, 1, 2, "m", editable=False)

        for r in range(2):
            tbl.setRowHeight(r, 30)

        tbl.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        tbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        tbl.setFixedHeight(66)
        return tbl

    def _build_structure_model_box(self) -> QGroupBox:
        box = QGroupBox("结构模型信息")
        box.setStyleSheet("""
            QGroupBox {
                font-size: 12pt;
                font-weight: bold;
                margin-top: 12px;
                border: none;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 8px;
                padding: 0 6px;
                background-color: #ffffff;
            }
        """)
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(10, 8, 10, 8)
        box_layout.setSpacing(6)

        kv_tbl = self._build_structure_model_kv_table()
        box_layout.addWidget(self._make_update_button_row(self._on_update_structure_model_info_to_db, "结构模型信息"), 0)
        box_layout.addWidget(kv_tbl, 0)

        layer_row = QWidget(box)
        layer_lay = QHBoxLayout(layer_row)
        layer_lay.setContentsMargins(0, 0, 0, 0)
        layer_lay.setSpacing(6)
        lab_layers = QLabel("水平层高程")
        lab_layers.setFont(self._songti_small_four_font(bold=True))
        lab_layers.setStyleSheet("color: #1d2b3a;")
        btn_update_layers = self._make_update_db_button("更新水平层高程", "水平层高程")
        btn_update_layers.clicked.connect(self._on_update_horizontal_levels_to_db)
        layer_lay.addWidget(lab_layers, 0)
        layer_lay.addStretch(1)
        layer_lay.addWidget(btn_update_layers, 0)
        box_layout.addWidget(layer_row, 0)

        self.tbl_layers = QTableWidget(1, 1, box)
        self.tbl_layers.setFocusPolicy(Qt.NoFocus)
        self._init_table_common(self.tbl_layers, show_vertical_header=False)
        self.tbl_layers.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl_layers.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._set_center_item(self.tbl_layers, 0, 0, "Z(m)", editable=False)
        self.tbl_layers.setRowHeight(0, 30)

        self.tbl_layers.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.tbl_layers.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tbl_layers.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tbl_layers.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.tbl_layers.setFixedHeight(82)

        box_layout.addWidget(self.tbl_layers, 1)

        margins = box_layout.contentsMargins()
        total_h = (
            margins.top() + margins.bottom()
            + 32 + kv_tbl.height()
            + layer_row.sizeHint().height()
            + self.tbl_layers.height()
            + box_layout.spacing() * 3
            + 18
        )
        box.setFixedHeight(total_h)
        box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        return box

    def _init_table_common(self, table: QTableWidget, show_vertical_header: bool):
        table.setFont(self._songti_small_four_font())
        table.horizontalHeader().setFont(self._songti_small_four_font(bold=True))
        table.verticalHeader().setFont(self._songti_small_four_font(bold=True))
        table.setEditTriggers(QAbstractItemView.AllEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectItems)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                gridline-color: #d0d0d0;
                border: 1px solid #d0d0d0;
                font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
                font-size: 12pt;
            }
            QTableWidget::item { border: 1px solid #e6e6e6; padding: 2px; }
            QTableWidget::item:selected { background-color: #dbe9ff; color: #000000; }
            QTableWidget::item:focus { outline: none; }
            QHeaderView::section {
                background-color: #f3f6fb;
                border: 1px solid #e6e6e6;
                padding: 4px;
                font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
                font-size: 12pt;
                font-weight: bold;
            }
        """)
        table.verticalHeader().setVisible(bool(show_vertical_header))
        table.horizontalHeader().setVisible(True)
        table.verticalHeader().setDefaultSectionSize(28)

    def _set_center_item(self, table: QTableWidget, row: int, col: int, text: str, editable: bool = True):
        item = QTableWidgetItem(str(text))
        item.setFont(table.font())
        item.setTextAlignment(Qt.AlignCenter)
        if not editable:
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        table.setItem(row, col, item)

    def _build_left_tables(self) -> Tuple[QGroupBox, QGroupBox, QGroupBox]:
        section_title_qss = """
            QGroupBox {
                font-size: 12pt;
                font-weight: bold;
                margin-top: 12px;
                border: none;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 8px;
                padding: 0 6px;
                background-color: #ffffff;
            }
        """

        # 飞溅区腐蚀余量
        splash_box = QGroupBox("飞溅区腐蚀余量")
        splash_box.setStyleSheet(section_title_qss)
        splash_layout = QVBoxLayout(splash_box)
        splash_layout.setContentsMargins(8, 8, 8, 8)
        splash_layout.addWidget(self._make_update_button_row(self._on_update_splash_table_to_db, "飞溅区腐蚀余量"), 0)

        tbl_splash = QTableWidget(1, 3, splash_box)
        self.tbl_splash = tbl_splash
        tbl_splash.setHorizontalHeaderLabels(["飞溅区上限(m)", "飞溅区下限(m)", "腐蚀余量(mm/y)"])
        self._init_table_common(tbl_splash, show_vertical_header=False)
        tbl_splash.setEditTriggers(QAbstractItemView.NoEditTriggers)
        for c in range(3):
            self._set_center_item(tbl_splash, 0, c, "")
        tbl_splash.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tbl_splash.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tbl_splash.setRowHeight(0, 32)
        splash_header_h = tbl_splash.horizontalHeader().height() if not tbl_splash.horizontalHeader().isHidden() else 0
        splash_rows_h = sum(tbl_splash.rowHeight(r) for r in range(tbl_splash.rowCount()))
        splash_tbl_h = splash_header_h + splash_rows_h + tbl_splash.frameWidth() * 2 + 6
        tbl_splash.setMinimumHeight(splash_tbl_h)
        tbl_splash.setMaximumHeight(splash_tbl_h)
        tbl_splash.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        tbl_splash.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        tbl_splash.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        splash_layout.addWidget(tbl_splash, 1)

        splash_margins = splash_layout.contentsMargins()
        splash_box_h = splash_margins.top() + splash_margins.bottom() + splash_tbl_h + 38 + 18
        splash_box.setMinimumHeight(splash_box_h)
        splash_box.setMaximumHeight(splash_box_h)
        splash_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # 桩基信息
        pile_box = QGroupBox("桩基信息")
        pile_box.setStyleSheet(section_title_qss)
        pile_layout = QVBoxLayout(pile_box)
        pile_layout.setContentsMargins(8, 8, 8, 8)
        pile_layout.addWidget(self._make_update_button_row(self._on_update_pile_table_to_db, "桩基信息"), 0)

        tbl_pile = QTableWidget(1, 4, pile_box)
        self.tbl_pile = tbl_pile
        tbl_pile.setHorizontalHeaderLabels(["基础冲刷(m)", "桩基础抗压承载能力(t)", "桩基础抗拔承载能力(t)", "单根桩泥下自重(t)"])
        self._init_table_common(tbl_pile, show_vertical_header=False)
        tbl_pile.setEditTriggers(QAbstractItemView.NoEditTriggers)
        for c in range(4):
            self._set_center_item(tbl_pile, 0, c, "")
        tbl_pile.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tbl_pile.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tbl_pile.setRowHeight(0, 32)
        pile_header_h = tbl_pile.horizontalHeader().height() if not tbl_pile.horizontalHeader().isHidden() else 0
        pile_rows_h = sum(tbl_pile.rowHeight(r) for r in range(tbl_pile.rowCount()))
        pile_tbl_h = pile_header_h + pile_rows_h + tbl_pile.frameWidth() * 2 + 6
        tbl_pile.setMinimumHeight(pile_tbl_h)
        tbl_pile.setMaximumHeight(pile_tbl_h)
        tbl_pile.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        tbl_pile.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        tbl_pile.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        pile_layout.addWidget(tbl_pile, 1)

        pile_margins = pile_layout.contentsMargins()
        pile_box_h = pile_margins.top() + pile_margins.bottom() + pile_tbl_h + 38 + 18
        pile_box.setMinimumHeight(pile_box_h)
        pile_box.setMaximumHeight(pile_box_h)
        pile_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # 海生物信息
        marine_box = QGroupBox("海生物信息")
        marine_box.setStyleSheet(section_title_qss)
        marine_layout = QVBoxLayout(marine_box)
        marine_layout.setContentsMargins(8, 8, 8, 8)
        marine_layout.addWidget(self._make_marine_button_row(), 0)

        default_marine_items = self._default_marine_layer_items()
        tbl_marine = QTableWidget(5, 3 + len(default_marine_items), marine_box)
        self.tbl_marine = tbl_marine
        self._init_table_common(tbl_marine, show_vertical_header=False)
        tbl_marine.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tbl_marine.horizontalHeader().setVisible(False)
        tbl_marine.verticalHeader().setVisible(False)
        tbl_marine.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._default_marine_items = default_marine_items
        self._populate_marine_display_table(self._default_marine_items)

        tbl_marine.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tbl_marine.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        tbl_marine.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        tbl_marine.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        tbl_marine.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for r in range(tbl_marine.rowCount()):
            tbl_marine.setRowHeight(r, 28)

        marine_rows_h = sum(tbl_marine.rowHeight(r) for r in range(tbl_marine.rowCount()))
        marine_tbl_h = marine_rows_h + tbl_marine.frameWidth() * 2 + 8
        tbl_marine.setMinimumHeight(marine_tbl_h)
        tbl_marine.setMaximumHeight(marine_tbl_h)
        tbl_marine.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        tbl_marine.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        marine_layout.addWidget(tbl_marine, 1)
        marine_margins = marine_layout.contentsMargins()
        marine_box_h = marine_margins.top() + marine_margins.bottom() + marine_tbl_h + 38 + 12
        marine_box.setMinimumHeight(marine_box_h)
        marine_box.setMaximumHeight(marine_box_h)
        marine_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        return splash_box, pile_box, marine_box
