# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import os
import sys
import traceback
from pathlib import Path

from PyQt5.QtWidgets import QApplication


def _ensure_project_root_on_path() -> None:
    here = Path(__file__).resolve()
    root = here.parents[1] if here.parent.name == "services" else here.parent
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)


def _atomic_save_qimage(image, target_path: Path) -> str:
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target_path.with_name(f".{target_path.stem}.{os.getpid()}.tmp{target_path.suffix or '.png'}")
    if tmp_path.exists():
        try:
            tmp_path.unlink()
        except Exception:
            pass
    ok = image.save(str(tmp_path), "PNG")
    if not ok:
        raise RuntimeError(f"保存临时图片失败：{tmp_path}")
    os.replace(str(tmp_path), str(target_path))
    return str(target_path)


def _pump_events(app: QApplication, times: int = 4) -> None:
    for _ in range(max(1, int(times))):
        app.processEvents()


def _norm(value: object) -> str:
    return os.path.normpath(str(value or "").strip()) if str(value or "").strip() else ""


def _is_existing_file(path: object) -> bool:
    text = str(path or "").strip()
    return bool(text) and os.path.exists(text) and os.path.isfile(text)


def _project_root() -> Path:
    here = Path(__file__).resolve()
    return here.parents[1] if here.parent.name == "services" else here.parent


def _api_base_url() -> str:
    env_url = os.environ.get("SHIYOU_API_BASE_URL", "").strip()
    if env_url:
        return env_url.rstrip("/")
    cfg_path = _project_root() / "client_config.json"
    if cfg_path.exists():
        try:
            import json
            payload = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
            value = str(payload.get("api_base_url") or "").strip()
            if value:
                return value.rstrip("/")
        except Exception:
            pass
    return "http://127.0.0.1:8000"


def _download_latest_sacinp_from_fastapi(facility_code: str) -> str:
    """客户端辅助导图进程兜底：从 FastAPI 服务端下载当前 sacinp 到本地缓存。"""
    try:
        import requests
    except Exception:
        return ""

    code = str(facility_code or "").strip()
    if not code:
        return ""

    cache_dir = _project_root() / ".client_cache" / "model_files" / code
    cache_dir.mkdir(parents=True, exist_ok=True)
    output_path = cache_dir / "sacinp_from_server"
    tmp_path = output_path.with_name(output_path.name + ".download.tmp")

    try:
        with requests.get(
            f"{_api_base_url()}/api/files/download/latest-model",
            params={"facility_code": code},
            stream=True,
            timeout=300,
        ) as resp:
            resp.raise_for_status()
            with open(tmp_path, "wb") as fp:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        fp.write(chunk)
        tmp_path.replace(output_path)
        return str(output_path) if _is_existing_file(output_path) else ""
    except Exception as exc:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass
        print("[ReportImageExporter] download latest model from FastAPI failed:", exc, flush=True)
        return ""


def _find_client_cached_rebuilt_model(facility_code: str) -> str:
    """客户端兜底查找新增构件后下载/生成的 sacinp.M1。"""
    code = str(facility_code or "").strip()
    if not code:
        return ""

    roots = [
        _project_root() / ".client_cache" / "feasibility" / code,
        _project_root() / "feasibility_assessment_runtime" / code,
        Path.cwd() / ".client_cache" / "feasibility" / code,
        Path.cwd() / "feasibility_assessment_runtime" / code,
    ]

    candidates: list[Path] = []
    for root in roots:
        try:
            if root.exists():
                candidates.extend([p for p in root.rglob("sacinp.M1") if p.is_file()])
                candidates.extend([p for p in root.rglob("*.M1") if p.is_file() and p.name.lower().startswith("sacinp")])
        except Exception:
            continue

    if not candidates:
        return ""

    candidates.sort(key=lambda item: item.stat().st_mtime if item.exists() else 0, reverse=True)
    return str(candidates[0])


def _ensure_usable_model_path(path: object, facility_code: str, *, allow_download: bool = True) -> str:
    text = _norm(path)
    if _is_existing_file(text):
        return text
    if allow_download:
        downloaded = _download_latest_sacinp_from_fastapi(facility_code)
        if _is_existing_file(downloaded):
            return _norm(downloaded)
    return ""


