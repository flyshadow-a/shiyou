# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import Dict, List, Tuple, Optional

from PyQt5.QtCore import Qt, QRectF, QTimer, QPointF
from PyQt5.QtGui import QBrush, QColor, QPainter, QPen, QFont
from PyQt5.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

from services.file_db_adapter import (
    FileBackendError,
    is_file_db_configured,
    list_storage_paths,
    list_storage_paths_by_prefix,
)
from core.app_paths import external_path, first_existing_path

import openpyxl
import csv
import json

try:
    import pandas as pd
except Exception:
    pd = None


class RiskNodeItem(QGraphicsEllipseItem):
    def __init__(self, rect: QRectF, tooltip: str = "", hover_callback=None, *args, **kwargs):
        super().__init__(rect, *args, **kwargs)
        self.setAcceptHoverEvents(False)
        self.setToolTip(tooltip)
        self._hover_callback = hover_callback

    def hoverEnterEvent(self, event):
        if self._hover_callback:
            self._hover_callback(self.toolTip())
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        if self._hover_callback:
            self._hover_callback("")
        super().hoverLeaveEvent(event)


class RiskMemberItem(QGraphicsLineItem):
    def __init__(self, x1, y1, x2, y2, tooltip: str = "", hover_callback=None, *args, **kwargs):
        super().__init__(x1, y1, x2, y2, *args, **kwargs)
        self.setAcceptHoverEvents(False)
        self.setToolTip(tooltip)
        self._hover_callback = hover_callback

    def hoverEnterEvent(self, event):
        if self._hover_callback:
            self._hover_callback(self.toolTip())
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        if self._hover_callback:
            self._hover_callback("")
        super().hoverLeaveEvent(event)


