# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


PROJECT_ROOT = Path(SPECPATH).resolve()
REPORT_MODULE_ROOT = PROJECT_ROOT / 'pages' / 'output_feasibility_analysis_report'
REPORT_SRC_ROOT = REPORT_MODULE_ROOT / 'src'
SPECIAL_STRATEGY_HIDDENIMPORTS = [
    'pages.output_special_strategy.inspection_tool',
    'pages.output_special_strategy.report_jinja2_generator',
]


def _collect_report_hiddenimports() -> list[str]:
    modules: list[str] = []
    if not REPORT_SRC_ROOT.exists():
        return modules

    skipped = {'api_app.py', 'main.py', '__init__.py'}
    for path in sorted(REPORT_SRC_ROOT.rglob('*.py')):
        if path.name in skipped or '__pycache__' in path.parts:
            continue
        rel = path.relative_to(REPORT_SRC_ROOT).with_suffix('')
        modules.append('.'.join(('src', *rel.parts)))
    return modules


# Files listed in datas are copied beside the exe in the one-folder build.
# They stay external to the executable itself.
STATIC_DATAS = [
    ('pict/*.png', 'pict'),
]
EXTERNAL_RESOURCE_DATAS = [
    ('special_strategy_inputs/*', 'special_strategy_inputs'),
    ('pages/output_special_strategy/special_strategy_run_config.json', 'special_strategy_inputs'),
    ('shiyou_db/db_config.json', 'shiyou_db'),
    ('pages/output_feasibility_analysis_report/*.docx', 'output_feasibility_analysis_report'),
    ('pages/output_feasibility_analysis_report/config/*.json', 'output_feasibility_analysis_report/config'),
    ('pages/output_feasibility_analysis_report/config/*.xml', 'output_feasibility_analysis_report/config'),
]
REPORT_HIDDENIMPORTS = _collect_report_hiddenimports()

a = Analysis(
    ['main.py'],
    pathex=[str(PROJECT_ROOT), str(REPORT_MODULE_ROOT)],
    binaries=[],
    datas=STATIC_DATAS + EXTERNAL_RESOURCE_DATAS,
    hiddenimports=[
        'xlrd',
        'openpyxl',
        *REPORT_HIDDENIMPORTS,
        *SPECIAL_STRATEGY_HIDDENIMPORTS,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt6',
        'PySide2',
        'PySide6',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['logo.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='main',  # output folder name
)