def _resolve_outline_model_bundles(facility_code: str) -> dict[str, dict]:
    """为“生成评估报告”准备原模型/改造后模型。

    - original: 用户最初上传的当前结构模型；
    - rebuilt : 当前仍有效的最新历史改造模型；若不存在，则回退到 original。

    这样：
    1) 旧报告流程仍可使用 rebuilt 作为默认轮廓图；
    2) 同时额外保存 original / rebuilt 两套轮廓图，供新报告模板插图。
    """
    from services.history_rebuild_auto_service import (
        find_latest_active_history_model_bundle,
        find_original_uploaded_model_bundle,
    )

    original = find_original_uploaded_model_bundle(facility_code) or {}
    latest = find_latest_active_history_model_bundle(facility_code) or {}

    original_model = _norm(original.get("model_file"))
    latest_model = _norm(latest.get("model_file")) or original_model

    return {
        "original": {
            "source": original.get("source") or "original",
            "project_id": original.get("project_id"),
            "project_name": original.get("project_name") or "原始模型",
            "model_file": original_model,
        },
        "rebuilt": {
            "source": latest.get("source") or ("history" if latest_model and latest_model != original_model else "original_fallback"),
            "project_id": latest.get("project_id"),
            "project_name": latest.get("project_name") or ("最新改造模型" if latest_model and latest_model != original_model else "原始模型"),
            "model_file": latest_model,
        },
    }


def _load_row_names(
    view,
    facility_code: str,
    context: dict,
    year_label: str,
    app: QApplication,
    model_path_override: str = "",
) -> list[str]:
    view.clear_inspection_overlay()
    view.load_for_facility(
        facility_code=facility_code,
        context=context,
        year_label=year_label,
        row_name="XZ 前",
        model_path_override=model_path_override or None,
    )
    _pump_events(app, times=8)
    row_names = view.available_row_names()
    if not row_names:
        row_names = ["XZ 前", "XZ 后", "YZ 左", "YZ 右"]
    return row_names


def _export_one_image(
    *,
    app: QApplication,
    view,
    facility_code: str,
    run_id: int | None,
    context: dict,
    page_code: str,
    image_type: str,
    year_label: str | None,
    row_name: str,
    overlay: dict | None = None,
    remark: str = "",
    model_path_override: str = "",
    show_level_ii: bool = False,
) -> str:
    from services.special_strategy_image_service import build_strategy_image_path, save_strategy_image_record

    is_risk_image = str(image_type or "").strip() == "elevation_risk"

    view.clear_inspection_overlay()
    if is_risk_image and hasattr(view, "set_show_level_ii"):
        view.set_show_level_ii(bool(show_level_ii))

    view.load_for_facility(
        facility_code=facility_code,
        context=context,
        year_label=year_label or "当前",
        row_name=row_name,
        model_path_override=model_path_override or None,
    )
    if overlay and hasattr(view, "set_inspection_overlay"):
        view.set_inspection_overlay(overlay)

    if is_risk_image and hasattr(view, "set_show_level_ii"):
        view.set_show_level_ii(bool(show_level_ii))

    _pump_events(app, times=8)

    image_path = build_strategy_image_path(
        facility_code=facility_code,
        run_id=run_id,
        page_code=page_code,
        image_type=image_type,
        year_label=year_label,
        row_name=row_name,
    )

    # 使用 SacsElevationRiskView 已存在的 export_current_scene_to_png，避免调用不存在的 capture_current_scene_to_image。
    export_scale = 2.5 if str(image_type or "").startswith("elevation_outline") else 2.0
    saved_path = view.export_current_scene_to_png(str(image_path), scale=export_scale)
    save_strategy_image_record(
        facility_code=facility_code,
        run_id=run_id,
        page_code=page_code,
        image_type=image_type,
        year_label=year_label,
        row_name=row_name,
        image_path=saved_path,
        remark=remark,
    )
    return saved_path


