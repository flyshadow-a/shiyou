from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    base = Path(__file__).resolve().parent
    runner = base / "run_sacs_report_from_config.py"
    default_config = base / "wc19_1d_run_config.json"

    if len(sys.argv) > 1:
        config_path = Path(sys.argv[1]).resolve()
    else:
        config_path = default_config

    if not runner.exists():
        raise FileNotFoundError(f"Runner not found: {runner}")
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    cmd = [sys.executable, str(runner), "--config", str(config_path)]
    return subprocess.call(cmd, cwd=str(base.parent.parent))


if __name__ == "__main__":
    raise SystemExit(main())
