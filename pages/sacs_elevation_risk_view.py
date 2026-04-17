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

from file_db_adapter import (
    FileBackendError,
    is_file_db_configured,
    list_storage_paths,
    list_storage_paths_by_prefix,
)
from app_paths import external_path, first_existing_path

import openpyxl
import csv
import json

try:
    import pandas as pd
except Exception:
    pd = None

class RiskNodeItem(QGraphicsEllipseItem):
    def __init__(self, rect: QRectF, tooltip: str, hover_callback=None, *args, **kwargs):
        super().__init__(rect, *args, **kwargs)
        self.setAcceptHoverEvents(True)
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
    def __init__(self, x1, y1, x2, y2, tooltip: str, hover_callback=None, *args, **kwargs):
        super().__init__(x1, y1, x2, y2, *args, **kwargs)
        self.setAcceptHoverEvents(True)
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
    COLOR_MEMBER_DEFAULT = QColor(205, 210, 218)  # 非风险构件：浅灰
    COLOR_NODE_DEFAULT = QColor(180, 185, 195)
    COLOR_GRID = QColor(190, 190, 190)

    RISK_COLORS = {
        "1": QColor("#ff3b30"),   # 一：红
        "2": QColor("#f5c400"),   # 二：黄
        "3": QColor("#ead94c"),   # 三：浅黄
        "4": QColor("#2f84d6"),   # 四：蓝
        "5": QColor("#6b4a3b"),   # 五：棕
    }

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

        self._facility_code = ""
        self._model_path = ""
        self._row_name = "ROW A"
        self._info_label = None

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

    def _show_hover_info(self, text: str):
        if self._info_label is None:
            return

        if not text:
            self._info_label.setText(f"当前显示：{self._row_name} 立面风险图；滚轮缩放，按住左键可拖动。")
            return

        compact = str(text).replace("\n", "  |  ")
        self._info_label.setText(compact)

    def reset_view(self):
        rect = self._scene.itemsBoundingRect()
        if not rect.isValid():
            return

        # 上方留少一点，下方留多一点，避免模型底部被截掉
        rect = rect.adjusted(-70, -90, 70, 140)
        self._scene.setSceneRect(rect)

        self.resetTransform()
        self.fitInView(rect, Qt.KeepAspectRatio)

        # 初始只轻微放大，不要放太大
        self.scale(1.04, 1.04)

        self._initial_scene_rect = QRectF(rect)
        self._fit_done = True
        self._zoom_steps = 1

        # 关键：把中心点稍微往下压一点，这样模型在屏幕里会上移
        cx = rect.center().x()
        cy = rect.center().y() + rect.height() * 0.06
        self.centerOn(QPointF(cx, cy))

        self.reset_pan_state()

    # ---------------- 外部入口 ----------------
    def load_for_facility(
        self,
        facility_code: str,
        context: Dict,
        year_label: str,
        row_name: str = "ROW A",
    ) -> None:
        self._facility_code = (facility_code or "").strip()
        self._row_name = (row_name or "ROW A").strip()

        self._model_path = self._resolve_model_path(self._facility_code)

        print("[Elevation] facility_code =", self._facility_code)
        print("[Elevation] row_name =", self._row_name)
        print("[Elevation] resolved model_path =", self._model_path)

        if not self._model_path or not os.path.exists(self._model_path):
            self._draw_message("未找到结构模型文件")
            return

        self.nodes, self.members, _groups = self.parse_sacs_full_robust(self._model_path)
        if not self.nodes or not self.members:
            self._draw_message("模型文件未解析到有效 JOINT/MEMBER")
            return

        self.node_risk_map = self._extract_node_risks_from_context(context, year_label)
        self.member_risk_map = self._extract_member_risks_from_context(context, year_label)

        print("[Elevation] year =", year_label)
        print("[Elevation] node_risk_count =", len(self.node_risk_map))
        print("[Elevation] member_risk_count =", len(self.member_risk_map))

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
        # pages 目录的上一级就是项目根目录 D:\shiyou
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _resolve_risk_workbook_path(self) -> str:
        """
        先从项目根目录读取你放进去的 xlsm：
        D:\shiyou\检验策略- wc19-1d-10.30.xlsm
        """
        root = self._project_root()
        candidates = [
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

    # ---------------- 风险提取 ----------------
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

    def _get_axis_clusters(self):
        xs = [coord[0] for coord in self.nodes.values()]
        ys = [coord[1] for coord in self.nodes.values()]
        if not xs or not ys:
            return [], []

        x_span = max(xs) - min(xs)
        y_span = max(ys) - min(ys)

        x_tol = max(0.8, x_span * 0.03)
        y_tol = max(0.8, y_span * 0.03)

        x_clusters = self._cluster_axis_values(xs, x_tol)
        y_clusters = self._cluster_axis_values(ys, y_tol)

        return x_clusters, y_clusters

    def _resolve_row_definition(self):
        x_clusters, y_clusters = self._get_axis_clusters()
        row = self._row_name.upper().strip()

        if row in ("ROW A", "A"):
            plane_axis = "Y"
            plane_value = min(y_clusters) if y_clusters else 0.0
            proj_axis = "X"
            top_labels = [(v, str(i + 1)) for i, v in enumerate(sorted(x_clusters))]
        elif row in ("ROW B", "B"):
            plane_axis = "Y"
            plane_value = max(y_clusters) if y_clusters else 0.0
            proj_axis = "X"
            top_labels = [(v, str(i + 1)) for i, v in enumerate(sorted(x_clusters))]
        elif row.startswith("ROW "):
            suffix = row[4:].strip()
            if suffix.isdigit():
                idx = int(suffix) - 1
                xs = sorted(x_clusters)
                if 0 <= idx < len(xs):
                    plane_axis = "X"
                    plane_value = xs[idx]
                else:
                    plane_axis = "X"
                    plane_value = xs[0] if xs else 0.0
                proj_axis = "Y"

                y_sorted = sorted(y_clusters)
                names = ["A", "B", "C", "D", "E", "F"]
                top_labels = [(v, names[i] if i < len(names) else f"C{i+1}") for i, v in enumerate(y_sorted)]
            else:
                plane_axis = "Y"
                plane_value = min(y_clusters) if y_clusters else 0.0
                proj_axis = "X"
                top_labels = [(v, str(i + 1)) for i, v in enumerate(sorted(x_clusters))]
        else:
            plane_axis = "Y"
            plane_value = min(y_clusters) if y_clusters else 0.0
            proj_axis = "X"
            top_labels = [(v, str(i + 1)) for i, v in enumerate(sorted(x_clusters))]

        return plane_axis, plane_value, proj_axis, top_labels, x_clusters, y_clusters

    def _nearest_cluster(self, value: float, clusters: List[float]) -> float:
        if not clusters:
            return value
        return min(clusters, key=lambda c: abs(c - value))

    def _filter_row_members(self):
        
        if self._row_name == "全部":
            x_clusters, y_clusters = self._get_axis_clusters()
            node_map = dict(self.nodes)
            selected_members = list(self.members)
            top_labels = [(v, str(i + 1)) for i, v in enumerate(sorted(x_clusters))]
            proj_axis = "X"
            return node_map, selected_members, proj_axis, top_labels

        plane_axis, plane_value, proj_axis, top_labels, x_clusters, y_clusters = self._resolve_row_definition()

        axis_clusters = y_clusters if plane_axis == "Y" else x_clusters
        if not axis_clusters:
            return {}, [], proj_axis, []

        target_cluster = self._nearest_cluster(plane_value, axis_clusters)

        selected_nodes = set()
        selected_members = []

        for na, nb, gid in self.members:
            if na not in self.nodes or nb not in self.nodes:
                continue

            xa, ya, za = self.nodes[na]
            xb, yb, zb = self.nodes[nb]

            va = ya if plane_axis == "Y" else xa
            vb = yb if plane_axis == "Y" else xb

            ca = self._nearest_cluster(va, axis_clusters)
            cb = self._nearest_cluster(vb, axis_clusters)

            if abs(ca - target_cluster) < 1e-6 and abs(cb - target_cluster) < 1e-6:
                selected_members.append((na, nb, gid))
                selected_nodes.add(na)
                selected_nodes.add(nb)

        node_map = {nid: self.nodes[nid] for nid in selected_nodes}

        if proj_axis == "X":
            used_vals = sorted({self._nearest_cluster(coord[0], x_clusters) for coord in node_map.values()})
            top_labels = [(v, str(i + 1)) for i, v in enumerate(used_vals)]
        else:
            used_vals = sorted({self._nearest_cluster(coord[1], y_clusters) for coord in node_map.values()})
            names = ["A", "B", "C", "D", "E", "F"]
            top_labels = [(v, names[i] if i < len(names) else f"C{i + 1}") for i, v in enumerate(used_vals)]

        return node_map, selected_members, proj_axis, top_labels

    # ---------------- ROW立面绘制 ----------------
    def _render_row_elevation(self):
        self._scene.clear()

        row_nodes, row_members, proj_axis, top_labels = self._filter_row_members()

        row_risk_nodes = [nid for nid in row_nodes if nid in self.node_risk_map]
        row_risk_members = [
            (na, nb) for na, nb, _gid in row_members
            if tuple(sorted((na, nb))) in self.member_risk_map
        ]

        print("[Elevation] row =", self._row_name)
        print("[Elevation] row_node_total =", len(row_nodes))
        print("[Elevation] row_member_total =", len(row_members))
        print("[Elevation] row_risk_node_count =", len(row_risk_nodes))
        print("[Elevation] row_risk_member_count =", len(row_risk_members))

        if not row_nodes or not row_members:
            self._draw_message(f"{self._row_name} 未识别到有效排架")
            return

        if proj_axis == "X":
            projected_nodes = {nid: (coord[0], coord[2]) for nid, coord in row_nodes.items()}
        else:
            projected_nodes = {nid: (coord[1], coord[2]) for nid, coord in row_nodes.items()}

        xs = [p[0] for p in projected_nodes.values()]
        zs = [p[1] for p in projected_nodes.values()]
        if not xs or not zs:
            self._draw_message("没有可绘制的立面数据")
            return

        min_x, max_x = min(xs), max(xs)
        min_z, max_z = min(zs), max(zs)

        if self._row_name == "全部":
            view_w = 1500.0
            view_h = 2000.0
            margin_left = 90.0
            margin_right = 50.0
            margin_top = 60.0
            margin_bottom = 110.0
            x_factor = self.HORIZONTAL_EXAGGERATION_ALL
        else:
            view_w = 1100.0
            view_h = 1550.0
            margin_left = 80.0
            margin_right = 40.0
            margin_top = 55.0
            margin_bottom = 95.0
            x_factor = self.HORIZONTAL_EXAGGERATION_ROW

        dx = max(max_x - min_x, 1e-6)
        dz = max(max_z - min_z, 1e-6)

        avail_w = view_w - margin_left - margin_right
        avail_h = view_h - margin_top - margin_bottom

        scale_z = avail_h / dz
        scale_x_raw = avail_w / dx
        scale_x = min(scale_x_raw, scale_z * x_factor)

        used_w = dx * scale_x
        used_h = dz * scale_z

        x_origin = (view_w - used_w) / 2.0
        y_base = view_h - margin_bottom - max(0.0, (avail_h - used_h) / 2.0)

        def map_pt(xv: float, zv: float) -> Tuple[float, float]:
            px = x_origin + (xv - min_x) * scale_x
            py = y_base - (zv - min_z) * scale_z
            return px, py

        # 高程虚线
        z_vals = sorted(set(round(v[1], 1) for v in projected_nodes.values()))
        z_levels = []
        for z in z_vals:
            if not z_levels or abs(z - z_levels[-1]) > 3.0:
                z_levels.append(z)

        for z in z_levels:
            x1, y1 = map_pt(min_x, z)
            x2, y2 = map_pt(max_x, z)
            line = RiskMemberItem(x1, y1, x2, y2, f"高程 {z:.2f}")
            line.setPen(QPen(self.COLOR_GRID, 0.8, Qt.DashLine))
            self._scene.addItem(line)

            txt = QGraphicsSimpleTextItem(f"{z:.0f}")
            txt.setBrush(QBrush(QColor(90, 90, 90)))
            txt.setFont(QFont("Arial", 8))
            txt.setPos(max(8, x_origin - 40), y1 - 8)
            self._scene.addItem(txt)

        # 顶部轴线
        for axis_value, axis_name in top_labels:
            px, py = map_pt(axis_value, max_z)
            mark = RiskMemberItem(px, margin_top - 10, px, margin_top - 2, str(axis_name))
            mark.setPen(QPen(QColor(80, 80, 80), 1.0))
            self._scene.addItem(mark)

            txt = QGraphicsSimpleTextItem(str(axis_name))
            txt.setBrush(QBrush(QColor(40, 40, 40)))
            txt.setFont(QFont("Arial", 9, QFont.Bold))
            txt.setPos(px - 6, 10)
            self._scene.addItem(txt)

        # 构件：风险高亮，非风险浅灰
        for na, nb, gid in row_members:
            if na not in projected_nodes or nb not in projected_nodes:
                continue

            x1, z1 = projected_nodes[na]
            x2, z2 = projected_nodes[nb]
            p1 = map_pt(x1, z1)
            p2 = map_pt(x2, z2)

            risk = self.member_risk_map.get(tuple(sorted((na, nb))), "")

            if risk:
                color = self.RISK_COLORS.get(risk, self.COLOR_MEMBER_DEFAULT)
                pen = QPen(color, 2.2)
            else:
                color = self.COLOR_MEMBER_DEFAULT
                pen = QPen(color, 0.8)

            tooltip = f"{self._row_name}\n构件: {na} - {nb}\n风险等级: {risk or '未标注'}"
            item = RiskMemberItem(
                p1[0], p1[1], p2[0], p2[1],
                tooltip,
                hover_callback=self._show_hover_info,
            )
            item.setPen(pen)
            self._scene.addItem(item)

            if risk and self.SHOW_MEMBER_TEXT:
                mx = (p1[0] + p2[0]) * 0.5
                my = (p1[1] + p2[1]) * 0.5
                txt = QGraphicsSimpleTextItem(str(risk))
                txt.setBrush(QBrush(color))
                txt.setFont(QFont("Arial", 8, QFont.Bold))
                txt.setPos(mx + 2, my - 12)
                txt.setZValue(20)
                self._scene.addItem(txt)

        # 节点：只画风险节点
        for nid, (px_raw, pz_raw) in projected_nodes.items():
            px, py = map_pt(px_raw, pz_raw)
            risk = self.node_risk_map.get(nid, "")

            if not risk and not self.DRAW_NONRISK_NODES:
                continue

            color = self.RISK_COLORS.get(risk, self.COLOR_NODE_DEFAULT)
            r = 3.8 if risk else 1.4

            item = RiskNodeItem(
                QRectF(px - r, py - r, 2 * r, 2 * r),
                f"{self._row_name}\n节点: {nid}\n风险等级: {risk or '未标注'}\nX={row_nodes[nid][0]:.3f}, Y={row_nodes[nid][1]:.3f}, Z={row_nodes[nid][2]:.3f}",
                hover_callback=self._show_hover_info,
            )
            item.setPen(QPen(Qt.NoPen))
            item.setBrush(QBrush(color))
            item.setZValue(30)
            self._scene.addItem(item)

            if risk and self.SHOW_NODE_TEXT:
                txt = QGraphicsSimpleTextItem(str(risk))
                txt.setBrush(QBrush(color))
                txt.setFont(QFont("Arial", 8, QFont.Bold))
                txt.setPos(px + 5, py - 14)
                txt.setZValue(40)
                self._scene.addItem(txt)

        rect = self._scene.itemsBoundingRect()
        if rect.isValid():
            self._scene.setSceneRect(rect.adjusted(-40, -40, 40, 40))
        self._show_hover_info("")

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