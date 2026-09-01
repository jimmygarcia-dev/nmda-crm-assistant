from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any
import re

from services.ollama_client import OllamaClient, OllamaError


@dataclass
class FirstEmailDraft:
    action: str
    subject: str
    body: str
    model: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class FirstEmailAIService:
    """
    Usa Ollama solo para redactar el First Email.

    La decisión de que corresponde FIRST_EMAIL sigue siendo responsabilidad
    del FollowupService (código determinista).
    """

    def __init__(self, ollama: OllamaClient):
        self.ollama = ollama

    def generate(self, lead: dict[str, Any]) -> FirstEmailDraft:
        context = self._build_context(lead)
        prompt = self._build_prompt(context)

        data = self.ollama.generate_json(prompt)

        subject = self._clean_text(data.get("subject"), max_chars=140)

        # Preferimos párrafos estructurados para evitar que el correo llegue
        # como un solo bloque de texto. Mantenemos compatibilidad con "body".
        paragraphs = data.get("paragraphs")
        if isinstance(paragraphs, list):
            body = self._build_body_from_paragraphs(paragraphs)
        else:
            body = self._clean_body(data.get("body"))

        if not subject:
            raise OllamaError("Ollama no generó un asunto utilizable.")
        if not body:
            raise OllamaError("Ollama no generó un cuerpo de correo utilizable.")

        return FirstEmailDraft(
            action="FIRST_EMAIL",
            subject=subject,
            body=body,
            model=self.ollama.model,
        )

    # ------------------------------------------------------------------
    # CONTEXTO
    # ------------------------------------------------------------------

    def _build_context(self, lead: dict[str, Any]) -> dict[str, str]:
        return {
            "company": self._first(
                lead, "accountName", "cCompany", "companyName", "name"
            ),
            "contact_first_name": self._first(lead, "firstName"),
            "contact_full_name": self._first(
                lead, "cFullname", "fullName", "name"
            ),
            "email": self._first(lead, "emailAddress"),
            "website": self._first(lead, "cWebsite", "website"),
            "industry": self._first(lead, "cIndustry", "industry"),
            "description": self._first(
                lead,
                "cCompanydescription",
                "companyDescription",
                "description",
            ),
            "services": self._first(
                lead,
                "cServices",
                "services",
                "leadServices",
            ),
            "target_market": self._first(
                lead,
                "cTargetmarket",
                "targetMarket",
            ),
            "location": self._first(
                lead,
                "cLocation",
                "location",
            ),
            "company_size": self._first(
                lead,
                "cCompanysize",
                "companySize",
            ),
            "event_related": self._first(
                lead,
                "cEventrelated",
                "eventRelated",
            ),
            "recommended_product": self._first(
                lead,
                "cRecommendedproduct",
                "recommendedProduct",
            ),
            "recommendation_reason": self._first(
                lead,
                "cRecommendationreason",
                "recommendationReason",
            ),
            "business_signals": self._first(
                lead,
                "cBusinesssignals",
                "businessSignals",
            ),
            "opportunity_signals": self._first(
                lead,
                "cOpportunitysignals",
                "opportunitySignals",
            ),
            "website_text": self._first(
                lead,
                "cWebsitetext",
                "websiteText",
            ),
        }

    def _build_prompt(self, context: dict[str, str]) -> str:
        compact = {
            key: self._truncate(value, 2800 if key == "website_text" else 700)
            for key, value in context.items()
            if value
        }

        context_json = self._jsonish(compact)

        return f"""
Eres un redactor comercial para NMDA Events.

Tu tarea es redactar el PRIMER correo de prospección para un lead B2B.
El correo será revisado por Jimmy García antes de enviarse.

PRODUCTO
NMDA Events es una plataforma para operación de eventos que puede cubrir:
- registro y RSVP,
- gestión de asistentes,
- check-in,
- acreditaciones,
- comunicación,
- experiencias interactivas,
- métricas en tiempo real.

OBJETIVO
No intentes cerrar una venta. Busca iniciar una conversación y entender cómo
resuelve hoy la empresa la operación de asistentes y qué herramientas utiliza.
El CTA debe ser una demo o llamada breve de 15–20 minutos.

VOZ DE JIMMY
- Escribe siempre en primera persona singular.
- Jimmy es fundador de NMDA Solutions y desarrollador de NMDA Events.
- Nunca digas que Jimmy es "asistente", "representante comercial" o "parte del equipo".
- Evita lenguaje corporativo genérico como "nos complace", "estaríamos encantados",
  "queremos ofrecerle", "optimizar sus procesos", "solución innovadora" o similares.
- Debe sonar como un correo escrito personalmente después de investigar la empresa.

PERSONALIZACIÓN
1. Usa solo 1 o 2 observaciones relevantes del contexto.
2. Sintetiza la información: NO copies listas crudas de servicios, texto separado por
   "|", enumeraciones del CRM ni párrafos completos del website text.
3. No inventes clientes, cifras, cargos, dolores, procesos ni tecnología.
4. La ausencia de información NO significa que la empresa no tenga una plataforma.
5. Si el contexto indica que ya usa o desarrolla tecnología, plantea NMDA Events
   como posible complemento, no como reemplazo.
6. Si hay un primer nombre de contacto confiable, saluda por ese nombre.
   Si no, usa: "Hola equipo de {{empresa}},".

ORTOGRAFÍA Y ESTILO
- Español natural de México, profesional y cercano.
- Revisa ortografía, acentos, concordancia y puntuación antes de responder.
- No uses anglicismos innecesarios salvo términos normales del sector.
- No uses markdown, HTML, viñetas ni emojis.
- Evita frases demasiado largas.
- Aproximadamente 130–190 palabras.

ESTRUCTURA OBLIGATORIA
Devuelve el correo dividido en párrafos, NO como un solo bloque:
1. Saludo.
2. Presentación breve de Jimmy.
3. Observación personalizada sobre la empresa.
4. Qué es NMDA Events y por qué podría tener sentido.
5. Pregunta de descubrimiento.
6. CTA de 15–20 minutos.
7. Cierre.
8. Firma: Jimmy García.

Devuelve EXCLUSIVAMENTE JSON válido:
{{
  "subject": "asunto corto, natural y específico",
  "paragraphs": [
    "Hola equipo de Empresa,",
    "Soy Jimmy García, fundador de NMDA Solutions y desarrollador de NMDA Events.",
    "Párrafo personalizado.",
    "Párrafo sobre NMDA Events.",
    "Párrafo de descubrimiento.",
    "¿Tendrían oportunidad de revisarlo en una llamada de 15–20 minutos?",
    "Quedo atento.",
    "Jimmy García"
  ]
}}

CONTEXTO DEL LEAD
{context_json}
""".strip()

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def _first(self, lead: dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = lead.get(key)
            if value not in (None, "", [], {}):
                return self._normalize(value)
        return ""

    def _normalize(self, value: Any) -> str:
        if isinstance(value, list):
            return " | ".join(str(v).strip() for v in value if str(v).strip())
        if isinstance(value, dict):
            return " | ".join(
                f"{k}: {v}" for k, v in value.items() if v not in (None, "")
            )
        return re.sub(r"\s+", " ", str(value)).strip()

    def _truncate(self, text: str, limit: int) -> str:
        text = text.strip()
        if len(text) <= limit:
            return text
        return text[:limit].rsplit(" ", 1)[0] + "…"

    def _jsonish(self, data: dict[str, str]) -> str:
        # Formato legible para el prompt sin depender de pretty JSON complejo.
        lines = []
        for key, value in data.items():
            safe = value.replace("\n", " ").strip()
            lines.append(f"- {key}: {safe}")
        return "\n".join(lines)

    def _clean_text(self, value: Any, max_chars: int) -> str:
        if value is None:
            return ""
        text = re.sub(r"\s+", " ", str(value)).strip()
        text = text.strip('"').strip()
        return text[:max_chars].strip()

    def _build_body_from_paragraphs(self, paragraphs: list[Any]) -> str:
        cleaned: list[str] = []
        for value in paragraphs:
            paragraph = self._clean_paragraph(value)
            if paragraph:
                cleaned.append(paragraph)
        return "\n\n".join(cleaned).strip()

    def _clean_paragraph(self, value: Any) -> str:
        if value is None:
            return ""
        paragraph = str(value).strip()
        paragraph = re.sub(r"^```(?:text)?\s*", "", paragraph, flags=re.I)
        paragraph = re.sub(r"\s*```$", "", paragraph)
        paragraph = re.sub(r"[ \t]+", " ", paragraph)
        paragraph = re.sub(r"\s*\n\s*", " ", paragraph)
        return paragraph.strip()

    def _clean_body(self, value: Any) -> str:
        """Compatibilidad si el modelo aún regresa un único campo body."""
        if value is None:
            return ""
        body = str(value).strip()
        body = re.sub(r"^```(?:text)?\s*", "", body, flags=re.I)
        body = re.sub(r"\s*```$", "", body)
        raw_paragraphs = re.split(r"\n\s*\n+", body)
        cleaned = [self._clean_paragraph(p) for p in raw_paragraphs]
        cleaned = [p for p in cleaned if p]
        return "\n\n".join(cleaned).strip()
