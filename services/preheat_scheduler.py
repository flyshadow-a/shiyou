# -*- coding: utf-8 -*-
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Literal


PreheatStatus = Literal["done", "failed"]


@dataclass(frozen=True)
class PreheatTask:
    name: str
    run: Callable[[], object]


@dataclass(frozen=True)
class PreheatResult:
    name: str
    status: PreheatStatus
    error: str = ""


def run_preheat_tasks(
    tasks: list[PreheatTask],
    *,
    pause_seconds: float = 0.2,
    sleep: Callable[[float], object] = time.sleep,
) -> list[PreheatResult]:
    results: list[PreheatResult] = []
    total = len(tasks)
    for index, task in enumerate(tasks):
        try:
            task.run()
        except Exception as exc:
            results.append(PreheatResult(task.name, "failed", type(exc).__name__))
        else:
            results.append(PreheatResult(task.name, "done"))

        if pause_seconds > 0 and index < total - 1:
            sleep(pause_seconds)
    return results
