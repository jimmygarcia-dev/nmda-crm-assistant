from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from services.followup_service import email_datetime, is_sent_email


@dataclass
class FollowupDraft:
    action: str
    subject: str
    greeting: str
    body: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class FollowupDraftService:
    """
    Generador determinista de borradores.

    No usa IA y no envía nada. Su propósito es quitar trabajo repetitivo
    manteniendo al usuario en control del texto final.
    """

    def __init__(self, our_email: str):
        self.our_email = our_email.strip().lower()

    def generate(
        self,
        lead: dict[str, Any],
        emails: list[dict[str, Any]],
        action: str,
    ) -> FollowupDraft:
        if action not in {"FOLLOW_UP_1", "FOLLOW_UP_2"}:
            raise ValueError("Solo se generan borradores para Follow-up #1 o #2.")

        subject = self._reply_subject(emails)
        greeting = self._greeting(lead)

        if action == "FOLLOW_UP_1":
            body = self._followup_1(greeting)
        else:
            body = self._followup_2(greeting)

        return FollowupDraft(
            action=action,
            subject=subject,
            greeting=greeting,
            body=body,
        )

    def _reply_subject(self, emails: list[dict[str, Any]]) -> str:
        sent = [e for e in emails if is_sent_email(e, self.our_email)]
        sent.sort(key=lambda e: email_datetime(e) or 0)

        if not sent:
            return "Re: NMDA Events"

        # Preferimos el asunto original del hilo, quitando Re: repetidos.
        subject = str(sent[0].get("subject") or "NMDA Events").strip()
        while subject.lower().startswith("re:"):
            subject = subject[3:].strip()

        return f"Re: {subject}"

    def _greeting(self, lead: dict[str, Any]) -> str:
        first_name = str(lead.get("firstName") or "").strip()
        if first_name:
            return f"Hola {first_name},"
        return "Hola,"

    def _followup_1(self, greeting: str) -> str:
        return f"""{greeting}

Retomo brevemente el correo que te compartí sobre NMDA Events.

Quería saber si actualmente gestionan el registro y seguimiento de asistentes con alguna herramienta o si lo llevan internamente.

Si te parece, puedo mostrarte en 15 minutos cómo estamos resolviendo esa parte en NMDA Events.

Saludos,
Jimmy García"""

    def _followup_2(self, greeting: str) -> str:
        return f"""{greeting}

Solo retomo por última vez el correo anterior sobre NMDA Events.

Si la gestión de asistentes y registro de eventos no es algo que estén revisando ahora, no hay problema.

Si en algún momento tiene sentido conocer la plataforma, con gusto podemos conversarlo.

Saludos,
Jimmy García"""
