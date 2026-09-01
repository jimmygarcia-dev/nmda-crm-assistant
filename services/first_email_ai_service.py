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
Eres un asistente comercial de NMDA Events.

Tu tarea es redactar el PRIMER correo de prospección para un lead B2B.
El correo será revisado por una persona antes de enviarse.

PRODUCTO
NMDA Events es una plataforma para operación de eventos que puede cubrir:
- registro y RSVP,
- gestión de asistentes,
- check-in,
- acreditaciones,
- comunicación,
- experiencias interactivas,
- métricas en tiempo real.

OBJETIVO DEL CORREO
No intentes cerrar una venta.
Busca iniciar una conversación y entender cómo resuelve hoy la empresa
la operación de asistentes y qué herramientas utiliza.
El CTA debe ser una demo o llamada breve de 15–20 minutos.

REGLAS IMPORTANTES
1. Escribe en español natural, profesional y humano.
2. No suenes como plantilla ni como correo generado por IA.
3. Usa máximo 1 o 2 observaciones relevantes del contexto.
4. NO copies listas crudas de servicios ni texto separado por "|", comas o bullets.
   Sintetiza y razona la información.
5. No inventes clientes, cifras, cargos, dolores, procesos ni tecnología.
6. La ausencia de información NO significa que la empresa no tenga una plataforma.
7. Si el contexto indica que ya usan/desarrollan tecnología, plantea NMDA Events
   como posible complemento, no como reemplazo.
8. Si hay nombre de contacto confiable, saluda por su primer nombre.
   Si no, usa "Hola equipo de {{empresa}},".
9. Evita frases exageradas como "solución revolucionaria", "transformar su negocio",
   "sé que necesitan", etc.
10. Mantén el cuerpo aproximadamente entre 130 y 190 palabras.
11. No uses markdown, viñetas ni HTML.
12. Firma únicamente:
Jimmy García

Devuelve EXCLUSIVAMENTE un JSON válido con esta estructura:
{{
  "subject": "asunto corto y específico",
  "body": "correo completo"
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

    def _clean_body(self, value: Any) -> str:
        if value is None:
            return ""
        body = str(value).strip()
        body = re.sub(r"^```(?:text)?\s*", "", body, flags=re.I)
        body = re.sub(r"\s*```$", "", body)
        return body.strip()
