from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
import re

from services.ollama_client import OllamaClient, OllamaError


@dataclass
class FirstEmailDraft:
    action: str
    subject: str
    body: str
    model: str
    qualified: bool
    confidence: float
    signal: str
    sales_angle: str
    reason_to_contact: str
    contact_strategy: str
    evidence: list[dict[str, str]]
    relevance: str
    cta_type: str
    mention_product: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FirstEmailAIService:
    """Califica la oportunidad y redacta un primer correo con Ollama."""

    def __init__(self, ollama: OllamaClient):
        self.ollama = ollama

    def generate(self, lead: dict[str, Any]) -> FirstEmailDraft:
        context = self._build_context(lead)
        analysis = self.ollama.generate_json(self._build_analysis_prompt(context))
        evidence = self._validated_evidence(analysis.get("evidence"), context)
        strategy_data = self.ollama.generate_json(
            self._build_strategy_prompt(context, evidence)
        )
        strategy = self._contact_strategy(strategy_data.get("cta_type"), evidence)

        # El redactor solo recibe evidencia literal verificada, no el resto del
        # perfil del lead. Esto reduce la posibilidad de inventar verticales,
        # clientes, procesos o tipos de evento.
        writing_context = {
            "company": context["email_company"],
            "greeting": context["greeting"],
            "evidence": evidence,
            "sales_angle": self._clean_text(strategy_data.get("sales_angle"), 300),
            "relevance": self._clean_text(strategy_data.get("relevance"), 500),
            "question": self._clean_text(strategy_data.get("question"), 300),
            "opening_angle": self._clean_text(strategy_data.get("opening_angle"), 300),
            "contact_strategy": strategy,
            "mention_product": bool(evidence) and (
                self._evidence_level(evidence) != "weak"
                or any(item["source"] == "contact_title" for item in evidence)
            ),
            "product_variant": self._product_variant(context, evidence),
        }
        data = self.ollama.generate_json(self._build_prompt(writing_context))

        subject = self._clean_text(data.get("subject"), max_chars=140)
        # El cuerpo se compone desde evidencia verificada. Dejar que el LLM lo
        # redacte libremente producía mensajes casi idénticos o preguntas ajenas
        # al dato del lead (p. ej. selección de asistentes).

        signal = self._clean_text(analysis.get("signal"), max_chars=600)
        sales_angle = writing_context["sales_angle"]
        reason = self._clean_text(strategy_data.get("reason_to_contact"), max_chars=600)
        relevance = writing_context["relevance"]
        confidence = self._confidence(analysis.get("confidence"))
        qualified = analysis.get("qualified")

        if not isinstance(qualified, bool):
            raise OllamaError("Ollama debe indicar qualified como booleano.")
        if not evidence:
            qualified = False
            signal = signal or "No se encontró evidencia específica de eventos en los datos del lead."
            sales_angle = sales_angle or "confirmar si gestionan registro de asistentes"
            reason = reason or "La información disponible no confirma su relación con eventos."
            relevance = relevance or "Aún hace falta confirmar si la operación de eventos es relevante."
        else:
            sales_angle = sales_angle or "operación de registro y asistentes"
            signal = signal or evidence[0]["text"]
            reason = reason or "La evidencia del lead justifica una pregunta de descubrimiento."
            relevance = relevance or "La actividad descrita puede relacionarse con la gestión de asistentes."
        if not subject:
            raise OllamaError("Ollama no generó un asunto utilizable.")
        body = self._compose_safe_body(
            context, evidence, strategy,
            writing_context["mention_product"], writing_context["question"],
        )
        self._validate_draft(body, evidence)

        return FirstEmailDraft(
            action="FIRST_EMAIL",
            subject=subject,
            body=body,
            model=self.ollama.model,
            qualified=qualified,
            confidence=confidence,
            signal=signal,
            sales_angle=sales_angle,
            reason_to_contact=reason,
            contact_strategy=strategy,
            evidence=evidence,
            relevance=relevance,
            cta_type="qualification" if strategy == "qualification" else strategy,
            mention_product=writing_context["mention_product"],
        )

    def _build_context(self, lead: dict[str, Any]) -> dict[str, str]:
        first_name = self._first(lead, "firstName")
        company = self._first(lead, "accountName", "cCompany", "companyName")
        contact_title = self._first(lead, "title")
        # Algunos imports colocan el puesto del lead en el campo de empresa.
        # No usar ese texto como si fuera una razón social.
        company_contains_title = bool(company and (
            (contact_title and company.casefold() == contact_title.casefold())
            or re.search(
                r"\b(productor|productora|coordinador|coordinadora|director|directora)\b.*\b(eventos?)\b",
                company,
                re.I,
            )
        ))
        if company_contains_title:
            if not contact_title:
                contact_title = company
        if not self._looks_like_person_name(first_name, company):
            first_name = ""
        return {
            "company": company,
            "email_company": "" if company_contains_title else company,
            "company_reliable": "false" if company_contains_title else "true",
            "contact_first_name": first_name,
            "contact_title": contact_title,
            "greeting": f"Hola {first_name}," if first_name else "Hola,",
            "email": self._first(lead, "emailAddress"),
            "website": self._first(lead, "cWebsite", "website"),
            "industry": self._first(lead, "cIndustry", "industry"),
            "description": self._first(
                lead, "cCompanydescription", "companyDescription", "description"
            ),
            "services": self._first(lead, "cServices", "services", "leadServices"),
            "target_market": self._first(lead, "cTargetmarket", "targetMarket"),
            "location": self._first(lead, "cLocation", "location"),
            "company_size": self._first(lead, "cCompanysize", "companySize"),
            "event_related": self._first(lead, "cEventrelated", "eventRelated"),
            "operational_signals": self._first(
                lead, "cOperationalSignals", "operationalSignals"
            ),
            "website_signals": self._first(
                lead, "cWebsiteSignals", "websiteSignals"
            ),
            "research_evidence": self._first(
                lead, "cResearchEvidence", "researchEvidence"
            ),
            "research_summary": self._first(
                lead, "cResearchSummary", "researchSummary"
            ),
            "research_status": self._first(lead, "cResearchStatus", "researchStatus"),
            "research_confidence": self._first(
                lead, "cResearchConfidence", "researchConfidence"
            ),
            "qualification_reason": self._first(
                lead, "cQualificationReason", "qualificationReason"
            ),
            "qualification_opportunity": self._first(
                lead, "cQualificationOpportunity", "qualificationOpportunity"
            ),
            "qualification_fit": self._first(
                lead, "cQualificationFit", "qualificationFit"
            ),
            "qualification_status": self._first(
                lead, "cQualificationStatus", "qualificationStatus"
            ),
            "agent_reason": self._first(lead, "cAgentReason", "agentReason"),
            "agent_decision": self._first(lead, "cAgentDecision", "agentDecision"),
            "agent_next_action": self._first(
                lead, "cAgentNextAction", "agentNextAction"
            ),
            "agent_relationship": self._first(
                lead, "cAgentRelationship", "agentRelationship"
            ),
            "business_score": self._first(
                lead, "cBusinessscore", "cBusinessScore", "businessScore"
            ),
            "opportunity_score": self._first(
                lead, "cOpportunityScore", "opportunityScore"
            ),
            "icp_fit_score": self._first(lead, "cICPFitScore", "icpFitScore"),
            "commercial_capacity": self._first(
                lead, "cCommercialCapacity", "commercialCapacity"
            ),
            "sales_readiness": self._first(lead, "cSalesReadiness", "salesReadiness"),
            "contact_priority": self._first(
                lead, "cContactPriority", "contactPriority"
            ),
            "is_b2b": self._first(lead, "cIsB2B", "isB2B"),
            "campaign_goal": self._first(lead, "cCampaignGoal", "campaignGoal"),
            "campaign_category": self._first(
                lead, "cCampaignCategory", "campaignCategory"
            ),
            "recommended_product": self._first(
                lead, "cRecommendedproduct", "recommendedProduct"
            ),
            "recommendation_reason": self._first(
                lead, "cRecommendationReason", "cRecommendationreason", "recommendationReason"
            ),
            "business_signals": self._first(
                lead, "cBusinessSignals", "cBusinesssignals", "businessSignals"
            ),
            "opportunity_signals": self._first(
                lead, "cOpportunitySignals", "cOpportunitysignals", "opportunitySignals"
            ),
            "website_text": self._first(lead, "cWebsitetext", "websiteText"),
        }

    def _build_analysis_prompt(self, context: dict[str, str]) -> str:
        sources = {
            key: self._truncate(value, 2800 if key == "website_text" else 900)
            for key, value in context.items()
            if value and key not in {
                "company", "contact_first_name", "greeting", "email", "website",
                "location", "company_size", "research_status", "research_confidence",
                "qualification_fit", "qualification_opportunity", "agent_relationship",
                "campaign_category", "qualification_status", "agent_decision",
                "agent_next_action", "business_score", "opportunity_score",
                "icp_fit_score", "commercial_capacity", "sales_readiness",
                "contact_priority", "is_b2b",
            }
        }
        return f"""
Actúas como analista de prospección B2B. Esta etapa NO redacta correo.
Determina si los datos sustentan que NMDA Events pueda ser relevante.

NMDA Events gestiona registro/RSVP, asistentes, check-in, acreditaciones,
comunicación y métricas de eventos.

REGLAS
- No infieras tipos de evento, clientes, procesos, problemas ni resultados.
- Cada evidencia debe ser una cita textual breve copiada exactamente de uno de
  los campos provistos, junto con el nombre exacto del campo.
- Da prioridad a research_evidence, website_signals, business_signals,
  operational_signals, services, description y website_text. Industry puede ser
  solo una señal débil: úsala para discovery, nunca para afirmar servicios concretos
  ni justificar una demo. Trata summaries,
  recommendations, qualification y agent fields como pistas, no como hechos
  independientes si no existe una cita verificable.
- Si no hay texto explícito relacionado con eventos o asistentes, devuelve
  evidence=[] y qualified=false. No conviertas la industria genérica en señal.
- confidence es certeza cualitativa de 0 a 1, no probabilidad estadística.

Devuelve exclusivamente JSON válido:
{{
  "qualified": true,
  "confidence": 0.0,
  "evidence": [{{"source": "services", "text": "cita textual exacta"}}],
  "signal": "resumen estrictamente sustentado por evidence"
}}

DATOS DEL LEAD
{self._jsonish(sources)}
""".strip()

    def _build_strategy_prompt(
        self, context: dict[str, str], evidence: list[dict[str, str]]
    ) -> str:
        evidence_text = "\n".join(
            f'- {item["source"]}: "{item["text"]}"' for item in evidence
        ) or "(Sin evidencia textual específica.)"
        return f"""
Eres estratega de prospección B2B de NMDA Solutions. No escribas el correo.
Decide una estrategia a partir exclusivamente de las citas verificadas.

EVIDENCIA
{evidence_text}

EMPRESA: {context["email_company"] or "(sin nombre de empresa confiable)"}

SEPARA HECHO E INFERENCIA
- La evidencia debe seguir siendo un hecho; no la adornes ni agregues contexto.
- relevance puede ser una hipótesis prudente: explica por qué la actividad podría
  relacionarse con registro o seguimiento de asistentes, sin atribuir un problema.
- opening_angle debe señalar cuál dato concreto conviene mencionar. Si la única
  evidencia es genérica (por ejemplo, "producción de eventos"), dilo de forma
  honesta; no simules haber investigado formatos, clientes o proyectos concretos.
- question debe ser UNA sola pregunta comercial que ayude a saber cómo resuelven
  esa operación. No combines preguntas.
- sales_angle debe limitarse a una capacidad de NMDA Events.
- mention_product puede ser false si nombrar NMDA todavía haría el correo genérico.
- cta_type: qualification si no hay evidencia; discovery si sabemos que trabajan
  con eventos; demo solo si la cita menciona directamente registro, asistentes o
  check-in.
- reason_to_contact explica por qué vale la pena escribirles, no que Jimmy quiera
  investigar el mercado o mejorar su estrategia.

Devuelve exclusivamente JSON válido:
{{
  "relevance": "hipótesis comercial prudente",
  "opening_angle": "dato concreto que se debe destacar",
  "sales_angle": "una capacidad de NMDA Events",
  "question": "una sola pregunta comercial",
  "mention_product": false,
  "cta_type": "discovery",
  "reason_to_contact": "razón comercial concreta"
}}
""".strip()

    def _build_prompt(self, context: dict[str, Any]) -> str:
        evidence_text = "\n".join(
            f'- {item["source"]}: "{item["text"]}"' for item in context["evidence"]
        ) or "(No hay evidencia específica; formula una pregunta para confirmar si gestionan eventos.)"
        return f"""
Eres redactor de prospección B2B de NMDA Solutions. Redacta un primer correo que
inicie una conversación comercial concreta. No lo conviertas en encuesta ni pidas
una demo por rutina.

NMDA EVENTS
Plataforma para gestionar operación de eventos: registro y RSVP, asistentes,
check-in, acreditaciones, comunicación y métricas.

HECHOS DEL PROSPECTO (ÚNICA FUENTE PERMITIDA)
{evidence_text}
Relevancia comercial posible: {context["relevance"] or "explorar si existe encaje"}.
Ángulo: {context["sales_angle"] or "registro y seguimiento de asistentes"}.
CTA: {context["contact_strategy"]}.
Menciona NMDA Events: {"sí" if context["mention_product"] else "no"}.
Enfoque de apertura sugerido: {context["opening_angle"] or "menciona únicamente el hecho citado"}.
Pregunta planeada (usa exactamente una pregunta comercial basada en esto): {context["question"] or "¿Cómo gestionan actualmente el registro y seguimiento de asistentes?"}

No agregues hechos sobre la empresa fuera de las citas. Puedes expresar la
relevancia como hipótesis prudente ("me interesa conocer cómo resuelven..."),
pero nunca digas que tienen un problema, que necesitan automatizar o que usan
procesos/herramientas que no están citados. No extrapoles de "eventos" a galas,
congresos, convenciones o marcas. No digas que escribes para mejorar tu estrategia
ni pidas información sin valor comercial para NMDA Events.

PERSONALIZACIÓN Y VOZ
Escribe como Jimmy García, fundador de NMDA Solutions, en primera persona.
Español natural de México, directo, profesional y humano. Elige el dato más
distintivo y concreto de la evidencia; si hay varios, puedes combinar dos que
formen una observación natural. No repitas la misma secuencia de frases en todos
los correos. Explica por qué esa actividad conecta con el registro/seguimiento de
asistentes como una posibilidad, no como un problema que atribuyes al prospecto.
Haz exactamente una pregunta en todo el correo. No agregues una segunda pregunta
de seguimiento. Entre 65 y
105 palabras. Solo menciona NMDA Events si el indicador anterior dice sí; si lo
mencionas, di en una frase sencilla qué hace y no enumeres funcionalidades.

CTA proporcional: demo puede invitar a 15 minutos solo con evidencia directa de
registro/asistentes/check-in. discovery hace solo la pregunta útil sobre el
proceso; no agregues una invitación de demo. qualification pregunta si gestionan
directamente registro/asistentes; no agregues demo. No uses "si hay encaje", "si te parece relevante",
"si consideras que", "estaré encantado", "estaríamos encantados",
"soluciones integrales", "solución eficiente", "podemos ayudarte" ni "presentarte
nuestra solución". qualification se usa
solo sin evidencia: pregunta si gestionan directamente registro/asistentes; no
afirmes que trabajan con eventos. Si la evidencia menciona otra plataforma,
pregunta cómo les funciona y presenta NMDA, si se menciona, como posible
complemento o comparación; nunca como reemplazo asumido.

SALUDO DETERMINISTA
El sistema ya decidió el saludo. Empieza el cuerpo EXACTAMENTE con:
{context.get("greeting", "Hola,")}
No agregues otro saludo ni cambies el nombre. No uses el nombre de empresa como
nombre de persona. El nombre confiable de la empresa es: {context.get("company", "")}

Genera únicamente un asunto breve, específico y natural (sin cuerpo del correo).
Devuelve exclusivamente JSON válido con este esquema:
{{
  "subject": "asunto breve y específico"
}}
""".strip()

    def _validated_evidence(
        self, raw_evidence: Any, context: dict[str, str]
    ) -> list[dict[str, str]]:
        if not isinstance(raw_evidence, list):
            raw_evidence = []
        allowed_sources = {
            "business_signals", "opportunity_signals", "recommendation_reason",
            "services", "description", "target_market", "website_text",
            "research_evidence", "website_signals", "operational_signals",
            "research_summary", "qualification_reason", "agent_reason",
            "qualification_opportunity", "campaign_goal", "industry", "contact_title",
        }
        valid = self._extract_evidence_from_crm(context)
        for item in raw_evidence:
            if not isinstance(item, dict):
                continue
            source = self._clean_text(item.get("source"), 80)
            quote = self._clean_text(item.get("text"), 500)
            source_value = context.get(source, "") if source in allowed_sources else ""
            if quote and source_value and self._normalize_quote(quote) in self._normalize_quote(source_value):
                if not any(existing["text"].casefold() == quote.casefold() for existing in valid):
                    valid.append({"source": source, "text": quote})
        return valid[:4]

    def _extract_evidence_from_crm(
        self, context: dict[str, str]
    ) -> list[dict[str, str]]:
        """Extract direct event-related snippets without depending on LLM quoting."""
        priorities = (
            "research_evidence", "website_signals", "business_signals",
            "operational_signals", "services", "description", "website_text",
            "research_summary", "recommendation_reason", "qualification_reason",
            "agent_reason", "qualification_opportunity", "campaign_goal", "target_market",
            "industry", "contact_title",
        )
        event_terms = (
            "evento", "eventos", "congreso", "congresos", "convención",
            "convenciones", "convencion", "feria", "festival", "concierto",
            "reunión", "reunion", "lanzamiento", "producción", "produccion",
            "planificación", "planificacion", "registro", "asistentes", "check-in",
            "acreditación", "experiencias de marca", "activación de marca",
            "fiesta", "fiestas", "celebración", "celebraciones",
        )
        specific_terms = (
            "congreso", "convención", "convencion", "feria", "festival", "concierto",
            "reunión", "reunion", "lanzamiento",
            "experiencias de marca", "activación de marca",
            "registro", "asistentes", "check-in", "acreditación",
        )
        candidates: list[tuple[int, int, str, str]] = []
        for priority, source in enumerate(priorities):
            value = context.get(source, "")
            if not value:
                continue
            chunks = re.split(
                r"(?:\s*[|;]\s*|(?<=[.!?])\s+|\r?\n+|\bver\s+m[aá]s\b)",
                value,
                flags=re.I,
            )
            for chunk in chunks:
                quote = re.sub(r"\s+", " ", chunk).strip(" .;,:|-\t")
                lowered = quote.casefold()
                if len(quote) < 4 or not any(term in lowered for term in event_terms):
                    continue
                labels = re.findall(
                    r"(?:convenciones|congresos|conciertos|ferias|festivales|"
                    r"lanzamientos|activaciones|eventos políticos|eventos corporativos)",
                    quote,
                    flags=re.I,
                )
                if labels and source != "contact_title":
                    for label in labels:
                        candidates.append((-2, priority, source, label))
                    continue
                specificity = sum(term in lowered for term in specific_terms)
                candidates.append((-specificity, priority, source, quote[:500]))
        candidates.sort()
        result: list[dict[str, str]] = []
        seen: set[str] = set()
        for _, _, source, quote in candidates:
            key = quote.casefold()
            if key in seen:
                continue
            seen.add(key)
            result.append({"source": source, "text": quote})
            if len(result) == 4:
                break
        return result

    def _normalize_quote(self, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip().casefold()

    def _contact_strategy(self, requested: Any, evidence: list[dict[str, str]]) -> str:
        allowed = {"discovery", "demo", "qualification"}
        strategy = str(requested or "qualification").strip().casefold()
        if not evidence:
            return "qualification"
        if strategy not in allowed:
            strategy = "discovery"
        if all(item["source"] == "contact_title" for item in evidence):
            return "discovery"
        level = self._evidence_level(evidence)
        text = " ".join(item["text"] for item in evidence).casefold()
        if level == "weak":
            return "qualification"
        if level == "direct":
            has_registration = any(term in text for term in ("registro", "rsvp", "check-in", "check in"))
            has_attendees = any(term in text for term in ("asistente", "asistencia", "acreditación", "acreditacion"))
            has_checkin = any(term in text for term in ("check-in", "check in", "acceso", "control de acceso"))
            if strategy == "demo" and has_registration and has_attendees and has_checkin:
                return "demo"
            return "discovery"
        # Categorías de eventos prueban actividad, pero no que gestionen el
        # registro. Por eso la primera pregunta debe averiguar quién lo opera.
        return "discovery"

    def _evidence_level(self, evidence: list[dict[str, str]]) -> str:
        """Classify evidence by what it proves: event category vs. operations."""
        if not evidence:
            return "none"
        text = " ".join(item["text"] for item in evidence).casefold()
        weak_sources = {"industry", "contact_title"}
        if all(item["source"] in weak_sources for item in evidence):
            return "weak"
        direct_terms = (
            "registro de asistentes", "registro y rsvp", "registro y check-in",
            "gestión de asistentes", "gestion de asistentes", "gestiona asistentes",
            "check-in", "check in", "acreditación", "acreditacion", "rsvp",
            "control de acceso", "eventbrite", "cvent", "swoogo", "hubilo",
            "bizzabo", "eventtia", "meetmaps", "whova",
        )
        if any(term in text for term in direct_terms):
            return "direct"
        attendance_only = (
            "participación en eventos", "participacion en eventos", "participó en eventos",
            "participado en eventos", "asistió a eventos", "asistio a eventos",
            "attended events", "participated in events",
        )
        if any(term in text for term in attendance_only):
            return "weak"
        return "strong"

    def _product_variant(
        self, context: dict[str, str], evidence: list[dict[str, str]]
    ) -> str:
        """Choose controlled copy variants consistently per lead, without freeform LLM copy."""
        seed = "|".join((context.get("company", ""), *(item["text"] for item in evidence)))
        return ("A", "B", "C")[sum(ord(char) for char in seed) % 3]

    def _validate_draft(self, body: str, evidence: list[dict[str, str]]) -> None:
        body_lower = body.casefold()
        evidence_lower = " ".join(item["text"] for item in evidence).casefold()
        generic_phrases = (
            "empresa líder", "soluciones integrales", "solución integral",
            "solución eficiente", "solución innovadora", "optimizar tus procesos",
            "optimizar sus procesos", "transformar la forma", "estaríamos encantados",
            "estaré encantado", "nos complace", "podemos ayudarte",
            "mejorar nuestra estrategia", "mejorar la eficiencia operativa",
            "puede mejorar la eficiencia operativa", "mejorar tu flujo de trabajo",
            "si hay encaje", "si te parece relevante", "si consideras que",
            "presentarte nuestra solución", "presentarle nuestra solución",
        )
        for phrase in generic_phrases:
            if phrase in body_lower:
                raise OllamaError(f"El borrador contiene lenguaje comercial genérico: {phrase}")

        specific_terms = (
            "gala", "galas", "congreso", "congresos", "convención", "convenciones",
            "feria", "ferias", "festival", "festivales", "boda", "bodas",
            "concierto", "conciertos", "reunión", "reuniones", "lanzamiento",
            "fiesta", "fiestas", "celebración", "celebraciones",
        )
        unsupported = [term for term in specific_terms if term in body_lower and term not in evidence_lower]
        if unsupported:
            raise OllamaError(
                "El borrador incluye un tipo de evento sin evidencia: " + unsupported[0]
            )

    def _apply_strategy_constraints(
        self, body: str, strategy: dict[str, Any]
    ) -> str:
        paragraphs: list[str] = []
        for paragraph in body.split("\n\n"):
            kept = []
            for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
                lowered = sentence.casefold()
                if not strategy["mention_product"] and "nmda events" in lowered:
                    continue
                is_demo_invite = any(
                    marker in lowered
                    for marker in ("15 minutos", "llamada breve", "puedo mostrar", "te muestro", "demo de")
                )
                if is_demo_invite and strategy["contact_strategy"] != "demo":
                    continue
                kept.append(sentence)
            paragraph_text = " ".join(kept).strip()
            if paragraph_text:
                paragraphs.append(paragraph_text)
        return "\n\n".join(paragraphs)

    def _sanitize_unsupported_claims(
        self, body: str, evidence: list[dict[str, str]]
    ) -> str:
        evidence_text = " ".join(item["text"] for item in evidence).casefold()
        risky_claims = (
            "en el pasado", "en los últimos años", "en los ultimos años",
            "en años recientes", "ha producido", "han producido", "produjo eventos",
            "participó en eventos", "participado en eventos", "participa en eventos",
            "participación en eventos", "participacion en eventos",
            "eventos de la industria", "evento corporativo", "eventos corporativos",
            "lanzamiento de producto", "lanzamientos de producto", "experiencias de marca",
            "captación de leads", "captacion de leads", "generación de leads",
            "generacion de leads", "prospección de clientes", "prospeccion de clientes",
            "clientes potenciales", "captación de clientes", "captacion de clientes",
            "necesidad de mejorar", "necesitan mejorar",
            "necesitas mejorar", "desafíos", "desafios", "retos principales",
            "problemas de", "mejorar la eficiencia", "mejorar la experiencia",
            "mejorar tu flujo de trabajo", "puede mejorar", "si hay encaje",
            "me lleva a creer", "proceso sólido", "proceso solido", "gran experiencia",
            "todo tipo de eventos", "captar nuevos clientes", "atraer nuevos asistentes",
            "si te parece relevante", "si consideras que", "soluciones integrales",
            "solución eficiente", "solucion eficiente", "estaríamos encantados",
            "estaremos encantados", "mejorar nuestra estrategia",
            "empresa líder", "soluciones integrales", "solución integral",
            "solución innovadora", "optimizar tus procesos", "optimizar sus procesos",
            "transformar la forma", "nos complace", "podemos ayudarte",
            "presentarte nuestra solución", "presentarle nuestra solución",
            "gala", "galas", "congreso", "congresos", "convención", "convenciones",
            "feria", "ferias", "festival", "festivales", "boda", "bodas",
            "concierto", "conciertos", "reunión", "reuniones", "lanzamiento",
        )
        paragraphs: list[str] = []
        for paragraph in body.split("\n\n"):
            kept = []
            for sentence in re.split(r"(?<=[.!?])\s+", paragraph):
                lowered = sentence.casefold()
                if any(claim in lowered and claim not in evidence_text for claim in risky_claims):
                    continue
                kept.append(sentence)
            paragraph_text = " ".join(kept).strip()
            if paragraph_text:
                paragraphs.append(paragraph_text)
        return "\n\n".join(paragraphs)

    def _remove_indirect_duplicate_question(self, body: str) -> str:
        if not re.search(r"¿[^?]*\?", body):
            return body
        indirect = re.compile(
            r"\b(me interesa|quisiera|quiero|me gustaría|me gustaria)\s+(?:conocer|saber)\s+c[oó]mo\b",
            re.I,
        )
        paragraphs = []
        for paragraph in body.split("\n\n"):
            sentences = re.split(r"(?<=[.!?])\s+", paragraph)
            kept = [sentence for sentence in sentences if not indirect.search(sentence)]
            if kept:
                paragraphs.append(" ".join(kept).strip())
        return "\n\n".join(paragraphs)

    def _ensure_single_question(
        self,
        body: str,
        planned_question: str,
        evidence: list[dict[str, str]],
        strategy: str,
    ) -> str:
        # La pregunta la define la etapa de estrategia; descartamos las preguntas
        # del redactor para evitar duplicados o preguntas de encuesta.
        clean_body = re.sub(r"¿[^?]*\?", "", body)
        clean_body = re.sub(r"\n{3,}", "\n\n", clean_body).strip()
        planned_question = self._sanitize_unsupported_claims(planned_question, evidence).strip()
        if not self._is_relevant_question(planned_question):
            planned_question = ""
        if not planned_question:
            if strategy == "qualification":
                planned_question = "¿Su empresa gestiona directamente el registro de asistentes para eventos?"
            else:
                planned_question = "¿Cómo gestionan actualmente el registro y seguimiento de asistentes?"
        return clean_body + "\n\n" + planned_question

    def _is_relevant_question(self, question: str) -> bool:
        lowered = question.casefold()
        topic_terms = (
            "registro", "asistentes", "check-in", "acreditación", "acreditacion",
            "rsvp", "plataforma", "herramienta",
        )
        off_topic_terms = (
            "prospectación", "prospeccion", "nuevos clientes", "captación de leads",
            "captacion de leads", "atraer", "estrategia actual", "desafíos", "desafios",
            "problemas", "clientes potenciales", "prospección de clientes",
            "prospeccion de clientes", "captación de clientes", "captacion de clientes",
            "seleccionar asistentes", "selección de asistentes", "seleccion de asistentes",
        )
        return (
            "¿" in question and "?" in question
            and any(term in lowered for term in topic_terms)
            and not any(term in lowered for term in off_topic_terms)
        )

    def _compose_safe_body(
        self,
        context: dict[str, str],
        evidence: list[dict[str, str]],
        strategy: str,
        mention_product: bool,
        planned_question: str,
    ) -> str:
        """Fallback cuando la limpieza deja un borrador demasiado vacío."""
        greeting = context["greeting"]
        company = context["email_company"]
        paragraphs = [greeting]
        if evidence:
            quote = re.sub(r"\s+", " ", evidence[0]["text"]).strip(" .;,:|-")
            if len(quote) > 140:
                quote = self._truncate(quote, 140)
            if quote:
                if evidence[0]["source"] == "contact_title":
                    paragraphs.append("Vi que tu cargo está enfocado en eventos corporativos.")
                elif company:
                    paragraphs.append(f"Vi en la información de {company} que mencionan «{quote}».")
                else:
                    paragraphs.append(f"Vi que mencionan «{quote}».")
        # Sin evidencia validada no citamos ni parafraseamos otros campos.

        if strategy == "qualification":
            question = (
                f"¿La organización de eventos forma parte de las responsabilidades de {company}?"
                if company else "¿La organización de eventos forma parte de tus responsabilidades?"
            )
        else:
            event_focus = self._event_focus(evidence)
            if event_focus:
                question = f"¿Cómo gestionan el registro de asistentes en {event_focus}?"
            else:
                question = "¿Cómo gestionan actualmente el registro y seguimiento de asistentes en sus eventos?"
        # Evita que una sugerencia del LLM introduzca un ángulo comercial
        # distinto del que permite sostener el hecho citado.
        if evidence and evidence[0]["source"] == "contact_title":
            question = "¿Sueles participar directamente en la gestión del registro y seguimiento de asistentes?"
        elif evidence and self._evidence_level(evidence) == "strong":
            focus = self._event_focus(evidence)
            event_phrase = f" para {focus}" if focus else " para esos eventos"
            question = (
                "¿El registro de asistentes"
                f"{event_phrase} lo gestiona su equipo o un proveedor/plataforma?"
            )
        elif evidence and self._evidence_level(evidence) == "direct":
            text = " ".join(item["text"] for item in evidence).casefold()
            platforms = ("eventbrite", "cvent", "swoogo", "hubilo", "bizzabo", "eventtia", "meetmaps", "whova")
            platform = next((name for name in platforms if name in text), "")
            if platform:
                question = f"¿Qué tal les funciona {platform.title()} para gestionar el registro y seguimiento?"
            elif strategy == "demo":
                question = "¿Te parece si te muestro NMDA Events en 15 minutos para comparar cómo resuelve esa operación?"
            else:
                question = "¿Qué herramienta utilizan actualmente para gestionar el registro de asistentes?"

        if evidence and mention_product:
            variants = {
                "A": "Soy Jimmy García, fundador de NMDA Solutions. Estoy desarrollando NMDA Events para gestionar el registro y seguimiento de asistentes.",
                "B": "Soy Jimmy García, fundador de NMDA Solutions. Trabajo en NMDA Events, una plataforma enfocada en la gestión de asistentes para eventos.",
                "C": "Soy Jimmy García, fundador de NMDA Solutions. En NMDA estamos desarrollando una plataforma para simplificar la gestión de asistentes en eventos.",
            }
            paragraphs.append(variants.get(self._product_variant(context, evidence), variants["A"]))
        else:
            paragraphs.append(
                "Soy Jimmy García, fundador de NMDA Solutions. "
                "Quisiera confirmar si la gestión de eventos forma parte de su operación."
            )
        paragraphs.append(question)
        paragraphs.append("Jimmy García\nFundador, NMDA Solutions")
        return "\n\n".join(paragraphs)

    def _event_focus(self, evidence: list[dict[str, str]]) -> str:
        """Return one narrow, source-backed event category for the email question."""
        text = " ".join(item["text"] for item in evidence).casefold()
        focuses = (
            (("fiestas de fin de año", "fiesta de fin de año"), "sus fiestas de fin de año"),
            (("fiestas", "fiesta", "celebraciones", "celebración"), "sus eventos"),
            (("activaciones", "activación"), "sus activaciones"),
            (("convenciones", "convención"), "sus convenciones"),
            (("congresos", "congreso"), "sus congresos"),
            (("conciertos", "concierto"), "sus conciertos"),
            (("lanzamientos", "lanzamiento"), "sus lanzamientos"),
            (("ferias", "feria"), "sus ferias"),
            (("festivales", "festival"), "sus festivales"),
            (("eventos corporativos",), "sus eventos corporativos"),
        )
        for terms, phrase in focuses:
            if any(term in text for term in terms):
                return phrase
        return ""

    def _fallback_context_snippet(self, context: dict[str, str]) -> str:
        for key in (
            "research_evidence", "website_signals", "business_signals",
            "operational_signals", "services", "description", "research_summary",
            "recommendation_reason", "qualification_reason", "target_market", "industry",
        ):
            value = context.get(key, "").strip()
            if not value:
                continue
            snippet = re.split(r"(?:\s*[|;]\s*|(?<=[.!?])\s+|\r?\n+)", value, maxsplit=1)[0]
            snippet = re.sub(r"\s+", " ", snippet).strip(" .;,:|-")
            if snippet:
                return self._truncate(snippet, 150)
        return ""

    def _trim_feature_dump(self, body: str, mention_product: bool) -> str:
        """Reduce listas de funciones sin descartar el resto del correo."""
        feature_terms = (
            "registro", "rsvp", "asistentes", "check-in", "acreditaciones",
            "comunicación", "métricas",
        )

        def simplify(sentence: str) -> str:
            lowered = sentence.casefold()
            count = sum(term in lowered for term in feature_terms)
            if count <= 2:
                return sentence
            if mention_product:
                return "Estoy desarrollando NMDA Events para apoyar esa parte de la operación."
            return "Esa parte de la operación es el punto que me interesa explorar."

        paragraphs = []
        for paragraph in body.split("\n\n"):
            sentences = re.split(r"(?<=[.!?])\s+", paragraph)
            paragraphs.append(" ".join(simplify(sentence) for sentence in sentences))
        return "\n\n".join(paragraphs)

    def _looks_like_person_name(self, value: str, company: str = "") -> bool:
        if not value:
            return False
        words = re.findall(r"[\wÁÉÍÓÚÜÑáéíóúüñ'-]+", value)
        if not 1 <= len(words) <= 2:
            return False
        forbidden = {
            "productor", "productora", "eventos", "evento", "corporativo",
            "corporativos", "virtual", "media", "group", "marketing",
            "director", "agencia", "empresa", "produccion", "producción",
            "de", "del", "para",
        }
        if any(word.casefold() in forbidden for word in words):
            return False
        if company and value.casefold() in company.casefold():
            return False
        return True

    def _confidence(self, value: Any) -> float:
        if isinstance(value, bool):
            raise OllamaError("Confidence inválido.")
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            raise OllamaError("Confidence inválido.") from None
        if not 0 <= confidence <= 1:
            raise OllamaError("Confidence debe estar entre 0 y 1.")
        return confidence

    def _set_deterministic_greeting(self, body: str, greeting: str) -> str:
        paragraphs = body.split("\n\n")
        if paragraphs and re.match(r"^(hola|buenos días|buenas tardes)\b", paragraphs[0], re.I):
            paragraphs[0] = greeting
        else:
            paragraphs.insert(0, greeting)
        return "\n\n".join(paragraphs)

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
        return "\n".join(
            f"- {key}: {value.replace(chr(10), ' ').strip()}"
            for key, value in data.items()
        )

    def _clean_text(self, value: Any, max_chars: int) -> str:
        if value is None:
            return ""
        return re.sub(r"\s+", " ", str(value)).strip().strip('"')[:max_chars].strip()

    def _build_body_from_paragraphs(self, paragraphs: list[Any]) -> str:
        cleaned = [self._clean_paragraph(value) for value in paragraphs]
        return "\n\n".join(value for value in cleaned if value).strip()

    def _clean_paragraph(self, value: Any) -> str:
        if value is None:
            return ""
        paragraph = str(value).strip()
        paragraph = re.sub(r"^```(?:text)?\s*", "", paragraph, flags=re.I)
        paragraph = re.sub(r"\s*```$", "", paragraph)
        paragraph = re.sub(r"[ \t]+", " ", paragraph)
        return re.sub(r"\s*\n\s*", " ", paragraph).strip()

    def _clean_body(self, value: Any) -> str:
        if value is None:
            return ""
        body = str(value).strip()
        body = re.sub(r"^```(?:text)?\s*", "", body, flags=re.I)
        body = re.sub(r"\s*```$", "", body)
        paragraphs = re.split(r"\n\s*\n+", body)
        return "\n\n".join(
            clean for clean in (self._clean_paragraph(p) for p in paragraphs) if clean
        ).strip()
