# -*- coding: utf-8 -*-
from services.preheat_scheduler import PreheatTask, run_preheat_tasks


def test_run_preheat_tasks_executes_tasks_in_order() -> None:
    calls: list[str] = []

    results = run_preheat_tasks(
        [
            PreheatTask("first", lambda: calls.append("first")),
            PreheatTask("second", lambda: calls.append("second")),
        ],
        pause_seconds=0,
    )

    assert calls == ["first", "second"]
    assert [(item.name, item.status) for item in results] == [
        ("first", "done"),
        ("second", "done"),
    ]


def test_run_preheat_tasks_continues_after_failure() -> None:
    calls: list[str] = []

    def fail() -> None:
        calls.append("fail")
        raise RuntimeError("boom")

    results = run_preheat_tasks(
        [
            PreheatTask("bad", fail),
            PreheatTask("good", lambda: calls.append("good")),
        ],
        pause_seconds=0,
    )

    assert calls == ["fail", "good"]
    assert [(item.name, item.status) for item in results] == [
        ("bad", "failed"),
        ("good", "done"),
    ]
    assert results[0].error == "RuntimeError"


def test_run_preheat_tasks_pauses_between_tasks_only() -> None:
    pauses: list[float] = []

    run_preheat_tasks(
        [
            PreheatTask("first", lambda: None),
            PreheatTask("second", lambda: None),
            PreheatTask("third", lambda: None),
        ],
        pause_seconds=0.2,
        sleep=pauses.append,
    )

    assert pauses == [0.2, 0.2]
