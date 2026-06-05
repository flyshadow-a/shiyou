# client_api/api_client.py
from __future__ import annotations

import json
import os
import shutil
import time
import zipfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import requests


def _project_root_dir() -> Path:
    # 当前文件位于 client_api/api_client.py 时，parents[1] 就是项目根目录。
    try:
        return Path(__file__).resolve().parents[1]
    except Exception:
        return Path.cwd()


def _default_base_url() -> str:
    """后端地址读取顺序：环境变量 -> client_config.json -> 127.0.0.1。"""
    env_url = os.environ.get("SHIYOU_API_BASE_URL", "").strip()
    if env_url:
        return env_url.rstrip("/")

    for cfg_path in (
        _project_root_dir() / "client_config.json",
        Path.cwd() / "client_config.json",
    ):
        if not cfg_path.exists():
            continue
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
            value = str(data.get("api_base_url") or "").strip()
            if value:
                return value.rstrip("/")
        except Exception as exc:
            print("[ApiClient] read client_config.json failed:", exc)

    return "http://127.0.0.1:8000"


def _json_safe(value: Any) -> Any:
    """递归转换为 requests.post(json=...) 可序列化对象。"""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        # 保留精度；服务端如果需要数值可再 float/Decimal 转换。
        return str(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(_json_safe(k)): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]

    # 兼容 numpy / pandas 标量。
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return _json_safe(item())
        except Exception:
            pass

    return str(value)


def _filename_from_content_disposition(value: str) -> str:
    text = str(value or "")
    if not text:
        return ""

    # filename*=UTF-8''xxx
    for part in text.split(";"):
        part = part.strip()
        if part.lower().startswith("filename*="):
            raw = part.split("=", 1)[1].strip().strip('"')
            if "''" in raw:
                raw = raw.split("''", 1)[1]
            return unquote(raw)

    # filename="xxx"
    for part in text.split(";"):
        part = part.strip()
        if part.lower().startswith("filename="):
            return part.split("=", 1)[1].strip().strip('"')

    return ""


