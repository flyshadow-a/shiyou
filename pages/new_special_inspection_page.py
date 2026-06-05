# -*- coding: utf-8 -*-
# pages/new_special_inspection_page.py

import os
import shutil
import datetime
import re
import json
import time
from pathlib import Path
from typing import Any, List
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QWidget,
    QFileDialog, QMessageBox, QProgressDialog, QScrollArea,
    QApplication, QAbstractItemView, QSizePolicy, QDialog, QDialogButtonBox,
    QTreeWidget, QTreeWidgetItem, QSplitter, QMenu
)
from PyQt5.QtCore import QObject, QPoint, Qt, pyqtSignal, QThread, QTimer

from core.app_paths import external_path, external_root, first_existing_path
from core.base_page import BasePage
from services.file_db_adapter import (
    DEFAULT_DB_CONFIG,
    FileBackendError,
    hard_delete_storage_path,
    is_file_db_configured,
    list_files,
    list_files_by_prefix,
    resolve_storage_path,
    upload_file as upload_file_to_db,
)

from pages.model_files_page import ModelFilesDocsWidget
from pages.upgrade_special_inspection_result_page import UpgradeSpecialInspectionResultPage
from services.special_strategy_runtime import (
    finalize_special_strategy_calculation,
    load_base_config,
    load_default_params,
    prepare_special_strategy_calculation,
    resolve_current_model_inputs,
    run_special_strategy_calculation,
    special_strategy_inputs_dir,
)
from services.special_strategy_history_overlay_service import load_history_detection_overlay

from pages.special_strategy_rule_dialogs import (
    RULE_MODE_JOINT_CLASSIFICATION,
    RULE_MODE_JOINT_EXCLUSION,
    RULE_MODE_MEMBER_CLASSIFICATION,
    RULE_MODE_MEMBER_EXCLUSION,
    SpecialStrategyRuleDialog,
    normalize_rule_overrides,
)


# =========================
# FastAPI 客户端调用封装
# =========================
# 说明：
# 1. 默认启用远程 FastAPI 后端：环境变量 SHIYOU_USE_FASTAPI 未设置或不为 0/false/no/off 时启用。
# 2. 后端地址读取顺序：环境变量 SHIYOU_API_BASE_URL -> 项目根目录 client_config.json -> http://127.0.0.1:8000。
# 3. 如果需要临时恢复旧的本地计算方式，可在启动客户端前设置：set SHIYOU_USE_FASTAPI=0。
try:
    import requests
except Exception:  # pragma: no cover - 允许在未安装 requests 时退回本地模式
    requests = None


def _project_root_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _use_fastapi_backend() -> bool:
    flag = os.environ.get("SHIYOU_USE_FASTAPI", "1").strip().lower()
    return flag not in {"0", "false", "no", "off", "local"}


def _api_base_url() -> str:
    env_url = os.environ.get("SHIYOU_API_BASE_URL", "").strip()
    if env_url:
        return env_url.rstrip("/")

    cfg_path = _project_root_dir() / "client_config.json"
    if cfg_path.exists():
        try:
            payload = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
            value = str(payload.get("api_base_url") or "").strip()
            if value:
                return value.rstrip("/")
        except Exception:
            pass

    return "http://127.0.0.1:8000"


class _RemoteBackendError(RuntimeError):
    pass


