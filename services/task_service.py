from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from services.followup_service import add_business_days


@dataclass(frozen=True)
class PlannedTask:
    """Tarea planificada para el siguiente paso de un lead."""

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


_NEXT_TASK = {
    # Enviar el correo de Follow-up #1 => tarea para preparar/enviar Follow-up #2.
    "FOLLOW_UP_1": ("Enviar Follow-up #2", "FOLLOW_UP_2"),
    # Enviar el correo de Follow-up #2 => última etapa: revisar respuesta o reciclaje.
    "FOLLOW_UP_2": ("Revisar respuesta o reciclaje", "RECYCLE"),
}


class TaskPlanner:
    """Genera la tarea del siguiente paso (vencimiento a N días hábiles).

    Los días hábiles no cuentan sábados ni domingos (add_business_days).
    Solo planifica para Follow-up #1 y Follow-up #2.
    """

    def __init__(self, followup_2_days: int = 3, recycle_days: int = 3):
        self.followup_2_days = followup_2_days
        self.recycle_days = recycle_days

    def plan(
        self,
        action: str,
        now: datetime | None = None,
    ) -> PlannedTask:
        now = now or datetime.now()

        if action not in _NEXT_TASK:
            raise ValueError(
                "Solo se planifica una tarea para Follow-up #1 o Follow-up #2."
            )

        name = _NEXT_TASK[action][0]
        label = _NEXT_TASK[action][1]

        if action == "FOLLOW_UP_1":
            days = self.followup_2_days
        else:
            days = self.recycle_days

        start = now.replace(microsecond=0)
        due = add_business_days(start, days).replace(
            hour=18, minute=0, second=0, microsecond=0
        )

        # add_business_days salta sábados y domingos (solo cuenta weekday() < 5):
        # si la fecha original cae de madrugada o fin de semana, el vencimiento
        # terminó igual en un día hábil. OK.
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
    """Idempotencia: ¿ya existe una tarea abierta con ese nombre?"""
    for task in tasks:
        if not is_open_task(task):
            continue
        current = str(task.get("name") or "").strip().lower()
        if current and any(token in current for token in (name.lower(),)):
            return True
    return False