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
        greeting, singular = self._greeting(lead)

        if action == "FOLLOW_UP_1":
            body = self._followup_1(greeting, singular)
        else:
            body = self._followup_2(greeting, singular)

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

    def _greeting(self, lead: dict[str, Any]) -> tuple[str, bool]:
        first_name = str(lead.get("firstName") or "").strip()
        last_name = str(lead.get("lastName") or "").strip()

        # Si EspoCRM tiene nombre de persona, usamos saludo singular.
        if first_name:
            return f"Hola {first_name},", True

        company = (
            str(lead.get("accountName") or "").strip()
            or str(lead.get("cCompany") or "").strip()
            or str(lead.get("name") or "").strip()
            or "equipo"
        )

        # Si "name" parece una persona pero no tenemos firstName, no intentamos
        # adivinar. Mejor un saludo de equipo que equivocarnos.
        return f"Hola equipo de {company},", False

    def _followup_1(self, greeting: str, singular: bool) -> str:
        possessive = "te" if singular else "les"
        demo = "mostrarte" if singular else "mostrarles"

        return f"""{greeting}

Retomo brevemente el correo que {possessive} compartí sobre NMDA Events.

Me interesa conocer cómo gestionan actualmente la parte de registro, asistentes y accesos en sus eventos, y saber si nuestra plataforma podría complementar alguno de esos procesos.

Si hace sentido, con gusto puedo {demo} una demo breve de 15–20 minutos.

Quedo atento.

Saludos,
Jimmy García"""

    def _followup_2(self, greeting: str, singular: bool) -> str:
        possessive = "te" if singular else "les"
        demo = "mostrarte" if singular else "mostrarles"

        return f"""{greeting}

Solo retomo por última vez el correo que {possessive} compartí sobre NMDA Events.

Me parecía interesante explorar si la plataforma podría complementar alguna parte de su operación de eventos, especialmente en registro, asistentes, accesos y comunicación.

Si en este momento no es una prioridad, no hay problema. Si más adelante consideran que puede tener sentido revisarlo, con gusto puedo {demo} una demo breve de 15 minutos.

Quedo atento.

Saludos,
Jimmy García"""
