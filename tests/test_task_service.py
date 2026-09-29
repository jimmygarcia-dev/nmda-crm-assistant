from datetime import datetime

import pytest

from services.task_service import (
    TaskPlanner,
    has_planned_task,
    is_open_task,
)


PLANNER = TaskPlanner(followup_2_days=3, recycle_days=3)


def test_followup_1_creates_followup_2_task_3_business_days_ahead():
    planned = PLANNER.plan("FOLLOW_UP_1", datetime(2026, 9, 4, 15, 0, 0))
    assert planned.name == "Enviar Follow-up #2"
    # Viernes 2026-09-04 + 3 días hábiles => miércoles 2026-09-09 a las 18:00.
    assert planned.date_start.strftime("%Y-%m-%d") == "2026-09-04"
    assert planned.date_end == datetime(2026, 9, 9, 18, 0, 0)


def test_weekend_days_are_not_counted():
    # Sábado 2026-08-29 + 3 días hábiles => miércoles 2026-09-02.
    planned = PLANNER.plan("FOLLOW_UP_1", datetime(2026, 8, 29, 10, 0, 0))
    assert planned.date_end == datetime(2026, 9, 2, 18, 0, 0)


def test_followup_2_creates_review_task():
    planned = PLANNER.plan("FOLLOW_UP_2", datetime(2026, 9, 7, 9, 0, 0))
    assert planned.name == "Revisar respuesta o reciclaje"
    assert planned.label == "RECYCLE"
    assert planned.date_end == datetime(2026, 9, 10, 18, 0, 0)


def test_invalid_action_raises():
    with pytest.raises(ValueError):
        PLANNER.plan("FIRST_EMAIL", datetime(2026, 9, 7, 9, 0, 0))
    with pytest.raises(ValueError):
        PLANNER.plan("RECYCLE", datetime(2026, 9, 7, 9, 0, 0))


def test_planned_to_dict_has_espo_dt_format():
    planned = PLANNER.plan("FOLLOW_UP_1", datetime(2026, 9, 4, 15, 0, 0))
    data = planned.to_dict()
    assert data["dateEnd"] == "2026-09-09 18:00:00"
    assert data["dateStart"] == "2026-09-04 15:00:00"


def test_is_open_task():
    assert is_open_task({"status": "Not Started"})
    assert is_open_task({"status": "In Progress"})
    assert not is_open_task({"status": "Completed"})
    assert not is_open_task({"status": "Canceled"})


def test_has_planned_task_ignores_completed():
    tasks = [{"name": "Enviar Follow-up #2", "status": "Completed"}]
    assert not has_planned_task(tasks, "Enviar Follow-up #2")


def test_has_planned_task_matches_open():
    tasks = [
        {"name": "Enviar Follow-up #2", "status": "Not Started"},
        {"name": "Enviar Follow-up #2", "status": "Completed"},
        {"name": "Otra cosa", "status": "Not Started"},
    ]
    assert has_planned_task(tasks, "Enviar Follow-up #2")
    assert has_planned_task(tasks, "Otra cosa")
    assert not has_planned_task(tasks, "Revisar respuesta")