class _RemoteStrategyApiClient:
    """新增特检策略页面使用的最小 FastAPI 客户端。"""

    def __init__(self, base_url: str | None = None, timeout: int = 30):
        if requests is None:
            raise _RemoteBackendError("未安装 requests，无法调用 FastAPI 后端。请执行：pip install requests")
        self.base_url = (base_url or _api_base_url()).rstrip("/")
        self.timeout = int(timeout)

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = requests.post(self._url(path), json=payload, timeout=self.timeout)
        except Exception as exc:
            raise _RemoteBackendError(f"无法连接 FastAPI 服务端：{self.base_url}\n{exc}") from exc
        if resp.status_code in (404, 405):
            raise FileNotFoundError(f"后端接口不存在：{path}")
        try:
            data = resp.json()
        except Exception:
            data = {"text": resp.text}
        if resp.status_code >= 400:
            raise _RemoteBackendError(f"后端接口调用失败：{path}\nHTTP {resp.status_code}\n{data}")
        return data if isinstance(data, dict) else {"data": data}

    def _get_json(self, path: str) -> dict[str, Any]:
        try:
            resp = requests.get(self._url(path), timeout=self.timeout)
        except Exception as exc:
            raise _RemoteBackendError(f"无法连接 FastAPI 服务端：{self.base_url}\n{exc}") from exc
        try:
            data = resp.json()
        except Exception:
            data = {"text": resp.text}
        if resp.status_code >= 400:
            raise _RemoteBackendError(f"后端接口调用失败：{path}\nHTTP {resp.status_code}\n{data}")
        return data if isinstance(data, dict) else {"data": data}

    def _wait_strategy_task(self, task_id: str, *, interval: float = 1.0) -> dict[str, Any]:
        while True:
            task = self._get_json(f"/api/strategy/tasks/{task_id}")
            status = str(task.get("status") or "").lower()
            if status in {"success", "failed", "error"}:
                if status != "success":
                    raise _RemoteBackendError(str(task.get("error") or task.get("message") or "服务端任务执行失败"))
                result = task.get("result")
                return result if isinstance(result, dict) else task
            time.sleep(max(0.2, float(interval)))

    def _submit_and_wait(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = self._post_json(path, payload)
        task_id = str(data.get("task_id") or "").strip()
        if task_id:
            return self._wait_strategy_task(task_id)
        result = data.get("result")
        return result if isinstance(result, dict) else data

    def _download_binary(self, path: str, local_output_path: str | Path, *, params: dict[str, Any] | None = None) -> str:
        output_path = Path(local_output_path).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = output_path.with_name(output_path.name + ".download.tmp")

        try:
            resp = requests.get(
                self._url(path),
                params=params or {},
                stream=True,
                timeout=max(self.timeout, 300),
            )
        except Exception as exc:
            raise _RemoteBackendError(f"下载服务端文件失败：{self.base_url}{path}\n{exc}") from exc

        try:
            if resp.status_code >= 400:
                try:
                    data = resp.json()
                except Exception:
                    data = {"text": resp.text}
                raise _RemoteBackendError(f"下载服务端文件失败：HTTP {resp.status_code}\n{data}")

            with open(temp_path, "wb") as fp:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        fp.write(chunk)

            temp_path.replace(output_path)
            return str(output_path)
        finally:
            try:
                resp.close()
            except Exception:
                pass

    def _client_cache_dir(self, facility_code: str, *parts: str) -> Path:
        root = _project_root_dir() / ".client_cache" / "model_files" / str(facility_code or "default_facility").strip()
        for part in parts:
            text = str(part or "").strip().replace("/", "_").replace("\\", "_")
            if text:
                root = root / text
        root.mkdir(parents=True, exist_ok=True)
        return root

    def download_latest_model_file(self, facility_code: str) -> str:
        cache_dir = self._client_cache_dir(facility_code)
        return os.path.normpath(self._download_binary(
            "/api/files/download/latest-model",
            cache_dir / "sacinp_from_server",
            params={"facility_code": str(facility_code or "").strip()},
        ))

    def download_latest_sea_file(self, facility_code: str) -> str:
        cache_dir = self._client_cache_dir(facility_code)
        return os.path.normpath(self._download_binary(
            "/api/files/download/latest-sea",
            cache_dir / "seainp_from_server",
            params={"facility_code": str(facility_code or "").strip()},
        ))

    def load_strategy_input_files(self, facility_code: str) -> dict[str, Any]:
        """从服务端读取特检策略当前默认输入文件清单。

        注意：这里返回的是服务端可访问的 D:/shiyou_file_storage 等路径，
        仅用于表格展示和提交给服务端计算；客户端预览仍使用 download_latest_model_file 下载到本地缓存。
        """
        try:
            resp = requests.get(
                self._url("/api/files/strategy-inputs"),
                params={"facility_code": str(facility_code or "").strip()},
                timeout=max(self.timeout, 120),
            )
        except Exception as exc:
            raise _RemoteBackendError(f"无法读取服务端特检策略输入文件清单：{self.base_url}\n{exc}") from exc
        try:
            data = resp.json()
        except Exception:
            data = {"text": resp.text}
        if resp.status_code >= 400:
            raise _RemoteBackendError(f"读取服务端特检策略输入文件清单失败：HTTP {resp.status_code}\n{data}")
        return data if isinstance(data, dict) else {"data": data}

    def prepare_strategy(
        self,
        *,
        facility_code: str,
        param_overrides: dict[str, Any],
        input_overrides: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        payload = {
            "facility_code": facility_code,
            "param_overrides": param_overrides or {},
            "input_overrides": input_overrides or {},
            "metadata": {},
        }
        try:
            result = self._submit_and_wait("/api/strategy/prepare", payload)
            return "prepare", result
        except FileNotFoundError:
            # 兼容第一版只实现 /api/strategy/run 的服务端：无法做后置规则弹窗时，直接完成整套计算。
            result = self._submit_and_wait("/api/strategy/run", payload)
            state = result.get("state") if isinstance(result, dict) else {}
            run_id = (
                result.get("run_id")
                or result.get("db_run_id")
                or (state.get("db_run_id") if isinstance(state, dict) else None)
            )
            if run_id:
                try:
                    result = self._get_json(f"/api/strategy/result/{facility_code}?run_id={int(run_id)}")
                except Exception:
                    pass
            return "run", result

    def finalize_strategy(
        self,
        *,
        facility_code: str,
        prepared_calculation: dict[str, Any],
        rule_overrides: dict[str, Any] | None,
    ) -> dict[str, Any]:
        prepare_token = str(
            prepared_calculation.get("prepare_token")
            or prepared_calculation.get("prepared_token")
            or prepared_calculation.get("token")
            or ""
        ).strip()
        payload = {
            "facility_code": facility_code,
            "prepare_token": prepare_token,
            "prepared_calculation": prepared_calculation,
            "rule_overrides": rule_overrides or {},
        }
        result = self._submit_and_wait("/api/strategy/finalize", payload)
        state = result.get("state") if isinstance(result, dict) else {}
        run_id = (
            result.get("run_id")
            or result.get("db_run_id")
            or (state.get("db_run_id") if isinstance(state, dict) else None)
        )
        if run_id:
            try:
                return self._get_json(f"/api/strategy/result/{facility_code}?run_id={int(run_id)}")
            except Exception:
                return result
        return result

    def check_manual_fill(
        self,
        *,
        facility_code: str,
        param_overrides: dict[str, Any],
        input_overrides: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._post_json(
            "/api/strategy/manual-fill/check",
            {
                "facility_code": facility_code,
                "param_overrides": param_overrides or {},
                "input_overrides": input_overrides or {},
                "metadata": metadata or {},
            },
        )

    def run_strategy(
        self,
        *,
        facility_code: str,
        param_overrides: dict[str, Any],
        input_overrides: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "facility_code": facility_code,
            "param_overrides": param_overrides or {},
            "input_overrides": input_overrides or {},
            "metadata": metadata or {},
        }
        result = self._submit_and_wait("/api/strategy/run", payload)
        state = result.get("state") if isinstance(result, dict) else {}
        run_id = (
            result.get("run_id")
            or result.get("db_run_id")
            or (state.get("db_run_id") if isinstance(state, dict) else None)
        )
        if run_id:
            try:
                return self._get_json(f"/api/strategy/result/{facility_code}?run_id={int(run_id)}")
            except Exception:
                return result
        return result


class _SystemFilePickerDialog(QDialog):
    def __init__(self, title: str, rows: List[dict[str, Any]], parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(980, 520)
        self._rows = rows
        self._selected_path = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        tip = QLabel("请选择系统文件库中的文件。双击行可直接确认。", self)
        layout.addWidget(tip)

        self.table = QTableWidget(len(rows), 6, self)
        self.table.setHorizontalHeaderLabels(["序号", "文件名", "当前路径", "逻辑路径", "修改时间", "备注"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                gridline-color: #d0d0d0;
            }
            QTableWidget::item {
                border-bottom: 1px solid #d0d0d0;
                border-right: 1px solid #d0d0d0;
                padding: 4px 8px;
            }
            QTableWidget::item:selected {
                background-color: #dbeafe;
                color: #111827;
            }
            QHeaderView::section {
                background-color: #f3f4f6;
                border: 0px;
                border-bottom: 1px solid #d0d0d0;
                border-right: 1px solid #d0d0d0;
                padding: 4px 8px;
            }
        """)

        for row_idx, row in enumerate(rows):
            storage_path = os.path.normpath(str(row.get("storage_path") or "").strip())
            original_name = str(row.get("original_name") or os.path.basename(storage_path)).strip() or os.path.basename(
                storage_path)
            display_path = str(row.get("display_path") or storage_path).strip()
            logical_path = str(row.get("logical_path") or "").replace("\\", "/").strip().strip("/")
            modified = row.get("source_modified_at") or row.get("uploaded_at") or row.get("updated_at")
            modified_text = modified.strftime("%Y-%m-%d %H:%M") if hasattr(modified, "strftime") else ""
            remark = str(row.get("remark") or "").strip()

            index_item = QTableWidgetItem(str(row_idx + 1))
            index_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 0, index_item)

            name_item = QTableWidgetItem(original_name)
            name_item.setData(Qt.UserRole, storage_path)
            self.table.setItem(row_idx, 1, name_item)
            path_item = QTableWidgetItem(display_path or storage_path)
            path_item.setToolTip(storage_path)
            self.table.setItem(row_idx, 2, path_item)
            self.table.setItem(row_idx, 3, QTableWidgetItem(logical_path))

            modified_item = QTableWidgetItem(modified_text)
            modified_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 4, modified_item)
            self.table.setItem(row_idx, 5, QTableWidgetItem(remark))

        self.table.itemDoubleClicked.connect(self._accept_current_selection)
        self.table.itemSelectionChanged.connect(self._sync_buttons)
        layout.addWidget(self.table, 1)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        self.button_box.accepted.connect(self._accept_current_selection)
        self.button_box.rejected.connect(self.reject)
        self.button_box.button(QDialogButtonBox.Ok).setText("确定")
        self.button_box.button(QDialogButtonBox.Cancel).setText("取消")
        layout.addWidget(self.button_box)

        if rows:
            self.table.selectRow(0)
        self._sync_buttons()

    def _current_storage_path(self) -> str:
        current_row = self.table.currentRow()
        if current_row < 0:
            return ""
        item = self.table.item(current_row, 1)
        if item is None:
            return ""
        return os.path.normpath(str(item.data(Qt.UserRole) or "").strip())

    def _sync_buttons(self) -> None:
        ok_button = self.button_box.button(QDialogButtonBox.Ok)
        if ok_button is not None:
            ok_button.setEnabled(bool(self._current_storage_path()))

    def _accept_current_selection(self) -> None:
        chosen = self._current_storage_path()
        if not chosen:
            QMessageBox.information(self, "系统导入", "请先选择一条文件记录。")
            return
        self._selected_path = chosen
        self.accept()

    @property
    def selected_path(self) -> str:
        return self._selected_path


class _SystemLibraryPickerDialog(QDialog):
    def __init__(self, title: str, tree_spec: list[dict[str, Any]], fetch_rows, *, group_mode: bool = False,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(1120, 620)
        self._fetch_rows = fetch_rows
        self._group_mode = bool(group_mode)
        self._current_rows: list[dict[str, Any]] = []
        self._selected_row: dict[str, Any] | None = None
        self._selected_rows: list[dict[str, Any]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        if self._group_mode:
            tip_text = "请先从左侧选择模型文件中的文件夹。右侧将展示该文件夹下参与计算的整组文件，点击”确定”后会整组导入。"
        else:
            tip_text = "请先从左侧选择模型文件中的文件夹，再在右侧选择具体文件。双击文件可直接确认。"
        tip = QLabel(tip_text, self)
        layout.addWidget(tip)

        splitter = QSplitter(Qt.Horizontal, self)
        layout.addWidget(splitter, 1)

        self.tree = QTreeWidget(splitter)
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumWidth(240)

        self.table = QTableWidget(0, 5, splitter)
        self.table.setHorizontalHeaderLabels(["文件名", "当前路径", "逻辑路径", "修改时间", "备注"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setHighlightSections(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                gridline-color: #d0d0d0;
            }
            QTableWidget::item {
                border-bottom: 1px solid #d0d0d0;
                border-right: 1px solid #d0d0d0;
                padding: 4px 8px;
            }
            QTableWidget::item:selected {
                background-color: #dbeafe;
                color: #111827;
            }
            QHeaderView::section {
                background-color: #f3f4f6;
                border: 0px;
                border-bottom: 1px solid #d0d0d0;
                border-right: 1px solid #d0d0d0;
                padding: 4px 8px;
            }
        """)

        for root_spec in tree_spec:
            root_item = QTreeWidgetItem([str(root_spec.get("label") or "")])
            root_item.setFlags(root_item.flags() & ~Qt.ItemIsSelectable)
            for child in root_spec.get("children") or []:
                child_item = QTreeWidgetItem([str(child.get("label") or "")])
                child_item.setData(0, Qt.UserRole, (child.get("path_key"), child.get("model_key")))
                root_item.addChild(child_item)
            self.tree.addTopLevelItem(root_item)
            root_item.setExpanded(True)

        self.tree.currentItemChanged.connect(self._on_tree_current_changed)
        self.table.itemDoubleClicked.connect(self._accept_current_selection)
        self.table.itemSelectionChanged.connect(self._sync_buttons)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        self.button_box.accepted.connect(self._accept_current_selection)
        self.button_box.rejected.connect(self.reject)
        self.button_box.button(QDialogButtonBox.Ok).setText("确定")
        self.button_box.button(QDialogButtonBox.Cancel).setText("取消")
        layout.addWidget(self.button_box)

        if self.tree.topLevelItemCount() > 0 and self.tree.topLevelItem(0).childCount() > 0:
            self.tree.setCurrentItem(self.tree.topLevelItem(0).child(0))
        self._sync_buttons()

    def _on_tree_current_changed(self, current: QTreeWidgetItem, _previous: QTreeWidgetItem) -> None:
        payload = current.data(0, Qt.UserRole) if current is not None else None
        if not payload:
            self._current_rows = []
            self.table.setRowCount(0)
            self._sync_buttons()
            return
        path_key, model_key = payload
        rows = list(self._fetch_rows(path_key, model_key) or [])
        self._current_rows = rows
        self.table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            storage_path = os.path.normpath(str(row.get("storage_path") or "").strip())
            original_name = str(row.get("original_name") or os.path.basename(storage_path)).strip() or os.path.basename(
                storage_path)
            current_path = str(row.get("display_path") or storage_path).strip()
            logical_path = str(row.get("logical_path") or "").replace("\\", "/").strip().strip("/")
            modified = row.get("source_modified_at") or row.get("uploaded_at") or row.get("updated_at")
            modified_text = modified.strftime("%Y-%m-%d %H:%M") if hasattr(modified, "strftime") else ""
            remark = str(row.get("remark") or "").strip()

            name_item = QTableWidgetItem(original_name)
            name_item.setData(Qt.UserRole, row_idx)
            name_item.setToolTip(storage_path)
            self.table.setItem(row_idx, 0, name_item)
            self.table.setItem(row_idx, 1, QTableWidgetItem(current_path))
            self.table.setItem(row_idx, 2, QTableWidgetItem(logical_path))

            modified_item = QTableWidgetItem(modified_text)
            modified_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 3, modified_item)
            self.table.setItem(row_idx, 4, QTableWidgetItem(remark))
            self.table.setRowHeight(row_idx, 36)

        if rows:
            self.table.selectRow(0)
        self._sync_buttons()

    def _current_row(self) -> dict[str, Any] | None:
        current_row = self.table.currentRow()
        if current_row < 0 or current_row >= len(self._current_rows):
            return None
        return self._current_rows[current_row]

    def _sync_buttons(self) -> None:
        ok_button = self.button_box.button(QDialogButtonBox.Ok)
        if ok_button is not None:
            if self._group_mode:
                ok_button.setEnabled(bool(self._current_rows))
            else:
                ok_button.setEnabled(self._current_row() is not None)

    def _accept_current_selection(self) -> None:
        if self._group_mode:
            if not self._current_rows:
                QMessageBox.information(self, "系统导入", "当前文件夹下没有可导入的文件。")
                return
            self._selected_rows = [dict(row) for row in self._current_rows]
            self._selected_row = dict(self._current_rows[0])
        else:
            row = self._current_row()
            if row is None:
                QMessageBox.information(self, "系统导入", "请先选择一条文件记录。")
                return
            self._selected_row = dict(row)
            self._selected_rows = [dict(row)]
        self.accept()

    @property
    def selected_row(self) -> dict[str, Any] | None:
        return self._selected_row

    @property
    def selected_rows(self) -> list[dict[str, Any]]:
        return list(self._selected_rows)



class ManualBraceClientDialog(QDialog):
    """客户端 ManualBrace 人工补全弹窗。"""

    def __init__(self, rows: list[dict[str, Any]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("疲劳输入检查")
        self.resize(720, 420)
        self._rows = list(rows or [])
        self._result_entries: list[dict[str, Any]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        tip = QLabel(
            "检测到疲劳分析模型文件中存在需要人工补充的 ManualBrace。\n"
            "请在客户端输入 ManualBrace。ManualBrace 为 4 个字符；留空表示跳过。"
        )
        tip.setWordWrap(True)
        layout.addWidget(tip)

        self.table = QTableWidget(len(self._rows), 6, self)
        self.table.setHorizontalHeaderLabels(["序号", "JointI", "JointJ", "Case", "ManualBrace", "原始信息"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)

        for row_idx, row in enumerate(self._rows):
            raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
            joint_i = str(row.get("joint_i") or raw.get("JointI") or raw.get("JSLCA") or raw.get("A") or "").strip()
            joint_j = str(row.get("joint_j") or raw.get("JointJ") or raw.get("JSLCB") or raw.get("B") or raw.get("Joint") or "").strip()
            case_text = str(row.get("case") or raw.get("Case") or raw.get("Source") or raw.get("File") or "疲劳分析模型文件").strip()
            default_value = str(row.get("manual_brace") or raw.get("ManualBrace") or "").strip()
            raw_text = "; ".join(f"{k}={v}" for k, v in raw.items() if not str(k).startswith("_"))

            values = [str(row_idx + 1), joint_i, joint_j, case_text, default_value, raw_text]
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter if col in {0, 1, 2, 4} else Qt.AlignLeft | Qt.AlignVCenter)
                if col != 4:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row_idx, col, item)
            self.table.setRowHeight(row_idx, 34)

        layout.addWidget(self.table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.button(QDialogButtonBox.Ok).setText("确定")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self):
        entries: list[dict[str, Any]] = []
        for row_idx, row in enumerate(self._rows):
            item = self.table.item(row_idx, 4)
            manual_brace = item.text().strip() if item is not None else ""
            if manual_brace and len(manual_brace) != 4:
                QMessageBox.warning(self, "输入错误", f"第 {row_idx + 1} 行 ManualBrace 必须为 4 个字符；留空表示跳过。")
                return
            current = dict(row)
            raw = dict(current.get("raw") or {})
            raw["ManualBrace"] = manual_brace
            raw["manual_brace"] = manual_brace
            current["raw"] = raw
            current["manual_brace"] = manual_brace
            current["ManualBrace"] = manual_brace
            entries.append(current)
        self._result_entries = entries
        self.accept()

    @property
    def result_entries(self) -> list[dict[str, Any]]:
        return list(self._result_entries)

class _NoWheelFileTable(QTableWidget):
    def wheelEvent(self, event):
        # 不在表格内部滚动，把滚轮交回外层滚动区域
        event.ignore()


class _SpecialStrategyCalculationWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(
        self,
        facility_code: str,
        *,
        stage: str = "run",
        param_overrides: dict[str, Any] | None = None,
        input_overrides: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        prepared_calculation: dict[str, Any] | None = None,
    ):
        super().__init__()
        self._facility_code = facility_code
        self._stage = stage
        self._param_overrides = dict(param_overrides or {})
        self._input_overrides = dict(input_overrides or {})
        self._metadata = dict(metadata or {})
        self._prepared_calculation = prepared_calculation

    def run(self) -> None:
        try:
            if _use_fastapi_backend():
                api = _RemoteStrategyApiClient()
                if self._stage == "prepare":
                    emit_stage, result = api.prepare_strategy(
                        facility_code=self._facility_code,
                        param_overrides=self._param_overrides,
                        input_overrides=self._input_overrides,
                    )
                    self.finished.emit({"stage": emit_stage, "payload": result})
                    return

                if self._stage == "finalize":
                    if self._prepared_calculation is None:
                        raise ValueError("missing prepared calculation for finalize stage")
                    result = api.finalize_strategy(
                        facility_code=self._facility_code,
                        prepared_calculation=self._prepared_calculation,
                        rule_overrides=self._param_overrides.get("rule_overrides"),
                    )
                    self.finished.emit({"stage": "finalize", "payload": result})
                    return

                result = api.run_strategy(
                    facility_code=self._facility_code,
                    param_overrides=self._param_overrides,
                    input_overrides=self._input_overrides,
                    metadata=self._metadata,
                )
                self.finished.emit({"stage": "run", "payload": result})
                return

            # 本地兼容模式：set SHIYOU_USE_FASTAPI=0 后启用。
            if self._stage == "prepare":
                result = prepare_special_strategy_calculation(
                    self._facility_code,
                    param_overrides=self._param_overrides,
                    input_overrides=self._input_overrides,
                )
            elif self._stage == "finalize":
                if self._prepared_calculation is None:
                    raise ValueError("missing prepared calculation for finalize stage")
                result = finalize_special_strategy_calculation(
                    self._prepared_calculation,
                    rule_overrides=self._param_overrides.get("rule_overrides"),
                )
            else:
                result = run_special_strategy_calculation(
                    self._facility_code,
                    param_overrides=self._param_overrides,
                    input_overrides=self._input_overrides,
                    metadata=self._metadata,
                )
            self.finished.emit({"stage": self._stage, "payload": result})
        except Exception as exc:
            self.failed.emit(str(exc))


def _sacinp_fixed_sub(line: str, start: int, length: int) -> str:
    return line[max(0, start - 1): max(0, start - 1) + length]


def _parse_sacinp_rule_preview_file(model_path: str) -> tuple[list[str], list[tuple[str, str]]]:
    joint_ids: list[str] = []
    member_pairs: list[tuple[str, str]] = []
    with open(model_path, "r", encoding="utf-8", errors="ignore") as file:
        for raw in file:
            line = raw.rstrip("\r\n")
            if line.startswith("MEMBER"):
                token8 = _sacinp_fixed_sub(line, 8, 8).strip()
                token7 = _sacinp_fixed_sub(line, 8, 7).strip().upper()
                if token8 == "" or token7 == "OFFSETS":
                    continue
                joint_a = _sacinp_fixed_sub(line, 8, 4).strip()
                joint_b = _sacinp_fixed_sub(line, 12, 4).strip()
                if joint_a and joint_b:
                    member_pairs.append((joint_a, joint_b))
                continue

            if line.startswith("JOINT"):
                token8 = _sacinp_fixed_sub(line, 7, 8).strip()
                token7 = _sacinp_fixed_sub(line, 8, 7).strip().upper()
                if token8 == "" or token7 == "OFFSETS":
                    continue
                joint_id = _sacinp_fixed_sub(line, 7, 4).strip()
                if joint_id:
                    joint_ids.append(joint_id)
                continue

            if any(token in line for token in ("CENTER", "SURFID", "WGTFP", "LOADCN")):
                break
    return joint_ids, member_pairs


class _RulePreviewWorker(QObject):
    finished = pyqtSignal(str, object, object)
    failed = pyqtSignal(str)

    def __init__(self, model_path: str):
        super().__init__()
        self._model_path = os.path.normpath(str(model_path or "").strip())

    def run(self) -> None:
        try:
            joint_ids, member_pairs = _parse_sacinp_rule_preview_file(self._model_path)
            self.finished.emit(self._model_path, joint_ids, member_pairs)
        except Exception as exc:
            self.failed.emit(f"{self._model_path}: {exc}")


class NewSpecialInspectionPage(BasePage):
    """
    新增检测策略打开的页面：
    - 左侧：上半（结构模型信息 + 设置倒塌分析结果文件）
           下半（用户设置：风险等级参数 + 按钮）
    - 整体支持滚轮滚动（ScrollArea）
    """

    CATEGORY_MODEL = "model"
    CATEGORY_COLLAPSE = "collapse"
    CATEGORY_FATIGUE = "fatigue"
    RISK_LEVEL_PLACEHOLDER = "▼"
    WORK_POINT_LABEL_COLUMN_WIDTH = 160
    FILE_TABLE_HEADERS = ["序号", "文件类别", "工况", "文件名", "文件格式", "修改时间", "备注"]
    RISK_LEVEL_OPTIONS = {
        "life_safety_level": {
            "S-1": "有人不撤离——有人员居住的平台，且在设计时未考虑在极端情况下人员的撤离，如风暴、地震等，或实际无法实施撤离的情况。",
            "S-2": "有人可撤离——有人员居住的平台，在极端情况下人员可以实施撤离的情况。",
            "S-3": "无人——无人员居住的平台。",
        },
        "failure_consequence_level": {
            "C-1": "高后果——发生失效时有可能发生油气泄露的平台。此外，它还包括失效时不具备关停油气生产的平台，以及具有储油/气功能或连接主要输油管道的平台。以及水深>=120米的平台（投资较大）。中心平台一般归入此类。",
            "C-2": "中后果——包含功能齐全的地下安全阀（SSSV），可在故障时关停油气生产的平台，以及作为中转和缓冲仅临时储油/气存储的平台。井口平台一般归入此类。",
            "C-3": "低后果——所有井口包含功能齐全的SSSV，在平台失效时，生产系统可以自行运转而不受影响。这些平台可以支持不依托平台的生产，平台仅包含低输量的内部管道，仅含有工艺库存。",
        },
        "global_level_tag": {
            "L-1": "",
            "L-2": "",
            "L-3": "",
        },
    }
    strategy_calculated = pyqtSignal(str, object)

    def __init__(self, facility_code: str, parent=None):
        self.facility_code = facility_code
        self._risk_updated = False
        self._latest_run_id: int | None = None
        self.upload_root = external_path("upload", "model_files")
        self.packaged_upload_root = first_existing_path("upload", "model_files")
        self._default_params = self._load_default_params()
        self._rule_overrides = normalize_rule_overrides((self._default_params or {}).get("rule_overrides"))

        # 页面仅展示"系统文件库"记录（当前用 upload/model_files 代替数据库）
        self.model_files: List[str] = []
        self.collapse_files: List[str] = []
        self.fatigue_result_files: List[str] = []
        self.fatigue_input_files: List[str] = []
        self._file_meta_by_path: dict[str, dict[str, Any]] = {}
        self._model_files_helper_widget: ModelFilesDocsWidget | None = None
        self.btn_update_risk: QPushButton | None = None
        self.btn_view_result: QPushButton | None = None
        self._risk_progress: QProgressDialog | None = None
        self._risk_progress_base_text = ""
        self._risk_progress_tick = 0
        self._risk_thread: QThread | None = None
        self._risk_worker: _SpecialStrategyCalculationWorker | None = None
        self._active_worker_stage = ""
        self._pending_prepared_calculation: dict[str, Any] | None = None
        self._auto_system_files_loaded = False
        self._auto_system_files_load_scheduled = False
        self._rule_preview_cache: dict[str, Any] | None = None
        self._rule_preview_thread: QThread | None = None
        self._rule_preview_worker: _RulePreviewWorker | None = None
        self._rule_preview_loading_path = ""
        self._remote_preview_model_path = ""
        self._remote_preview_sea_path = ""

        super().__init__("", parent)
        self._risk_progress_timer = QTimer(self)
        self._risk_progress_timer.setInterval(320)
        self._risk_progress_timer.timeout.connect(self._update_risk_progress_text)
        self._build_ui()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._apply_initial_splitter_sizes)
        QTimer.singleShot(0, self._adjust_files_table_widths)
        self._schedule_auto_system_files_load()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._adjust_files_table_widths)

    def _apply_initial_splitter_sizes(self) -> None:
        splitter = getattr(self, "_content_splitter", None)
        if splitter is None:
            return
        total_width = splitter.width()
        if total_width <= 0:
            return
        left_ratio = 7 / 11
        if total_width < 680:
            left_width = max(1, int(total_width * left_ratio))
            splitter.setSizes([left_width, max(1, total_width - left_width)])
            return
        right_min_width = 300
        left_width = int(total_width * left_ratio)
        left_width = max(360, left_width)
        left_width = min(left_width, max(240, total_width - right_min_width))
        right_width = max(right_min_width, total_width - left_width)
        splitter.setSizes([left_width, right_width])

    def reload_for_facility(self, facility_code: str) -> None:
        next_code = str(facility_code or "").strip()
        if not next_code:
            return
        platform_changed = next_code != self.facility_code
        self.facility_code = next_code
        self._risk_updated = False
        self._latest_run_id = None
        if platform_changed:
            self._remote_preview_model_path = ""
            self._remote_preview_sea_path = ""
            if hasattr(self, "model_preview_panel"):
                self.model_preview_panel.clear_model("正在加载当前平台模型...")
        self._default_params = self._load_default_params()
        self._rule_overrides = normalize_rule_overrides((self._default_params or {}).get("rule_overrides"))
        self._apply_default_form_values()
        self.model_files = []
        self.collapse_files = []
        self.fatigue_result_files = []
        self.fatigue_input_files = []
        self._file_meta_by_path.clear()
        self._invalidate_rule_preview_cache()
        self._refresh_files_table()
        self._refresh_model_preview()
        self._auto_system_files_loaded = False
        self._auto_system_files_load_scheduled = False
        self._schedule_auto_system_files_load()

    def _schedule_auto_system_files_load(self) -> None:
        if self._auto_system_files_loaded or self._auto_system_files_load_scheduled:
            return
        self._auto_system_files_load_scheduled = True
        self._set_model_preview_placeholder("正在加载模型文件...")
        QTimer.singleShot(120, self._auto_load_system_files_after_show)

    def _auto_load_system_files_after_show(self) -> None:
        self._auto_system_files_load_scheduled = False
        if self._auto_system_files_loaded:
            return
        self._auto_system_files_loaded = True
        self._reload_system_files_from_backend()

    def _params_json_path(self) -> Path | None:
        candidates = [
            special_strategy_inputs_dir() / "special_strategy_params.json",
            Path(__file__).resolve().parent / "output_special_strategy" / "special_strategy_params.json",
        ]
        for path in candidates:
            if path.exists():
                return path
        return candidates[0]

    def _load_default_params(self) -> dict:
        try:
            return load_default_params(self.facility_code)
        except Exception:
            path = self._params_json_path()
            if not path or not path.exists():
                return {}
            try:
                return json.loads(path.read_text(encoding="utf-8-sig"))
            except Exception:
                return {}

    @staticmethod
    def _fmt_default_value(value) -> str:
        if value is None:
            return ""
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

    def _default_leg_count(self) -> int:
        raw_value = (self._default_params or {}).get("no_legs", 4)
        try:
            count = int(float(raw_value))
        except (TypeError, ValueError):
            count = 4
        return max(count, 1)

    def _default_model_param_rows(self) -> list[tuple[str, str]]:
        raw = self._default_params or {}
        return [
            ("构件直线夹角容许误差(度)", self._fmt_default_value(raw.get("x_angle_deviation", 15))),
            ("腿柱节点直径最小值(mm)", self._fmt_default_value(raw.get("min_leg_od", 509))),
            ("Work Point Z(m)", self._fmt_default_value(raw.get("wp_z", 10))),
            ("腿柱数量", self._fmt_default_value(self._default_leg_count())),
        ]

    @staticmethod
    def _fallback_work_point_pairs(count: int) -> list[tuple[Any, Any]]:
        presets: dict[int, list[tuple[Any, Any]]] = {
            4: [(-10, -8), (-10, 8), (10, -8), (10, 8)],
            8: [
                (-24, -8), (-8, -8), (8, -8), (24, -8),
                (-24, 8), (-8, 8), (8, 8), (24, 8),
            ],
        }
        if count in presets:
            return list(presets[count])
        return [("", "") for _ in range(max(count, 1))]

    def _default_work_points(self) -> list[tuple[int, str, str]]:
        leg_count = self._default_leg_count()
        points = list(self._default_params.get("work_points") or [])
        if not points:
            points = self._fallback_work_point_pairs(leg_count)
        points = points[:leg_count]
        while len(points) < leg_count:
            points.append(("", ""))
        rows: list[tuple[int, str, str]] = []
        for idx, pair in enumerate(points, start=1):
            x, y = pair if isinstance(pair, (list, tuple)) and len(pair) >= 2 else ("", "")
            rows.append((idx, self._fmt_default_value(x), self._fmt_default_value(y)))
        return rows

    def _default_risk_specs(self) -> list[dict[str, Any]]:
        raw = self._default_params or {}
        return [
            {
                "label": "生命安全等级",
                "key": "life_safety_level",
                "value": self._fmt_default_value(raw.get("life_safety_level", "S-2")),
                "description": "",
                "numeric": False,
                "integer": False,
                "editable": True,
            },
            {
                "label": "失效后果等级",
                "key": "failure_consequence_level",
                "value": self._fmt_default_value(raw.get("failure_consequence_level", "C-1")),
                "description": "",
                "numeric": False,
                "integer": False,
                "editable": True,
            },
            {
                "label": "平台整体暴露等级",
                "key": "global_level_tag",
                "value": self._fmt_default_value(raw.get("global_level_tag", "L-1")),
                "description": "",
                "numeric": False,
                "integer": False,
                "editable": True,
            },
            {
                "label": "平台海域",
                "key": "region",
                "value": self._fmt_default_value(raw.get("region", "中国南海")),
                "description": "",
                "numeric": False,
                "integer": False,
                "editable": True,
            },
            {
                "label": "A",
                "key": "collapse_a_const",
                "value": self._fmt_default_value(raw.get("collapse_a_const", 0.272)),
                "description": "",
                "numeric": True,
                "integer": False,
                "editable": True,
            },
            {
                "label": "B",
                "key": "collapse_b_const",
                "value": self._fmt_default_value(raw.get("collapse_b_const", 0.158)),
                "description": "",
                "numeric": True,
                "integer": False,
                "editable": True,
            },
            {
                "label": "已服役时间（年）",
                "key": "served_years",
                "value": self._fmt_default_value(raw.get("served_years", 1)),
                "description": "",
                "numeric": True,
                "integer": True,
                "editable": True,
            },
            {
                "label": "设计寿命",
                "key": "design_life",
                "value": self._fmt_default_value(raw.get("design_life", 26)),
                "description": "",
                "numeric": True,
                "integer": True,
                "editable": True,
            },
        ]

    @classmethod
    def _risk_level_description(cls, key: str, value: str) -> str:
        return str(cls.RISK_LEVEL_OPTIONS.get(key, {}).get(value, ""))

    def _risk_level_cell_text(self, value: str) -> str:
        value_text = str(value or "").strip()
        if not value_text:
            return self.RISK_LEVEL_PLACEHOLDER
        return f"{value_text}  {self.RISK_LEVEL_PLACEHOLDER}"

    @staticmethod
    def _risk_level_menu_qss() -> str:
        return """
            QMenu {
                background-color: #ffffff;
                color: #1d2b3a;
                border: 1px solid #cfd8e3;
                padding: 4px 0;
            }
            QMenu::item {
                padding: 6px 18px;
                background-color: transparent;
                color: #1d2b3a;
            }
            QMenu::item:selected {
                background-color: #dbe9ff;
                color: #1d2b3a;
            }
        """

    def _select_risk_level(self, row: int, key: str, value: str) -> None:
        item = self.risk_param_table.item(row, 1)
        if item is not None:
            item.setText(self._risk_level_cell_text(value))
            item.setData(Qt.UserRole, value)
        self._on_risk_level_changed(row, key, value)

    def _on_risk_param_cell_clicked(self, row: int, column: int) -> None:
        if column != 1 or not (0 <= row < len(getattr(self, "_risk_param_specs", []))):
            return
        key = str(self._risk_param_specs[row].get("key", "")).strip()
        if key not in self.RISK_LEVEL_OPTIONS:
            return

        menu = QMenu(self.risk_param_table)
        menu.setStyleSheet(self._risk_level_menu_qss())
        for option in self.RISK_LEVEL_OPTIONS[key]:
            menu.addAction(option)

        item = self.risk_param_table.item(row, column)
        if item is None:
            return
        rect = self.risk_param_table.visualItemRect(item)
        menu_width = menu.sizeHint().width()
        # Align the menu's right edge with the value cell's right edge, where the arrow is drawn.
        local_x = max(0, rect.right() - menu_width + 1)
        local_y = rect.bottom() + 1
        action = menu.exec_(self.risk_param_table.viewport().mapToGlobal(QPoint(local_x, local_y)))
        if action is not None:
            self._select_risk_level(row, key, action.text())

    def _on_risk_level_changed(self, row: int, key: str, value: str) -> None:
        description = self._risk_level_description(key, value)
        if 0 <= row < len(getattr(self, "_risk_param_specs", [])):
            self._risk_param_specs[row]["value"] = value
            self._risk_param_specs[row]["description"] = description
        item = self.risk_param_table.item(row, 2)
        if item is not None:
            item.setText(description)
            self._resize_risk_param_row(row)

    def _resize_risk_param_row(self, row: int) -> None:
        table = self.risk_param_table
        table.resizeRowToContents(row)
        table.setRowHeight(row, max(table.rowHeight(row), 38))
        self._fit_table_height_from_current_rows(table)

    def _apply_default_form_values(self) -> None:
        if hasattr(self, "model_param_table"):
            params = self._default_model_param_rows()
            self.model_param_table.blockSignals(True)
            try:
                for row, (_, value) in enumerate(params):
                    item = self.model_param_table.item(row, 1)
                    if item is not None:
                        item.setText(value)
            finally:
                self.model_param_table.blockSignals(False)

        if hasattr(self, "coord_table"):
            self._reset_coord_table_rows(self._default_work_points())

        if hasattr(self, "risk_param_table"):
            self._risk_param_specs = self._default_risk_specs()
            for row, spec in enumerate(self._risk_param_specs):
                key = str(spec.get("key", "")).strip()
                if key in self.RISK_LEVEL_OPTIONS:
                    value = str(spec.get("value") or "").strip()
                    spec["value"] = value
                    spec["description"] = self._risk_level_description(key, value)
                label_item = self.risk_param_table.item(row, 0)
                value_item = self.risk_param_table.item(row, 1)
                desc_item = self.risk_param_table.item(row, 2)
                if label_item is not None:
                    label_item.setText(str(spec["label"]))
                if value_item is not None:
                    value_item.setText(
                        self._risk_level_cell_text(str(spec["value"]))
                        if key in self.RISK_LEVEL_OPTIONS
                        else str(spec["value"])
                    )
                    value_item.setData(Qt.UserRole, str(spec["value"]) if key in self.RISK_LEVEL_OPTIONS else None)
                if desc_item is not None:
                    desc_item.setText(str(spec["description"]))
                self.risk_param_table.setRowHeight(row, 38)
            self._fit_table_height_from_current_rows(self.risk_param_table)

    def _build_ui(self):
        # 整页浅蓝灰背景
        self.setStyleSheet("""
            QWidget { 
                background: #e6eef7; 
                font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
            }
            QFrame#Card {
                background: #e6eef7;
                border: 1px solid #c7d2e3;
            }
            QFrame#InnerPanel {
                background: #ffffff;
                border: 1px solid #cfdae8;
                border-radius: 6px;
            }
            QLabel#SectionTitle,
            QLabel#RedSectionTitle {
                background: transparent;
                font-weight: bold;
                color: #1f3b57;
                font-size: 12pt;
            }
            QPushButton#ActionBtn {
                background: #00a0d6;
                color: white;
                border: 1px solid #007aa3;
                border-radius: 4px;
                padding: 4px 12px;
                min-height: 34px;
                font-size: 12pt;
                font-weight: bold;
            }
            QPushButton#ActionBtn:hover { background: #00b6f2; }

            QPushButton#BigBlueBtn {
                background: #00a0d6;
                color: black;
                border: 1px solid #0a5f7a;
                border-radius: 6px;
                min-height: 50px;
                font-size: 12pt;
                font-weight: bold;
            }
            QPushButton#BigBlueBtn:hover { background: #00b6f2; }

            QTableWidget {
                background: #ffffff;
                alternate-background-color: #fbfdff;
                gridline-color: #d0d0d0;
                border: 1px solid #d0d0d0;
                font-size: 12pt;
            }
            QTableWidget::item {
                border-bottom: 1px solid #e6edf5;
                border-right: 1px solid #e6edf5;
                padding: 3px 6px;
            }
            QTableWidget::item:selected {
                background: #dbeafe;
                color: #111827;
            }
            QHeaderView::section {
                background: #edf4fb;
                color: #1f3b57;
                border: 1px solid #d9e4f0;
                padding: 6px 6px;
                font-weight: bold;
                font-size: 12pt;
            }
            QLineEdit {
                background: white;
                border: 1px solid #c7d2e3;
                padding: 4px 6px;
                font-size: 12pt;
            }
        """)

        # ===== 关键：用 ScrollArea 包裹"中间主要内容"，滚轮可下滑查看下半部分 =====
        # 保留右侧模型展示区域，但暂时不接入实际渲染，避免页面打不开
        content = QFrame()
        content.setObjectName("Card")
        lay = QHBoxLayout(content)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(12)

        left_scroll = QScrollArea(content)
        left_scroll.setWidgetResizable(True)
        left_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setObjectName("LeftScrollArea")
        left_scroll.setStyleSheet("""
            QScrollArea#LeftScrollArea {
                background: transparent;
                border: none;
            }
            QScrollArea#LeftScrollArea > QWidget > QWidget {
                background: transparent;
            }
        """)

        left = self._build_left_panel()
        left_scroll.setWidget(left)
        right = self._build_right_panel()

        self._content_splitter = QSplitter(Qt.Horizontal, content)
        self._content_splitter.setChildrenCollapsible(False)
        self._content_splitter.setHandleWidth(6)
        self._content_splitter.addWidget(left_scroll)
        self._content_splitter.addWidget(right)
        self._content_splitter.setStretchFactor(0, 7)
        self._content_splitter.setStretchFactor(1, 4)
        self._content_splitter.setCollapsible(0, False)
        self._content_splitter.setCollapsible(1, False)
        self._content_splitter.splitterMoved.connect(lambda *_: self._adjust_files_table_widths())

        lay.addWidget(self._content_splitter, 1)

        self.main_layout.addWidget(content, 1)

    # ---------------- 左侧：上下拼接 ----------------
    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.left_panel = panel

        v = QVBoxLayout(panel)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)

        v.addWidget(self._build_model_info_block(), 0)

        # 只保留一个文件设置块
        self.analysis_files_block = self._build_analysis_files_block()
        v.addWidget(self.analysis_files_block, 0)

        v.addWidget(self._build_risk_level_settings_block(), 1)
        return panel

    # ---------------- 上半：结构模型信息 ----------------
    def _build_model_info_block(self) -> QFrame:
        block = QFrame()
        block.setObjectName("InnerPanel")
        block.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        block_lay = QVBoxLayout(block)
        block_lay.setContentsMargins(12, 10, 12, 12)
        block_lay.setSpacing(10)

        title = QLabel("结构模型信息")
        title.setObjectName("SectionTitle")
        block_lay.addWidget(title)

        # 参数表（两列：项目/值，默认从平台参数读取，值列可编辑）
        params = self._default_model_param_rows()
        self.model_param_table = QTableWidget(len(params), 2)
        param_table = self.model_param_table
        param_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        param_table.verticalHeader().setVisible(False)
        param_table.horizontalHeader().setVisible(False)

        for r, (k, val) in enumerate(params):
            item_k = QTableWidgetItem(k)
            item_v = QTableWidgetItem(val)
            item_k.setTextAlignment(Qt.AlignCenter)
            item_v.setTextAlignment(Qt.AlignCenter)
            item_k.setFlags(item_k.flags() & ~Qt.ItemIsEditable)
            param_table.setItem(r, 0, item_k)
            param_table.setItem(r, 1, item_v)

        self._lock_table_full_display(param_table, row_height=34, show_header=False)
        param_table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
        )
        param_table.setSelectionMode(QAbstractItemView.SingleSelection)
        param_table.itemChanged.connect(self._on_model_param_item_changed)

        block_lay.addWidget(param_table)

        # 坐标表（默认从平台参数读取，X/Y 可编辑）
        coords = self._default_work_points()
        self.coord_table = QTableWidget(max(len(coords), 1), 3)
        coord_table = self.coord_table
        coord_table.setHorizontalHeaderLabels(["腿柱工作点坐标", "X坐标（m）", "Y坐标（m）"])
        coord_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        coord_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        coord_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        coord_table.setColumnWidth(0, self.WORK_POINT_LABEL_COLUMN_WIDTH)
        coord_table.verticalHeader().setVisible(False)

        for r, (idx, x, y) in enumerate(coords):
            for c, val in enumerate([idx, x, y]):
                it = QTableWidgetItem(str(val))
                it.setTextAlignment(Qt.AlignCenter)
                if c == 0:
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                coord_table.setItem(r, c, it)

        self._lock_table_full_display(coord_table, row_height=34, show_header=True)
        coord_table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
        )
        coord_table.setSelectionMode(QAbstractItemView.SingleSelection)
        coord_table.setSelectionBehavior(QAbstractItemView.SelectRows)

        block_lay.addWidget(coord_table)
        self.model_info_block = block
        return block

    def _renumber_coord_rows(self) -> None:
        for row in range(self.coord_table.rowCount()):
            item = self.coord_table.item(row, 0)
            if item is None:
                item = QTableWidgetItem()
                self.coord_table.setItem(row, 0, item)
            item.setText(str(row + 1))
            item.setTextAlignment(Qt.AlignCenter)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)

    def _on_model_param_item_changed(self, item: QTableWidgetItem) -> None:
        if item.row() == 3 and item.column() == 1:
            self._sync_coord_rows_to_leg_count()

    def _coord_target_leg_count(self) -> int | None:
        item = self.model_param_table.item(3, 1)
        if item is None:
            return None
        try:
            count = int(float((item.text() or "").strip()))
        except (TypeError, ValueError):
            return None
        return max(count, 1)

    def _sync_coord_rows_to_leg_count(self) -> None:
        target = self._coord_target_leg_count()
        if target is None:
            return
        leg_item = self.model_param_table.item(3, 1)
        if leg_item is not None and leg_item.text().strip() != str(target):
            self.model_param_table.blockSignals(True)
            try:
                leg_item.setText(str(target))
            finally:
                self.model_param_table.blockSignals(False)

        current = self.coord_table.rowCount()
        if current < target:
            for row in range(current, target):
                self.coord_table.insertRow(row)
                for col in range(3):
                    item = QTableWidgetItem("" if col else str(row + 1))
                    item.setTextAlignment(Qt.AlignCenter)
                    if col == 0:
                        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    self.coord_table.setItem(row, col, item)
        elif current > target:
            for row in range(current - 1, target - 1, -1):
                self.coord_table.removeRow(row)

        self._renumber_coord_rows()
        self._lock_table_full_display(self.coord_table, row_height=34, show_header=True)
        self.coord_table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
        )
        self.coord_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.coord_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._refresh_model_info_layout()

    def _reset_coord_table_rows(self, rows: list[tuple[int, str, str]]) -> None:
        self.coord_table.setRowCount(max(len(rows), 1))
        for row, (idx, x, y) in enumerate(rows):
            for col, value in enumerate([idx, x, y]):
                item = self.coord_table.item(row, col)
                if item is None:
                    item = QTableWidgetItem()
                    self.coord_table.setItem(row, col, item)
                item.setText(str(value))
                item.setTextAlignment(Qt.AlignCenter)
                if col == 0:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        self._renumber_coord_rows()
        self._lock_table_full_display(self.coord_table, row_height=34, show_header=True)
        self.coord_table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
        )
        self.coord_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.coord_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._refresh_model_info_layout()

    def _refresh_model_info_layout(self) -> None:
        block = getattr(self, "model_info_block", None)
        if block is None:
            return
        layout = block.layout()
        if layout is not None:
            layout.activate()
        block.updateGeometry()
        panel = getattr(self, "left_panel", None)
        if panel is not None:
            panel_layout = panel.layout()
            if panel_layout is not None:
                panel_layout.activate()
            panel.updateGeometry()

    # # ---------------- 上半：模型文件（新增） ----------------
    def _build_model_files_block(self) -> QFrame:
        block = QFrame()
        block_lay = QVBoxLayout(block)
        block_lay.setContentsMargins(0, 0, 0, 0)
        block_lay.setSpacing(6)

        self.model_files_table = _NoWheelFileTable(0, len(self.FILE_TABLE_HEADERS))
        self._configure_file_table(self.model_files_table)

        block_lay.addWidget(self.model_files_table)
        return block

    # # ---------------- 上半：倒塌分析结果文件 ----------------
    def _build_analysis_files_block(self) -> QFrame:
        block = QFrame()
        block.setObjectName("InnerPanel")
        block.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        block_lay = QVBoxLayout(block)
        block_lay.setContentsMargins(12, 10, 12, 12)
        block_lay.setSpacing(0)

        self.files_table = _NoWheelFileTable(0, len(self.FILE_TABLE_HEADERS))
        self._configure_file_table(self.files_table)

        block_lay.addWidget(self.files_table)
        return block

    def _configure_file_table(self, table: QTableWidget) -> None:
        table.setColumnCount(len(self.FILE_TABLE_HEADERS))
        table.setHorizontalHeaderLabels(self.FILE_TABLE_HEADERS)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setWordWrap(False)

        header = table.horizontalHeader()
        header.setVisible(True)
        header.setHighlightSections(False)

        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.Interactive)

        table.setColumnWidth(0, self.WORK_POINT_LABEL_COLUMN_WIDTH)

    def _adjust_files_table_widths(self) -> None:
        if not hasattr(self, "files_table") or self.files_table is None:
            return

        table = self.files_table
        if table.viewport().width() <= 0:
            return

        table.setColumnWidth(0, self.WORK_POINT_LABEL_COLUMN_WIDTH)

        # 先只让固定列按内容收缩
        for c in [1, 2, 4, 5]:
            table.resizeColumnToContents(c)

        fixed_cols = [0, 1, 2, 4, 5]
        fixed_width = sum(table.columnWidth(c) for c in fixed_cols)

        remaining = max(320, table.viewport().width() - fixed_width - 8)

        file_name_w = int(remaining * 0.62)
        remark_w = remaining - file_name_w

        table.setColumnWidth(3, max(220, file_name_w))
        table.setColumnWidth(6, max(120, remark_w))

        self._fit_table_height(table)

    # ---------------- 下半：风险等级参数（新增） ----------------
    def _build_risk_level_settings_block(self) -> QFrame:
        block = QFrame()
        block.setObjectName("InnerPanel")
        v = QVBoxLayout(block)
        v.setContentsMargins(12, 10, 12, 12)
        v.setSpacing(10)
        block.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # 红色标题（对应截图"设置等级参数"）
        title = QLabel("设置等级参数")
        title.setObjectName("RedSectionTitle")
        v.addWidget(title)

        self._risk_param_specs = self._default_risk_specs()
        rows = self._risk_param_specs
        self.risk_param_table = QTableWidget(len(rows), 3)
        table = self.risk_param_table
        table.horizontalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setWordWrap(True)

        for r, spec in enumerate(rows):
            key = str(spec.get("key", "")).strip()
            if key in self.RISK_LEVEL_OPTIONS:
                value = str(spec.get("value") or "").strip()
                spec["value"] = value
                spec["description"] = self._risk_level_description(key, value)

            it0 = QTableWidgetItem(str(spec["label"]))
            it1 = QTableWidgetItem(str(spec["value"]))
            it2 = QTableWidgetItem(str(spec["description"]))

            it0.setTextAlignment(Qt.AlignCenter)
            it1.setTextAlignment(Qt.AlignCenter)
            it2.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

            it0.setFlags(it0.flags() & ~Qt.ItemIsEditable)
            it2.setFlags(it2.flags() & ~Qt.ItemIsEditable)
            if spec.get("editable", False):
                it1.setBackground(Qt.white)
                it2.setBackground(Qt.white)
            else:
                it1.setFlags(it1.flags() & ~Qt.ItemIsEditable)
            table.setItem(r, 0, it0)
            table.setItem(r, 1, it1)
            table.setItem(r, 2, it2)

            if key in self.RISK_LEVEL_OPTIONS:
                it1.setText(self._risk_level_cell_text(str(spec["value"])))
                it1.setData(Qt.UserRole, str(spec["value"]))
                it1.setFlags(it1.flags() & ~Qt.ItemIsEditable)
                it1.setToolTip("点击选择")

        table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
        )
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.cellClicked.connect(self._on_risk_param_cell_clicked)
        for r in range(table.rowCount()):
            table.setRowHeight(r, 38)
        self._fit_table_height_from_current_rows(table)
        table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        v.addWidget(table, 1)

        # 两个大按钮（对应截图：更新风险等级 / 查看结果）
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        btn_update = QPushButton("更新风险等级")
        btn_update.setObjectName("BigBlueBtn")
        btn_update.setFixedWidth(200)
        btn_update.clicked.connect(self._on_update_risk_level)
        self.btn_update_risk = btn_update

        btn_view = QPushButton("查看结果")
        btn_view.setObjectName("BigBlueBtn")
        btn_view.setFixedWidth(200)
        btn_view.clicked.connect(self._on_view_result)
        self.btn_view_result = btn_view

        btn_row.addWidget(btn_update)
        btn_row.addWidget(btn_view)
        btn_row.addStretch(1)

        v.addLayout(btn_row, 0)

        return block

    # ---------------- 右侧：黑色模型展示区（当前占位，不渲染模型） ----------------
    def _build_right_panel(self) -> QFrame:
        panel = QFrame()
        panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        panel.setMinimumWidth(300)
        panel.setMaximumWidth(520)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._model_preview_host = panel
        self._model_preview_layout = layout
        self.model_preview_panel = None
        self.model_preview_placeholder = QLabel("当前未加载模型文件", panel)
        self.model_preview_placeholder.setAlignment(Qt.AlignCenter)
        self.model_preview_placeholder.setStyleSheet(
            """
            QLabel {
                background: #ffffff;
                border: 1px solid #b9c6d6;
                color: #506070;
                font-size: 12pt;
            }
            """
        )
        layout.addWidget(self.model_preview_placeholder, 1)

        return panel

    def _set_model_preview_placeholder(self, text: str) -> None:
        placeholder = getattr(self, "model_preview_placeholder", None)
        if placeholder is not None:
            placeholder.setText(text)

    def _ensure_model_preview_panel(self) -> bool:
        if getattr(self, "model_preview_panel", None) is not None:
            return True
        layout = getattr(self, "_model_preview_layout", None)
        host = getattr(self, "_model_preview_host", None)
        if layout is None or host is None:
            return False
        try:
            from pages.special_inspection_model_preview import SpecialInspectionModelPreviewPanel
        except Exception as exc:
            self._set_model_preview_placeholder(f"模型预览组件加载失败：\n{exc}")
            return False

        placeholder = getattr(self, "model_preview_placeholder", None)
        if placeholder is not None:
            layout.removeWidget(placeholder)
            placeholder.deleteLater()
            self.model_preview_placeholder = None

        self.model_preview_panel = SpecialInspectionModelPreviewPanel(host)
        layout.addWidget(self.model_preview_panel, 1)
        return True

    def _resolve_db_storage_path(self, row: dict[str, Any]) -> str:
        return resolve_storage_path(row, config_path=str(DEFAULT_DB_CONFIG))

    def _display_storage_path(self, path: str) -> str:
        normalized = os.path.normpath(str(path or "").strip())
        if not normalized:
            return ""
        return self._short_path(normalized)

    # ---------------- actions ----------------
    def _on_find_nodes(self):
        QMessageBox.information(self, "查找节点", f"这里执行：根据 {self.facility_code} 的模型/参数查找节点（待接算法）。")

    def _on_extract_analysis(self):
        self._reload_system_files_from_backend()
        QMessageBox.information(self, "提取分析", "已从系统文件库提取并刷新分析结果文件。")

    def _on_extract_model_files(self):
        self.model_files = self._db_fetch_file_records(self.CATEGORY_MODEL)
        self._invalidate_rule_preview_cache()
        self._start_rule_preview_preload()
        self._refresh_model_files_table()
        self._refresh_model_preview()
        QMessageBox.information(self, "提取模型", "已从系统文件库提取并刷新模型文件。")

    def _show_risk_progress(self, text: str) -> None:
        base_text = (text or "正在计算风险等级").rstrip(".。 ")
        self._risk_progress_base_text = base_text
        self._risk_progress_tick = 0
        progress = self._risk_progress
        if progress is None:
            progress = QProgressDialog(f"{base_text}...", None, 0, 0, self)
            progress.setWindowTitle("更新风险等级")
            progress.setWindowModality(Qt.WindowModal)
            progress.setCancelButton(None)
            progress.setMinimumDuration(0)
            progress.setAutoClose(False)
            progress.setAutoReset(False)
            self._risk_progress = progress
        else:
            progress.setLabelText(f"{base_text}...")
        progress.show()
        if not self._risk_progress_timer.isActive():
            self._risk_progress_timer.start()
        QApplication.processEvents()

    def _update_risk_progress_text(self) -> None:
        if self._risk_progress is None or not self._risk_progress_base_text:
            return
        dot_count = (self._risk_progress_tick % 3) + 1
        self._risk_progress.setLabelText(f"{self._risk_progress_base_text}{'.' * dot_count}")
        self._risk_progress_tick += 1

    def _close_risk_progress(self) -> None:
        if self._risk_progress_timer.isActive():
            self._risk_progress_timer.stop()
        if self._risk_progress is not None:
            try:
                self._risk_progress.close()
            except Exception:
                pass
            self._risk_progress = None
        self._risk_progress_base_text = ""
        self._risk_progress_tick = 0

    def _set_risk_running(self, running: bool) -> None:
        if self.btn_update_risk is not None:
            self.btn_update_risk.setEnabled(not running)
        if self.btn_view_result is not None:
            self.btn_view_result.setEnabled(not running)
        if running:
            self._show_risk_progress("正在计算风险等级")
        else:
            self._close_risk_progress()

    def _on_risk_thread_finished(self) -> None:
        finished_stage = self._active_worker_stage
        self._risk_thread = None
        self._risk_worker = None
        self._active_worker_stage = ""
        if finished_stage == "prepare" and self._pending_prepared_calculation is not None:
            QTimer.singleShot(0, self._begin_post_risk_rule_stage)

    def _start_risk_calculation_worker(
        self,
        *,
        stage: str = "run",
        param_overrides: dict[str, Any] | None = None,
        input_overrides: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        prepared_calculation: dict[str, Any] | None = None,
    ) -> None:
        self._set_risk_running(True)

        thread = QThread(self)
        worker = _SpecialStrategyCalculationWorker(
            self.facility_code,
            stage=stage,
            param_overrides=param_overrides,
            input_overrides=input_overrides,
            metadata=metadata,
            prepared_calculation=prepared_calculation,
        )
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.finished.connect(self._on_risk_calculation_finished)
        worker.failed.connect(self._on_risk_calculation_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(self._on_risk_thread_finished)
        thread.finished.connect(thread.deleteLater)

        self._risk_thread = thread
        self._risk_worker = worker
        self._active_worker_stage = stage
        thread.start()

    def _on_risk_calculation_finished(self, result_bundle: dict[str, Any]) -> None:
        self._set_risk_running(False)
        stage = str(result_bundle.get("stage") or "") if isinstance(result_bundle, dict) else ""
        payload = result_bundle.get("payload") if isinstance(result_bundle, dict) else result_bundle
        if stage == "prepare":
            self._pending_prepared_calculation = payload if isinstance(payload, dict) else None
            return

        self._risk_updated = True
        state = payload.get("state") if isinstance(payload, dict) else {}
        run_id = None
        if isinstance(payload, dict):
            run_id = payload.get("run_id") or payload.get("db_run_id")
        if not run_id and isinstance(state, dict):
            run_id = state.get("db_run_id") or state.get("run_id")
        try:
            self._latest_run_id = int(run_id) if run_id not in ("", None) else None
        except Exception:
            self._latest_run_id = run_id
        self.strategy_calculated.emit(self.facility_code, self._latest_run_id)
        QMessageBox.information(self, "更新风险等级", "已按当前参数完成风险结果计算。")

    def _on_risk_calculation_failed(self, message: str) -> None:
        self._set_risk_running(False)
        QMessageBox.warning(self, "更新风险等级失败", f"风险结果计算失败：\n{message}")


    def _collect_client_manual_fill_entries(
        self,
        param_overrides: dict[str, Any],
        input_overrides: dict[str, Any],
    ) -> list[dict[str, Any]] | None:
        """远程模式下先让服务端做无 GUI 检查，再在客户端补充 ManualBrace。"""
        if not _use_fastapi_backend():
            return []

        try:
            api = _RemoteStrategyApiClient()
            data = api.check_manual_fill(
                facility_code=self.facility_code,
                param_overrides=param_overrides,
                input_overrides=input_overrides,
                metadata={"disable_server_gui": True, "manual_fill_check_only": True},
            )
        except FileNotFoundError:
            # 旧服务端没有检查接口时，为避免服务端继续弹 GUI，直接提示更新服务端。
            QMessageBox.warning(
                self,
                "ManualBrace 检查失败",
                "服务端缺少 /api/strategy/manual-fill/check 接口。\n"
                "请先替换 server/routers/strategy.py 和 services/special_strategy_runtime.py。",
            )
            return None
        except Exception as exc:
            QMessageBox.warning(self, "ManualBrace 检查失败", f"检查疲劳输入人工补全项失败：\n{exc}")
            return None

        rows = data.get("manual_fill_rows") or data.get("rows") or []
        if not rows:
            return []

        dialog = ManualBraceClientDialog(rows, self)
        if dialog.exec_() != QDialog.Accepted:
            return None
        return dialog.result_entries

    def _on_update_risk_level(self):
        if not self._validate_fatigue_groups():
            return
        if self._risk_thread is not None and self._risk_thread.isRunning():
            QMessageBox.information(self, "提示", "风险结果正在计算，请稍候。")
            return
        if not self._run_pre_risk_rule_dialog_sequence():
            return

        try:
            param_overrides = self._collect_runtime_overrides()
            input_overrides = self._collect_runtime_input_overrides()
        except Exception as exc:
            QMessageBox.warning(self, "参数错误", f"收集计算参数失败：\n{exc}")
            return

        manual_entries = self._collect_client_manual_fill_entries(param_overrides, input_overrides)
        if manual_entries is None:
            QMessageBox.information(self, "更新风险等级", "已取消 ManualBrace 人工补全，本次计算未继续。")
            return

        metadata = {
            "manual_fill_entries": manual_entries,
            "manual_fill_source": "client",
            "disable_server_gui": True,
        }

        # 远程模式保持原来的 /api/strategy/run 计算流程，只是把客户端补全项随 metadata 传给服务端。
        self._start_risk_calculation_worker(
            stage="run",
            param_overrides=param_overrides,
            input_overrides=input_overrides,
            metadata=metadata,
        )

    def _validate_fatigue_groups(self) -> bool:
        result_files = self._sorted_existing_paths(
            self.fatigue_result_files,
            category=self.CATEGORY_FATIGUE,
            branch="result",
        )
        input_files = self._sorted_existing_paths(
            self.fatigue_input_files,
            category=self.CATEGORY_FATIGUE,
            branch="input",
        )
        if not result_files and not input_files:
            return True
        if not result_files or not input_files:
            QMessageBox.warning(
                self,
                "疲劳文件组不完整",
                "疲劳分析结果文件组和输入文件组需要同时提供。\n如本次不想覆盖默认疲劳配置，请先删除已导入的疲劳文件。",
            )
            return False
        if len(result_files) != len(input_files):
            QMessageBox.warning(
                self,
                "疲劳文件组数量不一致",
                f"当前疲劳结果文件为 {len(result_files)} 个，输入文件为 {len(input_files)} 个，请先调整一致。",
            )
            return False
        try:
            cfg = load_base_config(self.facility_code)
        except Exception:
            cfg = {}
        expected_result_count = len(cfg.get("ftglst", []) or [])
        expected_input_count = len(cfg.get("ftginp", []) or [])
        if expected_result_count and len(result_files) < expected_result_count:
            QMessageBox.warning(
                self,
                "疲劳结果文件不足",
                f"当前平台默认需要至少 {expected_result_count} 个疲劳结果文件，当前仅有 {len(result_files)} 个。",
            )
            return False
        if expected_input_count and len(input_files) < expected_input_count:
            QMessageBox.warning(
                self,
                "疲劳输入文件不足",
                f"当前平台默认需要至少 {expected_input_count} 个疲劳输入文件，当前仅有 {len(input_files)} 个。",
            )
            return False
        return True

    def _on_view_result(self):
        if not self._risk_updated or not self._latest_run_id:
            QMessageBox.information(self, "提示", "请先点击“更新风险等级”，再查看结果。")
            return

        mw = self.window()  # ✅比 self.parent() 稳定

        # ✅这里判断/调用你 main.py 里真实存在的方法名
        if mw is not None and hasattr(mw, "open_upgrade_special_inspection_result_tab"):
            mw.open_upgrade_special_inspection_result_tab(self.facility_code, run_id=self._latest_run_id)
            return

        # 兜底：直接加tab
        if mw is not None and hasattr(mw, "tab_widget"):
            page = UpgradeSpecialInspectionResultPage(self.facility_code, mw, run_id=self._latest_run_id)
            idx = mw.tab_widget.addTab(page, f"{self.facility_code}更新风险结果")
            mw.tab_widget.setCurrentIndex(idx)
            return

        QMessageBox.warning(self, "错误", "未找到 MainWindow/tab_widget，无法打开结果页。")

    # ---------------- 文件来源：后续数据库接入接口（先走 upload/model_files） ----------------
    @staticmethod
    def _is_existing_file(path: str) -> bool:
        text = str(path or "").strip()
        return bool(text) and os.path.exists(text) and os.path.isfile(text)

    def _download_latest_model_for_preview(self, *, force: bool = False) -> str:
        """C/S 模式下，右侧模型预览和规则弹窗都必须使用客户端本地缓存文件。"""
        if not _use_fastapi_backend():
            return ""
        cached = os.path.normpath(str(getattr(self, "_remote_preview_model_path", "") or ""))
        if (not force) and self._is_existing_file(cached):
            return cached
        try:
            path = _RemoteStrategyApiClient().download_latest_model_file(self.facility_code)
            path = os.path.normpath(str(path or "").strip())
            if self._is_existing_file(path):
                self._remote_preview_model_path = path
                print("[NewSpecialInspectionPage] remote model downloaded for preview:", path)
                return path
        except Exception as exc:
            print("[NewSpecialInspectionPage] download latest model for preview failed:", exc)
        return cached if self._is_existing_file(cached) else ""

    def _download_latest_sea_for_preview(self, *, force: bool = False) -> str:
        if not _use_fastapi_backend():
            return ""
        cached = os.path.normpath(str(getattr(self, "_remote_preview_sea_path", "") or ""))
        if (not force) and self._is_existing_file(cached):
            return cached
        try:
            path = _RemoteStrategyApiClient().download_latest_sea_file(self.facility_code)
            path = os.path.normpath(str(path or "").strip())
            if self._is_existing_file(path):
                self._remote_preview_sea_path = path
                print("[NewSpecialInspectionPage] remote sea downloaded for preview:", path)
                return path
        except Exception as exc:
            print("[NewSpecialInspectionPage] download latest sea for preview failed:", exc)
        return cached if self._is_existing_file(cached) else ""

    def _current_model_path_for_rule_preview(self) -> str:
        # 远程模式下优先使用服务端下载到客户端的当前模型，避免客户端直接读服务端 D 盘路径。
        remote_model = self._download_latest_model_for_preview()
        if remote_model:
            return remote_model

        input_overrides = self._collect_runtime_input_overrides()
        override_model = str(input_overrides.get("model") or "").strip()
        if self._is_existing_file(override_model):
            return override_model

        model_candidates = self._sorted_existing_paths(self.model_files, category=self.CATEGORY_MODEL)
        if model_candidates:
            return model_candidates[0]

        try:
            cfg = load_base_config(self.facility_code)
        except Exception:
            return ""
        return str(cfg.get("model") or "").strip()

    def _invalidate_rule_preview_cache(self) -> None:
        self._rule_preview_cache = None

    def _on_rule_preview_loaded(self, model_path: str, joint_ids: object, member_pairs: object) -> None:
        normalized_path = os.path.normpath(str(model_path or "").strip())
        self._rule_preview_cache = {
            "model_path": normalized_path,
            "joint_ids": list(joint_ids or []),
            "member_pairs": list(member_pairs or []),
        }

    def _on_rule_preview_thread_finished(self) -> None:
        self._rule_preview_thread = None
        self._rule_preview_worker = None
        self._rule_preview_loading_path = ""

    def _start_rule_preview_preload(self, model_path: str | None = None) -> None:
        path = os.path.normpath(str(model_path or self._current_model_path_for_rule_preview() or "").strip())
        if not path or not os.path.exists(path):
            return
        cached = self._rule_preview_cache
        if isinstance(cached, dict) and cached.get("model_path") == path:
            return
        if self._rule_preview_thread is not None and self._rule_preview_thread.isRunning():
            if self._rule_preview_loading_path == path:
                return
            return

        thread = QThread(self)
        worker = _RulePreviewWorker(path)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_rule_preview_loaded)
        worker.failed.connect(lambda message: print("[NewSpecialInspectionPage] rule preview preload failed:", message))
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(self._on_rule_preview_thread_finished)
        thread.finished.connect(thread.deleteLater)
        self._rule_preview_thread = thread
        self._rule_preview_worker = worker
        self._rule_preview_loading_path = path
        thread.start()

    def _load_rule_preview_inputs(self) -> tuple[list[str], list[tuple[str, str]], bool]:
        model_path = self._current_model_path_for_rule_preview()
        if not model_path or not Path(model_path).exists():
            return [], [], False
        cached = self._rule_preview_cache
        if isinstance(cached, dict) and cached.get("model_path") == os.path.normpath(model_path):
            return (
                list(cached.get("joint_ids") or []),
                list(cached.get("member_pairs") or []),
                True,
            )
        self._start_rule_preview_preload(model_path)
        return [], [], False

    def _open_rule_dialog(
        self,
        mode: str,
        *,
        joint_ids: list[str],
        member_pairs: list[tuple[str, str]],
        preview_available: bool,
        current_rules: dict[str, Any],
    ) -> dict[str, Any] | None:
        dialog = SpecialStrategyRuleDialog(
            mode,
            current_rules,
            joint_ids=joint_ids,
            member_pairs=member_pairs,
            preview_available=preview_available,
            parent=self,
        )
        if dialog.exec_() != QDialog.Accepted:
            return None
        return normalize_rule_overrides(dialog.result_rules)

    def _run_pre_risk_rule_dialog_sequence(self) -> bool:
        joint_ids, member_pairs, preview_available = self._load_rule_preview_inputs()
        current_rules = normalize_rule_overrides(self._rule_overrides)
        for mode in (
            RULE_MODE_MEMBER_CLASSIFICATION,
            RULE_MODE_JOINT_CLASSIFICATION,
        ):
            next_rules = self._open_rule_dialog(
                mode,
                joint_ids=joint_ids,
                member_pairs=member_pairs,
                preview_available=preview_available,
                current_rules=current_rules,
            )
            if next_rules is None:
                return False
            current_rules = next_rules
        self._rule_overrides = current_rules
        return True

    def _load_post_risk_rule_preview_inputs(
        self,
        prepared_calculation: dict[str, Any],
    ) -> tuple[list[str], list[tuple[str, str]], bool]:
        # 远程 FastAPI prepare 接口建议直接返回这两个预览字段：
        #   joint_ids: ["301L", ...]
        #   member_pairs: [["301L", "401L"], ...]
        remote_joint_ids = prepared_calculation.get("joint_ids") or prepared_calculation.get("preview_joint_ids")
        remote_member_pairs = prepared_calculation.get("member_pairs") or prepared_calculation.get("preview_member_pairs")
        if isinstance(remote_joint_ids, list) or isinstance(remote_member_pairs, list):
            joint_ids = [
                str(value or "").strip()
                for value in (remote_joint_ids or [])
                if str(value or "").strip()
            ]
            member_pairs: list[tuple[str, str]] = []
            for item in remote_member_pairs or []:
                if isinstance(item, dict):
                    a = str(item.get("joint_a") or item.get("JointA") or item.get("a") or "").strip()
                    b = str(item.get("joint_b") or item.get("JointB") or item.get("b") or "").strip()
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    a = str(item[0] or "").strip()
                    b = str(item[1] or "").strip()
                else:
                    continue
                if a and b:
                    member_pairs.append((a, b))
            return joint_ids, member_pairs, bool(joint_ids or member_pairs)

        # 本地兼容模式仍使用原始 prepared_pipeline DataFrame。
        prepared_pipeline = prepared_calculation.get("prepared_pipeline")
        if not isinstance(prepared_pipeline, dict):
            return [], [], False

        member_risk_df = prepared_pipeline.get("member_risk_df")
        forecast_df = prepared_pipeline.get("forecast_df")
        try:
            joint_a_values = member_risk_df["JointA"].astype(str).str.strip().tolist()
            joint_b_values = member_risk_df["JointB"].astype(str).str.strip().tolist()
            member_pairs = [
                (joint_a, joint_b)
                for joint_a, joint_b in zip(joint_a_values, joint_b_values)
                if joint_a and joint_b and joint_a.lower() != "nan" and joint_b.lower() != "nan"
            ]
            joint_ids = [
                str(value or "").strip()
                for value in forecast_df["JoitID"].astype(str).str.strip().tolist()
                if str(value or "").strip() and str(value or "").strip().lower() != "nan"
            ]
        except Exception:
            return [], [], False
        return joint_ids, member_pairs, True

    def _run_post_risk_rule_dialog_sequence(self, prepared_calculation: dict[str, Any]) -> bool:
        joint_ids, member_pairs, preview_available = self._load_post_risk_rule_preview_inputs(prepared_calculation)
        current_rules = normalize_rule_overrides(self._rule_overrides)
        for mode in (
            RULE_MODE_MEMBER_EXCLUSION,
            RULE_MODE_JOINT_EXCLUSION,
        ):
            next_rules = self._open_rule_dialog(
                mode,
                joint_ids=joint_ids,
                member_pairs=member_pairs,
                preview_available=preview_available,
                current_rules=current_rules,
            )
            if next_rules is None:
                return False
            current_rules = next_rules
        self._rule_overrides = current_rules
        return True

    def _begin_post_risk_rule_stage(self) -> None:
        prepared_calculation = self._pending_prepared_calculation
        self._pending_prepared_calculation = None
        if not isinstance(prepared_calculation, dict):
            QMessageBox.warning(self, "更新风险等级失败", "未能取得第 8 步后的中间结果，无法继续后置过滤。")
            return
        if not self._run_post_risk_rule_dialog_sequence(prepared_calculation):
            return
        self._start_risk_calculation_worker(
            stage="finalize",
            param_overrides=self._collect_runtime_overrides(),
            prepared_calculation=prepared_calculation,
        )

    def _wrap_storage_paths_as_rows(self, records: List[str]) -> List[dict[str, Any]]:
        rows: List[dict[str, Any]] = []
        for raw_path in records:
            path = os.path.normpath(str(raw_path or "").strip())
            if not path:
                continue
            rows.append(
                {
                    "storage_path": path,
                    "display_path": self._display_storage_path(path),
                    "original_name": os.path.basename(path),
                    "logical_path": "",
                    "module_code": "upload_scan",
                }
            )
        return rows

    def _filter_file_rows_by_branch(
            self,
            category: str,
            rows: List[dict[str, Any]],
            branch: str | None,
    ) -> List[dict[str, Any]]:
        return [row for row in rows if self._is_runtime_supported_row(row, category, branch)]

    def _db_fetch_file_rows(self, category: str, branch: str | None = None) -> List[dict[str, Any]]:
        """
        数据库读取接口：返回系统文件记录。

        当数据库配置存在时，系统导入只从数据库中选文件；
        仅在未配置数据库时，才回退到本地 upload/model_files 扫描。
        """

        def _normalize_rows(rows: List[dict[str, Any]]) -> List[dict[str, Any]]:
            normalized: List[dict[str, Any]] = []
            for row in rows:
                current = dict(row)
                resolved_path = self._resolve_db_storage_path(current)
                current["storage_path"] = resolved_path
                current["display_path"] = self._display_storage_path(resolved_path)
                if self._is_runtime_supported_row(current, category, branch):
                    normalized.append(current)
            normalized.sort(
                key=lambda item: (
                    str(item.get("work_condition") or "").strip().lower(),
                    str(item.get("logical_path") or "").replace("\\", "/").strip().lower(),
                    str(item.get("original_name") or "").strip().lower(),
                )
            )
            return normalized

        if is_file_db_configured():
            try:
                default_rows = list_files_by_prefix(
                    file_type_code=category,
                    module_code="model_files",
                    logical_path_prefix=self._default_model_logical_prefix(category, branch),
                    facility_code=(self.facility_code or "").strip() or None,
                )
                if default_rows:
                    return self._filter_file_rows_by_branch(category, _normalize_rows(default_rows), branch)
                legacy_rows = list_files(
                    file_type_code=category,
                    module_code="special_strategy",
                    logical_path=self._legacy_special_strategy_logical_path(category),
                    facility_code=(self.facility_code or "").strip() or None,
                )
                if legacy_rows:
                    return self._filter_file_rows_by_branch(category, _normalize_rows(legacy_rows), branch)
                return []
            except FileBackendError:
                return []
        return self._wrap_storage_paths_as_rows(self._fetch_system_files_from_upload(category, branch))

    def _db_fetch_file_records(self, category: str, branch: str | None = None) -> List[str]:
        """
        数据库读取接口（预留）：返回系统文件记录。

        后续接数据库时，只需要替换本方法内部实现即可，页面其余逻辑无需改动。
        当前实现：从 upload/model_files 扫描提取。
        """
        rows = self._db_fetch_file_rows(category, branch)
        self._remember_file_rows(rows)
        return self._sorted_existing_paths(
            [
                os.path.normpath(str(row.get("storage_path") or "").strip())
                for row in rows
                if str(row.get("storage_path") or "").strip()
            ],
            category=category,
            branch=branch,
        )

    def _db_store_local_file(self, local_path: str, category: str, branch: str | None = None) -> str:
        """
        本地导入只保存到本地 upload/model_files，不写入数据库。
        系统导入才从数据库读取。
        """
        return self._store_local_file_to_upload(local_path, category, branch)

    def _db_delete_file(self, storage_path: str, category: str) -> bool:
        if not is_file_db_configured():
            return False
        try:
            deleted = hard_delete_storage_path(
                storage_path,
                file_type_code=category,
                module_code="model_files",
                facility_code=(self.facility_code or "").strip() or None,
            )
            if deleted:
                return True
            return hard_delete_storage_path(
                storage_path,
                file_type_code=category,
                module_code="special_strategy",
                logical_path=self._legacy_special_strategy_logical_path(category),
                facility_code=(self.facility_code or "").strip() or None,
            )
        except FileBackendError:
            return False

    def _db_logical_path(self, category: str, branch: str | None = None) -> str:
        segment_map = {
            self.CATEGORY_MODEL: "当前模型/结构模型/用户上传",
            self.CATEGORY_COLLAPSE: "当前模型/倒塌分析/结果/用户上传",
            self.CATEGORY_FATIGUE: f"当前模型/疲劳分析/{'输入' if branch == 'input' else '结果'}/用户上传",
        }
        facility = (self.facility_code or "").strip() or "default_facility"
        tail = segment_map.get(category, "当前模型/其他")
        return f"{facility}/{tail}"

    def _legacy_special_strategy_logical_path(self, category: str) -> str:
        segment_map = {
            self.CATEGORY_MODEL: "当前模型/结构模型",
            self.CATEGORY_COLLAPSE: "当前模型/倒塌分析",
            self.CATEGORY_FATIGUE: "当前模型/疲劳分析",
        }
        facility = (self.facility_code or "").strip() or "default_facility"
        tail = segment_map.get(category, "当前模型/其他")
        return f"{facility}/{tail}"

    def _default_model_logical_prefix(self, category: str, branch: str | None = None) -> str:
        facility = (self.facility_code or "").strip() or "default_facility"
        if category == self.CATEGORY_MODEL:
            tail = "当前模型/结构模型"
        elif category == self.CATEGORY_COLLAPSE:
            tail = "当前模型/倒塌分析"
        elif category == self.CATEGORY_FATIGUE:
            tail = f"当前模型/疲劳分析/{'输入' if branch == 'input' else '结果'}" if branch else "当前模型/疲劳分析"
        else:
            tail = "当前模型"
        return f"{facility}/{tail}"

    def _filter_records_by_branch(self, category: str, records: List[str], branch: str | None) -> List[str]:
        if category != self.CATEGORY_FATIGUE or not branch:
            return records
        return [path for path in records if self._fatigue_branch_for_path(path) == branch]

    def _collect_runtime_overrides(self) -> dict:
        def get_text(table: QTableWidget, row: int, col: int) -> str:
            item = table.item(row, col)
            if item is not None:
                user_value = item.data(Qt.UserRole)
                if user_value is not None:
                    return str(user_value).strip()
            return item.text().strip() if item is not None else ""

        def parse_number(text: str, *, integer: bool = False):
            raw = (text or "").strip()
            if raw == "":
                return None
            return int(float(raw)) if integer else float(raw)

        overrides: dict[str, Any] = {}

        model_keys = [
            ("x_angle_deviation", False),
            ("min_leg_od", False),
            ("wp_z", False),
            ("no_legs", True),
        ]
        for row, (key, integer) in enumerate(model_keys):
            value = parse_number(get_text(self.model_param_table, row, 1), integer=integer)
            if value is not None:
                overrides[key] = value

        for row, spec in enumerate(getattr(self, "_risk_param_specs", [])):
            key = str(spec.get("key", "")).strip()
            if not key:
                continue
            raw = get_text(self.risk_param_table, row, 1)
            if spec.get("numeric"):
                value = parse_number(raw, integer=bool(spec.get("integer")))
            else:
                value = raw
            if value not in ("", None):
                overrides[key] = value

        work_points: list[list[float]] = []
        for row in range(self.coord_table.rowCount()):
            x_val = parse_number(get_text(self.coord_table, row, 1))
            y_val = parse_number(get_text(self.coord_table, row, 2))
            if x_val is None and y_val is None:
                continue
            if x_val is None or y_val is None:
                raise ValueError("工作点坐标必须成对填写。")
            work_points.append([x_val, y_val])
        if work_points:
            overrides["work_points"] = work_points

        overrides["rule_overrides"] = normalize_rule_overrides(self._rule_overrides)

        return overrides

    def _collect_runtime_input_overrides(self) -> dict[str, Any]:
        overrides: dict[str, Any] = {}
        model_candidates = self._sorted_existing_paths(self.model_files, category=self.CATEGORY_MODEL)
        if model_candidates:
            overrides["model"] = model_candidates[0]

        collapse_candidates = self._sorted_existing_paths(self.collapse_files, category=self.CATEGORY_COLLAPSE)
        if collapse_candidates:
            overrides["clplog"] = collapse_candidates
        fatigue_result_candidates = self._sorted_existing_paths(
            self.fatigue_result_files,
            category=self.CATEGORY_FATIGUE,
            branch="result",
        )
        fatigue_input_candidates = self._sorted_existing_paths(
            self.fatigue_input_files,
            category=self.CATEGORY_FATIGUE,
            branch="input",
        )
        if fatigue_result_candidates and fatigue_input_candidates:
            overrides["ftglst"] = fatigue_result_candidates
            overrides["ftginp"] = fatigue_input_candidates
        return overrides

    def _fatigue_branch_for_path(self, path: str) -> str:
        normalized = str(path or "").replace("\\", "/").lower()
        filename = os.path.basename(str(path or "")).lower()
        stem = os.path.splitext(filename)[0]
        ext = os.path.splitext(filename)[1].lower()
        if "/疲劳分析/" in normalized and "/输入/" in normalized:
            return "input"
        if stem.startswith("ftginp"):
            return "input"
        if "/疲劳分析/" in normalized and "/结果/" in normalized:
            return "result"
        if stem.startswith("ftglst") or stem.startswith("wvrinp") or ext in {".wit", ".wjt"}:
            return "result"
        if "/疲劳分析/" in normalized:
            return "result"
        return ""

    def _set_fatigue_groups_from_candidates(self, candidates: List[str]) -> None:
        self.fatigue_result_files = []
        self.fatigue_input_files = []
        for raw_path in candidates:
            path = os.path.normpath(str(raw_path or "").strip())
            if not path:
                continue
            branch = self._runtime_fatigue_branch_for_name(path)
            if branch == "input":
                if path not in self.fatigue_input_files:
                    self.fatigue_input_files.append(path)
            elif branch == "result":
                if path not in self.fatigue_result_files:
                    self.fatigue_result_files.append(path)
        self.fatigue_result_files = self._sorted_existing_paths(
            self.fatigue_result_files,
            category=self.CATEGORY_FATIGUE,
            branch="result",
        )
        self.fatigue_input_files = self._sorted_existing_paths(
            self.fatigue_input_files,
            category=self.CATEGORY_FATIGUE,
            branch="input",
        )

    def _fetch_system_files_from_upload(self, category: str, branch: str | None = None) -> List[str]:
        search_roots = []
        for root in [self.upload_root, self.packaged_upload_root]:
            if root and os.path.isdir(root) and root not in search_roots:
                search_roots.append(root)

        if not search_roots:
            return []

        records = []
        code_lower = (self.facility_code or "").strip().lower()

        for search_root in search_roots:
            for dir_path, _, file_names in os.walk(search_root):
                for fn in file_names:
                    full_path = os.path.normpath(os.path.join(dir_path, fn))
                    full_low = full_path.lower()
                    ext_no_dot = os.path.splitext(fn)[1].lower().lstrip(".")
                    stem = os.path.splitext(fn)[0].lower()

                    keep = False
                    score = 0

                    if category == self.CATEGORY_MODEL:
                        name_score = self._sacinp_name_score(fn)
                        if name_score > 0 and self._scan_model_signature(full_path):
                            keep = True
                            score += name_score
                    else:
                        if self._is_runtime_supported_path(full_path, category, branch):
                            keep = True
                            score += 100

                    if not keep:
                        continue

                    if code_lower and code_lower in stem:
                        score += 80
                    if code_lower and code_lower in full_low:
                        score += 120

                    try:
                        mtime = os.path.getmtime(full_path)
                    except OSError:
                        mtime = 0.0
                    records.append((score, mtime, full_path))

        records.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return [p for _, _, p in records]

    def _store_local_file_to_upload(self, local_path: str, category: str, branch: str | None = None) -> str:
        relative_dir = self._db_logical_path(category, branch).replace("/", os.sep)
        target_dir = os.path.join(self.upload_root, relative_dir)
        os.makedirs(target_dir, exist_ok=True)

        base = os.path.basename(local_path)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = os.path.join(target_dir, f"{stamp}_{base}")
        shutil.copy2(local_path, dest)
        return os.path.normpath(dest)

    def _sacinp_name_score(self, file_name: str) -> int:
        name = (file_name or "").strip().lower()
        if not name:
            return 0

        stem, ext = os.path.splitext(name)
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

    def _append_unique_path(self, arr: List[str], path: str):
        raw = str(path or "").strip()
        if not raw:
            return

        p = os.path.normpath(raw)
        if p in (".", ".."):
            return
        if not os.path.isabs(p) and not os.path.exists(p):
            return
        if not os.path.exists(p):
            return

        if p in arr:
            arr.remove(p)
        arr.insert(0, p)

    def _is_usable_path(self, path: str) -> bool:
        raw = str(path or "").strip()
        if not raw:
            return False
        normalized = os.path.normpath(raw)
        if normalized in (".", ".."):
            return False
        return os.path.exists(normalized) or self._is_remote_server_path_for_display(normalized)

    def _remember_file_meta(
            self,
            path: str,
            row: dict[str, Any] | None = None,
            *,
            original_name: str | None = None,
            logical_path: str | None = None,
            display_path: str | None = None,
            remark: str | None = None,
            category_name: str | None = None,
            work_condition: str | None = None,
            modified_at: Any = None,
            branch_label: str | None = None,
            format_label: str | None = None,
            source_label: str | None = None,
    ) -> None:
        normalized = os.path.normpath(str(path or "").strip())
        if not normalized:
            return
        meta = dict(self._file_meta_by_path.get(normalized) or {})
        if row:
            meta.update(
                {
                    "original_name": row.get("original_name"),
                    "logical_path": row.get("logical_path"),
                    "display_path": row.get("display_path"),
                    "remark": row.get("remark"),
                    "category_name": row.get("category_name"),
                    "work_condition": row.get("work_condition"),
                    "modified_at": row.get("source_modified_at") or row.get("uploaded_at") or row.get("updated_at"),
                    "branch_label": row.get("branch_label"),
                    "format_label": row.get("format_label"),
                    "source_label": row.get("source_label"),
                    "storage_path": normalized,
                }
            )
        if original_name:
            meta["original_name"] = original_name
        if logical_path:
            meta["logical_path"] = logical_path
        if display_path:
            meta["display_path"] = display_path
        if remark:
            meta["remark"] = remark
        if category_name:
            meta["category_name"] = category_name
        if work_condition:
            meta["work_condition"] = work_condition
        if modified_at is not None:
            meta["modified_at"] = modified_at
        if branch_label:
            meta["branch_label"] = branch_label
        if format_label:
            meta["format_label"] = format_label
        if source_label:
            meta["source_label"] = source_label
        meta.setdefault("original_name", os.path.basename(normalized))
        meta.setdefault("display_path", self._display_storage_path(normalized))
        meta["storage_path"] = normalized
        self._file_meta_by_path[normalized] = meta

    def _remember_file_rows(self, rows: List[dict[str, Any]]) -> None:
        for row in rows:
            path = os.path.normpath(str(row.get("storage_path") or "").strip())
            if path:
                self._remember_file_meta(path, row=row)

    def _file_meta(self, path: str) -> dict[str, Any]:
        normalized = os.path.normpath(str(path or "").strip())
        return dict(self._file_meta_by_path.get(normalized) or {})

    def _path_format_label(self, path: str) -> str:
        name = os.path.basename(str(path or "")).lower()
        for token in ("ftginp", "ftglst", "wvrinp", "clplog", "clplst", "clprst", "sacinp"):
            if token in name:
                return token.upper()
        suffix = os.path.splitext(name)[1].lstrip(".")
        return suffix.upper() if suffix else ""

    @staticmethod
    def _name_stem(text: str) -> str:
        return os.path.splitext(os.path.basename(str(text or "").strip()).lower())[0]

    def _runtime_fatigue_branch_for_name(self, name: str, logical_path: str = "") -> str:
        stem = self._name_stem(name)
        normalized_logical = str(logical_path or "").replace("\\", "/").lower()
        if stem.startswith("ftginp"):
            return "input"
        if stem.startswith("ftglst"):
            return "result"
        if stem == "ftg" and "/疲劳分析/" in normalized_logical and "/输入/" in normalized_logical:
            return "input"
        if stem == "ftg" and "/疲劳分析/" in normalized_logical and "/结果/" in normalized_logical:
            return "result"
        return ""

    def _is_runtime_supported_name(self, name: str, category: str, branch: str | None = None,
                                   logical_path: str = "") -> bool:
        stem = self._name_stem(name)
        if category == self.CATEGORY_MODEL:
            return stem.startswith("sacinp")
        if category == self.CATEGORY_COLLAPSE:
            return stem.startswith("clplog")
        if category == self.CATEGORY_FATIGUE:
            file_branch = self._runtime_fatigue_branch_for_name(name, logical_path)
            if branch:
                return file_branch == branch
            return file_branch in {"input", "result"}
        return False

    def _is_runtime_supported_path(self, path: str, category: str, branch: str | None = None) -> bool:
        return self._is_runtime_supported_name(path, category, branch)

    def _is_runtime_supported_row(self, row: dict[str, Any], category: str, branch: str | None = None) -> bool:
        logical_path = str(row.get("logical_path") or "")
        name = str(row.get("original_name") or row.get("storage_path") or "").strip()
        return self._is_runtime_supported_name(name, category, branch, logical_path)

    def _path_sort_key(self, path: str) -> tuple[str, str, str]:
        meta = self._file_meta(path)
        return (
            str(meta.get("work_condition") or "").strip().lower(),
            str(meta.get("logical_path") or "").replace("\\", "/").strip().lower(),
            str(meta.get("original_name") or os.path.basename(str(path or ""))).strip().lower(),
        )

    def _is_remote_server_path_for_display(self, path: str) -> bool:
        """C/S 模式下，表格中的 D:/shiyou_file_storage 路径属于服务端路径。

        客户端本机通常无法 os.path.exists，但它仍然是服务端计算可用路径，
        因此不能因为客户端不可访问而从表格和 input_overrides 中过滤掉。
        """
        if not _use_fastapi_backend():
            return False
        text = str(path or "").strip()
        if not text:
            return False
        meta = self._file_meta(text)
        source = str(meta.get("source_label") or meta.get("remark") or "").lower()
        logical = str(meta.get("logical_path") or "").replace("\\", "/")
        return (
            bool(meta)
            or "服务端" in source
            or "server" in source
            or "当前模型" in logical
            or "shiyou_file_storage" in text.replace("\\", "/").lower()
        )

    def _sorted_existing_paths(self, values: List[str], *, category: str, branch: str | None = None) -> List[str]:
        ordered: List[str] = []
        seen: set[str] = set()
        for value in values:
            path = os.path.normpath(str(value or "").strip())
            if not path or path in seen:
                continue
            if not os.path.exists(path) and not self._is_remote_server_path_for_display(path):
                continue
            if not self._is_runtime_supported_path(path, category, branch):
                continue
            seen.add(path)
            ordered.append(path)
        return sorted(ordered, key=self._path_sort_key)

    def _path_modified_text(self, path: str) -> str:
        meta = self._file_meta(path)
        modified_at = meta.get("modified_at")
        if hasattr(modified_at, "strftime"):
            return modified_at.strftime("%Y/%m/%d")
        normalized = os.path.normpath(str(path or "").strip())
        if normalized and os.path.exists(normalized):
            try:
                stamp = datetime.datetime.fromtimestamp(os.path.getmtime(normalized))
                return stamp.strftime("%Y/%m/%d")
            except Exception:
                return ""
        return ""

    def _default_category_label(self, category: str, branch: str | None = None) -> str:
        if category == self.CATEGORY_MODEL:
            return "结构模型文件"
        if category == self.CATEGORY_COLLAPSE:
            return "倒塌分析日志文件"
        if category == self.CATEGORY_FATIGUE and branch == "input":
            return "疲劳分析模型文件"
        if category == self.CATEGORY_FATIGUE:
            return "疲劳分析结果文件"
        return ""

    def _infer_category_from_meta(self, meta: dict[str, Any]) -> str:
        logical_path = str(meta.get("logical_path") or "").replace("\\", "/")
        filename = str(meta.get("original_name") or meta.get("storage_path") or "").strip()
        if self._is_runtime_supported_name(filename, self.CATEGORY_MODEL):
            return self.CATEGORY_MODEL
        if self._is_runtime_supported_name(filename, self.CATEGORY_COLLAPSE):
            return self.CATEGORY_COLLAPSE
        if self._runtime_fatigue_branch_for_name(filename, logical_path):
            return self.CATEGORY_FATIGUE
        return ""

    def _infer_branch_from_meta(self, meta: dict[str, Any]) -> str | None:
        logical_path = str(meta.get("logical_path") or "").replace("\\", "/")
        filename = str(meta.get("original_name") or meta.get("storage_path") or "").strip()
        if self._infer_category_from_meta(meta) != self.CATEGORY_FATIGUE:
            return None
        branch = self._runtime_fatigue_branch_for_name(filename, logical_path)
        return branch or None

    def _file_display_payload(self, path: str, *, category: str, branch: str | None = None) -> dict[str, str]:
        meta = self._file_meta(path)
        return {
            "category": str(meta.get("category_name") or self._default_category_label(category, branch)).strip(),
            "work_condition": str(meta.get("work_condition") or "").strip(),
            "filename": str(meta.get("original_name") or os.path.basename(str(path or ""))).strip(),
            "format": str(meta.get("format_label") or self._path_format_label(path)).strip(),
            "modified": self._path_modified_text(path),
            "remark": str(meta.get("remark") or "").strip(),
        }

    def _display_marks_for_path(self, path: str) -> list[str]:
        meta = self._file_meta(path)
        marks: list[str] = []
        branch_label = str(meta.get("branch_label") or "").strip()
        format_label = str(meta.get("format_label") or "").strip()
        source_label = str(meta.get("source_label") or "").strip()
        if branch_label:
            marks.append(branch_label)
        if format_label:
            marks.append(format_label)
        if source_label:
            marks.append(source_label)
        return marks

    def _friendly_display_name(self, path: str) -> str:
        meta = self._file_meta(path)
        primary = str(meta.get("original_name") or os.path.basename(path or "")).strip()
        marks = self._display_marks_for_path(path)
        if not marks:
            return primary
        return f"{primary}\n{' | '.join(marks)}"

    def _friendly_tooltip(self, path: str) -> str:
        normalized = os.path.normpath(str(path or "").strip())
        meta = self._file_meta(normalized)
        payload = self._file_display_payload(normalized, category=self._infer_category_from_meta(meta),
                                             branch=self._infer_branch_from_meta(meta))
        lines = [f"文件名：{payload['filename']}"]
        if payload["category"]:
            lines.append(f"文件类别：{payload['category']}")
        if payload["work_condition"]:
            lines.append(f"工况：{payload['work_condition']}")
        if payload["format"]:
            lines.append(f"文件格式：{payload['format']}")
        if payload["modified"]:
            lines.append(f"修改时间：{payload['modified']}")
        marks = self._display_marks_for_path(normalized)
        display_path = str(meta.get("display_path") or normalized).strip()
        logical_path = str(meta.get("logical_path") or "").replace("\\", "/").strip().strip("/")
        remark = str(meta.get("remark") or "").strip()
        if marks:
            lines.append(f"标识：{' | '.join(marks)}")
        if display_path:
            lines.append(f"当前路径：{display_path}")
        if logical_path:
            lines.append(f"逻辑路径：{logical_path}")
        if remark:
            lines.append(f"备注：{remark}")
        return "\n".join(lines)

    def _display_name_for_path(self, path: str) -> str:
        meta = self._file_meta(path)
        name = str(meta.get("original_name") or os.path.basename(path or "")).strip()
        logical_path = str(meta.get("logical_path") or "").replace("\\", "/").strip().strip("/")
        if not logical_path:
            return name
        parts = logical_path.split("/")
        tail = "/".join(parts[-2:]) if len(parts) >= 2 else logical_path
        return f"{name}  [{tail}]"

    def _tooltip_for_path(self, path: str) -> str:
        normalized = os.path.normpath(str(path or "").strip())
        meta = self._file_meta(normalized)
        lines = [f"文件名：{str(meta.get('original_name') or os.path.basename(normalized)).strip()}"]
        display_path = str(meta.get("display_path") or normalized).strip()
        logical_path = str(meta.get("logical_path") or "").replace("\\", "/").strip().strip("/")
        remark = str(meta.get("remark") or "").strip()
        if display_path:
            lines.append(f"当前路径：{display_path}")
        if logical_path:
            lines.append(f"逻辑路径：{logical_path}")
        if remark:
            lines.append(f"备注：{remark}")
        return "\n".join(lines)

    def _model_files_helper(self) -> ModelFilesDocsWidget:
        if self._model_files_helper_widget is None:
            self._model_files_helper_widget = ModelFilesDocsWidget()
        self._model_files_helper_widget.set_facility_code(self.facility_code)
        return self._model_files_helper_widget

    def _system_library_allowed_model_keys(self, category: str, branch: str | None = None) -> set[str]:
        if category == self.CATEGORY_COLLAPSE:
            return {"collapse"}
        if category == self.CATEGORY_FATIGUE:
            return {"fatigue"}
        return {"static", "seismic", "fatigue", "collapse", "other"}

    def _system_library_allowed_formats(self, category: str, branch: str | None = None) -> set[str]:
        if category == self.CATEGORY_MODEL:
            return {"sacinp"}
        if category == self.CATEGORY_COLLAPSE:
            return {"clplog"}
        if branch == "input":
            return {"ftginp"}
        return {"ftglst"}

    @staticmethod
    def _system_library_row_sort_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
        work_condition = str(row.get("work_condition") or "").strip().lower()
        logical_path = str(row.get("logical_path") or "").replace("\\", "/").strip().strip("/").lower()
        original_name = str(row.get("original_name") or "").lower()
        uploaded_at = str(row.get("uploaded_at") or "")
        return (work_condition, logical_path, original_name, uploaded_at)

    def _system_library_tree_spec(self, category: str, branch: str | None = None) -> list[dict[str, Any]]:
        helper = self._model_files_helper()
        if category == self.CATEGORY_MODEL:
            spec: list[dict[str, Any]] = []
            for root_name in helper.folder_tree.keys():
                spec.append(
                    {
                        "label": root_name,
                        "children": [
                            {
                                "label": "结构模型",
                                "path_key": root_name,
                                "model_key": "__model_root__",
                            }
                        ],
                    }
                )
            return spec
        allowed_model_keys = self._system_library_allowed_model_keys(category, branch)
        spec: list[dict[str, Any]] = []
        for root_name, root_cfg in helper.folder_tree.items():
            children: list[dict[str, Any]] = []
            for child_name, child_cfg in (root_cfg.get("children") or {}).items():
                model_key = str(child_cfg.get("model_key") or "").strip()
                if model_key not in allowed_model_keys:
                    continue
                children.append(
                    {
                        "label": child_name,
                        "path_key": f"{root_name}/{child_name}",
                        "model_key": model_key,
                    }
                )
            if children:
                spec.append({"label": root_name, "children": children})
        return spec

    def _system_library_rows_for_leaf(
            self,
            path_key: str,
            model_key: str,
            category: str,
            branch: str | None = None,
    ) -> List[dict[str, Any]]:
        helper = self._model_files_helper()
        if category == self.CATEGORY_MODEL and model_key == "__model_root__":
            facility = (self.facility_code or "").strip() or None
            prefix = f"{facility}/{path_key}/结构模型" if facility else f"{path_key}/结构模型"
            rows: List[dict[str, Any]] = []
            seen_ids: set[int] = set()
            for row in list_files_by_prefix(
                    module_code="model_files",
                    logical_path_prefix=prefix,
                    facility_code=facility,
            ):
                row_id = row.get("id")
                if row_id in seen_ids:
                    continue
                name = str(row.get("original_name") or "").lower()
                if not name.startswith("sacinp"):
                    continue
                current = dict(row)
                resolved_path = self._resolve_db_storage_path(current)
                current["storage_path"] = resolved_path
                current["display_path"] = self._display_storage_path(resolved_path)
                current["format_label"] = "SACINP"
                current["source_label"] = f"{path_key} / 结构模型"
                rows.append(current)
                if row_id is not None:
                    seen_ids.add(row_id)
            rows.sort(
                key=lambda item: (
                    item.get("source_modified_at") or item.get("uploaded_at") or item.get("updated_at") or "",
                    str(item.get("original_name") or ""),
                ),
                reverse=True,
            )
            self._remember_file_rows(rows)
            return rows

        # 新逻辑：直接获取文件夹下所有匹配格式的文件，不再受配置行数限制
        allowed_formats = self._system_library_allowed_formats(category, branch)
        rows: List[dict[str, Any]] = []
        seen_ids: set[int] = set()

        # 构建搜索前缀
        facility = (self.facility_code or "").strip() or None
        if category == self.CATEGORY_COLLAPSE:
            prefix = f"{facility}/{path_key}/倒塌分析" if facility else f"{path_key}/倒塌分析"
        elif category == self.CATEGORY_FATIGUE:
            if branch:
                branch_cn = "输入" if branch == "input" else "结果"
                prefix = f"{facility}/{path_key}/疲劳分析/{branch_cn}" if facility else f"{path_key}/疲劳分析/{branch_cn}"
            else:
                prefix = f"{facility}/{path_key}/疲劳分析" if facility else f"{path_key}/疲劳分析"
        else:
            # 其他类型使用原有逻辑
            prefix = f"{facility}/{path_key}" if facility else path_key

        # 直接搜索该前缀下的所有文件
        for row in list_files_by_prefix(
                module_code="model_files",
                logical_path_prefix=prefix,
                facility_code=facility,
        ):
            row_id = row.get("id")
            if row_id in seen_ids:
                continue
            name = str(row.get("original_name") or "").lower()
            fmt = self._format_from_original_name(name)
            if fmt.lower() not in allowed_formats:
                continue
            current = dict(row)
            resolved_path = self._resolve_db_storage_path(current)
            current["storage_path"] = resolved_path
            current["display_path"] = self._display_storage_path(resolved_path)
            current["format_label"] = fmt.upper()
            current["source_label"] = path_key.replace("/", " / ")
            if category == self.CATEGORY_FATIGUE and branch:
                current["branch_label"] = f"疲劳{self._fatigue_branch_label(branch)}"
            rows.append(current)
            if row_id is not None:
                seen_ids.add(row_id)

        rows.sort(
            key=lambda item: (
                item.get("source_modified_at") or item.get("uploaded_at") or item.get("updated_at") or "",
                str(item.get("original_name") or ""),
            ),
            reverse=True,
        )
        self._remember_file_rows(rows)
        return rows

    def _pick_system_library_file(self, category: str, title: str, branch: str | None = None) -> str:
        if is_file_db_configured():
            tree_spec = self._system_library_tree_spec(category, branch)
            if not tree_spec:
                QMessageBox.information(self, "系统导入", "模型文件库中暂无可选文件夹。")
                return ""

            dialog = _SystemLibraryPickerDialog(
                title,
                tree_spec,
                lambda path_key, model_key: self._system_library_rows_for_leaf(path_key, model_key, category, branch),
                parent=self,
            )
            if dialog.exec_() != QDialog.Accepted or not dialog.selected_row:
                return ""

            chosen_row = dict(dialog.selected_row)
            chosen_path = os.path.normpath(str(chosen_row.get("storage_path") or "").strip())

            if not self._is_usable_path(chosen_path):
                QMessageBox.warning(self, "系统导入",
                                    "所选文件记录的物理路径无效，请检查数据库字段 storage_path / stored_name / storage_root。")
                return ""

            self._remember_file_meta(chosen_path, row=chosen_row)
            return chosen_path

        return self._pick_system_file_dialog(category, title, branch)

    def _pick_system_library_files(self, category: str, title: str, branch: str | None = None) -> List[str]:
        if not is_file_db_configured():
            return []

        tree_spec = self._system_library_tree_spec(category, branch)
        if not tree_spec:
            QMessageBox.information(self, "系统导入", "模型文件库中暂无可选文件夹。")
            return []

        dialog = _SystemLibraryPickerDialog(
            title,
            tree_spec,
            lambda path_key, model_key: self._system_library_rows_for_leaf(path_key, model_key, category, branch),
            group_mode=True,
            parent=self,
        )
        if dialog.exec_() != QDialog.Accepted:
            return []

        chosen_rows = sorted(dialog.selected_rows, key=self._system_library_row_sort_key)
        chosen_paths: List[str] = []
        for row in chosen_rows:
            chosen_path = os.path.normpath(str(row.get("storage_path") or "").strip())
            if not self._is_usable_path(chosen_path):
                continue
            self._remember_file_meta(chosen_path, row=row)
            if chosen_path not in chosen_paths:
                chosen_paths.append(chosen_path)
        if not chosen_paths:
            QMessageBox.warning(self, "系统导入", "当前文件夹下没有可用于计算的文件。")
        return chosen_paths

    def _pick_system_file_dialog(self, category: str, title: str, branch: str | None = None) -> str:
        candidate_rows = self._db_fetch_file_rows(category, branch)
        if not candidate_rows:
            QMessageBox.information(self, "系统导入", "系统文件库中暂无可用文件。")
            return ""
        dialog = _SystemFilePickerDialog(title, candidate_rows, self)
        if dialog.exec_() != QDialog.Accepted:
            return ""
        return dialog.selected_path

    def _short_path(self, path: str) -> str:
        try:
            rel = os.path.relpath(path, str(external_root()))
            return rel if len(rel) < 140 else f"...{rel[-140:]}"
        except Exception:
            return path

    def _fit_table_height(self, table: QTableWidget):
        # 这里只处理行高和总高度，不再动列宽
        table.resizeRowsToContents()
        table.doItemsLayout()
        table.updateGeometry()

        total = table.frameWidth() * 2 + 2

        if table.horizontalHeader().isVisible():
            total += table.horizontalHeader().height()

        for r in range(table.rowCount()):
            total += table.rowHeight(r)

        if table.horizontalScrollBar().isVisible():
            total += table.horizontalScrollBar().height()

        table.setFixedHeight(max(total, 42))

    def _fit_table_height_from_current_rows(self, table: QTableWidget):
        table.doItemsLayout()
        table.updateGeometry()

        total = table.frameWidth() * 2 + 2
        if table.horizontalHeader().isVisible():
            total += table.horizontalHeader().height()
        for row in range(table.rowCount()):
            total += table.rowHeight(row)
        if table.horizontalScrollBar().isVisible():
            total += table.horizontalScrollBar().height()
        table.setFixedHeight(max(total, 42))

    def _lock_table_full_display(self, table: QTableWidget, row_height: int = 34, show_header: bool = True):
        table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setVisible(show_header)
        if show_header:
            header_height = max(36, table.horizontalHeader().fontMetrics().height() + 16)
            table.horizontalHeader().setMinimumHeight(max(header_height, table.horizontalHeader().minimumHeight()))
        final_row_height = max(row_height, table.fontMetrics().height() + 16)
        for r in range(table.rowCount()):
            table.setRowHeight(r, final_row_height)
        self._fit_table_height_from_current_rows(table)

    def _remote_row_path(self, row: dict[str, Any]) -> str:
        return os.path.normpath(str(
            row.get("storage_path")
            or row.get("server_path")
            or row.get("path")
            or ""
        ).strip())

    def _apply_remote_strategy_input_rows(self, payload: dict[str, Any]) -> bool:
        files = payload.get("files") if isinstance(payload, dict) else {}
        if not isinstance(files, dict):
            return False

        def rows_for(key: str) -> list[dict[str, Any]]:
            rows = files.get(key) or []
            return [dict(row) for row in rows if isinstance(row, dict)]

        model_rows = rows_for("model")
        collapse_rows = rows_for("collapse")
        fatigue_result_rows = rows_for("fatigue_result")
        fatigue_input_rows = rows_for("fatigue_input")

        all_rows: list[dict[str, Any]] = []
        for row in model_rows:
            row.setdefault("category_name", self._default_category_label(self.CATEGORY_MODEL))
            row.setdefault("format_label", self._path_format_label(self._remote_row_path(row)))
            row.setdefault("source_label", "服务端当前模型")
            all_rows.append(row)
        for row in collapse_rows:
            row.setdefault("category_name", self._default_category_label(self.CATEGORY_COLLAPSE))
            row.setdefault("format_label", self._path_format_label(self._remote_row_path(row)))
            row.setdefault("source_label", "服务端倒塌分析结果")
            all_rows.append(row)
        for row in fatigue_result_rows:
            row.setdefault("category_name", self._default_category_label(self.CATEGORY_FATIGUE, "result"))
            row.setdefault("branch_label", "疲劳结果文件")
            row.setdefault("format_label", self._path_format_label(self._remote_row_path(row)))
            row.setdefault("source_label", "服务端疲劳结果")
            all_rows.append(row)
        for row in fatigue_input_rows:
            row.setdefault("category_name", self._default_category_label(self.CATEGORY_FATIGUE, "input"))
            row.setdefault("branch_label", "疲劳输入文件")
            row.setdefault("format_label", self._path_format_label(self._remote_row_path(row)))
            row.setdefault("source_label", "服务端疲劳输入")
            all_rows.append(row)

        self._remember_file_rows(all_rows)

        self.model_files = [self._remote_row_path(row) for row in model_rows if self._remote_row_path(row)]
        self.collapse_files = [self._remote_row_path(row) for row in collapse_rows if self._remote_row_path(row)]
        self.fatigue_result_files = [self._remote_row_path(row) for row in fatigue_result_rows if self._remote_row_path(row)]
        self.fatigue_input_files = [self._remote_row_path(row) for row in fatigue_input_rows if self._remote_row_path(row)]

        return bool(self.model_files or self.collapse_files or self.fatigue_result_files or self.fatigue_input_files)

    def _reload_system_files_from_backend(self):
        if _use_fastapi_backend():
            try:
                payload = _RemoteStrategyApiClient().load_strategy_input_files(self.facility_code)
                if self._apply_remote_strategy_input_rows(payload):
                    print(
                        "[NewSpecialInspectionPage] remote strategy input files loaded:",
                        "model=", len(self.model_files),
                        "collapse=", len(self.collapse_files),
                        "ftglst=", len(self.fatigue_result_files),
                        "ftginp=", len(self.fatigue_input_files),
                    )
                    self._refresh_files_table()
                    self._refresh_model_preview()
                    return
            except Exception as exc:
                print("[NewSpecialInspectionPage] load remote strategy input files failed:", exc)

        self.model_files = self._db_fetch_file_records(self.CATEGORY_MODEL)
        self._invalidate_rule_preview_cache()
        self._start_rule_preview_preload()
        self.collapse_files = self._db_fetch_file_records(self.CATEGORY_COLLAPSE)
        self._set_fatigue_groups_from_candidates(
            self._db_fetch_file_records(self.CATEGORY_FATIGUE)
        )

        self._refresh_files_table()
        self._refresh_model_preview()

    # ---------------- 文件动态表格刷新与事件 ----------------
    def _set_file_table_row(
            self,
            table: QTableWidget,
            row: int,
            index: int,
            path: str,
            *,
            category: str,
            branch: str | None = None,
    ) -> None:
        payload = self._file_display_payload(path, category=category, branch=branch)
        values = [
            str(index),
            payload["category"],
            payload["work_condition"],
            payload["filename"],
            payload["format"],
            payload["modified"],
            payload["remark"],
        ]
        for col, text in enumerate(values):
            item = QTableWidgetItem(text)
            if col in {0, 1, 2, 4, 5}:
                item.setTextAlignment(Qt.AlignCenter)
            else:
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            if col == 3:
                item.setToolTip(self._friendly_tooltip(path))
            table.setItem(row, col, item)
        table.setRowHeight(row, 40)

    def _insert_empty_hint_row(self, table: QTableWidget, text: str) -> None:
        row = table.rowCount()
        table.insertRow(row)
        table.setSpan(row, 0, 1, table.columnCount())
        empty_widget = QWidget()
        empty_widget.setStyleSheet("background-color: #ffffff;")
        empty_layout = QHBoxLayout(empty_widget)
        empty_layout.setContentsMargins(10, 0, 10, 0)
        empty_label = QLabel(text)
        empty_label.setStyleSheet(
            'color: #666; font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei"; font-size: 12pt;'
        )
        empty_layout.addWidget(empty_label)
        empty_layout.addStretch(1)
        table.setCellWidget(row, 0, empty_widget)
        table.setRowHeight(row, 36)

    def _append_file_section(
            self,
            table: QTableWidget,
            *,
            title: str,
            buttons_info: list[tuple[str, Any]],
            paths: List[str],
            row_map: dict[int, int] | None,
            category: str,
            branch: str | None = None,
            empty_hint: str,
    ) -> None:
        header_row = table.rowCount()
        table.insertRow(header_row)
        table.setSpan(header_row, 0, 1, table.columnCount())
        table.setCellWidget(header_row, 0, self._create_title_row_widget(title, buttons_info))
        table.setRowHeight(header_row, 38)
        if not paths:
            self._insert_empty_hint_row(table, empty_hint)
            return
        for i, path in enumerate(paths, start=1):
            row = table.rowCount()
            table.insertRow(row)
            self._set_file_table_row(table, row, i, path, category=category, branch=branch)
            if row_map is not None:
                row_map[row] = i - 1

    def _refresh_model_files_table(self):
        self._refresh_files_table()

    def _refresh_files_table(self):
        self.files_table.clearSpans()
        self.files_table.clearContents()
        self.files_table.setRowCount(0)

        self._model_row_map = {}
        self._collapse_row_map = {}
        self._fatigue_result_row_map = {}
        self._fatigue_input_row_map = {}

        # 先放模型文件
        self._append_file_section(
            self.files_table,
            title="设置模型文件",
            buttons_info=[
                ("上传", self._on_add_model_local),
                ("删除选中行", self._on_del_model),
            ],
            paths=self.model_files,
            row_map=self._model_row_map,
            category=self.CATEGORY_MODEL,
            empty_hint="暂无选择模型文件。",
        )

        # 再放倒塌
        self._append_file_section(
            self.files_table,
            title="设置倒塌分析结果文件",
            buttons_info=[
                ("上传", self._on_add_collapse_local),
                ("删除选中行", self._on_del_collapse),
            ],
            paths=self.collapse_files,
            row_map=self._collapse_row_map,
            category=self.CATEGORY_COLLAPSE,
            empty_hint="暂无选择倒塌分析结果文件。",
        )

        # 疲劳结果
        self._append_file_section(
            self.files_table,
            title="设置疲劳分析结果文件组",
            buttons_info=[
                ("上传", self._on_add_fatigue_result_local),
                ("删除选中行", self._on_del_fatigue_result),
            ],
            paths=self.fatigue_result_files,
            row_map=self._fatigue_result_row_map,
            category=self.CATEGORY_FATIGUE,
            branch="result",
            empty_hint="暂无选择疲劳分析结果文件。",
        )

        # 疲劳输入
        self._append_file_section(
            self.files_table,
            title="设置疲劳分析输入文件组",
            buttons_info=[
                ("上传", self._on_add_fatigue_input_local),
                ("删除选中行", self._on_del_fatigue_input),
            ],
            paths=self.fatigue_input_files,
            row_map=self._fatigue_input_row_map,
            category=self.CATEGORY_FATIGUE,
            branch="input",
            empty_hint="暂无选择疲劳分析输入文件。",
        )

        self._fit_table_height(self.files_table)
        QTimer.singleShot(0, self._adjust_files_table_widths)

    def _on_add_model_local(self):
        fp, _ = QFileDialog.getOpenFileName(self, "选择模型文件", "", "所有文件 (*.*)")
        if not fp:
            return
        if self._sacinp_name_score(fp) <= 0 or not self._scan_model_signature(fp):
            QMessageBox.warning(self, "导入失败",
                                "当前选择的文件不是可参与计算的结构模型文件，请重新选择 sacinp 模型文件。")
            return
        try:
            system_path = self._db_store_local_file(fp, self.CATEGORY_MODEL)
        except Exception as e:
            QMessageBox.warning(self, "导入失败", f"本地文件入库失败：\n{e}")
            return

        self._remember_file_meta(
            system_path,
            original_name=os.path.basename(fp),
            logical_path=self._db_logical_path(self.CATEGORY_MODEL),
            display_path=self._display_storage_path(system_path),
            category_name=self._default_category_label(self.CATEGORY_MODEL),
            modified_at=datetime.datetime.fromtimestamp(os.path.getmtime(fp)),
            remark="本地导入",
        )
        self._remember_file_meta(
            system_path,
            format_label=self._path_format_label(fp),
            source_label="本地导入",
        )
        self._append_unique_path(self.model_files, system_path)
        self._invalidate_rule_preview_cache()
        self._start_rule_preview_preload()
        self._refresh_model_files_table()
        self._refresh_model_preview()
        QMessageBox.information(self, "本地导入", f"文件已入系统库并显示：\n{system_path}")

    def _on_add_model_sys(self):
        return

    def _on_add_collapse_sys(self):
        return

    def _on_del_model(self):
        selected = self.files_table.selectionModel().selectedRows()
        indexes = sorted(
            {self._model_row_map[idx.row()] for idx in selected if idx.row() in self._model_row_map},
            reverse=True
        )
        if not indexes:
            QMessageBox.warning(self, "提示", "请先在“设置模型文件”区域选中要删除的行。")
            return

        failed = False
        deleted_count = 0
        for idx in indexes:
            if 0 <= idx < len(self.model_files):
                path = self.model_files[idx]
                deleted = self._db_delete_file(path, self.CATEGORY_MODEL)
                if is_file_db_configured() and not deleted:
                    failed = True
                    continue
                del self.model_files[idx]
                deleted_count += 1

        self._invalidate_rule_preview_cache()
        self._refresh_files_table()
        self._refresh_model_preview()
        if failed:
            QMessageBox.warning(self, "警告", "部分文件未能同步更新数据库删除状态，已保留在列表中。")
        elif deleted_count:
            QMessageBox.information(self, "删除成功", "删除成功")

    def _on_add_collapse_local(self):
        fp, _ = QFileDialog.getOpenFileName(self, "选择倒塌分析结果文件", "", "所有文件 (*.*)")
        if not fp:
            return
        if not self._is_runtime_supported_path(fp, self.CATEGORY_COLLAPSE):
            QMessageBox.warning(self, "导入失败", "当前选择的文件不是可参与计算的 clplog 文件，请重新选择。")
            return
        try:
            system_path = self._db_store_local_file(fp, self.CATEGORY_COLLAPSE)
        except Exception as e:
            QMessageBox.warning(self, "导入失败", f"本地文件入库失败：\n{e}")
            return

        self._remember_file_meta(
            system_path,
            original_name=os.path.basename(fp),
            logical_path=self._db_logical_path(self.CATEGORY_COLLAPSE),
            display_path=self._display_storage_path(system_path),
            category_name=self._default_category_label(self.CATEGORY_COLLAPSE),
            modified_at=datetime.datetime.fromtimestamp(os.path.getmtime(fp)),
            remark="本地导入",
        )
        self._remember_file_meta(
            system_path,
            format_label=self._path_format_label(fp),
            source_label="本地导入",
        )
        self._append_unique_path(self.collapse_files, system_path)
        self._refresh_files_table()

    def _on_del_collapse(self):
        selected = self.files_table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.warning(self, "提示", "请先在表格中点击选中要删除的倒塌文件行。")
            return

        rows_to_delete = sorted([idx.row() for idx in selected], reverse=True)
        failed = False
        deleted_count = 0
        for r in rows_to_delete:
            if 1 <= r <= len(self.collapse_files):
                path = self.collapse_files[r - 1]
                deleted = self._db_delete_file(path, self.CATEGORY_COLLAPSE)
                if is_file_db_configured() and not deleted:
                    failed = True
                    continue
                del self.collapse_files[r - 1]
                deleted_count += 1

        self._refresh_files_table()
        if failed:
            QMessageBox.warning(self, "警告", "部分文件未能同步更新数据库删除状态，已保留在列表中。")
        elif deleted_count:
            QMessageBox.information(self, "删除成功", "删除成功")

    def _fatigue_target_list(self, branch: str) -> List[str]:
        return self.fatigue_input_files if branch == "input" else self.fatigue_result_files

    def _fatigue_branch_label(self, branch: str) -> str:
        return "输入文件" if branch == "input" else "结果文件"

    def _on_add_fatigue_local(self, branch: str):
        branch_label = self._fatigue_branch_label(branch)
        fp, _ = QFileDialog.getOpenFileName(self, f"选择疲劳分析{branch_label}", "", "所有文件 (*.*)")
        if not fp:
            return
        actual_branch = self._runtime_fatigue_branch_for_name(fp)
        if actual_branch != branch:
            target_label = "ftginp" if branch == "input" else "ftglst"
            QMessageBox.warning(self, "导入失败",
                                f"当前选择的文件不是可参与计算的 {target_label} 文件，请检查后重新导入。")
            return
        try:
            system_path = self._db_store_local_file(fp, self.CATEGORY_FATIGUE, branch)
        except Exception as e:
            QMessageBox.warning(self, "导入失败", f"本地文件入库失败：\n{e}")
            return

        self._remember_file_meta(
            system_path,
            original_name=os.path.basename(fp),
            logical_path=self._db_logical_path(self.CATEGORY_FATIGUE, branch),
            display_path=self._display_storage_path(system_path),
            category_name=self._default_category_label(self.CATEGORY_FATIGUE, branch),
            modified_at=datetime.datetime.fromtimestamp(os.path.getmtime(fp)),
            remark="本地导入",
        )
        self._remember_file_meta(
            system_path,
            branch_label=f"疲劳{branch_label}",
            format_label=self._path_format_label(fp),
            source_label="本地导入",
        )
        self._append_unique_path(self._fatigue_target_list(branch), system_path)
        self._refresh_files_table()
        QMessageBox.information(self, "本地导入", f"文件已入系统库并显示：\n{system_path}")

    def _on_add_fatigue_sys(self, branch: str):
        branch_label = self._fatigue_branch_label(branch)
        chosen_paths = self._pick_system_library_files(self.CATEGORY_FATIGUE, f"系统导入疲劳分析{branch_label}", branch)
        if not chosen_paths:
            return
        target_list = self._fatigue_target_list(branch)
        target_list[:] = list(chosen_paths)
        self._refresh_files_table()

    def _on_del_fatigue(self, branch: str):
        row_map = self._fatigue_input_row_map if branch == "input" else self._fatigue_result_row_map
        selected = self.files_table.selectionModel().selectedRows()
        indexes = sorted({row_map[idx.row()] for idx in selected if idx.row() in row_map}, reverse=True)
        if not indexes:
            QMessageBox.warning(self, "提示", f"请先在疲劳分析{self._fatigue_branch_label(branch)}区域选中要删除的行。")
            return

        failed = False
        deleted_count = 0
        target_list = self._fatigue_target_list(branch)
        for idx in indexes:
            if 0 <= idx < len(target_list):
                path = target_list[idx]
                deleted = self._db_delete_file(path, self.CATEGORY_FATIGUE)
                if is_file_db_configured() and not deleted:
                    failed = True
                    continue
                del target_list[idx]
                deleted_count += 1

        self._refresh_files_table()
        if failed:
            QMessageBox.warning(self, "警告", "部分疲劳文件未能同步更新数据库删除状态，已保留在列表中。")
        elif deleted_count:
            QMessageBox.information(self, "删除成功", "删除成功")

    def _on_add_fatigue_result_local(self):
        self._on_add_fatigue_local("result")

    def _on_add_fatigue_result_sys(self):
        return

    def _on_add_fatigue_input_sys(self):
        return

    def _on_del_fatigue_result(self):
        self._on_del_fatigue("result")

    def _on_add_fatigue_input_local(self):
        self._on_add_fatigue_local("input")

    def _on_del_fatigue_input(self):
        self._on_del_fatigue("input")

    def _refresh_model_preview(self, *, force_remote: bool = False):
        if not hasattr(self, "model_preview_panel"):
            return

        model_path = ""

        # C/S 远程模式：右侧预览必须使用客户端下载缓存，而不能直接读数据库记录里的服务端 D 盘路径。
        if _use_fastapi_backend():
            model_path = self._download_latest_model_for_preview(force=force_remote)

        # 本地兼容或远程下载失败时，保留原有文件列表兜底。
        if not model_path and self.model_files:
            candidate = os.path.normpath(str(self.model_files[0] or "").strip())
            if self._is_existing_file(candidate):
                model_path = candidate

        history_overlay = {}
        try:
            history_overlay = load_history_detection_overlay(self.facility_code) or {}
        except Exception as exc:
            print("[NewSpecialInspectionPage] load history overlay failed:", exc)
            history_overlay = {}

        if model_path and os.path.exists(model_path):
            if not self._ensure_model_preview_panel():
                return
            self.model_preview_panel.load_model(model_path, target_z=9.1, history_overlay=history_overlay)
        else:
            if getattr(self, "model_preview_panel", None) is not None:
                self.model_preview_panel.clear_model("当前未加载模型文件")
            else:
                self._set_model_preview_placeholder("当前未加载模型文件")

    def _create_title_row_widget(self, title_text: str, buttons_info: list) -> QWidget:
        """创建一个内嵌于表格标题行的自定义 Widget，包含标题文字和对应按钮"""
        w = QWidget()
        w.setStyleSheet("background-color: #ffffff;")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(10, 2, 10, 2)
        lay.setSpacing(8)

        # 左侧标题文本
        lbl = QLabel(title_text)
        lbl.setStyleSheet(
            'font-weight: bold; color: #333; border: none; font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei"; font-size: 12pt;')
        lay.addWidget(lbl)

        # 弹簧，将按钮挤到最右侧
        lay.addStretch(1)

        # 动态添加右侧的按钮
        for btn_text, callback in buttons_info:
            btn = QPushButton(btn_text)
            btn.setFixedHeight(32)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background: #ffffff; 
                    border: 1px solid #b9c6d6; 
                    border-radius: 3px; 
                    padding: 0 12px; 
                    color: #1b2a3a; 
                    font-weight: normal;
                    font-family: "SimSun", "NSimSun", "宋体", "Microsoft YaHei UI", "Microsoft YaHei";
                    font-size: 12pt;
                }
                QPushButton:hover { background: #d9e6f5; }
            """)
            btn.clicked.connect(callback)
            lay.addWidget(btn)

        return w