class ApiClient:
    """
    C/S 分离客户端统一 API。

    覆盖范围：
    - 特检策略：/api/strategy、/api/images、/api/reports
    - 可行性评估：/api/feasibility
    - 模型文件下载：/api/files/download/latest-model、latest-sea
    """

    def __init__(self, base_url: str | None = None, timeout: int = 30):
        self.base_url = str(base_url or _default_base_url()).rstrip("/")
        self.timeout = int(timeout)

    # =========================
    # 基础请求封装
    # =========================
    def _url(self, path: str) -> str:
        text = str(path or "")
        if text.startswith("http://") or text.startswith("https://"):
            return text
        if not text.startswith("/"):
            text = "/" + text
        return f"{self.base_url}{text}"

    def _raise_for_status_with_detail(self, resp: requests.Response, path: str) -> None:
        if resp.status_code < 400:
            return
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text
        raise requests.HTTPError(
            f"后端接口调用失败：{path}\nHTTP {resp.status_code}\n{detail}",
            response=resp,
        )

    def _get_json(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        resp = requests.get(
            self._url(path),
            params=_json_safe(params or {}),
            timeout=timeout or self.timeout,
        )
        self._raise_for_status_with_detail(resp, path)
        try:
            data = resp.json()
        except Exception:
            data = {"text": resp.text}
        return data if isinstance(data, dict) else {"data": data}

    def _post_json(
        self,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        resp = requests.post(
            self._url(path),
            json=_json_safe(payload or {}),
            timeout=timeout or self.timeout,
        )
        self._raise_for_status_with_detail(resp, path)
        try:
            data = resp.json()
        except Exception:
            data = {"text": resp.text}
        return data if isinstance(data, dict) else {"data": data}

    @staticmethod
    def _task_id_from_response(data: dict[str, Any]) -> str:
        if not isinstance(data, dict):
            return ""
        for key in ("task_id", "taskId", "id"):
            value = data.get(key)
            if value not in (None, ""):
                return str(value)
        result = data.get("result")
        if isinstance(result, dict):
            for key in ("task_id", "taskId", "id"):
                value = result.get(key)
                if value not in (None, ""):
                    return str(value)
        return ""

    def _wait_task(
        self,
        getter,
        task_id: str,
        *,
        interval: float = 1.0,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        start = time.time()
        while True:
            task = getter(task_id)
            status = str(task.get("status") or "").lower()
            if status in {"success", "failed", "error", "cancelled", "canceled"}:
                return task
            if timeout_seconds is not None and time.time() - start > timeout_seconds:
                raise TimeoutError(f"等待任务超时：{task_id}")
            time.sleep(max(0.2, float(interval)))

    def _download_file(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        local_output_path: str | Path | None = None,
        default_output_path: str | Path | None = None,
        default_filename: str = "downloaded_file",
        treat_output_path_as_dir: bool = False,
        timeout: int | None = None,
    ) -> str:
        resp = requests.get(
            self._url(path),
            params=_json_safe(params or {}),
            stream=True,
            timeout=timeout or max(self.timeout, 120),
        )
        self._raise_for_status_with_detail(resp, path)

        content_type = str(resp.headers.get("content-type") or "").lower()
        if "application/json" in content_type:
            data = resp.json()
            for key in ("path", "file_path", "local_path", "storage_path", "server_path"):
                value = data.get(key) if isinstance(data, dict) else None
                if value:
                    return str(value)
            raise RuntimeError(f"下载接口返回 JSON，但未包含文件路径：{data}")

        filename = (
            _filename_from_content_disposition(str(resp.headers.get("content-disposition") or ""))
            or default_filename
            or "downloaded_file"
        )

        if local_output_path is not None:
            target = Path(local_output_path)
            if treat_output_path_as_dir or str(local_output_path).endswith(("/", "\\")) or target.is_dir():
                target = target / filename
        elif default_output_path is not None:
            target = Path(default_output_path)
        else:
            target = Path.cwd() / filename

        target = target.expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        temp_path = target.with_name(target.name + ".download.tmp")

        try:
            with open(temp_path, "wb") as fp:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        fp.write(chunk)
            temp_path.replace(target)
        finally:
            try:
                resp.close()
            except Exception:
                pass
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass

        return str(target)

    def _cache_file_path(self, *parts: str, filename: str) -> Path:
        root = _project_root_dir() / ".client_cache"
        for part in parts:
            clean = str(part or "").strip().replace("/", "_").replace("\\", "_")
            if clean:
                root = root / clean
        root.mkdir(parents=True, exist_ok=True)
        return root / filename

    # =========================
    # 基础接口
    # =========================
    def health(self) -> dict[str, Any]:
        return self._get_json("/api/health")

    # =========================
    # 文件下载接口
    # =========================
    def get_latest_model_file(self, facility_code: str) -> dict[str, Any]:
        return self._get_json(
            "/api/files/latest-model",
            params={"facility_code": facility_code},
            timeout=max(self.timeout, 120),
        )

    def download_latest_model_file(
        self,
        facility_code: str,
        local_output_path: str | Path | None = None,
        *,
        output_path: str | Path | None = None,
        cache_dir: str | Path | None = None,
    ) -> str:
        code = str(facility_code or "").strip()
        if not code:
            raise ValueError("facility_code 不能为空")

        if output_path is not None and local_output_path is None:
            local_output_path = output_path

        if cache_dir is not None:
            return self._download_file(
                "/api/files/download/latest-model",
                params={"facility_code": code},
                local_output_path=cache_dir,
                default_filename="sacinp_from_server",
                treat_output_path_as_dir=True,
                timeout=max(self.timeout, 300),
            )

        return self._download_file(
            "/api/files/download/latest-model",
            params={"facility_code": code},
            local_output_path=local_output_path,
            default_output_path=self._cache_file_path("model_files", code, filename="sacinp_from_server"),
            default_filename="sacinp_from_server",
            timeout=max(self.timeout, 300),
        )

    def get_latest_sea_file(self, facility_code: str) -> dict[str, Any]:
        return self._get_json(
            "/api/files/latest-sea",
            params={"facility_code": facility_code},
            timeout=max(self.timeout, 120),
        )

    def download_latest_sea_file(
        self,
        facility_code: str,
        local_output_path: str | Path | None = None,
        *,
        output_path: str | Path | None = None,
        cache_dir: str | Path | None = None,
    ) -> str:
        code = str(facility_code or "").strip()
        if not code:
            raise ValueError("facility_code 不能为空")

        if output_path is not None and local_output_path is None:
            local_output_path = output_path

        if cache_dir is not None:
            return self._download_file(
                "/api/files/download/latest-sea",
                params={"facility_code": code},
                local_output_path=cache_dir,
                default_filename="seainp_from_server",
                treat_output_path_as_dir=True,
                timeout=max(self.timeout, 300),
            )

        return self._download_file(
            "/api/files/download/latest-sea",
            params={"facility_code": code},
            local_output_path=local_output_path,
            default_output_path=self._cache_file_path("model_files", code, filename="seainp_from_server"),
            default_filename="seainp_from_server",
            timeout=max(self.timeout, 300),
        )

    # 旧名称兼容
    download_latest_model = download_latest_model_file
    download_latest_sea = download_latest_sea_file

    # =========================
    # 特检策略接口
    # =========================
    def run_strategy(
        self,
        *,
        facility_code: str,
        param_overrides: dict[str, Any] | None = None,
        input_overrides: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        data = self._post_json(
            "/api/strategy/run",
            {
                "facility_code": facility_code,
                "param_overrides": param_overrides or {},
                "input_overrides": input_overrides or {},
                "metadata": metadata or {},
            },
            timeout=max(self.timeout, 120),
        )
        task_id = self._task_id_from_response(data)
        if not task_id:
            raise RuntimeError(f"特检策略接口未返回 task_id：{data}")
        return task_id

    def check_strategy_manual_fill(
        self,
        *,
        facility_code: str,
        param_overrides: dict[str, Any] | None = None,
        input_overrides: dict[str, Any] | None = None,
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
            timeout=max(self.timeout, 120),
        )

    def get_strategy_task(self, task_id: str) -> dict[str, Any]:
        return self._get_json(f"/api/strategy/tasks/{task_id}", timeout=max(self.timeout, 120))

    def wait_strategy_task(
        self,
        task_id: str,
        interval: float = 1.0,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        return self._wait_task(self.get_strategy_task, task_id, interval=interval, timeout_seconds=timeout_seconds)

    def get_strategy_result(
        self,
        facility_code: str,
        run_id: int | None = None,
        *,
        compact: bool = False,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"compact": "true" if compact else "false"}
        if run_id:
            params["run_id"] = int(run_id)
        return self._get_json(
            f"/api/strategy/result/{facility_code}",
            params=params,
            timeout=max(self.timeout, 120),
        )

    def export_images(
        self,
        *,
        facility_code: str,
        run_id: int | None = None,
        mode: str = "risk",
        show_level_ii: bool = False,
    ) -> str:
        data = self._post_json(
            "/api/images/export",
            {
                "facility_code": facility_code,
                "run_id": run_id,
                "mode": mode,
                "show_level_ii": bool(show_level_ii),
            },
            timeout=max(self.timeout, 120),
        )
        task_id = self._task_id_from_response(data)
        if not task_id:
            raise RuntimeError(f"图片导出接口未返回 task_id：{data}")
        return task_id

    def get_image_task(self, task_id: str) -> dict[str, Any]:
        return self._get_json(f"/api/images/tasks/{task_id}", timeout=max(self.timeout, 120))

    def wait_image_task(
        self,
        task_id: str,
        interval: float = 1.0,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        return self._wait_task(self.get_image_task, task_id, interval=interval, timeout_seconds=timeout_seconds)

    def generate_report(
        self,
        *,
        facility_code: str,
        run_id: int | None = None,
        metadata: dict[str, Any] | None = None,
        output_path: str | None = None,
        generate_pdf: bool = True,
        pdf_timeout_seconds: int = 300,
    ) -> str:
        data = self._post_json(
            "/api/reports/generate",
            {
                "facility_code": facility_code,
                "run_id": run_id,
                "metadata": metadata or {},
                "output_path": output_path,
                "generate_pdf": bool(generate_pdf),
                "pdf_timeout_seconds": int(pdf_timeout_seconds),
            },
            timeout=max(self.timeout, 120),
        )
        task_id = self._task_id_from_response(data)
        if not task_id:
            raise RuntimeError(f"报告生成接口未返回 task_id：{data}")
        return task_id

    def get_report_task(self, task_id: str) -> dict[str, Any]:
        return self._get_json(f"/api/reports/tasks/{task_id}", timeout=max(self.timeout, 120))

    def wait_report_task(
        self,
        task_id: str,
        interval: float = 1.0,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        return self._wait_task(self.get_report_task, task_id, interval=interval, timeout_seconds=timeout_seconds)

    def download_report_task(
        self,
        task_id: str,
        local_output_path: str | Path,
        *,
        file_type: str = "docx",
    ) -> str:
        suffix = ".pdf" if str(file_type).lower() == "pdf" else ".docx"
        target = Path(local_output_path)
        if target.suffix.lower() != suffix:
            target = target.with_suffix(suffix)
        return self._download_file(
            f"/api/reports/tasks/{task_id}/download",
            params={"file_type": file_type},
            local_output_path=target,
            default_filename=f"report_{task_id}{suffix}",
            timeout=max(self.timeout, 300),
        )

    # =========================
    # 可行性评估：创建新模型
    # =========================
    def create_feasibility_model(
        self,
        *,
        facility_code: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        data = self._post_json(
            "/api/feasibility/model/create",
            {
                "facility_code": facility_code,
                "metadata": metadata or {},
            },
            timeout=max(self.timeout, 120),
        )
        task_id = self._task_id_from_response(data)
        if not task_id:
            raise RuntimeError(f"创建新模型接口未返回 task_id：{data}")
        return task_id

    def get_feasibility_model_task(self, task_id: str) -> dict[str, Any]:
        return self._get_json(f"/api/feasibility/model/tasks/{task_id}", timeout=max(self.timeout, 120))

    def wait_feasibility_model_task(
        self,
        task_id: str,
        interval: float = 1.0,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        return self._wait_task(
            self.get_feasibility_model_task,
            task_id,
            interval=interval,
            timeout_seconds=timeout_seconds,
        )

    # 旧名称兼容
    create_model = create_feasibility_model
    get_create_model_task = get_feasibility_model_task
    wait_create_model_task = wait_feasibility_model_task

    # =========================
    # 可行性评估：计算分析
    # =========================
    def run_feasibility(
        self,
        *,
        facility_code: str,
        analysis_mode: str = "auto",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        data = self._post_json(
            "/api/feasibility/run",
            {
                "facility_code": facility_code,
                "analysis_mode": analysis_mode or "auto",
                "metadata": metadata or {},
            },
            timeout=max(self.timeout, 120),
        )
        task_id = self._task_id_from_response(data)
        if not task_id:
            raise RuntimeError(f"可行性分析接口未返回 task_id：{data}")
        return task_id

    def run_feasibility_analysis(
        self,
        *,
        facility_code: str,
        analysis_mode: str = "auto",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        return self.run_feasibility(
            facility_code=facility_code,
            analysis_mode=analysis_mode,
            metadata=metadata,
        )

    # 旧名称兼容
    run_analysis = run_feasibility

    def get_feasibility_task(self, task_id: str) -> dict[str, Any]:
        return self._get_json(f"/api/feasibility/tasks/{task_id}", timeout=max(self.timeout, 120))

    def wait_feasibility_task(
        self,
        task_id: str,
        interval: float = 1.0,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        return self._wait_task(
            self.get_feasibility_task,
            task_id,
            interval=interval,
            timeout_seconds=timeout_seconds,
        )

    def get_feasibility_result(self, facility_code: str, run_id: int | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if run_id:
            params["run_id"] = int(run_id)
        return self._get_json(
            f"/api/feasibility/result/{facility_code}",
            params=params,
            timeout=max(self.timeout, 120),
        )

    # =========================
    # 可行性评估：导出服务端生成文件
    # =========================
    def export_feasibility_files(
        self,
        *,
        facility_code: str,
        analysis_mode: str = "auto",
        include_model_files: bool = True,
        include_result_file: bool = True,
    ) -> str:
        data = self._post_json(
            "/api/feasibility/files/export",
            {
                "facility_code": facility_code,
                "analysis_mode": analysis_mode or "auto",
                "include_model_files": bool(include_model_files),
                "include_result_file": bool(include_result_file),
            },
            timeout=max(self.timeout, 120),
        )
        task_id = self._task_id_from_response(data)
        if not task_id:
            raise RuntimeError(f"可行性文件导出接口未返回 task_id：{data}")
        return task_id

    def get_feasibility_export_task(self, task_id: str) -> dict[str, Any]:
        return self._get_json(f"/api/feasibility/files/tasks/{task_id}", timeout=max(self.timeout, 120))

    def wait_feasibility_export_task(
        self,
        task_id: str,
        interval: float = 1.0,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        return self._wait_task(
            self.get_feasibility_export_task,
            task_id,
            interval=interval,
            timeout_seconds=timeout_seconds,
        )

    def download_feasibility_export_file(
        self,
        task_id: str,
        local_output_path: str | Path,
    ) -> str:
        return self._download_file(
            f"/api/feasibility/files/tasks/{task_id}/download",
            local_output_path=local_output_path,
            default_filename=f"feasibility_files_{task_id}.zip",
            timeout=max(self.timeout, 300),
        )

    # 旧名称兼容
    get_feasibility_files_task = get_feasibility_export_task
    get_feasibility_file_task = get_feasibility_export_task
    wait_feasibility_files_task = wait_feasibility_export_task
    wait_feasibility_file_task = wait_feasibility_export_task
    download_feasibility_files_task = download_feasibility_export_file
    download_feasibility_file_task = download_feasibility_export_file

    def export_feasibility_files_and_extract(
        self,
        *,
        facility_code: str,
        analysis_mode: str = "auto",
        local_output_dir: str | Path,
        include_model_files: bool = True,
        include_result_file: bool = True,
    ) -> list[str]:
        output_dir = Path(local_output_dir).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)

        task_id = self.export_feasibility_files(
            facility_code=facility_code,
            analysis_mode=analysis_mode,
            include_model_files=include_model_files,
            include_result_file=include_result_file,
        )
        task = self.wait_feasibility_export_task(task_id, interval=1.0)
        if str(task.get("status") or "").lower() != "success":
            raise RuntimeError(str(task.get("error") or task.get("message") or "服务端导出文件失败"))

        zip_path = self.download_feasibility_export_file(
            task_id,
            output_dir / f"feasibility_files_{task_id}.zip",
        )
        zip_path_obj = Path(zip_path)
        if not zip_path_obj.exists():
            raise FileNotFoundError(f"服务端导出文件下载失败：{zip_path}")

        if not zipfile.is_zipfile(zip_path_obj):
            return [str(zip_path_obj)]

        # 清理旧解压目录，避免 stale 文件干扰本次结果。
        extract_dir = output_dir / f"extract_{task_id}"
        if extract_dir.exists():
            shutil.rmtree(extract_dir, ignore_errors=True)
        extract_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path_obj, "r") as zf:
            zf.extractall(extract_dir)

        extracted: list[str] = []
        for path in extract_dir.rglob("*"):
            if path.is_file():
                extracted.append(str(path))
        extracted.sort()
        return extracted

    # =========================
    # 可行性评估：报告生成/下载
    # =========================
    def generate_feasibility_report(
        self,
        *,
        facility_code: str,
        run_id: int | None = None,
        report_payload: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        output_path: str | None = None,
    ) -> str:
        data = self._post_json(
            "/api/feasibility/report/generate",
            {
                "facility_code": facility_code,
                "run_id": run_id,
                "report_payload": report_payload or {},
                "metadata": metadata or {},
                "output_path": output_path,
            },
            timeout=max(self.timeout, 120),
        )
        task_id = self._task_id_from_response(data)
        if not task_id:
            raise RuntimeError(f"可行性报告生成接口未返回 task_id：{data}")
        return task_id

    def get_feasibility_report_task(self, task_id: str) -> dict[str, Any]:
        return self._get_json(f"/api/feasibility/report/tasks/{task_id}", timeout=max(self.timeout, 120))

    def wait_feasibility_report_task(
        self,
        task_id: str,
        interval: float = 1.0,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        return self._wait_task(
            self.get_feasibility_report_task,
            task_id,
            interval=interval,
            timeout_seconds=timeout_seconds,
        )

    def download_feasibility_report(
        self,
        task_id: str,
        local_output_path: str | Path,
    ) -> str:
        return self._download_file(
            f"/api/feasibility/report/tasks/{task_id}/download",
            local_output_path=local_output_path,
            default_filename=f"feasibility_report_{task_id}.pdf",
            timeout=max(self.timeout, 300),
        )
