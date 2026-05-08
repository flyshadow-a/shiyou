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


def _load_row_names(view, facility_code: str, context: dict, year_label: str, app: QApplication) -> list[str]:
    view.clear_inspection_overlay()
    view.load_for_facility(
        facility_code=facility_code,
        context=context,
        year_label=year_label,
        row_name="XZ 前",
    )
    _pump_events(app)
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
    year_label: str | None,
    row_name: str,
    overlay: dict | None = None,
    remark: str = "",
) -> str:
    from services.special_strategy_image_service import build_strategy_image_path, save_strategy_image_record

    view.clear_inspection_overlay()
    view.load_for_facility(
        facility_code=facility_code,
        context=context,
        year_label=year_label or "当前",
        row_name=row_name,
    )
    if overlay and hasattr(view, "set_inspection_overlay"):
        view.set_inspection_overlay(overlay)

    _pump_events(app)

    image_path = build_strategy_image_path(
        facility_code=facility_code,
        run_id=run_id,
        page_code=page_code,
        image_type="elevation_risk",
        year_label=year_label,
        row_name=row_name,
        create_dirs=True,
    )
    # 只在报告导出子进程中保存图片；页面浏览阶段不保存。
    # 使用 SacsElevationRiskView 已存在的 export_current_scene_to_png，避免调用不存在的 capture_current_scene_to_image。
    _pump_events(app, times=8)
    saved_path = view.export_current_scene_to_png(str(image_path))
    save_strategy_image_record(
        facility_code=facility_code,
        run_id=run_id,
        page_code=page_code,
        image_type="elevation_risk",
        year_label=year_label,
        row_name=row_name,
        image_path=saved_path,
        remark=remark,
    )
    return saved_path


def export_report_images(facility_code: str, run_id: int | None = None, include_outline: bool = True) -> int:
    _ensure_project_root_on_path()

    from pages.sacs_elevation_risk_view import SacsElevationRiskView
    from services.special_strategy_services import NodeYearLabelMapper, SpecialStrategyResultService
    from services.special_strategy_inspection_overlay_service import load_strategy_inspection_overlay

    app = QApplication.instance() or QApplication(sys.argv)
    result_service = SpecialStrategyResultService()
    bundle = result_service.load_result_bundle(facility_code, run_id)
    if not bundle:
        raise RuntimeError(f"当前没有可用的特检结果：{facility_code}, run_id={run_id}")
    context = bundle.get("context") or {}
    if not context:
        raise RuntimeError("结果上下文为空，无法导出报告图片")

    mapper = NodeYearLabelMapper()
    year_labels = mapper.display_labels()

    view = SacsElevationRiskView()
    view.resize(900, 900)
    view.showMinimized()
    _pump_events(app)

    row_names = _load_row_names(view, facility_code, context, mapper.default_display_label(), app)

    total = len(row_names) * len(year_labels) + (len(row_names) if include_outline else 0)
    done = 0
    print(f"[ReportImageExporter] start export, total={total}", flush=True)

    if include_outline:
        for row_name in row_names:
            _export_one_image(
                app=app,
                view=view,
                facility_code=facility_code,
                run_id=run_id,
                context=context,
                page_code="special_inspection_strategy",
                year_label=None,
                row_name=row_name,
                overlay=None,
                remark="生成报告前统一导出：特检策略主页轮廓图",
            )
            done += 1
            print(f"[ReportImageExporter] progress {done}/{total}: outline {row_name}", flush=True)

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

        for row_name in row_names:
            _export_one_image(
                app=app,
                view=view,
                facility_code=facility_code,
                run_id=run_id,
                context=context,
                page_code="upgrade_special_inspection_result",
                year_label=year_label,
                row_name=row_name,
                overlay=overlay,
                remark="生成报告前统一导出：更新风险结果页模型立面风险图",
            )
            done += 1
            print(f"[ReportImageExporter] progress {done}/{total}: {year_label} {row_name}", flush=True)

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
    parser.add_argument("--no-outline", action="store_true")
    parser.add_argument("--generate-report", action="store_true", help="导出图片后继续生成特检策略报告")
    args = parser.parse_args()

    run_id = None
    text = str(args.run_id or "").strip()
    if text:
        try:
            run_id = int(text)
        except Exception:
            run_id = None

    try:
        export_report_images(
            facility_code=args.facility_code,
            run_id=run_id,
            include_outline=not bool(args.no_outline),
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
