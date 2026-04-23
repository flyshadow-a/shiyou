# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Dict, List, Tuple

import numpy as np
import pyvista as pv
from pyvistaqt import QtInteractor

from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QSizePolicy, QSlider, QWidget
)


class SpecialInspectionSacsView(QFrame):
    COLOR_SCHEME = {
        "background": "white",
        "main_structure": "#E0C21B",   # 黄色，接近图二
        "leg_joint": "#C73A3A",        # 红色
        "tubular_joint": "#4B97B9",    # 蓝青色
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

    # 下面这些方法你要保留/补齐到这个类里
    def bind_sliders(self, slider_h, slider_v):
        self._slider_h = slider_h
        self._slider_v = slider_v

    def pan_view(self, x_value: int, y_value: int):
        dx = x_value - self._last_pan_x
        dy = y_value - self._last_pan_y
        self._last_pan_x = x_value
        self._last_pan_y = y_value

        camera = self.plotter.camera
        if camera is None:
            return

        try:
            scale = float(getattr(camera, "parallel_scale", 1.0) or 1.0)
        except Exception:
            scale = 1.0

        factor = max(scale * 0.01, 0.1)

        pos = np.array(camera.position, dtype=float)
        focal = np.array(camera.focal_point, dtype=float)
        up = np.array(camera.up, dtype=float)

        view_dir = focal - pos
        norm = np.linalg.norm(view_dir)
        if norm < 1e-9:
            return
        view_dir = view_dir / norm

        right = np.cross(view_dir, up)
        right_norm = np.linalg.norm(right)
        if right_norm < 1e-9:
            return
        right = right / right_norm

        up_norm = np.linalg.norm(up)
        if up_norm < 1e-9:
            return
        up = up / up_norm

        shift = (-dx) * factor * right + dy * factor * up

        camera.position = tuple(pos + shift)
        camera.focal_point = tuple(focal + shift)
        self.plotter.render()

    def reset_pan_state(self):
        self._last_pan_x = 0
        self._last_pan_y = 0
        if self._slider_h is not None:
            self._slider_h.blockSignals(True)
            self._slider_h.setValue(0)
            self._slider_h.blockSignals(False)
        if self._slider_v is not None:
            self._slider_v.blockSignals(True)
            self._slider_v.setValue(0)
            self._slider_v.blockSignals(False)

    def reset_to_initial_view(self):
        camera = self.plotter.camera
        if camera is None:
            return
        if self._initial_camera_position is not None:
            camera.position = self._initial_camera_position
        if self._initial_camera_focal_point is not None:
            camera.focal_point = self._initial_camera_focal_point
        if self._initial_camera_up is not None:
            camera.up = self._initial_camera_up
        if self._initial_parallel_scale is not None:
            camera.parallel_scale = self._initial_parallel_scale
        self.reset_pan_state()
        self.plotter.render()

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

        try:
            structure = mesh.tube(radius=0.12, n_sides=8)
            self.plotter.add_mesh(
                structure,
                color=self.COLOR_SCHEME["main_structure"],
                opacity=0.85,
                label="Main Structure",
            )
        except Exception:
            self.plotter.add_mesh(
                mesh,
                color=self.COLOR_SCHEME["main_structure"],
                line_width=1.2,
                opacity=0.9,
                label="Main Structure",
            )

        if leg_joints:
            leg_cloud = pv.PolyData(np.array(leg_joints, dtype=float))
            self.plotter.add_mesh(
                leg_cloud.glyph(
                    geom=pv.Sphere(radius=0.55, theta_resolution=12, phi_resolution=12),
                    scale=False,
                    orient=False,
                ),
                color=self.COLOR_SCHEME["leg_joint"],
                label="Leg Joint",
            )

        if tubular_joints:
            tub_cloud = pv.PolyData(np.array(tubular_joints, dtype=float))
            self.plotter.add_mesh(
                tub_cloud.glyph(
                    geom=pv.Sphere(radius=0.30, theta_resolution=10, phi_resolution=10),
                    scale=False,
                    orient=False,
                ),
                color=self.COLOR_SCHEME["tubular_joint"],
                label="Tubular Joint",
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


class SpecialInspectionModelPreviewPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_path = ""

        self.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border: 1px solid #b9c6d6;
            }
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(6)

        # ===== 标题 =====
        self.title_label = QLabel("结构模型预览")
        self.title_label.setFixedHeight(24)
        self.title_label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                color: #2b2b2b;
                font-size: 12pt;
                border: 1px solid #b9c6d6;
                background: #f5f8fc;
                padding-left: 6px;
            }
        """)
        outer.addWidget(self.title_label, 0)

        # ===== 路径栏 + 图例栏（分两行） =====
        self.meta_container = QFrame(self)
        self.meta_container.setStyleSheet("""
            QFrame {
                background: #f8fbff;
                border: 1px solid #c6d2df;
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        meta_layout = QVBoxLayout(self.meta_container)
        meta_layout.setContentsMargins(6, 3, 6, 3)
        meta_layout.setSpacing(1)


        # ---- 第一行：路径 ----
        self.path_row = QWidget(self)
        path_layout = QHBoxLayout(self.path_row)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.setSpacing(4)

        self.path_prefix_label = QLabel("当前模型文件：")
        self.path_prefix_label.setStyleSheet("color:#506070; font-size:9pt;")

        self.path_label = QLabel("未加载模型文件")
        self.path_label.setStyleSheet("color:#506070; font-size:9pt;")
        self.path_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.path_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        path_layout.addWidget(self.path_prefix_label, 0)
        path_layout.addWidget(self.path_label, 1)

        meta_layout.addWidget(self.path_row, 0)

        # ---- 第二行：图例 ----
        self.legend_row = QWidget(self)
        legend_layout = QHBoxLayout(self.legend_row)
        legend_layout.setContentsMargins(0, 0, 0, 0)
        legend_layout.setSpacing(12)

        legend_layout.addWidget(
            self._build_legend_item(
                "Main Structure",
                SpecialInspectionSacsView.COLOR_SCHEME["main_structure"]
            ),
            0
        )
        legend_layout.addWidget(
            self._build_legend_item(
                "Leg Joint",
                SpecialInspectionSacsView.COLOR_SCHEME["leg_joint"]
            ),
            0
        )
        legend_layout.addWidget(
            self._build_legend_item(
                "Tubular Joint",
                SpecialInspectionSacsView.COLOR_SCHEME["tubular_joint"]
            ),
            0
        )
        legend_layout.addStretch(1)

        meta_layout.addWidget(self.legend_row, 0)

        outer.addWidget(self.meta_container, 0)

        # ===== 中间：绘图 + 右侧滑动条 =====
        center = QHBoxLayout()
        center.setContentsMargins(0, 0, 0, 0)
        center.setSpacing(6)

        self.view = SpecialInspectionSacsView(self)
        self.view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        center.addWidget(self.view, 1)

        self.slider_v = QSlider(Qt.Vertical, self)
        self.slider_v.setFixedWidth(16)
        self.slider_v.setRange(-100, 100)
        self.slider_v.setValue(0)
        self.slider_v.valueChanged.connect(self._on_pan_changed)
        center.addWidget(self.slider_v, 0)

        outer.addLayout(center, 1)

        # ===== 底部水平滑动条 =====
        self.slider_h = QSlider(Qt.Horizontal, self)
        self.slider_h.setFixedHeight(16)
        self.slider_h.setRange(-100, 100)
        self.slider_h.setValue(0)
        self.slider_h.valueChanged.connect(self._on_pan_changed)
        outer.addWidget(self.slider_h, 0)

        self.view.bind_sliders(self.slider_h, self.slider_v)

    def _build_legend_item(self, text: str, color: str) -> QWidget:
        w = QWidget(self)
        w.setStyleSheet("QWidget{border:none; background:transparent;}")

        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        dot = QLabel()
        dot.setFixedSize(10, 10)
        dot.setStyleSheet(f"""
            QLabel {{
                background: {color};
                border: 1px solid #7f8c99;
                border-radius: 5px;
            }}
        """)

        lab = QLabel(text)
        lab.setStyleSheet("color:#4f5f6f; font-size:9pt;")

        lay.addWidget(dot, 0)
        lay.addWidget(lab, 0)

        return w

    def _set_path_text(self, full_path: str):
        full_path = os.path.normpath(full_path) if full_path else ""
        if not full_path:
            self.path_label.setText("未加载模型文件")
            self.path_label.setToolTip("")
            return

        parts = full_path.split(os.sep)
        if len(parts) >= 3:
            short_text = f"...{os.sep}{parts[-2]}{os.sep}{parts[-1]}"
        else:
            short_text = os.path.basename(full_path)

        self.path_label.setText(short_text)
        self.path_label.setToolTip(full_path)

    def _on_pan_changed(self):
        self.view.pan_view(self.slider_h.value(), self.slider_v.value())

    def load_model(self, file_path: str, target_z: float = 9.1):
        self._current_path = os.path.normpath(str(file_path or "").strip())

        if not self._current_path:
            self._set_path_text("")
            self.view.clear_view("未提供模型文件")
            return

        self._set_path_text(self._current_path)

        if not os.path.exists(self._current_path):
            self.view.clear_view(f"模型文件不存在：\n{self._current_path}")
            return

        try:
            self.slider_h.blockSignals(True)
            self.slider_v.blockSignals(True)
            self.slider_h.setValue(0)
            self.slider_v.setValue(0)
            self.slider_h.blockSignals(False)
            self.slider_v.blockSignals(False)

            self.view.reset_pan_state()
            self.view.load_inp(self._current_path, target_z=target_z)
        except Exception as exc:
            self.view.clear_view(f"模型预览失败：\n{exc}")

    def clear_model(self, message: str = "当前未加载模型文件"):
        self._set_path_text("")
        self.view.clear_view(message)