# -*- coding: utf-8 -*-
# pages/platform_strength_page.py

import os
import re

import numpy as np
import pyvista as pv
from pyvistaqt import QtInteractor

from typing import Dict, List, Tuple, Optional

from PyQt5.QtCore import Qt, QRectF,QEvent
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
    QGraphicsScene, QMessageBox, QPushButton, QHeaderView,QSlider,
)

<<<<<<< HEAD
from core.app_paths import first_existing_path
from core.base_page import BasePage
from core.dropdown_bar import DropdownBar
=======
from app_paths import first_existing_path
from base_page import BasePage
from dropdown_bar import DropdownBar
from feasibility_analysis_services.oilfield_env_service import (
    get_env_profile_id,
    load_platform_strength_marine_items,
    load_platform_strength_pile_items,
    load_platform_strength_splash_items,
    replace_platform_strength_marine_items,
    replace_platform_strength_pile_items,
    replace_platform_strength_splash_items,
)
from inspection_business_db_adapter import load_facility_profile
>>>>>>> origin/main
from pages.feasibility_assessment_page import FeasibilityAssessmentPage
from pages.file_management_platforms import default_platform, sync_platform_dropdowns

from pages.sacs_import_service import import_model_bundle_to_db

from shiyou_db.runtime_db import get_mysql_url

from collections import Counter

