from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_ask_yes_no_uses_chinese_button_labels() -> None:
    source = (PROJECT_ROOT / "core" / "message_boxes.py").read_text(encoding="utf-8")

    assert 'setText("是")' in source
    assert 'setText("否")' in source


def test_business_code_uses_chinese_yes_no_helper() -> None:
    allowed_paths = {
        PROJECT_ROOT / "core" / "message_boxes.py",
    }
    offenders = []

    for path in PROJECT_ROOT.rglob("*.py"):
        if path.parts[-2:-1] == ("tests",):
            continue
        if path in allowed_paths:
            continue
        source = path.read_text(encoding="utf-8", errors="ignore")
        if "QMessageBox.question" in source:
            offenders.append(path.relative_to(PROJECT_ROOT).as_posix())

    assert offenders == []
