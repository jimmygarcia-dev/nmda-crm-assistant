from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any
import re

from services.followup_service import email_datetime, is_sent_email


@dataclass
class EmailDraft:
    action: str
    subject: str
    body: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class EmailDraftService:
    """
    Generador local y determinista de borradores.

    - FIRST_EMAIL usa datos ya existentes en EspoCRM.
    - FOLLOW_UP_1 y FOLLOW_UP_2 usan el historial real del lead.
    - No usa IA.
    - No guarda ni envía nada.
    """

    def __init__(self, our_email: str):
        self.our_email = our_email.strip().lower()

    def generate(
        self,
        lead: dict[str, Any],
        emails: list[dict[str, Any]],
        action: str,
    ) -> EmailDraft:
        if action == "FIRST_EMAIL":
            return self._first_email(lead)

        if action in {"FOLLOW_UP_1", "FOLLOW_UP_2"}:
            subject = self._reply_subject(emails)
            greeting, singular = self._greeting(lead)

            if action == "FOLLOW_UP_1":
                body = self._followup_1(greeting, singular)
            else:
                body = self._followup_2(greeting, singular)

            return EmailDraft(action=action, subject=subject, body=body)

        raise ValueError(
            "Solo se generan borradores para First Email, Follow-up #1 o Follow-up #2."
        )

    # ------------------------------------------------------------------
    # FIRST EMAIL
    # ------------------------------------------------------------------

    def _first_email(self, lead: dict[str, Any]) -> EmailDraft:
        company = self._company_name(lead)
        greeting, _ = self._greeting(lead)

        services = self._first_value(
            lead,
            "cServices",
            "services",
            "leadServices",
            "cLeadservices",
        )
        description = self._first_value(
            lead,
            "cCompanydescription",
            "companyDescription",
            "description",
            "cDescription",
        )
        industry = self._first_value(
            lead,
            "cIndustry",
            "industry",
            "leadIndustry",
        )

        observation = self._observation(company, services, description, industry)

        subject = f"Una idea para complementar la operación de sus eventos"

        body = f"""{greeting}

Soy Jimmy García, fundador de NMDA Solutions y desarrollador de NMDA Events.

{observation}

Estoy desarrollando NMDA Events, una plataforma enfocada en la operación digital del asistente: registro y RSVP, gestión de participantes, check-in, acreditaciones, comunicación, experiencias interactivas y métricas en tiempo real.

Me gustaría conocer cómo gestionan actualmente esta parte de sus eventos y qué herramientas utilizan, para entender si NMDA Events pudiera complementar de alguna manera su operación.

Más que enviarles una propuesta sin conocer sus procesos, me gustaría mostrarles brevemente la plataforma.

¿Tendrían oportunidad de revisarlo en una llamada de 15–20 minutos?

Saludos,
Jimmy García"""

        return EmailDraft(action="FIRST_EMAIL", subject=subject, body=body)

    def _observation(
        self,
        company: str,
        services: str,
        description: str,
        industry: str,
    ) -> str:
        clean_services = self._clean_context(services, 150)
        clean_description = self._clean_context(description, 180)
        clean_industry = self._clean_context(industry, 90)

        if clean_services:
            return (
                f"Estuve revisando el trabajo de {company} y me llamó la atención "
                f"el tipo de servicios que manejan, especialmente {clean_services}."
            )

        if clean_description:
            # Evita repetir un párrafo largo del extractor.
            return (
                f"Estuve revisando el trabajo de {company} y me llamó la atención "
                f"su operación: {clean_description}."
            )

        if clean_industry:
            return (
                f"Estuve revisando el trabajo de {company} dentro de {clean_industry} "
                "y me interesó conocer un poco más sobre cómo gestionan la experiencia "
                "y operación de sus asistentes."
            )

        return (
            f"Estuve revisando el trabajo de {company} y me interesó conocer un poco "
            "más sobre cómo gestionan la parte operativa de sus eventos y asistentes."
        )

    # ------------------------------------------------------------------
    # FOLLOW-UPS
    # ------------------------------------------------------------------

    def _reply_subject(self, emails: list[dict[str, Any]]) -> str:
        sent = [e for e in emails if is_sent_email(e, self.our_email)]
        sent.sort(key=lambda e: email_datetime(e) or 0)

        if not sent:
            return "Re: NMDA Events"

        subject = str(sent[0].get("subject") or "NMDA Events").strip()
        while subject.lower().startswith("re:"):
            subject = subject[3:].strip()

        return f"Re: {subject}"

    def _followup_1(self, greeting: str, singular: bool) -> str:
        shared = "te compartí" if singular else "les compartí"
        demo = "mostrarte" if singular else "mostrarles"

        return f"""{greeting}

Retomo brevemente el correo que {shared} sobre NMDA Events.

Me interesa conocer cómo gestionan actualmente la parte de registro, asistentes y accesos en sus eventos, y saber si nuestra plataforma podría complementar alguno de esos procesos.

Si hace sentido, con gusto puedo {demo} una demo breve de 15–20 minutos.

Quedo atento.

Saludos,
Jimmy García"""

    def _followup_2(self, greeting: str, singular: bool) -> str:
        shared = "te compartí" if singular else "les compartí"
        demo = "mostrarte" if singular else "mostrarles"
        later = "consideras" if singular else "consideran"

        return f"""{greeting}

Solo retomo por última vez el correo que {shared} sobre NMDA Events.

Me parecía interesante explorar si la plataforma podría complementar alguna parte de su operación de eventos, especialmente en registro, asistentes, accesos y comunicación.

Si en este momento no es una prioridad, no hay problema. Si más adelante {later} que puede tener sentido revisarlo, con gusto puedo {demo} una demo breve de 15 minutos.

Quedo atento.

Saludos,
Jimmy García"""

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def _greeting(self, lead: dict[str, Any]) -> tuple[str, bool]:
        first_name = str(lead.get("firstName") or "").strip()

        if first_name:
            return f"Hola {first_name},", True

        company = self._company_name(lead)
        return f"Hola equipo de {company},", False

    def _company_name(self, lead: dict[str, Any]) -> str:
        return (
            str(lead.get("accountName") or "").strip()
            or str(lead.get("cCompany") or "").strip()
            or str(lead.get("companyName") or "").strip()
            or str(lead.get("name") or "").strip()
            or "su empresa"
        )

    def _first_value(self, lead: dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = lead.get(key)
            if value not in (None, "", [], {}):
                if isinstance(value, list):
                    return ", ".join(str(v) for v in value if v)
                return str(value)
        return ""

    def _clean_context(self, value: str, limit: int) -> str:
        if not value:
            return ""

        text = value.strip()
        text = re.sub(r"[\[\]{}\"]", "", text)
        text = re.sub(r"\s+", " ", text)
        text = text.strip(" ,.;:-")

        if len(text) > limit:
            text = text[:limit].rsplit(" ", 1)[0].rstrip(" ,.;:-")

        return text