class PyVistaSacsView(QFrame):
    COLOR_SCHEME = {
        "background": "white",
        "main_structure": "#E9D012",   # 原结构：暖黄色
        "leg_joint": "#B22222",        # 主腿节点：深红
        "tubular_joint": "#2A7F9E",    # 核心管节点：湖蓝
    }

    def __init__(self, parent=None):
        super().__init__(parent)

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

    def clear_view(self, message: str = ""):
        self.plotter.clear()
        self.plotter.set_background(self.COLOR_SCHEME["background"])
        self.plotter.add_axes()
        if message:
            self.plotter.add_text(message, position="upper_left", font_size=10)

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

        self.plotter.render()

    def load_inp(self, file_path: str, target_z: float = 9.1):
        self._loaded_path = file_path

        nodes, members, groups_od = self.parse_sacs_full_robust(file_path)
        self._nodes = nodes
        self._members = members
        self._groups_od = groups_od

        if not self._nodes or not self._members:
            self.clear_view("未解析到有效的 SACS JOINT/MEMBER 数据")
            return

        leg_joints, tubular_joints = self.apply_pdf_logic_diagnostic(
            self._nodes, self._members, self._groups_od, target_z=target_z
        )

        self.render_structure(self._nodes, self._members, leg_joints, tubular_joints)

    def parse_sacs_full_robust(self, filepath):
        nodes = {}
        members = []
        groups_od = {}

        lines = self._read_lines_with_fallback(filepath)
        for line in lines:
            if line.startswith('GRUP'):
                gid = line[5:8].strip()
                try:
                    od_str = line[14:24].strip()
                    od = float(od_str) if od_str else 0.0
                    groups_od[gid] = od
                except Exception:
                    groups_od[gid] = 0.0

            elif line.startswith('JOINT'):
                try:
                    nid = line[6:10].strip()
                    x = float(line[11:18].strip())
                    y = float(line[18:25].strip())
                    z = float(line[25:32].strip())
                    nodes[nid] = [x, y, z]
                except Exception:
                    continue

            elif line.startswith('MEMBER'):
                try:
                    na = line[7:11].strip()
                    nb = line[11:15].strip()
                    gid = line[15:18].strip()
                    members.append((na, nb, gid))
                except Exception:
                    continue

        return nodes, members, groups_od

    def apply_pdf_logic_diagnostic(self, nodes, members, groups_od, target_z=8.5):
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

        leg_joints = []
        tubular_joints = []

        if elevation_nodes:
            local_max_od = max(elevation_nodes.values())
            for nid in elevation_nodes:
                if node_to_max_od[nid] >= local_max_od * 0.95:
                    leg_joints.append(nodes[nid])

        for nid, neighbors in graph.items():
            if len(neighbors) >= 3:
                tubular_joints.append(nodes[nid])

        return leg_joints, tubular_joints

    def render_structure(self, nodes, members, leg_joints, tubular_joints):
        self.plotter.clear()
        self.plotter.set_background(self.COLOR_SCHEME["background"])

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

        # 主结构：恢复为更好看的管状体效果
        try:
            structure = mesh.tube(radius=0.12, n_sides=8)
            self.plotter.add_mesh(
                structure,
                color=self.COLOR_SCHEME["main_structure"],
                opacity=0.85,
                label="Main Structure"
            )
        except Exception:
            self.plotter.add_mesh(
                mesh,
                color=self.COLOR_SCHEME["main_structure"],
                line_width=1.2,
                opacity=0.9,
                label="Main Structure"
            )

        # 主腿节点：红色球
        if leg_joints:
            leg_cloud = pv.PolyData(np.array(leg_joints, dtype=float))
            self.plotter.add_mesh(
                leg_cloud.glyph(
                    geom=pv.Sphere(radius=0.55, theta_resolution=12, phi_resolution=12),
                    scale=False,
                    orient=False
                ),
                color=self.COLOR_SCHEME["leg_joint"],
                label="Leg Joint"
            )

        # 核心管节点：蓝色球
        if tubular_joints:
            tub_cloud = pv.PolyData(np.array(tubular_joints, dtype=float))
            self.plotter.add_mesh(
                tub_cloud.glyph(
                    geom=pv.Sphere(radius=0.30, theta_resolution=10, phi_resolution=10),
                    scale=False,
                    orient=False
                ),
                color=self.COLOR_SCHEME["tubular_joint"],
                label="Tubular Joint"
            )

        #self.plotter.add_legend(bcolor="white")
        self.plotter.add_axes()
        self.plotter.reset_camera()

        # 记录“初始视图”
        cam = self.plotter.camera
        self._initial_camera_position = tuple(cam.position)
        self._initial_camera_focal_point = tuple(cam.focal_point)
        self._initial_camera_up = tuple(cam.up)

        try:
            self._initial_parallel_scale = cam.parallel_scale
        except Exception:
            self._initial_parallel_scale = None

        self.plotter.render()

    def pan_view(self, x_value: int, y_value: int):
        dx_slider = x_value - self._last_pan_x
        dy_slider = y_value - self._last_pan_y

        self._last_pan_x = x_value
        self._last_pan_y = y_value

        if dx_slider == 0 and dy_slider == 0:
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

        self.plotter.render()

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

        self._model_signature_cache: Dict[str, Tuple[float, bool]] = {}
        self._default_splash_items: List[Dict] = []
        self._default_pile_items: List[Dict] = []
        self._default_marine_items: List[Dict] = []

        self._build_ui()
        self._capture_default_strength_env_tables()
        self._load_strength_env_tables()
        self._autoload_inp_to_view()

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
        self.dropdown_bar.set_options("branch", [profile["branch"]], profile["branch"])
        self.dropdown_bar.set_options("op_company", [profile["op_company"]], profile["op_company"])
        self.dropdown_bar.set_options("oilfield", [profile["oilfield"]], profile["oilfield"])
        self.dropdown_bar.set_options("facility_type", [profile["facility_type"]], profile["facility_type"])
        self.dropdown_bar.set_options("category", [profile["category"]], profile["category"])
        self.dropdown_bar.set_options("start_time", [profile["start_time"]], profile["start_time"])
        self.dropdown_bar.set_options("design_life", [profile["design_life"]], profile["design_life"])
        if hasattr(self, "tbl_splash") and hasattr(self, "tbl_pile") and hasattr(self, "tbl_marine"):
            self._load_strength_env_tables()

    def _on_top_key_changed(self, key: str, txt: str):
        if key in {"branch", "op_company", "oilfield", "facility_code", "facility_name"}:
            self._sync_platform_ui(changed_key=key)
            self._autoload_inp_to_view()

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
        density_value = self._parse_optional_float(self._table_text(self.tbl_marine, 4, 3))
        self._default_marine_items = []
        for i in range(9):
            col = 3 + i
            self._default_marine_items.append({
                "layer_no": i + 1,
                "upper_limit_m": self._parse_optional_float(self._table_text(self.tbl_marine, 1, col)),
                "lower_limit_m": self._parse_optional_float(self._table_text(self.tbl_marine, 2, col)),
                "thickness_mm": self._parse_optional_float(self._table_text(self.tbl_marine, 3, col)),
                "density_t_per_m3": density_value,
            })

    def _apply_splash_items(self, items: List[Dict]):
        source = items[0] if items else (self._default_splash_items[0] if self._default_splash_items else {})
        self._set_table_text(self.tbl_splash, 0, 0, self._format_optional_number(source.get("upper_limit_m")))
        self._set_table_text(self.tbl_splash, 0, 1, self._format_optional_number(source.get("lower_limit_m")))
        self._set_table_text(self.tbl_splash, 0, 2, self._format_optional_number(source.get("corrosion_allowance_mm_per_y")))

    def _apply_pile_items(self, items: List[Dict]):
        source = items[0] if items else (self._default_pile_items[0] if self._default_pile_items else {})
        self._set_table_text(self.tbl_pile, 0, 0, self._format_optional_number(source.get("scour_depth_m")))
        self._set_table_text(self.tbl_pile, 0, 1, self._format_optional_number(source.get("compressive_capacity_t")))
        self._set_table_text(self.tbl_pile, 0, 2, self._format_optional_number(source.get("uplift_capacity_t")))
        self._set_table_text(self.tbl_pile, 0, 3, self._format_optional_number(source.get("submerged_weight_t")))

    def _apply_marine_items(self, items: List[Dict]):
        source_items = items if items else self._default_marine_items
        by_layer = {
            int(item.get("layer_no", 0) or 0): item
            for item in source_items
            if int(item.get("layer_no", 0) or 0) > 0
        }
        density_text = ""
        for i in range(9):
            layer_no = i + 1
            source = by_layer.get(layer_no, {})
            col = 3 + i
            self._set_table_text(self.tbl_marine, 1, col, self._format_optional_number(source.get("upper_limit_m")))
            self._set_table_text(self.tbl_marine, 2, col, self._format_optional_number(source.get("lower_limit_m")))
            self._set_table_text(self.tbl_marine, 3, col, self._format_optional_number(source.get("thickness_mm")))
            if not density_text:
                density_text = self._format_optional_number(source.get("density_t_per_m3"))
        self._set_table_text(self.tbl_marine, 4, 3, density_text)

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
        except Exception:
            self._apply_splash_items([])
            self._apply_pile_items([])
            self._apply_marine_items([])

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

        pile_items = [{
            "scour_depth_m": self._parse_optional_float(self._table_text(self.tbl_pile, 0, 0)),
            "compressive_capacity_t": self._parse_optional_float(self._table_text(self.tbl_pile, 0, 1)),
            "uplift_capacity_t": self._parse_optional_float(self._table_text(self.tbl_pile, 0, 2)),
            "submerged_weight_t": self._parse_optional_float(self._table_text(self.tbl_pile, 0, 3)),
            "sort_order": 1,
        }]

        marine_items = []
        density_text = self._table_text(self.tbl_marine, 4, 3)
        density_value = self._parse_optional_float(density_text)
        for i in range(9):
            col = 3 + i
            marine_items.append({
                "layer_no": i + 1,
                "upper_limit_m": self._parse_optional_float(self._table_text(self.tbl_marine, 1, col)),
                "lower_limit_m": self._parse_optional_float(self._table_text(self.tbl_marine, 2, col)),
                "thickness_mm": self._parse_optional_float(self._table_text(self.tbl_marine, 3, col)),
                "density_t_per_m3": density_value,
                "sort_order": i + 1,
            })

        replace_platform_strength_splash_items(profile_id, facility_code, splash_items)
        replace_platform_strength_pile_items(profile_id, facility_code, pile_items)
        replace_platform_strength_marine_items(profile_id, facility_code, marine_items)
        return len(splash_items), len(pile_items), len(marine_items)

    def _get_level_threshold(self) -> int:
        if not hasattr(self, "edt_node_limit"):
            return 40
        return self._safe_int(self.edt_node_limit.text(), 40)

    def _get_workpoint_value(self) -> float:
        if not hasattr(self, "edt_workpoint"):
            return 9.1
        return self._safe_float(self.edt_workpoint.text(), 9.1)

    def _get_mysql_url(self) -> str:
        return get_mysql_url()

    def _find_matching_sea_file(self, model_path: str) -> Optional[str]:
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
        sea_file = self._find_matching_sea_file(model_path)

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

    def _compute_horizontal_levels(self) -> List[Tuple[float, int, bool]]:
        """
        返回 [(z, occurrence, selected), ...]
        """
        nodes = getattr(self.inp_view, "_nodes", {}) if hasattr(self, "inp_view") else {}
        if not nodes:
            return []

        threshold = self._get_level_threshold()

        # 为了避免浮点微小误差，把 Z 统一到 3 位小数
        counter = Counter()
        for coord in nodes.values():
            if coord is None or len(coord) < 3:
                continue
            z = coord[2]
            if z is None:
                continue
            z_key = round(float(z), 3)
            counter[z_key] += 1

        # 这里保持和你前面 VBA/Python 思路一致：节点数大于阈值才算水平层
        levels = [(z, occ, True) for z, occ in counter.items() if occ > threshold]
        levels.sort(key=lambda x: x[0], reverse=True)
        return levels

    def _refresh_layers_table(self):
        if not hasattr(self, "tbl_layers"):
            return

        levels = self._compute_horizontal_levels()

        col_count = max(1, len(levels) + 1)  # 第0列是行标题
        self.tbl_layers.setColumnCount(col_count)

        headers = ["编号"] + [str(i) for i in range(1, col_count)]
        self.tbl_layers.setHorizontalHeaderLabels(headers)

        self._set_center_item(self.tbl_layers, 0, 0, "Z(m)", editable=False)
        self._set_center_item(self.tbl_layers, 1, 0, "节点数量", editable=False)
        self._set_center_item(self.tbl_layers, 2, 0, "是否水平层", editable=False)

        # 清空旧数据
        for c in range(1, col_count):
            for r in range(3):
                self._set_center_item(self.tbl_layers, r, c, "", editable=(r != 2))

        # 回填动态结果
        for i, (z, occ, selected) in enumerate(levels, start=1):
            z_text = f"{z:.3f}".rstrip("0").rstrip(".")
            self._set_center_item(self.tbl_layers, 0, i, z_text)
            self._set_center_item(self.tbl_layers, 1, i, str(occ))
            self._set_center_item(self.tbl_layers, 2, i, "✓" if selected else "×", editable=False)

        # ===== 自适应列宽：少列铺满，多列滚动 =====
        self.tbl_layers.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)

        first_col_width = 95  # 左侧标题列
        base_data_width = 78  # 之前你想保留的列宽感觉
        self.tbl_layers.setColumnWidth(0, first_col_width)

        data_cols = col_count - 1
        if data_cols > 0:
            # 当前表格可用宽度
            available_width = self.tbl_layers.viewport().width() - first_col_width - 4

            # 如果按“基础宽度”能放下，就把多余空间均分给每一列，减少空白
            if data_cols * base_data_width <= available_width and available_width > 0:
                auto_width = max(base_data_width, available_width // data_cols)
                for c in range(1, col_count):
                    self.tbl_layers.setColumnWidth(c, auto_width)
            else:
                # 放不下时，恢复基础宽度，交给横向滚动条
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

        if hasattr(self, "edt_node_limit"):
            self.edt_node_limit.editingFinished.connect(self._refresh_layers_table)

        if hasattr(self, "edt_workpoint"):
            self.edt_workpoint.editingFinished.connect(self._autoload_inp_to_view)

    def on_quick_evaluate(self):
        facility_code = self._get_top_value("facility_code") or "XXXX"
        title = f"{facility_code}平台强度/改造可行性评估"

        try:
            self._save_strength_env_tables()
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"结构强度环境参数保存失败：\n{e}")
            return

        # 当前页面动态水平层高程
        levels = self._compute_horizontal_levels()
        elevations = [z for z, occ, selected in levels]

        if not elevations:
            elevations = [27, 23, 18, 7, -12, -34, -58]

        # 当前模型文件
        model_path = self._find_best_inp_file(facility_code)
        if not model_path:
            QMessageBox.warning(self, "提示", "未找到当前设施对应的 sacinp 模型文件，无法打开评估页。")
            return

        try:
            # 跳转前先把当前模型导入数据库
            job_name = self._prepare_current_model_job(model_path, facility_code)
        except Exception as e:
            QMessageBox.critical(self, "模型导入失败", f"导入当前 sacinp 到数据库失败：\n{e}")
            return

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
            page.env_branch = self._get_top_value("branch")
            page.env_op_company = self._get_top_value("op_company")
            page.env_oilfield = self._get_top_value("oilfield")

            # 保证保存按钮和后续创建新模型都用同一个 job_name / mysql_url
            page.job_name = job_name
            page.mysql_url = self._get_mysql_url()

            page.model_files_root = self.model_files_root

            idx = mw.tab_widget.addTab(page, title)
            mw.tab_widget.setCurrentIndex(idx)

            if hasattr(mw, "page_tab_map"):
                mw.page_tab_map[key] = page
        else:
            QMessageBox.information(self, "提示", "未检测到主窗口Tab组件，无法打开页面。")

    def _build_custom_legend(self) -> QWidget:
        w = QWidget(self)
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        def make_item(color: str, text: str) -> QWidget:
            item = QWidget(w)
            item_lay = QHBoxLayout(item)
            item_lay.setContentsMargins(0, 0, 0, 0)
            item_lay.setSpacing(4)

            dot = QLabel("●")
            dot.setStyleSheet(f"color:{color}; font-size:14px;")
            lab = QLabel(text)
            lab.setStyleSheet("color:#4a5b70; font-size:12px;")

            item_lay.addWidget(dot, 0)
            item_lay.addWidget(lab, 0)
            return item

        lay.addStretch(1)
        lay.addWidget(make_item("#E9D012", "Main Structure"), 0)
        lay.addWidget(make_item("#B22222", "Leg Joint"), 0)
        lay.addWidget(make_item("#2A7F9E", "Tubular Joint"), 0)

        return w
    # ---------------- 右侧模型 ----------------
    def _build_inp_view_panel(self) -> QWidget:
        frame = QFrame(self)
        frame.setStyleSheet("QFrame { background: #ffffff; border: 1px solid #b9c6d6; }")

        outer = QVBoxLayout(frame)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(6)

        self.inp_path_label = QLabel("")
        self.inp_path_label.setWordWrap(True)
        self.inp_path_label.setStyleSheet("color:#4a5b70; font-size:12px;")
        outer.addWidget(self.inp_path_label, 0)

        outer.addWidget(self._build_custom_legend(), 0)

        view_row = QHBoxLayout()
        view_row.setContentsMargins(0, 0, 0, 0)
        view_row.setSpacing(6)

        self.inp_view = PyVistaSacsView(frame)
        self.inp_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        view_row.addWidget(self.inp_view, 1)

        self.slider_v = QSlider(Qt.Vertical)
        self.slider_v.setRange(-100, 100)
        self.slider_v.setValue(0)
        self.slider_v.valueChanged.connect(
            lambda v: self.inp_view.pan_view(self.slider_h.value(), v)
        )
        view_row.addWidget(self.slider_v, 0)

        outer.addLayout(view_row, 1)

        self.slider_h = QSlider(Qt.Horizontal)
        self.slider_h.setRange(-100, 100)
        self.slider_h.setValue(0)
        self.slider_h.valueChanged.connect(
            lambda v: self.inp_view.pan_view(v, self.slider_v.value())
        )
        outer.addWidget(self.slider_h, 0)
        self.inp_view.bind_sliders(self.slider_h, self.slider_v)

        return frame

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

                    if code and code in name_low:
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
        lines = self.inp_view._read_lines_with_fallback(file_path)
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

    def _autoload_inp_to_view(self):
        if not hasattr(self, "inp_view"):
            return

        facility_code = self._get_top_value("facility_code")
        path = self._find_best_inp_file(facility_code)
        if not path:
            self.inp_path_label.setText("未找到可解析的 SACS 结构模型文件")
            self.inp_view.clear_view(
                "未找到可解析的 SACS 结构模型文件\n"
                "请先上传文件名以 sacinp 开头（或扩展名为 .sacinp）的模型文件"
            )
            self._refresh_layers_table()
            return

        try:
            target_z = self._get_workpoint_value()
            self.inp_view.load_inp(path, target_z=target_z)
            self.inp_view.reset_pan_state()

            if hasattr(self, "slider_h"):
                self.slider_h.blockSignals(True)
                self.slider_h.setValue(0)
                self.slider_h.blockSignals(False)

            if hasattr(self, "slider_v"):
                self.slider_v.blockSignals(True)
                self.slider_v.setValue(0)
                self.slider_v.blockSignals(False)

            self.inp_path_label.setText(f"当前模型文件：{path}")

            # 泥面高程：默认从模型读取，但用户仍可手改
            mud_level = self._parse_mud_level_from_sacinp(path)
            if mud_level and hasattr(self, "edt_mud_level"):
                self.edt_mud_level.setText(mud_level)

            # 动态生成水平层高程表
            self._refresh_layers_table()

        except Exception as e:
            self.inp_path_label.setText("模型加载失败")
            self.inp_view.clear_view(f"INP 加载失败：\n{e}")
            self._refresh_layers_table()

    # ---------------- 左侧表格 ----------------
    def _build_structure_model_kv_table(self) -> QTableWidget:
        tbl = QTableWidget(3, 3)
        tbl.setFocusPolicy(Qt.NoFocus)
        self._init_table_common(tbl, show_vertical_header=False)

        tbl.horizontalHeader().setVisible(False)
        tbl.verticalHeader().setVisible(False)
        tbl.setWordWrap(False)

        tbl.setColumnWidth(0, 280)
        tbl.setColumnWidth(1, 160)
        tbl.setColumnWidth(2, 70)

        self._set_center_item(tbl, 0, 0, "泥面高程", editable=False)
        self.edt_mud_level = QLineEdit("") # 初始为空，由模型加载后回填
        self.edt_mud_level.setFont(self._songti_small_four_font())
        tbl.setCellWidget(0, 1, self.edt_mud_level)
        self._set_center_item(tbl, 0, 2, "m", editable=False)

        self._set_center_item(tbl, 1, 0, "水平层高程节点数量限制", editable=False)
        self.edt_node_limit = QLineEdit("40") # 默认值 40
        self.edt_node_limit.setFont(self._songti_small_four_font())
        tbl.setCellWidget(1, 1, self.edt_node_limit)
        self._set_center_item(tbl, 1, 2, "", editable=False)

        self._set_center_item(tbl, 2, 0, "工作平面高程Workpoint", editable=False)
        self.edt_workpoint = QLineEdit("") # 用户输入，初始为空
        self.edt_workpoint.setFont(self._songti_small_four_font())
        tbl.setCellWidget(2, 1, self.edt_workpoint)
        self._set_center_item(tbl, 2, 2, "m", editable=False)

        for r in range(3):
            tbl.setRowHeight(r, 30)

        tbl.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        tbl.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        tbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        tbl.setFixedHeight(96)
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
        box_layout.addWidget(kv_tbl, 0)

        lab_layers = QLabel("水平层高程")
        lab_layers.setFont(self._songti_small_four_font(bold=True))
        lab_layers.setStyleSheet("color: #1d2b3a;")
        box_layout.addWidget(lab_layers, 0)

        self.tbl_layers = QTableWidget(3, 1, box)
        self.tbl_layers.setFocusPolicy(Qt.NoFocus)
        self._init_table_common(self.tbl_layers, show_vertical_header=False)
        self.tbl_layers.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._set_center_item(self.tbl_layers, 0, 0, "Z(m)", editable=False)
        self._set_center_item(self.tbl_layers, 1, 0, "节点数量", editable=False)
        self._set_center_item(self.tbl_layers, 2, 0, "是否水平层", editable=False)

        for r in range(3):
            self.tbl_layers.setRowHeight(r, 30)

        self.tbl_layers.cellClicked.connect(self._on_layers_cell_clicked)

        # 关键：允许横向滚动
        self.tbl_layers.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.tbl_layers.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.tbl_layers.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tbl_layers.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)

        # 高度要给滚动条留空间
        self.tbl_layers.setFixedHeight(140)

        box_layout.addWidget(self.tbl_layers, 1)

        margins = box_layout.contentsMargins()
        layer_tbl_h = self.tbl_layers.height()

        total_h = (
                margins.top() + margins.bottom()
                + kv_tbl.height()
                + lab_layers.sizeHint().height()
                + layer_tbl_h
                + box_layout.spacing() * 2
                + 18
        )
        box.setFixedHeight(total_h)
        box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        return box

    def _on_layers_cell_clicked(self, row: int, col: int):
        if row != 2 or col < 1:
            return
        it = self.tbl_layers.item(row, col)
        if it is None:
            it = QTableWidgetItem("")
            it.setTextAlignment(Qt.AlignCenter)
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.tbl_layers.setItem(row, col, it)
        it.setText("×" if (it.text() or "").strip() == "✓" else "✓")
        self.tbl_layers.clearSelection()

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

        tbl_splash = QTableWidget(1, 3, splash_box)
        self.tbl_splash = tbl_splash
        tbl_splash.setHorizontalHeaderLabels(["飞溅区上限(m)", "飞溅区下限(m)", "腐蚀余量(mm/y)"])
        self._init_table_common(tbl_splash, show_vertical_header=False)
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
        splash_box_h = splash_margins.top() + splash_margins.bottom() + splash_tbl_h + 18
        splash_box.setMinimumHeight(splash_box_h)
        splash_box.setMaximumHeight(splash_box_h)
        splash_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # 桩基信息
        pile_box = QGroupBox("桩基信息")
        pile_box.setStyleSheet(section_title_qss)
        pile_layout = QVBoxLayout(pile_box)
        pile_layout.setContentsMargins(8, 8, 8, 8)

        tbl_pile = QTableWidget(1, 4, pile_box)
        self.tbl_pile = tbl_pile
        tbl_pile.setHorizontalHeaderLabels(["基础冲刷(m)", "桩基础抗压承载能力(t)", "桩基础抗拔承载能力(t)", "单根桩泥下自重(t)"])
        self._init_table_common(tbl_pile, show_vertical_header=False)
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
        pile_box_h = pile_margins.top() + pile_margins.bottom() + pile_tbl_h + 18
        pile_box.setMinimumHeight(pile_box_h)
        pile_box.setMaximumHeight(pile_box_h)
        pile_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # 海生物信息
        marine_box = QGroupBox("海生物信息")
        marine_box.setStyleSheet(section_title_qss)
        marine_layout = QVBoxLayout(marine_box)
        marine_layout.setContentsMargins(8, 8, 8, 8)

        tbl_marine = QTableWidget(5, 12, marine_box)
        self.tbl_marine = tbl_marine
        self._init_table_common(tbl_marine, show_vertical_header=False)
        tbl_marine.horizontalHeader().setVisible(False)
        tbl_marine.verticalHeader().setVisible(False)
        tbl_marine.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        tbl_marine.setSpan(0, 0, 1, 3)
        self._set_center_item(tbl_marine, 0, 0, "层数", editable=False)
        for i in range(9):
            self._set_center_item(tbl_marine, 0, 3 + i, str(i + 1))

        tbl_marine.setSpan(1, 0, 2, 2)
        self._set_center_item(tbl_marine, 1, 0, "高度区域", editable=False)
        self._set_center_item(tbl_marine, 1, 2, "上限(m)", editable=False)
        self._set_center_item(tbl_marine, 2, 2, "下限(m)", editable=False)

        upper = ["0", "-15", "-30", "-50", "-60", "-70", "-80", "-95", "-110"]
        lower = ["-15", "-30", "-50", "-60", "-70", "-80", "-95", "-110", "-122"]
        for i in range(9):
            self._set_center_item(tbl_marine, 1, 3 + i, upper[i])
            self._set_center_item(tbl_marine, 2, 3 + i, lower[i])

        tbl_marine.setSpan(3, 0, 1, 2)
        self._set_center_item(tbl_marine, 3, 0, "海生物", editable=False)
        self._set_center_item(tbl_marine, 3, 2, "厚度(mm)", editable=False)
        thickness = ["10", "10", "10", "4.5", "4.5", "4.5", "4", "4", "4"]
        for i in range(9):
            self._set_center_item(tbl_marine, 3, 3 + i, thickness[i])
        self._set_center_item(tbl_marine, 3, 11, "1.4")

        tbl_marine.setSpan(4, 0, 1, 3)
        tbl_marine.setSpan(4, 3, 1, 9)
        self._set_center_item(tbl_marine, 4, 0, "海生物密度（t/m^3）", editable=False)
        self._set_center_item(tbl_marine, 4, 3, "1.4")

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
        marine_box_h = marine_margins.top() + marine_margins.bottom() + marine_tbl_h + 12
        marine_box.setMinimumHeight(marine_box_h)
        marine_box.setMaximumHeight(marine_box_h)
        marine_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        return splash_box, pile_box, marine_box
