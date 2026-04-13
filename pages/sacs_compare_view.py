# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pyvista as pv
from pyvistaqt import QtInteractor

from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QWidget,
    QSlider,
)


class PyVistaSacsCompareView(QFrame):
    COLOR_SCHEME = {
        "background": "white",

        # 结构
        "main_structure": "#E9D012",   # 原结构：暖黄色
        "added_structure": "#D95D39",  # 新增结构：砖橙红

        # 节点
        "leg_joint": "#B22222",        # 主腿节点：深红
        "tubular_joint": "#2A7F9E",    # 核心管节点：湖蓝
        "added_node": "#2E8B57",       # 新增节点：深绿
    }

    def __init__(self, parent=None):
        super().__init__(parent)

        self._old_file = ""
        self._new_file = ""

        self._old_nodes = {}
        self._old_members = []
        self._old_groups_od = {}

        self._new_nodes = {}
        self._new_members = []
        self._new_groups_od = {}

        self._last_pan_x = 0
        self._last_pan_y = 0

        self._initial_camera_position = None
        self._initial_camera_focal_point = None
        self._initial_camera_up = None
        self._initial_parallel_scale = None

        self._slider_h = None
        self._slider_v = None

        self._closing = False
        self._closed = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.plotter = QtInteractor(self)
        self.plotter.installEventFilter(self)
        layout.addWidget(self.plotter)

        self.plotter.set_background(self.COLOR_SCHEME["background"])
        self.plotter.add_axes()

    def clear_view(self, message: str = ""):
        if not self._can_render():
            return

        try:
            self.plotter.clear()
            self.plotter.set_background(self.COLOR_SCHEME["background"])
            self.plotter.add_axes()
            if message:
                self.plotter.add_text(message, position="upper_left", font_size=10)
        except Exception:
            pass

    def _can_render(self) -> bool:
        return (not self._closing) and (not self._closed) and hasattr(self, "plotter") and self.plotter is not None

    def _safe_render(self):
        if not self._can_render():
            return
        try:
            self.plotter.render()
        except Exception:
            pass

    def safe_close(self):
        if self._closed:
            return

        self._closing = True

        try:
            if self._slider_h is not None:
                self._slider_h.blockSignals(True)
            if self._slider_v is not None:
                self._slider_v.blockSignals(True)
        except Exception:
            pass

        plotter = getattr(self, "plotter", None)
        self.plotter = None

        try:
            if plotter is not None:
                try:
                    plotter.Finalize()
                except Exception:
                    pass
                try:
                    plotter.close()
                except Exception:
                    pass
                try:
                    plotter.setParent(None)
                except Exception:
                    pass
                try:
                    plotter.deleteLater()
                except Exception:
                    pass
        finally:
            self._closed = True

    def closeEvent(self, event):
        self.safe_close()
        super().closeEvent(event)

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

        self.reset_pan_state()

        if self._slider_h is not None:
            self._slider_h.blockSignals(True)
            self._slider_h.setValue(0)
            self._slider_h.blockSignals(False)

        if self._slider_v is not None:
            self._slider_v.blockSignals(True)
            self._slider_v.setValue(0)
            self._slider_v.blockSignals(False)

        self._safe_render()

    def bind_sliders(self, slider_h, slider_v):
        self._slider_h = slider_h
        self._slider_v = slider_v

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

        step = max(dist * 0.02, 0.5)
        shift = right * (dx_slider * step) + true_up * (dy_slider * step)

        cam.position = tuple(pos + shift)
        cam.focal_point = tuple(focal + shift)

        self._safe_render()

    def reset_pan_state(self):
        self._last_pan_x = 0
        self._last_pan_y = 0

    def load_compare(self, old_file: str, new_file: str, target_z: float = 9.1):
        self._old_file = old_file or ""
        self._new_file = new_file or ""

        if not self._old_file or (not os.path.exists(self._old_file)):
            self.clear_view(f"原模型文件不存在：\n{self._old_file}")
            return

        if not self._new_file or (not os.path.exists(self._new_file)):
            self.clear_view(f"新模型文件不存在：\n{self._new_file}")
            return

        old_nodes, old_members, old_groups_od = self.parse_sacs_full_robust(self._old_file)
        new_nodes, new_members, new_groups_od = self.parse_sacs_full_robust(self._new_file)

        self._old_nodes = old_nodes
        self._old_members = old_members
        self._old_groups_od = old_groups_od

        self._new_nodes = new_nodes
        self._new_members = new_members
        self._new_groups_od = new_groups_od

        if (not new_nodes) or (not new_members):
            self.clear_view("未解析到有效的新模型 JOINT/MEMBER 数据")
            return

        leg_joints, tubular_joints = self.apply_pdf_logic_diagnostic(
            new_nodes, new_members, new_groups_od, target_z=target_z
        )

        split_result = self.split_old_new_structure(
            old_nodes, old_members, new_nodes, new_members
        )

        self.render_compare_structure(
            new_nodes=new_nodes,
            common_members=split_result["common_members"],
            added_members=split_result["added_members"],
            leg_joints=leg_joints,
            tubular_joints=tubular_joints,
            added_node_ids=split_result["added_node_ids"],
        )

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

    def parse_sacs_full_robust(self, filepath: str):
        nodes = {}
        members = []
        groups_od = {}

        lines = self._read_lines_with_fallback(filepath)
        for line in lines:
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
                    body = line[6:].strip()
                    if body.startswith("OFFSETS"):
                        continue

                    na = line[7:11].strip()
                    nb = line[11:15].strip()
                    gid = line[15:18].strip()

                    if na and nb:
                        members.append((na, nb, gid))
                except Exception:
                    continue

        return nodes, members, groups_od

    def apply_pdf_logic_diagnostic(
        self,
        nodes: Dict[str, List[float]],
        members: List[Tuple[str, str, str]],
        groups_od: Dict[str, float],
        target_z: float = 8.5,
    ):
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
            nid: od
            for nid, od in node_to_max_od.items()
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

    @staticmethod
    def normalize_member_key(na: str, nb: str, gid: str):
        a, b = sorted([na, nb])
        return a, b, gid

    def split_old_new_structure(
        self,
        old_nodes: Dict[str, List[float]],
        old_members: List[Tuple[str, str, str]],
        new_nodes: Dict[str, List[float]],
        new_members: List[Tuple[str, str, str]],
    ):
        old_member_keys = {
            self.normalize_member_key(na, nb, gid)
            for na, nb, gid in old_members
        }
        new_member_keys = {
            self.normalize_member_key(na, nb, gid)
            for na, nb, gid in new_members
        }

        added_member_keys = new_member_keys - old_member_keys

        added_members = []
        common_members = []

        for na, nb, gid in new_members:
            key = self.normalize_member_key(na, nb, gid)
            if key in added_member_keys:
                added_members.append((na, nb, gid))
            else:
                common_members.append((na, nb, gid))

        old_node_ids = set(old_nodes.keys())
        new_node_ids = set(new_nodes.keys())
        added_node_ids = new_node_ids - old_node_ids

        return {
            "common_members": common_members,
            "added_members": added_members,
            "added_node_ids": added_node_ids,
        }

    def build_polyline_mesh(self, nodes: Dict[str, List[float]], members: List[Tuple[str, str, str]]):
        node_ids = list(nodes.keys())
        if not node_ids:
            return None

        id_map = {nid: i for i, nid in enumerate(node_ids)}
        points = np.array([nodes[nid] for nid in node_ids], dtype=float)

        lines = []
        for na, nb, _ in members:
            if na in id_map and nb in id_map:
                lines.extend([2, id_map[na], id_map[nb]])

        if not lines:
            return None

        mesh = pv.PolyData(points)
        mesh.lines = np.array(lines)
        return mesh

    def add_structure_mesh(self, mesh, color: str, label: str, tube_radius: float = 0.15, opacity: float = 0.8):
        if mesh is None:
            return

        try:
            structure = mesh.tube(radius=tube_radius, n_sides=6)
            self.plotter.add_mesh(structure, color=color, opacity=opacity, label=label)
        except Exception:
            self.plotter.add_mesh(mesh, color=color, line_width=2.0, opacity=opacity, label=label)

    def add_point_cloud(self, points, color: str, label: str, radius: float):
        if points is None or len(points) == 0:
            return
        cloud = pv.PolyData(np.array(points, dtype=float))
        glyph = cloud.glyph(
            geom=pv.Sphere(radius=radius, theta_resolution=12, phi_resolution=12),
            scale=False,
            orient=False
        )
        self.plotter.add_mesh(glyph, color=color, label=label)

    def render_compare_structure(
            self,
            new_nodes: Dict[str, List[float]],
            common_members: List[Tuple[str, str, str]],
            added_members: List[Tuple[str, str, str]],
            leg_joints,
            tubular_joints,
            added_node_ids,
    ):
        if not self._can_render():
            return

        try:
            self.plotter.clear()
            self.plotter.set_background(self.COLOR_SCHEME["background"])

            common_mesh = self.build_polyline_mesh(new_nodes, common_members)
            self.add_structure_mesh(
                common_mesh,
                color=self.COLOR_SCHEME["main_structure"],
                label="Original Structure",
                tube_radius=0.12,
                opacity=0.35,
            )

            added_mesh = self.build_polyline_mesh(new_nodes, added_members)
            self.add_structure_mesh(
                added_mesh,
                color=self.COLOR_SCHEME["added_structure"],
                label="Added Structure",
                tube_radius=0.20,
                opacity=0.95,
            )

            self.add_point_cloud(
                leg_joints,
                color=self.COLOR_SCHEME["leg_joint"],
                label="Leg Joint",
                radius=0.8,
            )

            self.add_point_cloud(
                tubular_joints,
                color=self.COLOR_SCHEME["tubular_joint"],
                label="Tubular Joint",
                radius=0.3,
            )

            added_points = [new_nodes[nid] for nid in added_node_ids if nid in new_nodes]
            self.add_point_cloud(
                added_points,
                color=self.COLOR_SCHEME["added_node"],
                label="Added Node",
                radius=0.45,
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

        except Exception:
            pass


class SacsComparePanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("QFrame { background: #ffffff; border: 1px solid #b9c6d6; }")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(6)

        self.path_label = QLabel("")
        self.path_label.setWordWrap(True)
        self.path_label.setStyleSheet("color:#4a5b70; font-size:12px;")
        outer.addWidget(self.path_label, 0)

        outer.addWidget(self._build_custom_legend(), 0)

        view_row = QHBoxLayout()
        view_row.setContentsMargins(0, 0, 0, 0)
        view_row.setSpacing(6)

        self.compare_view = PyVistaSacsCompareView(self)
        self.compare_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        view_row.addWidget(self.compare_view, 1)

        self.slider_v = QSlider(Qt.Vertical)
        self.slider_v.setRange(-100, 100)
        self.slider_v.setValue(0)
        self.slider_v.valueChanged.connect(
            lambda v: self.compare_view.pan_view(self.slider_h.value(), v)
        )
        view_row.addWidget(self.slider_v, 0)

        outer.addLayout(view_row, 1)

        self.slider_h = QSlider(Qt.Horizontal)
        self.slider_h.setRange(-100, 100)
        self.slider_h.setValue(0)
        self.slider_h.valueChanged.connect(
            lambda v: self.compare_view.pan_view(v, self.slider_v.value())
        )
        outer.addWidget(self.slider_h, 0)

        self.compare_view.bind_sliders(self.slider_h, self.slider_v)

    def _build_custom_legend(self) -> QWidget:
        w = QWidget(self)
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

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
        lay.addWidget(make_item("#E9D012", "Original Structure"), 0)
        lay.addWidget(make_item("#D95D39", "Added Structure"), 0)
        lay.addWidget(make_item("#B22222", "Leg Joint"), 0)
        lay.addWidget(make_item("#2A7F9E", "Tubular Joint"), 0)
        lay.addWidget(make_item("#2E8B57", "Added Node"), 0)

        return w

    def load_files(self, old_file: str, new_file: str, target_z: float = 9.1):
        self.path_label.setText(
            f"原模型文件：{old_file}\n新模型文件：{new_file}"
        )

        self.slider_h.blockSignals(True)
        self.slider_h.setValue(0)
        self.slider_h.blockSignals(False)

        self.slider_v.blockSignals(True)
        self.slider_v.setValue(0)
        self.slider_v.blockSignals(False)

        self.compare_view.reset_pan_state()
        self.compare_view.load_compare(old_file, new_file, target_z=target_z)

    def safe_close(self):
        try:
            if hasattr(self, "slider_h") and self.slider_h is not None:
                self.slider_h.blockSignals(True)
            if hasattr(self, "slider_v") and self.slider_v is not None:
                self.slider_v.blockSignals(True)
        except Exception:
            pass

        try:
            if hasattr(self, "compare_view") and self.compare_view is not None:
                self.compare_view.safe_close()
        except Exception:
            pass

    def closeEvent(self, event):
        self.safe_close()
        super().closeEvent(event)