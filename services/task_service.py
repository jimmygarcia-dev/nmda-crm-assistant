from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from services.followup_service import add_business_days


@dataclass(frozen=True)
class PlannedTask:
    """Planned task for the next step of a lead."""

    name: str
    date_start: datetime
    date_end: datetime
    action: str
    label: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "dateStart": self.date_start.strftime("%Y-%m-%d %H:%M:%S"),
            "dateEnd": self.date_end.strftime("%Y-%m-%d %H:%M:%S"),
            "action": self.action,
            "label": self.label,
        }


_NEXT_TASK_LABEL = {
    "FIRST_EMAIL": "FOLLOW_UP_1",
    "FOLLOW_UP_1": "FOLLOW_UP_2",
    "FOLLOW_UP_2": "RECYCLE",
}


def _format_task_name(action: str, due: datetime) -> str:
    """Format: 'Follow up #1 DD-MM' or 'Follow up #2 DD-MM'."""
    num = "2" if action == "FOLLOW_UP_2" else "1"
    dd_mm = due.strftime("%d-%m")
    return f"Follow up #{num} {dd_mm}"


class TaskPlanner:
    """Generates the next-step task (due in N business days).

    Business days skip weekends (add_business_days).
    Plans the next task after First Email, Follow-up #1, or Follow-up #2.
    """

    def __init__(
        self,
        followup_2_days: int = 3,
        recycle_days: int = 3,
        followup_1_days: int = 3,
    ):
        self.followup_2_days = followup_2_days
        self.recycle_days = recycle_days
        self.followup_1_days = followup_1_days

    def plan(
        self,
        action: str,
        now: datetime | None = None,
    ) -> PlannedTask:
        now = now or datetime.now()

        if action not in _NEXT_TASK_LABEL:
            raise ValueError("Only First Email or Follow-up #1/#2 can be planned.")

        label = _NEXT_TASK_LABEL[action]

        if action == "FIRST_EMAIL":
            days = self.followup_1_days
        elif action == "FOLLOW_UP_1":
            days = self.followup_2_days
        else:
            days = self.recycle_days

        start = now.replace(microsecond=0)
        due = add_business_days(start, days).replace(
            hour=18, minute=0, second=0, microsecond=0
        )

        # add_business_days skips weekends (weekday() < 5):
        # if the start date falls on a weekend, the due date still lands on a business day.
        name = _format_task_name(action, due)
        return PlannedTask(
            name=name,
            date_start=start,
            date_end=due,
            action=action,
            label=label,
        )


def is_open_task(task: dict) -> bool:
    return str(task.get("status") or "").lower() not in {
        "completed",
        "canceled",
        "cancelled",
    }


def has_planned_task(tasks: list[dict], name: str) -> bool:
    """Idempotency: does an open task with this name already exist?"""
    for task in tasks:
        if not is_open_task(task):
            continue
        current = str(task.get("name") or "").strip().lower()
        planned = name.strip().lower()
        stable_prefix = planned
        base, separator, date_suffix = planned.rpartition(" ")
        if (
            separator
            and len(date_suffix) == 5
            and date_suffix[2] == "-"
            and date_suffix[:2].isdigit()
            and date_suffix[3:].isdigit()
        ):
            stable_prefix = base
        if current and (
            current == planned
            or (stable_prefix != planned and current.startswith(stable_prefix + " "))
        ):
            return True
    return False
