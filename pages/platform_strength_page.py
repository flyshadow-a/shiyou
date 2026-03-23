# -*- coding: utf-8 -*-
# pages/platform_strength_page.py

import os
import re
import math
from typing import Dict, List, Tuple, Optional

from PyQt5.QtCore import Qt, QRectF
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
    QGraphicsScene, QMessageBox, QPushButton, QHeaderView,
)

from base_page import BasePage
from dropdown_bar import DropdownBar
from pages.feasibility_assessment_page import FeasibilityAssessmentPage
from pages.read_table_xls import ReadTableXls


class InpWireframeView(QGraphicsView):
    """
    用 QGraphicsScene 渲染 Abaqus .inp（*NODE + *ELEMENT）线框的 2D 投影。
    说明：这是“先能看见”的简化显示，不是完整三维交互渲染。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(self.renderHints())
        self.setStyleSheet("background:#0b0f14; border: 1px solid #2f3a4a;")
        self.setFrameShape(QFrame.NoFrame)
        self.setAlignment(Qt.AlignCenter)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)

        self._nodes: Dict[int, Tuple[float, float, float]] = {}
        self._edges: List[Tuple[int, int]] = []
        self._proj_pts: Dict[int, Tuple[float, float]] = {}
        self._loaded_path: str = ""
        self._user_view_changed: bool = False
        self._yaw_deg: float = 0.0
        self._pitch_deg: float = 0.0
        self._rotate_dragging: bool = False
        self._rotate_last_pos = None

    def clear_view(self, message: str = ""):
        self.scene().clear()
        self._nodes = {}
        self._edges = []
        self._proj_pts = {}
        self._loaded_path = ""
        self._user_view_changed = False
        self._rotate_dragging = False
        self._rotate_last_pos = None
        self.resetTransform()

        if message:
            t = self.scene().addText(message)
            t.setDefaultTextColor(QColor("#d7e3f0"))
            # center later in resizeEvent
            self._center_text_item(t)

    def load_inp(self, file_path: str):
        self._loaded_path = file_path
        nodes, edges = self._parse_inp_nodes_elements(file_path)
        self._nodes = nodes
        self._edges = edges
        self._user_view_changed = False
        self._yaw_deg = 0.0
        self._pitch_deg = 0.0
        self._rotate_dragging = False
        self._rotate_last_pos = None

        if not self._nodes or not self._edges:
            self.clear_view("未解析到 NODE/ELEMENT 数据")
            return

        self._render()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._nodes and self._edges:
            if not self._user_view_changed:
                rect = self.sceneRect()
                if rect.isValid() and (rect.width() > 0) and (rect.height() > 0):
                    self.fitInView(rect, Qt.KeepAspectRatio)
        else:
            # 让提示文字居中
            for it in self.scene().items():
                if hasattr(it, "toPlainText"):
                    self._center_text_item(it)

    def wheelEvent(self, event):
        if not (self._nodes and self._edges):
            super().wheelEvent(event)
            return

        delta = event.angleDelta().y()
        if delta == 0:
            return

        factor = 1.15 if delta > 0 else 1.0 / 1.15
        cur_scale = self.transform().m11()
        new_scale = cur_scale * factor
        if (new_scale < 0.03) or (new_scale > 300):
            return

        self.scale(factor, factor)
        self._user_view_changed = True
        event.accept()

    def mousePressEvent(self, event):
        if (event.button() == Qt.RightButton) and self._nodes and self._edges:
            self._rotate_dragging = True
            self._rotate_last_pos = event.pos()
            self._user_view_changed = True
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return

        if event.button() in (Qt.LeftButton, Qt.MiddleButton, Qt.RightButton):
            self._user_view_changed = True
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._rotate_dragging and self._rotate_last_pos is not None and self._nodes and self._edges:
            dx = event.pos().x() - self._rotate_last_pos.x()
            dy = event.pos().y() - self._rotate_last_pos.y()

            sens = 0.45
            self._yaw_deg += dx * sens
            self._pitch_deg += dy * sens
            self._pitch_deg = max(-85.0, min(85.0, self._pitch_deg))

            self._rotate_last_pos = event.pos()
            self._render(reset_camera=False)
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.RightButton and self._rotate_dragging:
            self._rotate_dragging = False
            self._rotate_last_pos = None
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self._nodes and self._edges:
            self._yaw_deg = 0.0
            self._pitch_deg = 0.0
            self._render(reset_camera=True)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _center_text_item(self, item):
        br = item.boundingRect()
        w = max(10, self.viewport().width())
        h = max(10, self.viewport().height())
        item.setPos((w - br.width()) / 2, (h - br.height()) / 2)

    # --------- 渲染（2D 投影） ----------
    def _render(self, reset_camera: bool = True):
        self.scene().clear()

        # 1) 3D -> 2D：垂直切面正对视角（默认）+ 可交互旋转
        #    yaw: 绕 Z 轴（平面内旋转）
        #    pitch: 上下俯仰（保持 Z 为主要竖向）
        if not self._nodes:
            self.clear_view("无可显示数据")
            return

        cx3 = sum(v[0] for v in self._nodes.values()) / len(self._nodes)
        cy3 = sum(v[1] for v in self._nodes.values()) / len(self._nodes)
        cz3 = sum(v[2] for v in self._nodes.values()) / len(self._nodes)

        yaw = math.radians(self._yaw_deg)
        pitch = math.radians(self._pitch_deg)
        cos_y, sin_y = math.cos(yaw), math.sin(yaw)
        cos_p, sin_p = math.cos(pitch), math.sin(pitch)

        proj = {}
        xs, ys = [], []
        for nid, (x, y, z) in self._nodes.items():
            x0 = x - cx3
            y0 = y - cy3
            z0 = z - cz3

            # yaw: around Z
            x1 = x0 * cos_y - y0 * sin_y
            depth = x0 * sin_y + y0 * cos_y

            # pitch: vertical keeps z-dominant, depth contributes with tilt
            y2 = z0 * cos_p + depth * sin_p

            px = x1
            py = -y2
            proj[nid] = (px, py)
            xs.append(px)
            ys.append(py)

        if not xs or not ys:
            self.clear_view("无可显示数据")
            return

        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        spanx = max(1e-6, maxx - minx)
        spany = max(1e-6, maxy - miny)

        self._proj_pts = proj

        # 3) 画线
        pen = QPen(QColor("#62ff62"))
        pen.setWidth(0)
        pen.setCosmetic(True)

        for n1, n2 in self._edges:
            p1 = self._proj_pts.get(n1)
            p2 = self._proj_pts.get(n2)
            if p1 is None or p2 is None:
                continue
            self.scene().addLine(p1[0], p1[1], p2[0], p2[1], pen)

        # 4) 设置 sceneRect 并自动拟合（首次加载）
        margin = max(2.0, 0.05 * max(spanx, spany))
        rect = QRectF(minx - margin, miny - margin, spanx + 2 * margin, spany + 2 * margin)
        self.scene().setSceneRect(rect)
        if reset_camera:
            self.resetTransform()
            self.fitInView(rect, Qt.KeepAspectRatio)
            self._user_view_changed = False

    # --------- INP 解析 ----------
    def _parse_inp_nodes_elements(self, file_path: str):
        """
        解析优先级：
        1) Abaqus INP: *NODE / *ELEMENT
        2) SACS INP: JOINT / MEMBER（简化）
        """
        nodes: Dict[int, Tuple[float, float, float]] = {}
        edges: List[Tuple[int, int]] = []

        lines = self._read_lines_with_fallback(file_path)
        in_node = False
        in_elem = False

        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("**"):
                continue

            if line.startswith("*"):
                u = line.upper()
                in_node = u.startswith("*NODE")
                in_elem = u.startswith("*ELEMENT")
                continue

            if in_node:
                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 4:
                    continue
                try:
                    nid = int(float(parts[0]))
                    x = float(parts[1])
                    y = float(parts[2])
                    z = float(parts[3])
                except Exception:
                    continue
                nodes[nid] = (x, y, z)
                continue

            if in_elem:
                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 3:
                    continue
                try:
                    n1 = int(float(parts[1]))
                    n2 = int(float(parts[2]))
                except Exception:
                    continue
                edges.append((n1, n2))
                continue

        # Abaqus 未解析到时，尝试 SACS（JOINT/MEMBER）
        if not nodes or not edges:
            nodes, edges = self._parse_sacs_joints_members(lines)

        return nodes, edges

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

    def _parse_sacs_joints_members(self, lines: List[str]):
        nodes: Dict[int, Tuple[float, float, float]] = {}
        edges: List[Tuple[int, int]] = []
        edge_set = set()
        id_map: Dict[str, int] = {}
        member_lines: List[str] = []
        plate_lines: List[str] = []
        num_pat = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")

        def add_edge(n1: Optional[int], n2: Optional[int]):
            if (n1 is None) or (n2 is None) or (n1 == n2):
                return
            a, b = (n1, n2) if n1 < n2 else (n2, n1)
            if (a, b) in edge_set:
                return
            edge_set.add((a, b))
            edges.append((n1, n2))

        def nid(token: str) -> Optional[int]:
            t = (token or "").strip().upper()
            if not t:
                return None
            if t in id_map:
                return id_map[t]
            try:
                v = int(float(t))
            except Exception:
                v = 1000000 + len(id_map) + 1
            id_map[t] = v
            return v

        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("$") or line.startswith("!") or line.startswith("**"):
                continue

            # JOINT：用正则抽取前三个数字坐标，兼容固定列导致的数字粘连
            m_joint = re.match(r"^\s*JOINT\s+(\S+)\s*(.*)$", line, re.IGNORECASE)
            if m_joint:
                j_tok = m_joint.group(1).strip().upper()
                nums = num_pat.findall(m_joint.group(2) or "")
                if len(nums) < 3:
                    continue
                try:
                    x = float(nums[0])
                    y = float(nums[1])
                    z = float(nums[2])
                except Exception:
                    continue
                j = nid(j_tok)
                if j is None:
                    continue
                nodes[j] = (x, y, z)
                continue

            if re.match(r"^\s*MEMBER\b", line, re.IGNORECASE):
                if re.match(r"^\s*MEMBER\s+OFFSETS\b", line, re.IGNORECASE):
                    continue
                member_lines.append(line)
                continue

            if re.match(r"^\s*PLATE\b", line, re.IGNORECASE):
                if re.match(r"^\s*PLATE\s+OFFSETS\b", line, re.IGNORECASE):
                    continue
                plate_lines.append(line)
                continue

        token_set = set(id_map.keys())
        token_lens = sorted({len(t) for t in token_set}, reverse=True)

        def split_member_pair_token(token: str) -> Optional[Tuple[str, str]]:
            t = (token or "").strip().upper()
            if not t:
                return None

            for sep in ("-", "/", "_", ","):
                if sep in t:
                    a, b = t.split(sep, 1)
                    if (a in token_set) and (b in token_set):
                        return a, b

            for i in range(1, len(t)):
                a = t[:i]
                b = t[i:]
                if (a in token_set) and (b in token_set):
                    return a, b

            # 常见 SACS 紧凑写法：两个 4 字符节点拼接
            if len(t) >= 8:
                a = t[:4]
                b = t[4:8]
                if (a in token_set) and (b in token_set):
                    return a, b
            return None

        def extract_joint_tokens(text: str, max_count: int = 4) -> List[str]:
            s = "".join(ch for ch in (text or "").upper() if ch.isalnum())
            out: List[str] = []
            i = 0
            while i < len(s) and len(out) < max_count:
                found = None
                for ln in token_lens:
                    if i + ln > len(s):
                        continue
                    cand = s[i:i + ln]
                    if cand in token_set:
                        found = cand
                        break
                if found is not None:
                    out.append(found)
                    i += len(found)
                else:
                    i += 1
            return out

        for line in member_lines:
            parts = [p for p in line.replace(",", " ").split() if p]
            if len(parts) < 2:
                continue

            fields = parts[1:]
            pair: Optional[Tuple[str, str]] = None

            # 形式1：MEMBER J1 J2 ...
            f0 = fields[0].upper() if len(fields) >= 1 else ""
            f1 = fields[1].upper() if len(fields) >= 2 else ""
            if len(fields) >= 2 and (f0 in token_set) and (f1 in token_set):
                pair = (f0, f1)
            else:
                # 形式2：MEMBER J1J2 ...（紧凑拼接）
                for fld in fields[:3]:
                    pair = split_member_pair_token(fld)
                    if pair:
                        break

            if not pair:
                continue

            n1 = id_map.get(pair[0])
            n2 = id_map.get(pair[1])
            add_edge(n1, n2)

        for line in plate_lines:
            m_plate = re.match(r"^\s*PLATE\s+\S+\s+(.*)$", line, re.IGNORECASE)
            if not m_plate:
                continue

            conn_text = (m_plate.group(1) or "")[:80]
            joints = extract_joint_tokens(conn_text, max_count=4)
            if len(joints) < 3:
                continue

            node_ids = [id_map.get(jt) for jt in joints]
            node_ids = [nid_v for nid_v in node_ids if nid_v is not None]
            if len(node_ids) < 3:
                continue

            node_ids = node_ids[:4]
            for i in range(len(node_ids) - 1):
                add_edge(node_ids[i], node_ids[i + 1])
            add_edge(node_ids[-1], node_ids[0])

        return nodes, edges


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

        self.data_dir = os.path.join(os.getcwd(), "data")
        self.upload_dir = os.path.join(os.getcwd(), "upload")
        self.model_files_root = os.path.join(self.upload_dir, "model_files")

        self._excel_provider = ReadTableXls()
        self._excel_loaded = False
        try:
            self._excel_provider.load()
            self._excel_loaded = True
        except Exception:
            self._excel_loaded = False

        self._top_records: List[Dict[str, str]] = self._load_top_records_from_excel()
        self._top_cascade_enabled: bool = len(self._top_records) > 0
        self._top_cascade_lock: bool = False
        self._model_signature_cache: Dict[str, Tuple[float, bool]] = {}

        self._build_ui()
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
        fallback_defaults = {k: v for k, v in self.TOP_FIELDS}
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
            if self._top_cascade_enabled:
                opts = self._unique_record_values(self._top_records, label)
                default = opts[0] if opts else fallback
            else:
                opts = self._mock_top_options(label, fallback)
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

    def _apply_top_cascade(self, changed_key: Optional[str] = None, changed_value: str = ""):
        if (not self._top_cascade_enabled) or (not hasattr(self, "dropdown_bar")):
            return

        records = self._top_records
        current = {k: self.dropdown_bar.get_value(k) for k in self.TOP_KEY_ORDER}
        if changed_key:
            current[changed_key] = self._normalize_top_value(changed_value)

        reset_downstream = {
            "branch": {"op_company", "oilfield", "facility_code", "facility_name"},
            "op_company": {"oilfield", "facility_code", "facility_name"},
            "oilfield": {"facility_code", "facility_name"},
            "facility_code": {"facility_name"},
            "facility_name": {"facility_code"},
        }
        reset = reset_downstream.get(changed_key or "", set())

        branches = self._unique_record_values(records, "分公司")
        branch = self._pick_option(branches, current.get("branch", ""))
        branch_rows = [r for r in records if r.get("分公司", "") == branch] if branch else list(records)

        op_opts = self._unique_record_values(branch_rows, "作业公司")
        op_pref = "" if "op_company" in reset else current.get("op_company", "")
        op_company = self._pick_option(op_opts, op_pref)
        op_rows = [r for r in branch_rows if r.get("作业公司", "") == op_company] if op_company else list(branch_rows)

        oil_opts = self._unique_record_values(op_rows, "油气田")
        oil_pref = "" if "oilfield" in reset else current.get("oilfield", "")
        oilfield = self._pick_option(oil_opts, oil_pref)
        oil_rows = [r for r in op_rows if r.get("油气田", "") == oilfield] if oilfield else list(op_rows)

        code_opts = self._unique_record_values(oil_rows, "设施编码")
        name_opts = self._unique_record_values(oil_rows, "设施名称")

        selected_row: Optional[Dict[str, str]] = None
        if changed_key == "facility_name":
            name_pref = current.get("facility_name", "")
            selected_name = self._pick_option(name_opts, name_pref)
            for rec in oil_rows:
                if rec.get("设施名称", "") == selected_name:
                    selected_row = rec
                    break
        else:
            code_pref = "" if "facility_code" in reset else current.get("facility_code", "")
            selected_code = self._pick_option(code_opts, code_pref)
            for rec in oil_rows:
                if rec.get("设施编码", "") == selected_code:
                    selected_row = rec
                    break

        if selected_row is None and oil_rows:
            selected_row = oil_rows[0]

        selected_code = self._normalize_top_value((selected_row or {}).get("设施编码", ""))
        selected_name = self._normalize_top_value((selected_row or {}).get("设施名称", ""))

        fixed_map = {
            "facility_type": "设施类型",
            "category": "分类",
            "start_time": "投产时间",
            "design_life": "设计年限",
        }

        self._top_cascade_lock = True
        try:
            self.dropdown_bar.set_options("branch", branches, branch)
            self.dropdown_bar.set_options("op_company", op_opts, op_company)
            self.dropdown_bar.set_options("oilfield", oil_opts, oilfield)
            self.dropdown_bar.set_options("facility_code", code_opts, selected_code)
            self.dropdown_bar.set_options("facility_name", name_opts, selected_name)

            for key, field_cn in fixed_map.items():
                val = self._normalize_top_value((selected_row or {}).get(field_cn, ""))
                self.dropdown_bar.set_options(key, [val] if val else [], val)
        finally:
            self._top_cascade_lock = False

    def _on_top_key_changed(self, key: str, txt: str):
        if self._top_cascade_enabled:
            if self._top_cascade_lock:
                return
            self._apply_top_cascade(changed_key=key, changed_value=txt)

        if key in {"branch", "op_company", "oilfield", "facility_code", "facility_name"}:
            self._autoload_inp_to_view()

    def _get_top_value(self, key: str) -> str:
        if not hasattr(self, "dropdown_bar"):
            return ""
        try:
            return (self.dropdown_bar.get_value(key) or "").strip()
        except Exception:
            return ""

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
        if self._top_cascade_enabled:
            self._apply_top_cascade()
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
        left_layout.setSpacing(12)

        struct_box = self._build_structure_model_box()
        pile_box, marine_box = self._build_left_tables()
        left_layout.addWidget(struct_box, 0)
        left_layout.addWidget(pile_box, 0)
        left_layout.addWidget(marine_box, 1)

        left_scroll.setWidget(left_frame)
        center_layout.addWidget(left_scroll, 7)

        right = self._build_inp_view_panel()
        center_layout.addWidget(right, 4)

    def on_quick_evaluate(self):
        facility_code = self._get_top_value("facility_code") or "XXXX"
        title = f"{facility_code}平台强度/改造可行性评估"

        mw = self.window()
        if hasattr(mw, "tab_widget"):
            key = f"platform::{facility_code}"
            if hasattr(mw, "page_tab_map") and key in mw.page_tab_map:
                w = mw.page_tab_map[key]
                idx = mw.tab_widget.indexOf(w)
                if idx != -1:
                    mw.tab_widget.setCurrentIndex(idx)
                    return

            page = FeasibilityAssessmentPage(mw, facility_code)
            idx = mw.tab_widget.addTab(page, title)
            mw.tab_widget.setCurrentIndex(idx)
            if hasattr(mw, "page_tab_map"):
                mw.page_tab_map[key] = page
        else:
            QMessageBox.information(self, "提示", "未检测到主窗口Tab组件，无法打开页面。")

    # ---------------- 右侧模型 ----------------
    def _build_inp_view_panel(self) -> QWidget:
        frame = QFrame(self)
        frame.setStyleSheet("QFrame { background: #ffffff; border: 1px solid #b9c6d6; }")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        title = QLabel("结构模型线框预览（读取导入的 SACS INP）")
        title.setStyleSheet("font-weight: bold; color: #1d2b3a;")
        lay.addWidget(title, 0)

        hint = QLabel("左键拖动平移，滚轮缩放，右键拖动旋转，双击复位")
        hint.setStyleSheet("color:#5d6f85; font-size:12px;")
        lay.addWidget(hint, 0)

        self.inp_path_label = QLabel("")
        self.inp_path_label.setWordWrap(True)
        self.inp_path_label.setStyleSheet("color:#4a5b70; font-size:12px;")
        lay.addWidget(self.inp_path_label, 0)

        self.inp_view = InpWireframeView(frame)
        self.inp_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        lay.addWidget(self.inp_view, 1)
        return frame

    def _sacinp_name_score(self, file_name: str) -> int:
        """按文件名判断是否为 SACS 结构模型文件，并返回命名匹配分。"""
        name = (file_name or "").strip().lower()
        if not name:
            return 0

        stem, ext = os.path.splitext(name)
        # 首选：前缀 sacinp*
        if stem.startswith("sacinp"):
            return 300
        # 兼容：*.sacinp
        if ext == ".sacinp":
            return 220
        # 兼容：名称中带独立标识 token（如 xx_sacinp_xx）
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
                if line.startswith("*NODE") or line.startswith("*ELEMENT"):
                    return True
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
                    if code and code in name_low:
                        score += 200
                    if "model_files" in path_low:
                        score += 60
                    if ("静力" in full) or ("static" in path_low):
                        score += 25
                    if "demo_platform_jacket" in name_low:
                        score -= 200

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
            return

        try:
            self.inp_view.load_inp(path)
            self.inp_path_label.setText(f"当前模型文件：{path}")
            
            # 解析泥面高程并回填
            mud_level = self._parse_mud_level_from_sacinp(path)
            if mud_level and hasattr(self, "edt_mud_level"):
                self.edt_mud_level.setText(mud_level)
        except Exception as e:
            self.inp_path_label.setText("模型加载失败")
            self.inp_view.clear_view(f"INP 加载失败：\n{e}")

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
        box_layout.setContentsMargins(10, 10, 10, 10)
        box_layout.setSpacing(8)

        kv_tbl = self._build_structure_model_kv_table()
        box_layout.addWidget(kv_tbl, 0)

        lab_layers = QLabel("水平层高程")
        lab_layers.setFont(self._songti_small_four_font(bold=True))
        lab_layers.setStyleSheet("color: #1d2b3a;")
        box_layout.addWidget(lab_layers, 0)

        self.tbl_layers = QTableWidget(3, 10, box)
        self.tbl_layers.setFocusPolicy(Qt.NoFocus)
        self.tbl_layers.setHorizontalHeaderLabels(["编号"] + [str(i) for i in range(1, 10)])
        self._init_table_common(self.tbl_layers, show_vertical_header=False)
        self.tbl_layers.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._set_center_item(self.tbl_layers, 0, 0, "Z(m)", editable=False)
        self._set_center_item(self.tbl_layers, 1, 0, "节点数量", editable=False)
        self._set_center_item(self.tbl_layers, 2, 0, "是否水平层", editable=False)

        demo_z = ["36", "31", "27", "23", "18", "7", "10", "15", "20"]
        demo_n = ["1", "412", "191", "456", "289", "85", "74", "62", "87"]
        demo_h = ["✓", "✓", "✓", "✓", "✓", "✓", "✓", "✓", "✓"]
        for i in range(9):
            self._set_center_item(self.tbl_layers, 0, i + 1, demo_z[i])
            self._set_center_item(self.tbl_layers, 1, i + 1, demo_n[i])
            self._set_center_item(self.tbl_layers, 2, i + 1, demo_h[i], editable=False)

        for r in range(3):
            self.tbl_layers.setRowHeight(r, 30)

        self.tbl_layers.cellClicked.connect(self._on_layers_cell_clicked)
        self.tbl_layers.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_layers.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tbl_layers.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)

        layer_header_h = self.tbl_layers.horizontalHeader().height() if not self.tbl_layers.horizontalHeader().isHidden() else 0
        layer_rows_h = sum(self.tbl_layers.rowHeight(r) for r in range(self.tbl_layers.rowCount()))
        layer_tbl_h = layer_header_h + layer_rows_h + self.tbl_layers.frameWidth() * 2 + 2
        self.tbl_layers.setFixedHeight(layer_tbl_h + 2)
        self.tbl_layers.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tbl_layers.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        box_layout.addWidget(self.tbl_layers, 1)

        margins = box_layout.contentsMargins()
        total_h = (
            margins.top() + margins.bottom()
            + kv_tbl.height()
            + lab_layers.sizeHint().height()
            + layer_tbl_h
            + box_layout.spacing() * 2
            + 24
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

    def _build_left_tables(self) -> Tuple[QGroupBox, QGroupBox]:
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

        # 桩基信息
        pile_box = QGroupBox("桩基信息")
        pile_box.setStyleSheet(section_title_qss)
        pile_layout = QVBoxLayout(pile_box)
        pile_layout.setContentsMargins(8, 10, 8, 8)

        tbl_pile = QTableWidget(1, 4, pile_box)
        tbl_pile.setHorizontalHeaderLabels(["基础冲刷(m)", "桩基础抗压承载能力(t)", "桩基础抗拔承载能力(t)", "单根桩泥下自重(t)"])
        self._init_table_common(tbl_pile, show_vertical_header=False)
        for c in range(4):
            self._set_center_item(tbl_pile, 0, c, "")
        tbl_pile.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tbl_pile.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        tbl_pile.setRowHeight(0, 34)
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
        pile_box_h = pile_margins.top() + pile_margins.bottom() + pile_tbl_h + 22
        pile_box.setMinimumHeight(pile_box_h)
        pile_box.setMaximumHeight(pile_box_h)
        pile_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # 海生物信息
        marine_box = QGroupBox("海生物信息")
        marine_box.setStyleSheet(section_title_qss)
        marine_layout = QVBoxLayout(marine_box)
        marine_layout.setContentsMargins(8, 10, 8, 10)

        tbl_marine = QTableWidget(5, 12, marine_box)
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
            tbl_marine.setRowHeight(r, 30)

        marine_rows_h = sum(tbl_marine.rowHeight(r) for r in range(tbl_marine.rowCount()))
        marine_tbl_h = marine_rows_h + tbl_marine.frameWidth() * 2 + 8
        tbl_marine.setMinimumHeight(marine_tbl_h)
        tbl_marine.setMaximumHeight(marine_tbl_h)
        tbl_marine.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        tbl_marine.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        marine_layout.addWidget(tbl_marine, 1)
        marine_margins = marine_layout.contentsMargins()
        marine_box_h = marine_margins.top() + marine_margins.bottom() + marine_tbl_h + 14
        marine_box.setMinimumHeight(marine_box_h)
        marine_box.setMaximumHeight(marine_box_h)
        marine_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        return pile_box, marine_box