class SacsElevationRiskView(QGraphicsView):

    COLOR_BG = QColor(255, 255, 255)

    # 轮廓颜色：单立面更清晰，全部总览略浅但不能太淡
    COLOR_MEMBER_ROW = QColor("#5f84b8")      # 单立面：中蓝
    COLOR_MEMBER_ALL = QColor("#a7b6c8")      # 全部：灰蓝
    COLOR_GRID = QColor("#d7dde6")            # 背景网格
    COLOR_AXIS = QColor("#5c6470")            # 轴线/文字
    COLOR_TEXT = QColor("#5c6470")

    SHOW_NODE_TEXT = False
    SHOW_MEMBER_TEXT = False
    DRAW_NONRISK_NODES = False

    HORIZONTAL_EXAGGERATION_ALL = 2.2
    HORIZONTAL_EXAGGERATION_ROW = 1.75

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setBackgroundBrush(QBrush(self.COLOR_BG))
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorViewCenter)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setCursor(Qt.ArrowCursor)
        self.setInteractive(True)

        self._fit_done = False
        self._zoom_steps = 0

        self._slider_h = None
        self._slider_v = None
        self._initial_scene_rect = QRectF()
        self._last_pan_x = 0
        self._last_pan_y = 0

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self.nodes: Dict[str, Tuple[float, float, float]] = {}
        self.members: List[Tuple[str, str, str]] = []
        self.node_risk_map: Dict[str, str] = {}
        self.member_risk_map: Dict[Tuple[str, str], str] = {}
        self._groups_od: Dict[str, float] = {}

        self._facility_code = ""
        self._model_path = ""
        self._row_name = "ROW A"
        self._info_label = None
        self._workpoint_z = 9.1
        self._level_threshold = 40

    # ---------------- UI helper ----------------
    def set_info_label(self, label):
        self._info_label = label

    def bind_sliders(self, slider_h, slider_v):
        self._slider_h = slider_h
        self._slider_v = slider_v

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

    def pan_view(self, x_value: int, y_value: int):
        if not self._initial_scene_rect.isValid():
            return

        rx = self._initial_scene_rect.width() * 0.14
        ry = self._initial_scene_rect.height() * 0.14

        cx = self._initial_scene_rect.center().x() + rx * (x_value / 100.0)
        cy = self._initial_scene_rect.center().y() - ry * (y_value / 100.0)

        self.centerOn(QPointF(cx, cy))

    def _show_hover_info(self, _text: str = ""):
        if self._info_label is None:
            return
        self._info_label.setText(
            f"当前显示：{self._row_name} 立面轮廓图；滚轮缩放，双击恢复初始视图。"
        )

    def reset_view(self):
        rect = self._scene.sceneRect()
        if (not rect.isValid()) or rect.isNull():
            rect = self._scene.itemsBoundingRect()
        if not rect.isValid():
            return

        # 改成更均衡的四周留白，避免图像被“视觉上往下压”
        rect = rect.adjusted(-10, -10, 10, 10)
        self._scene.setSceneRect(rect)

        self.resetTransform()
        self.fitInView(rect, Qt.KeepAspectRatio)

        self._initial_scene_rect = QRectF(rect)
        self._fit_done = True
        self._zoom_steps = 0

        # 直接严格居中，不再额外做上下偏移
        self.centerOn(rect.center())

        self.reset_pan_state()
        self._show_hover_info()

    # ---------------- 外部入口 ----------------
    def load_for_facility(
            self,
            facility_code: str,
            context: Dict,
            year_label: str,
            row_name: str = "XZ 前",
            workpoint_override: Optional[float] = None,
            level_threshold_override: Optional[int] = None,
    ) -> None:
        self._facility_code = (facility_code or "").strip()
        self._row_name = (row_name or "XZ 1").strip()

        self._model_path = self._resolve_model_path(self._facility_code)

        print("[Elevation] facility_code =", self._facility_code)
        print("[Elevation] row_name =", self._row_name)
        print("[Elevation] resolved model_path =", self._model_path)

        if not self._model_path or not os.path.exists(self._model_path):
            self._draw_message("未找到结构模型文件")
            return

        self.nodes, self.members, self._groups_od = self.parse_sacs_full_robust(self._model_path)
        if not self.nodes or not self.members:
            self._draw_message("模型文件未解析到有效 JOINT/MEMBER")
            return

        self.node_risk_map = {}
        self.member_risk_map = {}


        auto_wp = self._extract_workpoint_from_context(context)
        self._workpoint_z = auto_wp if workpoint_override in (None, "") else self._safe_float(workpoint_override,
                                                                                              auto_wp)
        auto_thr = self._extract_level_threshold_from_context(context)
        if level_threshold_override in (None, ""):
            self._level_threshold = auto_thr
        else:
            try:
                self._level_threshold = int(level_threshold_override)
            except Exception:
                self._level_threshold = auto_thr

        row_names = self.available_row_names()
        if row_names and self._row_name not in row_names:
            self._row_name = row_names[0]

        self._render_row_elevation()
        self._fit_done = False
        self._zoom_steps = 0
        QTimer.singleShot(0, self.reset_view)

    # ---------------- 模型文件路径 ----------------
    def _resolve_model_path(self, facility_code: str) -> str:
        code = (facility_code or "").strip() or None
        candidates: List[str] = []

        if is_file_db_configured():
            query_specs = [
                ("model_files", f"{facility_code}/当前模型/结构模型"),
                ("model_files", f"{facility_code}/当前模型/结构模型/用户上传"),
                ("special_strategy", f"{facility_code}/当前模型/结构模型"),
                ("special_strategy", f"{facility_code}/当前模型/结构模型/用户上传"),
            ]

            for module_code, logical_prefix in query_specs:
                try:
                    rows = list_storage_paths_by_prefix(
                        file_type_code="model",
                        module_code=module_code,
                        logical_path_prefix=logical_prefix,
                        facility_code=code,
                    )
                    if rows:
                        candidates.extend(rows)
                except FileBackendError:
                    pass

            if not candidates:
                for module_code, logical_prefix in query_specs:
                    try:
                        rows = list_storage_paths_by_prefix(
                            file_type_code="model",
                            module_code=module_code,
                            logical_path_prefix=logical_prefix,
                            facility_code=None,
                        )
                        if rows:
                            candidates.extend(rows)
                    except FileBackendError:
                        pass

            if not candidates:
                for module_code in ("model_files", "special_strategy"):
                    try:
                        rows = list_storage_paths(
                            file_type_code="model",
                            module_code=module_code,
                            facility_code=code,
                        )
                        if rows:
                            candidates.extend(rows)
                    except Exception:
                        pass

        upload_roots = [
            external_path("upload", "model_files"),
            first_existing_path("upload", "model_files"),
            r"Y:\upload\model_files",
            r"Y:\special_strategy_inputs",
        ]

        for upload_root in upload_roots:
            if not upload_root or not os.path.isdir(upload_root):
                continue
            for root, _dirs, files in os.walk(upload_root):
                for fn in files:
                    low = fn.lower()
                    if low.startswith("sacinp") or low.endswith(".sacinp") or "sacinp" in low:
                        candidates.append(os.path.join(root, fn))

        uniq = []
        seen = set()
        for p in candidates:
            np = os.path.normpath(str(p))
            if np not in seen:
                seen.add(np)
                uniq.append(np)

        if not uniq:
            return ""

        uniq.sort(
            key=lambda p: (
                self._score_model_candidate(p, facility_code),
                os.path.getmtime(p) if os.path.exists(p) else 0
            ),
            reverse=True,
        )

        for p in uniq:
            if os.path.exists(p):
                return p

        return ""

    def _detect_leg_joint_nodes(self) -> Dict[str, Tuple[float, float, float]]:
        if not self.nodes or not self.members:
            return {}

        node_to_max_od = {nid: 0.0 for nid in self.nodes}
        for na, nb, gid in self.members:
            if na in self.nodes and nb in self.nodes:
                od = float(self._groups_od.get(gid, 0.0))
                node_to_max_od[na] = max(node_to_max_od[na], od)
                node_to_max_od[nb] = max(node_to_max_od[nb], od)

        tolerance = 1.0
        elevation_nodes = {
            nid: self.nodes[nid]
            for nid in self.nodes
            if abs(float(self.nodes[nid][2]) - float(self._workpoint_z)) < tolerance
        }
        if not elevation_nodes:
            return {}

        local_max_od = max(node_to_max_od[nid] for nid in elevation_nodes)
        return {
            nid: self.nodes[nid]
            for nid in elevation_nodes
            if node_to_max_od[nid] >= local_max_od * 0.95
        }

    def _get_leg_plane_clusters(self) -> tuple[list[float], list[float]]:
        leg_nodes = self._detect_leg_joint_nodes()

        # 优先用主腿；主腿识别不到时再退回 workpoint 以下节点
        base_nodes = leg_nodes if leg_nodes else self._nodes_below_workpoint()
        return self._get_axis_clusters(base_nodes)

    def _score_model_candidate(self, path: str, facility_code: str) -> int:
        name = os.path.basename(path).lower()
        path_low = path.lower()
        score = 0
        if name.startswith("sacinp"):
            score += 300
        if name.endswith(".sacinp"):
            score += 220
        if "当前模型" in path:
            score += 80
        if "结构模型" in path:
            score += 60
        if facility_code and facility_code.lower() in path_low:
            score += 200
        if "user" in path_low or "用户上传" in path_low:
            score += 20
        return score

    # ---------------- 模型解析 ----------------
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

    def parse_sacs_full_robust(self, filepath):
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
                    nodes[nid] = (x, y, z)
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

    def _project_root(self) -> str:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _resolve_risk_workbook_path(self) -> str:
        root = self._project_root()
        strategy_root = os.path.join(root, "pages", "output_special_strategy")
        candidates = [
            os.path.join(strategy_root, "检验策略- wc19-1d-10.30.xlsm"),
            os.path.join(strategy_root, "wc19_1d_compare_source.xlsm"),
            os.path.join(strategy_root, "wc19_1d_source.xlsm"),
            os.path.join(root, "检验策略- wc19-1d-10.30.xlsm"),
            os.path.join(root, "检验策略-wc19-1d-10.30.xlsm"),
            os.path.join(root, "检验策略_wc19-1d-10.30.xlsm"),
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return ""

    def _normalize_year_label_for_sheet(self, year_label: str) -> str:
        if year_label == "当前":
            return "当前"
        mapping = {
            "+5年": "第5年",
            "+10年": "第10年",
            "+15年": "第15年",
            "+20年": "第20年",
            "+25年": "第25年",
        }
        return mapping.get(year_label, year_label)

    def _read_sheet_rows(self, workbook_path: str, sheet_name: str, header_row: int, data_start_row: int) -> List[Dict]:
        if not workbook_path or not os.path.exists(workbook_path):
            return []

        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Data Validation extension is not supported and will be removed")
            wb = openpyxl.load_workbook(workbook_path, data_only=True, read_only=True)

        if sheet_name not in wb.sheetnames:
            return []

        ws = wb[sheet_name]

        header_values = next(ws.iter_rows(min_row=header_row, max_row=header_row, values_only=True))
        headers = [("" if v is None else str(v).strip()) for v in header_values]

        rows: List[Dict] = []
        for values in ws.iter_rows(min_row=data_start_row, values_only=True):
            if not any(v not in (None, "", " ") for v in values):
                continue

            row = {}
            for idx, h in enumerate(headers):
                if not h:
                    continue
                row[h] = values[idx] if idx < len(values) else None
            rows.append(row)

        return rows

    def _normalize_existing_path(self, path: str) -> str:
        p = os.path.normpath(str(path or "").strip())
        if not p:
            return ""
        if os.path.exists(p):
            return p

        roots = [
            "",
            external_path(""),
            first_existing_path("upload"),
            first_existing_path("upload", "model_files"),
            r"Y:\shiyou_file_storage",
            r"Y:\upload",
            r"Y:\special_strategy_inputs",
        ]
        for root in roots:
            if not root:
                continue
            candidate = os.path.normpath(os.path.join(root, p))
            if os.path.exists(candidate):
                return candidate
        return ""

    def _collect_candidate_paths(self, context: Dict, keys: List[str]) -> List[str]:
        paths: List[str] = []
        for key in keys:
            value = context.get(key)
            if not value:
                continue

            if isinstance(value, str):
                paths.append(value)
            elif isinstance(value, dict):
                for kk in ("storage_path", "path", "file_path", "absolute_path"):
                    if value.get(kk):
                        paths.append(str(value[kk]))
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        paths.append(item)
                    elif isinstance(item, dict):
                        for kk in ("storage_path", "path", "file_path", "absolute_path"):
                            if item.get(kk):
                                paths.append(str(item[kk]))

        out: List[str] = []
        seen = set()
        for p in paths:
            real = self._normalize_existing_path(p)
            if real and real not in seen:
                seen.add(real)
                out.append(real)
        return out

    def _read_rows_from_table_file(self, path: str, preferred_sheet_keywords: List[str] | None = None) -> List[Dict]:
        if not path or not os.path.exists(path):
            return []

        ext = os.path.splitext(path)[1].lower()

        try:
            if ext == ".csv":
                with open(path, "r", encoding="utf-8-sig", newline="") as f:
                    return list(csv.DictReader(f))

            if ext == ".json":
                with open(path, "r", encoding="utf-8") as f:
                    obj = json.load(f)
                if isinstance(obj, list):
                    return [x for x in obj if isinstance(x, dict)]
                if isinstance(obj, dict):
                    for v in obj.values():
                        if isinstance(v, list) and v and isinstance(v[0], dict):
                            return v
                return []

            if ext in {".xlsx", ".xlsm", ".xls"} and pd is not None:
                sheets = pd.read_excel(path, sheet_name=None)
                rows: List[Dict] = []

                def _sheet_score(name: str) -> int:
                    if not preferred_sheet_keywords:
                        return 0
                    low = str(name).lower()
                    score = 0
                    for kw in preferred_sheet_keywords:
                        if kw.lower() in low:
                            score += 10
                    return score

                ordered = sorted(sheets.items(), key=lambda kv: _sheet_score(kv[0]), reverse=True)
                for sheet_name, df in ordered:
                    if df is None or df.empty:
                        continue
                    clean_df = df.where(pd.notnull(df), None)
                    records = clean_df.to_dict(orient="records")
                    if records:
                        rows.extend(records)
                        if preferred_sheet_keywords and _sheet_score(sheet_name) > 0:
                            return rows
                return rows
        except Exception as exc:
            print("[Elevation] read risk table failed:", path, exc)

        return []

    def _extract_rows_from_context_or_files(
            self,
            context: Dict,
            direct_keys: List[str],
            path_keys: List[str],
            preferred_sheet_keywords: List[str],
    ) -> List[Dict]:
        for key in direct_keys:
            value = context.get(key)
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return value

        paths = self._collect_candidate_paths(context, path_keys)
        for path in paths:
            rows = self._read_rows_from_table_file(path, preferred_sheet_keywords=preferred_sheet_keywords)
            if rows:
                print("[Elevation] loaded risk rows from file:", path, "count=", len(rows))
                return rows

        return []

    def _risk_text_to_num(self, value: object) -> str:
        raw = str(value or "").strip()
        mapping = {
            "一": "1", "二": "2", "三": "3", "四": "4", "五": "5",
            "Ⅰ": "1", "Ⅱ": "2", "Ⅲ": "3", "Ⅳ": "4", "Ⅴ": "5",
            "1": "1", "2": "2", "3": "3", "4": "4", "5": "5",
        }
        return mapping.get(raw, raw)

    def _match_time_node(self, row: Dict, year_label: str) -> bool:
        time_node = str(row.get("time_node") or row.get("year") or row.get("年份") or "").strip()
        if not time_node:
            return year_label == "当前"

        if year_label == "当前":
            return time_node in {"当前", "current", "Current"}

        if year_label.startswith("+") and year_label.endswith("年"):
            n = year_label[1:-1]
            return time_node in {f"第{n}年", year_label}

        return False

    # 下面两个函数保留，后续重新打开风险标注时可直接恢复使用
    def _extract_node_risks_from_context(self, context: Dict, year_label: str) -> Dict[str, str]:
        result: Dict[str, str] = {}

        workbook_path = self._resolve_risk_workbook_path()
        print("[Elevation] risk workbook =", workbook_path)

        rows = self._read_sheet_rows(
            workbook_path=workbook_path,
            sheet_name="节点检验策略",
            header_row=2,
            data_start_row=3,
        )

        target_year = self._normalize_year_label_for_sheet(year_label)
        print("[Elevation] node target_year =", target_year)
        print("[Elevation] node sheet rows =", len(rows))

        matched_rows = 0
        for row in rows:
            joint_id = str(row.get("JoitID") or "").strip()
            if not joint_id:
                continue

            time_node = str(row.get("检验时间节点") or "").strip()
            if time_node != target_year:
                continue

            matched_rows += 1

            risk = self._risk_text_to_num(row.get("节点风险等级"))
            if risk:
                result[joint_id] = risk

        print("[Elevation] node matched_rows =", matched_rows)
        print("[Elevation] node risk_map size =", len(result))
        return result

    def _extract_member_risks_from_context(self, context: Dict, year_label: str) -> Dict[Tuple[str, str], str]:
        result: Dict[Tuple[str, str], str] = {}

        workbook_path = self._resolve_risk_workbook_path()
        print("[Elevation] risk workbook =", workbook_path)

        rows = self._read_sheet_rows(
            workbook_path=workbook_path,
            sheet_name="构件检验策略",
            header_row=1,
            data_start_row=2,
        )

        target_year = self._normalize_year_label_for_sheet(year_label)
        print("[Elevation] member target_year =", target_year)
        print("[Elevation] member sheet rows =", len(rows))

        matched_rows = 0
        for row in rows:
            a = str(row.get("Joint A") or "").strip()
            b = str(row.get("Joint B") or "").strip()
            if not a or not b:
                continue

            time_node = str(row.get("检验时间节点") or "").strip()
            if time_node != target_year:
                continue

            matched_rows += 1

            risk = self._risk_text_to_num(row.get("构件风险等级"))
            if risk:
                result[tuple(sorted((a, b)))] = risk

        print("[Elevation] member matched_rows =", matched_rows)
        print("[Elevation] member risk_map size =", len(result))
        return result

    # ---------------- ROW 面识别 ----------------
    def _cluster_axis_values(self, values: List[float], tol: float) -> List[float]:
        if not values:
            return []
        vals = sorted(values)
        groups = [[vals[0]]]
        for v in vals[1:]:
            if abs(v - groups[-1][-1]) <= tol:
                groups[-1].append(v)
            else:
                groups.append([v])
        return [sum(g) / len(g) for g in groups]

    def _get_axis_clusters(self, node_map: Optional[Dict[str, Tuple[float, float, float]]] = None):
        src = node_map if node_map is not None else self.nodes

        xs = [coord[0] for coord in src.values()]
        ys = [coord[1] for coord in src.values()]
        if not xs or not ys:
            return [], []

        x_span = max(xs) - min(xs)
        y_span = max(ys) - min(ys)

        x_tol = max(0.8, x_span * 0.03)
        y_tol = max(0.8, y_span * 0.03)

        x_clusters = self._cluster_axis_values(xs, x_tol)
        y_clusters = self._cluster_axis_values(ys, y_tol)

        return x_clusters, y_clusters

    def _nodes_below_workpoint(self) -> Dict[str, Tuple[float, float, float]]:
        return {
            nid: coord
            for nid, coord in self.nodes.items()
            if float(coord[2]) <= self._workpoint_z + 1e-6
        }

    def _safe_float(self, value: object, default: float = 9.1) -> float:
        try:
            return float(str(value).strip())
        except Exception:
            return default

    def _extract_workpoint_from_context(self, context: Optional[Dict]) -> float:
        direct_keys = [
            "workpoint", "target_z", "targetZ", "work_point",
            "Workpoint", "工作平面高程", "工作平面高程Workpoint",
        ]

        if isinstance(context, dict):
            for key in direct_keys:
                if key in context and context.get(key) not in ("", None):
                    return self._safe_float(context.get(key), 9.1)

            for value in context.values():
                if isinstance(value, dict):
                    for key in direct_keys:
                        if key in value and value.get(key) not in ("", None):
                            return self._safe_float(value.get(key), 9.1)

        return 9.1

    def _extract_level_threshold_from_context(self, context: Optional[Dict]) -> int:
        direct_keys = [
            "level_threshold",
            "node_limit",
            "node_count_limit",
            "水平层高程节点数量限制",
        ]

        if isinstance(context, dict):
            for key in direct_keys:
                if key in context and context.get(key) not in ("", None):
                    try:
                        return int(float(str(context.get(key)).strip()))
                    except Exception:
                        pass

            for value in context.values():
                if isinstance(value, dict):
                    for key in direct_keys:
                        if key in value and value.get(key) not in ("", None):
                            try:
                                return int(float(str(value.get(key)).strip()))
                            except Exception:
                                pass

        return 40

    def _row_index_to_letters(self, idx: int) -> str:
        # 0 -> A, 1 -> B, ..., 25 -> Z, 26 -> AA
        out = ""
        n = idx
        while True:
            out = chr(ord("A") + (n % 26)) + out
            n = n // 26 - 1
            if n < 0:
                break
        return out

    def _row_letters_to_index(self, text: str) -> int:
        s = (text or "").strip().upper()
        if not s:
            return 0

        value = 0
        for ch in s:
            if not ("A" <= ch <= "Z"):
                return 0
            value = value * 26 + (ord(ch) - ord("A") + 1)
        return max(0, value - 1)

    def _get_horizontal_z_clusters(self) -> List[float]:
        zs = [float(coord[2]) for coord in self.nodes.values() if float(coord[2]) <= self._workpoint_z + 1e-6]
        if not zs:
            return []

        z_span = max(zs) - min(zs)
        z_tol = max(0.5, z_span * 0.01)

        raw_clusters = self._cluster_axis_values(zs, z_tol)
        if not raw_clusters:
            return []

        selected = []
        for c in raw_clusters:
            cnt = sum(1 for z in zs if abs(z - c) <= z_tol)
            if cnt >= self._level_threshold:
                selected.append(c)

        selected.sort(reverse=True)
        return selected

    def _build_dynamic_row_specs(self, node_map: Optional[Dict[str, Tuple[float, float, float]]] = None):
        z_clusters = self._get_horizontal_z_clusters()

        specs = [
            {"name": "XZ 前", "plane_axis": None, "plane_value": None, "proj_mode": "XZ_FRONT"},
            {"name": "XZ 后", "plane_axis": None, "plane_value": None, "proj_mode": "XZ_BACK"},
            {"name": "YZ 左", "plane_axis": None, "plane_value": None, "proj_mode": "YZ_LEFT"},
            {"name": "YZ 右", "plane_axis": None, "plane_value": None, "proj_mode": "YZ_RIGHT"},
        ]

        for zv in z_clusters:
            z_label = f"{zv:.3f}".rstrip("0").rstrip(".")
            specs.append({
                "name": f"XY {z_label}",
                "plane_axis": "Z",
                "plane_value": zv,
                "proj_mode": "XY",
            })

        return specs

    def _select_face_clusters(self, clusters: List[float], side: str) -> List[float]:
        vals = sorted(float(v) for v in clusters)
        if not vals:
            return []

        if len(vals) <= 2:
            return vals

        if side in ("front", "left"):
            return vals[:2]

        if side in ("back", "right"):
            return vals[-2:]

        return vals

    def _labels_from_segments_by_projection(self, segments, proj_mode: str):
        if not segments:
            return []

        xs = []
        for p1, p2 in segments:
            xs.extend([p1[0], p2[0]])

        if not xs:
            return []

        span = max(xs) - min(xs) if len(xs) >= 2 else 0.0
        tol = max(0.8, span * 0.03)
        clusters = self._cluster_axis_values(xs, tol)

        if proj_mode in ("XZ_FRONT", "XZ_BACK"):
            return [(v, str(i + 1)) for i, v in enumerate(sorted(clusters))]
        else:
            return [(v, self._row_index_to_letters(i)) for i, v in enumerate(sorted(clusters))]

    def _collect_side_face_segments(self, proj_mode: str):
        leg_x_clusters, leg_y_clusters = self._get_leg_plane_clusters()

        if proj_mode == "XZ_FRONT":
            plane_axis = "Y"
            face_clusters = self._select_face_clusters(leg_y_clusters, "front")
        elif proj_mode == "XZ_BACK":
            plane_axis = "Y"
            face_clusters = self._select_face_clusters(leg_y_clusters, "back")
        elif proj_mode == "YZ_LEFT":
            plane_axis = "X"
            face_clusters = self._select_face_clusters(leg_x_clusters, "left")
        elif proj_mode == "YZ_RIGHT":
            plane_axis = "X"
            face_clusters = self._select_face_clusters(leg_x_clusters, "right")
        else:
            return [], []

        if not face_clusters:
            return [], []

        kept_segments = []
        seen = set()

        all_clusters = leg_y_clusters if plane_axis == "Y" else leg_x_clusters

        for na, nb, _gid in self.members:
            if na not in self.nodes or nb not in self.nodes:
                continue

            clipped = self._clip_member_3d_to_workpoint(self.nodes[na], self.nodes[nb])
            if clipped is None:
                continue

            p1, p2 = clipped

            if plane_axis == "Y":
                c1 = self._nearest_cluster(float(p1[1]), all_clusters)
                c2 = self._nearest_cluster(float(p2[1]), all_clusters)

                if c1 not in face_clusters or c2 not in face_clusters:
                    continue

                seg2d_p1 = (float(p1[0]), float(p1[2]))
                seg2d_p2 = (float(p2[0]), float(p2[2]))
            else:
                c1 = self._nearest_cluster(float(p1[0]), all_clusters)
                c2 = self._nearest_cluster(float(p2[0]), all_clusters)

                if c1 not in face_clusters or c2 not in face_clusters:
                    continue

                seg2d_p1 = (float(p1[1]), float(p1[2]))
                seg2d_p2 = (float(p2[1]), float(p2[2]))

            a = (round(seg2d_p1[0], 3), round(seg2d_p1[1], 3))
            b = (round(seg2d_p2[0], 3), round(seg2d_p2[1], 3))
            key = tuple(sorted((a, b)))
            if key in seen:
                continue
            seen.add(key)

            kept_segments.append((seg2d_p1, seg2d_p2))

        top_labels = self._labels_from_segments_by_projection(kept_segments, proj_mode)
        return kept_segments, top_labels

    def _labels_from_face_segments(self, segments, proj_mode: str):
        if not segments:
            return []

        vals = []
        for p1, p2 in segments:
            vals.extend([p1[0], p2[0]])

        if not vals:
            return []

        span = max(vals) - min(vals) if len(vals) >= 2 else 0.0
        tol = max(0.8, span * 0.03)
        used_clusters = self._cluster_axis_values(vals, tol)

        if proj_mode in ("XZ_FRONT", "XZ_BACK"):
            return [(v, str(i + 1)) for i, v in enumerate(sorted(used_clusters))]
        else:
            return [(v, self._row_index_to_letters(i)) for i, v in enumerate(sorted(used_clusters))]

    def _clip_member_3d_to_workpoint(
            self,
            p1: Tuple[float, float, float],
            p2: Tuple[float, float, float],
    ) -> Optional[Tuple[Tuple[float, float, float], Tuple[float, float, float]]]:
        wp = float(self._workpoint_z)

        x1, y1, z1 = p1
        x2, y2, z2 = p2

        # 整根都在 workpoint 上方：不画
        if z1 > wp and z2 > wp:
            return None

        # 整根都在 workpoint 以下：直接保留
        if z1 <= wp and z2 <= wp:
            return p1, p2

        # 穿过 workpoint：裁到 workpoint 平面
        dz = z2 - z1
        if abs(dz) < 1e-12:
            return None

        t = (wp - z1) / dz
        t = max(0.0, min(1.0, t))
        cut = (
            x1 + t * (x2 - x1),
            y1 + t * (y2 - y1),
            wp,
        )

        if z1 > wp:
            return cut, p2
        return p1, cut

    def _segment_sample_bins(
            self,
            p1: Tuple[float, float],
            p2: Tuple[float, float],
            grid: float = 1.5,
            samples: int = 10,
    ) -> set:
        bins = set()
        for i in range(samples + 1):
            t = i / samples
            x = p1[0] + t * (p2[0] - p1[0])
            y = p1[1] + t * (p2[1] - p1[1])
            bins.add((round(x / grid), round(y / grid)))
        return bins

    def _top_labels_for_directional_view(self, proj_mode: str):
        leg_x_clusters, leg_y_clusters = self._get_leg_plane_clusters()

        if proj_mode in ("XZ_FRONT", "XZ_BACK"):
            return [(v, str(i + 1)) for i, v in enumerate(sorted(leg_x_clusters))]

        if proj_mode in ("YZ_LEFT", "YZ_RIGHT"):
            return [(v, self._row_index_to_letters(i)) for i, v in enumerate(sorted(leg_y_clusters))]

        return []

    def _collect_directional_view_segments(self, proj_mode: str):
        candidates = []

        for na, nb, _gid in self.members:
            if na not in self.nodes or nb not in self.nodes:
                continue

            raw1 = self.nodes[na]
            raw2 = self.nodes[nb]

            clipped_3d = self._clip_member_3d_to_workpoint(raw1, raw2)
            if clipped_3d is None:
                continue

            p1, p2 = clipped_3d

            if proj_mode in ("XZ_FRONT", "XZ_BACK"):
                seg2d_p1 = (p1[0], p1[2])
                seg2d_p2 = (p2[0], p2[2])
                depth = (p1[1] + p2[1]) * 0.5
                prefer_smaller = (proj_mode == "XZ_FRONT")
            else:
                seg2d_p1 = (p1[1], p1[2])
                seg2d_p2 = (p2[1], p2[2])
                depth = (p1[0] + p2[0]) * 0.5
                prefer_smaller = (proj_mode == "YZ_LEFT")

            bins = self._segment_sample_bins(seg2d_p1, seg2d_p2, grid=1.5, samples=10)

            candidates.append({
                "p1": seg2d_p1,
                "p2": seg2d_p2,
                "depth": depth,
                "bins": bins,
            })

        if not candidates:
            return [], self._top_labels_for_directional_view(proj_mode)

        winners: Dict[Tuple[int, int], int] = {}

        for idx, cand in enumerate(candidates):
            for b in cand["bins"]:
                prev_idx = winners.get(b)
                if prev_idx is None:
                    winners[b] = idx
                    continue

                prev = candidates[prev_idx]
                if prefer_smaller:
                    if cand["depth"] < prev["depth"] - 1e-6:
                        winners[b] = idx
                else:
                    if cand["depth"] > prev["depth"] + 1e-6:
                        winners[b] = idx

        keep_idx = sorted(set(winners.values()))
        kept_segments = [(candidates[i]["p1"], candidates[i]["p2"]) for i in keep_idx]
        top_labels = self._top_labels_for_directional_view(proj_mode)
        return kept_segments, top_labels

    def available_row_names(self) -> List[str]:
        if not self.nodes:
            return ["XZ 前"]
        specs = self._build_dynamic_row_specs()
        return [item["name"] for item in specs] if specs else ["XZ 前"]

    def _clip_projected_member_to_workpoint(
            self,
            p1: Tuple[float, float],
            p2: Tuple[float, float],
    ) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
        wp = float(self._workpoint_z)

        x1, z1 = p1
        x2, z2 = p2

        # 整根都在 workpoint 上方：不画
        if z1 > wp and z2 > wp:
            return None

        # 整根都在 workpoint 以下：直接保留
        if z1 <= wp and z2 <= wp:
            return p1, p2

        # 穿过 workpoint：裁到 workpoint 平面
        dz = z2 - z1
        if abs(dz) < 1e-12:
            return None

        t = (wp - z1) / dz
        t = max(0.0, min(1.0, t))
        xc = x1 + t * (x2 - x1)
        cut_point = (xc, wp)

        if z1 > wp:
            return cut_point, p2
        return p1, cut_point

    def _resolve_row_definition(self):
        specs = self._build_dynamic_row_specs()
        if not specs:
            return {
                "name": "XZ 前",
                "plane_axis": "Y",
                "plane_value": 0.0,
                "proj_mode": "XZ",
            }

        target = (self._row_name or "").strip()
        for spec in specs:
            if spec["name"] == target:
                return spec

        return specs[0]

    def _nearest_cluster(self, value: float, clusters: List[float]) -> float:
        if not clusters:
            return value
        return min(clusters, key=lambda c: abs(c - value))

    def _filter_row_members(self):
        spec = self._resolve_row_definition()
        plane_axis = spec["plane_axis"]
        plane_value = spec["plane_value"]
        proj_mode = spec["proj_mode"]

        # XZ/YZ 不再在这里按平面筛
        if proj_mode in ("XZ_FRONT", "XZ_BACK", "YZ_LEFT", "YZ_RIGHT"):
            return {}, [], proj_mode, self._top_labels_for_directional_view(proj_mode)

        # 这里只处理 XY 截面
        z_clusters = self._get_horizontal_z_clusters()
        axis_clusters = z_clusters

        if not axis_clusters:
            return {}, [], proj_mode, []

        target_cluster = self._nearest_cluster(plane_value, axis_clusters)

        selected_nodes = set()
        selected_members = []

        for na, nb, gid in self.members:
            if na not in self.nodes or nb not in self.nodes:
                continue

            xa, ya, za = self.nodes[na]
            xb, yb, zb = self.nodes[nb]

            ca = self._nearest_cluster(za, axis_clusters)
            cb = self._nearest_cluster(zb, axis_clusters)

            if abs(ca - target_cluster) < 1e-6 and abs(cb - target_cluster) < 1e-6:
                if target_cluster > self._workpoint_z + 1e-6:
                    continue
                selected_members.append((na, nb, gid))
                selected_nodes.add(na)
                selected_nodes.add(nb)

        node_map = {nid: self.nodes[nid] for nid in selected_nodes}
        return node_map, selected_members, proj_mode, []

    # ---------------- ROW立面绘制：当前只画轮廓 ----------------
    def _render_row_elevation(self):
        self._scene.clear()

        spec = self._resolve_row_definition()
        proj_mode = spec["proj_mode"]

        # 前后左右：按“两列外侧主腿面”取构件
        if proj_mode in ("XZ_FRONT", "XZ_BACK", "YZ_LEFT", "YZ_RIGHT"):
            clipped_segments, top_labels = self._collect_side_face_segments(proj_mode)

            print("[Elevation] row =", self._row_name)
            print("[Elevation] proj_mode =", proj_mode)
            print("[Elevation] side_face_segment_total =", len(clipped_segments))
            print("[Elevation] workpoint =", self._workpoint_z)

            if not clipped_segments:
                self._draw_message(f"{self._row_name} 没有可绘制轮廓")
                return

        else:
            row_nodes, row_members, proj_mode, top_labels = self._filter_row_members()

            print("[Elevation] row =", self._row_name)
            print("[Elevation] row_node_total =", len(row_nodes))
            print("[Elevation] row_member_total =", len(row_members))
            print("[Elevation] workpoint =", self._workpoint_z)

            if not row_nodes or not row_members:
                self._draw_message(f"{self._row_name} 未识别到有效截面")
                return

            projected_nodes = {nid: (coord[0], coord[1]) for nid, coord in row_nodes.items()}

            clipped_segments: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
            for na, nb, _gid in row_members:
                if na not in projected_nodes or nb not in projected_nodes:
                    continue
                clipped_segments.append((projected_nodes[na], projected_nodes[nb]))

            if not clipped_segments:
                self._draw_message(f"{self._row_name} 没有可绘制轮廓")
                return

        xs = []
        ys = []
        for p1, p2 in clipped_segments:
            xs.extend([p1[0], p2[0]])
            ys.extend([p1[1], p2[1]])

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        view_w = 760.0
        view_h = 760.0
        margin_left = 40.0
        margin_right = 24.0
        margin_top = 32.0
        margin_bottom = 32.0
        member_color = self.COLOR_MEMBER_ROW
        member_width = 1.30

        dx = max(max_x - min_x, 1e-6)
        dy = max(max_y - min_y, 1e-6)

        avail_w = view_w - margin_left - margin_right
        avail_h = view_h - margin_top - margin_bottom

        scale = min(avail_w / dx, avail_h / dy)
        used_w = dx * scale
        used_h = dy * scale

        x_origin = (view_w - used_w) / 2.0
        y_base = view_h - margin_bottom - (avail_h - used_h) / 2.0

        def map_pt(xv: float, yv: float) -> Tuple[float, float]:
            px = x_origin + (xv - min_x) * scale
            py = y_base - (yv - min_y) * scale
            return px, py

        # XZ / YZ：画高程虚线
        if proj_mode in ("XZ_FRONT", "XZ_BACK", "YZ_LEFT", "YZ_RIGHT"):
            y_levels = sorted(set(round(v, 1) for v in ys))
            sampled = []
            for yv in y_levels:
                if not sampled or abs(yv - sampled[-1]) > 3.0:
                    sampled.append(yv)

            for yv in sampled:
                x1, py = map_pt(min_x, yv)
                x2, _ = map_pt(max_x, yv)

                line = RiskMemberItem(x1, py, x2, py)
                line.setPen(QPen(self.COLOR_GRID, 0.8, Qt.DashLine))
                self._scene.addItem(line)

                txt = QGraphicsSimpleTextItem(f"{yv:.0f}")
                txt.setBrush(QBrush(self.COLOR_TEXT))
                txt.setFont(QFont("Arial", 8))
                txt.setPos(max(8, x_origin - 34), py - 8)
                self._scene.addItem(txt)

        # 顶部轴线标签
        for axis_value, axis_name in top_labels:
            px, _ = map_pt(axis_value, max_y)

            tick = RiskMemberItem(px, margin_top - 8, px, margin_top - 1)
            tick.setPen(QPen(self.COLOR_AXIS, 1.0))
            self._scene.addItem(tick)

            txt = QGraphicsSimpleTextItem(str(axis_name))
            txt.setBrush(QBrush(self.COLOR_AXIS))
            txt.setFont(QFont("Arial", 9, QFont.Bold))
            txt.setPos(px - 8, 8)
            self._scene.addItem(txt)

        # 只画当前方向的轮廓
        for p1, p2 in clipped_segments:
            x1, y1 = map_pt(p1[0], p1[1])
            x2, y2 = map_pt(p2[0], p2[1])

            item = RiskMemberItem(x1, y1, x2, y2)
            item.setPen(QPen(member_color, member_width))
            self._scene.addItem(item)

        self._scene.setSceneRect(QRectF(0, 0, view_w, view_h))
        self._show_hover_info()

    def _draw_message(self, text: str):
        self._scene.clear()
        item = QGraphicsSimpleTextItem(text)
        item.setBrush(QBrush(QColor(60, 60, 60)))
        item.setFont(QFont("Arial", 10))
        item.setPos(20, 20)
        self._scene.addItem(item)

        rect = item.boundingRect().adjusted(-20, -20, 40, 40)
        self._scene.setSceneRect(rect)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._fit_done:
            QTimer.singleShot(0, self.reset_view)

    def wheelEvent(self, event):
        delta = 1 if event.angleDelta().y() > 0 else -1
        new_steps = self._zoom_steps + delta

        if new_steps < -8 or new_steps > 20:
            event.accept()
            return

        self._zoom_steps = new_steps

        factor = 1.035 if delta > 0 else 1 / 1.035
        self.scale(factor, factor)
        event.accept()

    def mouseDoubleClickEvent(self, event):
        self.reset_view()
        event.accept()