def export_report_images(
    facility_code: str,
    run_id: int | None = None,
    mode: str = "all",
    include_outline: bool | None = None,
    show_level_ii: bool = False,
) -> int:
    """
    导出报告所需立面图片。

    mode:
        outline：只导出轮廓图，对应“生成评估报告”按钮。
        risk   ：只导出风险等级图，对应“生成特检策略报告”按钮。
        all    ：轮廓图 + 风险图，兼容旧调用。

    轮廓图分开保存：
        1. 原模型轮廓图：
           page_code = special_inspection_strategy
           image_type = elevation_outline_original
           用途：特检策略主页快速读取缓存图，避免进入页面实时绘图卡顿。

        2. 改造后轮廓图：
           page_code = feasibility_assessment_results_page
           image_type = elevation_outline_rebuilt
           用途：生成评估报告时插入报告。

    注意：这里不会生成新的 M1 文件，只会读取已有的：
        - 原模型：当前模型目录下的 sacinp.JKnew / sacinp...
        - 改造后模型：最新有效历史改造项目下的 sacinp.M1
    """
    _ensure_project_root_on_path()

    from pages.sacs_elevation_risk_view import SacsElevationRiskView
    from services.special_strategy_services import NodeYearLabelMapper, SpecialStrategyResultService
    from services.special_strategy_inspection_overlay_service import load_strategy_inspection_overlay

    mode = str(mode or "all").strip().lower()
    if mode not in {"all", "outline", "risk"}:
        mode = "all"
    if include_outline is not None and include_outline is False and mode == "all":
        mode = "risk"

    app = QApplication.instance() or QApplication(sys.argv)
    result_service = SpecialStrategyResultService()
    bundle = result_service.load_result_bundle(facility_code, run_id) or {}
    context = bundle.get("context") or {}

    # 轮廓图不需要风险计算结果，允许 context 为空；风险等级图必须有结果上下文。
    if mode in {"risk", "all"} and not context:
        raise RuntimeError(f"当前没有可用的特检结果，无法导出风险等级图：{facility_code}, run_id={run_id}")

    mapper = NodeYearLabelMapper()
    year_labels = mapper.display_labels()

    view = SacsElevationRiskView()
    view.resize(1200, 1200)
    view.showMinimized()
    _pump_events(app)

    outline_bundles = _resolve_outline_model_bundles(facility_code)
    original_bundle = outline_bundles.get("original") or {}
    rebuilt_bundle = outline_bundles.get("rebuilt") or {}

    original_model_path = _ensure_usable_model_path(original_bundle.get("model_file"), facility_code, allow_download=True)

    rebuilt_model_path = _norm(rebuilt_bundle.get("model_file"))
    if not _is_existing_file(rebuilt_model_path):
        cached_rebuilt = _find_client_cached_rebuilt_model(facility_code)
        if _is_existing_file(cached_rebuilt):
            rebuilt_model_path = _norm(cached_rebuilt)
        else:
            rebuilt_model_path = original_model_path

    # 如果数据库中的原始路径在客户端不可访问，上面会自动下载到 .client_cache。
    # 如果新增构件后的 M1 在客户端缓存中不存在，则改造后轮廓图临时回退到原模型，避免报告流程直接中断。
    if not original_model_path and _is_existing_file(rebuilt_model_path):
        original_model_path = rebuilt_model_path

    original_bundle["model_file"] = original_model_path
    rebuilt_bundle["model_file"] = rebuilt_model_path

    original_row_names: list[str] = []
    rebuilt_row_names: list[str] = []
    risk_row_names: list[str] = []

    if mode in {"all", "outline"}:
        if original_model_path and os.path.exists(original_model_path):
            original_row_names = _load_row_names(
                view,
                facility_code,
                context,
                mapper.default_display_label(),
                app,
                model_path_override=original_model_path,
            )
        else:
            print(f"[ReportImageExporter] original model missing: {original_model_path}", flush=True)

        if rebuilt_model_path and os.path.exists(rebuilt_model_path):
            rebuilt_row_names = _load_row_names(
                view,
                facility_code,
                context,
                mapper.default_display_label(),
                app,
                model_path_override=rebuilt_model_path,
            )
        else:
            print(f"[ReportImageExporter] rebuilt model missing: {rebuilt_model_path}", flush=True)

        if not original_row_names and not rebuilt_row_names:
            raise RuntimeError(f"未找到可用于导出轮廓图的结构模型：{facility_code}")

    if mode in {"all", "risk"}:
        risk_probe_model = rebuilt_model_path or original_model_path
        if not _is_existing_file(risk_probe_model):
            risk_probe_model = _ensure_usable_model_path("", facility_code, allow_download=True)
        if _is_existing_file(risk_probe_model):
            risk_row_names = _load_row_names(
                view,
                facility_code,
                context,
                mapper.default_display_label(),
                app,
                model_path_override=risk_probe_model,
            )
        else:
            print("[ReportImageExporter] risk probe model missing; use default row names", flush=True)
            risk_row_names = ["XZ 前", "XZ 后", "YZ 左", "YZ 右"]

    outline_count = len(original_row_names) + len(rebuilt_row_names) if mode in {"all", "outline"} else 0
    risk_count = len(risk_row_names) * len(year_labels) if mode in {"all", "risk"} else 0
    total = outline_count + risk_count
    done = 0
    print(
        f"[ReportImageExporter] start export, mode={mode}, "
        f"show_level_ii={bool(show_level_ii)}, "
        f"original_outline={len(original_row_names)}, rebuilt_outline={len(rebuilt_row_names)}, risk={risk_count}",
        flush=True,
    )

    # A. 原模型轮廓图：只放在特检策略主页专用位置。
    if mode in {"all", "outline"}:
        for row_name in original_row_names:
            _export_one_image(
                app=app,
                view=view,
                facility_code=facility_code,
                run_id=run_id,
                context=context,
                page_code="special_inspection_strategy",
                image_type="elevation_outline_original",
                year_label=None,
                row_name=row_name,
                overlay=None,
                remark=f"生成评估报告前导出：原模型立面轮廓图（{original_bundle.get('project_name') or '原始模型'}），供特检策略主页缓存显示",
                model_path_override=original_model_path,
            )
            done += 1
            print(f"[ReportImageExporter] progress {done}/{total}: original outline {row_name}", flush=True)

        # B. 改造后轮廓图：只放在评估结果/报告专用位置，不再写入 special_inspection_strategy。
        for row_name in rebuilt_row_names:
            _export_one_image(
                app=app,
                view=view,
                facility_code=facility_code,
                run_id=run_id,
                context=context,
                page_code="feasibility_assessment_results_page",
                image_type="elevation_outline_rebuilt",
                year_label=None,
                row_name=row_name,
                overlay=None,
                remark=f"生成评估报告前导出：改造后立面轮廓图（{rebuilt_bundle.get('project_name') or '最新改造模型'}），供评估报告插图使用",
                model_path_override=rebuilt_model_path,
            )
            done += 1
            print(f"[ReportImageExporter] progress {done}/{total}: rebuilt outline {row_name}", flush=True)

    # C. 风险等级图：保持原逻辑。
    if mode in {"all", "risk"}:
        for year_label in year_labels:
            try:
                overlay = load_strategy_inspection_overlay(
                    facility_code,
                    run_id=run_id,
                    display_year=year_label,
                )
            except Exception as exc:
                print(f"[ReportImageExporter] load overlay failed: year={year_label}, err={exc}", flush=True)
                overlay = {}

            for row_name in risk_row_names:
                _export_one_image(
                    app=app,
                    view=view,
                    facility_code=facility_code,
                    run_id=run_id,
                    context=context,
                    page_code="upgrade_special_inspection_result",
                    image_type="elevation_risk",
                    year_label=year_label,
                    row_name=row_name,
                    overlay=overlay,
                    remark=(
                        "生成特检策略报告前导出：更新风险结果页模型立面风险图"
                        f"（{'II/III/IV' if show_level_ii else 'III/IV'}）"
                    ),
                    model_path_override=rebuilt_model_path or original_model_path,
                    show_level_ii=bool(show_level_ii),
                )
                done += 1
                print(f"[ReportImageExporter] progress {done}/{total}: risk {year_label} {row_name}", flush=True)

    try:
        view.close()
        view.deleteLater()
        _pump_events(app)
    except Exception:
        pass

    print("[ReportImageExporter] finished", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Export special strategy report images in a separated process.")
    parser.add_argument("--facility-code", required=True)
    parser.add_argument("--run-id", default="")
    parser.add_argument(
        "--mode",
        choices=["all", "outline", "risk"],
        default="all",
        help="导出模式：all=轮廓图+风险图；outline=只导出轮廓图；risk=只导出风险等级图",
    )
    parser.add_argument("--no-outline", action="store_true", help="兼容旧参数：等价于 --mode risk")
    parser.add_argument("--show-level-ii", action="store_true", help="风险图导出 II/III/IV；默认只导出 III/IV")
    parser.add_argument("--generate-report", action="store_true", help="导出图片后继续生成特检策略报告")
    args = parser.parse_args()

    run_id = None
    text = str(args.run_id or "").strip()
    if text:
        try:
            run_id = int(text)
        except Exception:
            run_id = None

    mode = args.mode
    if args.no_outline and mode == "all":
        mode = "risk"

    try:
        export_report_images(
            facility_code=args.facility_code,
            run_id=run_id,
            mode=mode,
            show_level_ii=bool(args.show_level_ii),
        )
        if args.generate_report:
            _ensure_project_root_on_path()
            from services.special_strategy_services import SpecialStrategyResultService

            report_path = SpecialStrategyResultService().generate_report(args.facility_code, run_id=run_id)
            print(f"[ReportImageExporter] report generated: {report_path}", flush=True)
        return 0
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    # 重要：该脚本在独立子进程中创建 QApplication / QGraphicsView 批量导图。
    # 在部分 Windows + PyQt 环境下，正常 Python 解释器退出时 Qt 对象析构可能触发
    # 0xC0000409 之类的底层崩溃。这里在 main() 已经完成所有导图、写库、生成报告后，
    # 使用 os._exit(code) 直接结束子进程，跳过 Qt/C++ 对象的退出期析构，避免把“已成功生成报告”
    # 误表现为崩溃退出。
    _exit_code = 1
    try:
        _exit_code = int(main() or 0)
    except Exception:
        traceback.print_exc()
        _exit_code = 1
    finally:
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
        os._exit(_exit_code)
