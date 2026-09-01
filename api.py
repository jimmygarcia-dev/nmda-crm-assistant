from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify

from services.espocrm import EspoCRMClient, EspoCRMError
from services.followup_service import FollowupService
from services.email_draft_service import EmailDraftService
from services.ollama_client import OllamaClient, OllamaError
from services.first_email_ai_service import FirstEmailAIService


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__, static_folder="static", static_url_path="")

ESPOCRM_URL = os.getenv("ESPOCRM_URL", "http://localhost:8080")
ESPOCRM_API_KEY = os.getenv("ESPOCRM_API_KEY", "")
OUR_EMAIL = os.getenv("OUR_EMAIL", "contact@nmdasolutions.com")
EMAIL_LINK = os.getenv("ESPOCRM_EMAIL_LINK", "emails")
TASK_LINK = os.getenv("ESPOCRM_TASK_LINK", "tasks")
LEAD_STATUSES = {
    value.strip()
    for value in os.getenv("LEAD_STATUSES", "Assigned,In Process").split(",")
    if value.strip()
}
MAX_LEADS = int(os.getenv("MAX_LEADS", "200"))

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))

followups = FollowupService(
    our_email=OUR_EMAIL,
    followup_1_days=int(os.getenv("FOLLOWUP_1_AFTER_DAYS", "3")),
    followup_2_days=int(os.getenv("FOLLOWUP_2_AFTER_DAYS", "3")),
    recycle_days=int(os.getenv("RECYCLE_AFTER_DAYS", "3")),
)
drafts = EmailDraftService(OUR_EMAIL)
ollama = OllamaClient(
    base_url=OLLAMA_URL,
    model=OLLAMA_MODEL,
    timeout=OLLAMA_TIMEOUT,
)
first_email_ai = FirstEmailAIService(ollama)


def crm() -> EspoCRMClient:
    if not ESPOCRM_API_KEY:
        raise EspoCRMError(
            "Falta ESPOCRM_API_KEY. Copia .env.example como .env y configura tu API Key."
        )
    return EspoCRMClient(ESPOCRM_URL, ESPOCRM_API_KEY)


@app.get("/")
def index():
    return app.send_static_file("index.html")


@app.get("/api/health")
def health():
    try:
        data = crm().health()
        return jsonify(
            {
                "ok": True,
                "crmUrl": ESPOCRM_URL,
                "ourEmail": OUR_EMAIL,
                "ollamaModel": OLLAMA_MODEL,
                "apiUser": data.get("user", {}).get("name")
                if isinstance(data.get("user"), dict)
                else None,
            }
        )
    except EspoCRMError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502


@app.get("/api/leads")
def leads():
    try:
        client = crm()
        all_leads = client.list_leads(MAX_LEADS)
        selected = [
            lead
            for lead in all_leads
            if not LEAD_STATUSES or lead.get("status") in LEAD_STATUSES
        ]

        rows = []
        for lead in selected:
            lead_id = lead["id"]
            emails = client.lead_emails(lead_id, EMAIL_LINK)
            tasks = client.lead_tasks(lead_id, TASK_LINK)
            decision = followups.decide(lead, emails)

            open_tasks = [
                task
                for task in tasks
                if str(task.get("status") or "").lower()
                not in {"completed", "canceled", "cancelled"}
            ]

            rows.append(
                {
                    "id": lead_id,
                    "name": lead.get("name") or lead.get("accountName") or "(Sin nombre)",
                    "company": lead.get("accountName")
                    or lead.get("cCompany")
                    or lead.get("companyName")
                    or "",
                    "email": lead.get("emailAddress") or "",
                    "status": lead.get("status") or "",
                    "priority": lead.get("cContactpriority")
                    or lead.get("cContactPriority")
                    or "",
                    "modifiedAt": lead.get("modifiedAt"),
                    "decision": decision.to_dict(),
                    "openTasks": [
                        {
                            "id": task.get("id"),
                            "name": task.get("name"),
                            "status": task.get("status"),
                            "dateEnd": task.get("dateEnd"),
                            "dateStart": task.get("dateStart"),
                        }
                        for task in open_tasks[:5]
                    ],
                }
            )

        rows.sort(
            key=lambda row: (
                0 if row["decision"]["action"] == "REVIEW_RESPONSE" else 1,
                0 if row["decision"]["due"] else 1,
                row["decision"]["next_action_at"] or "9999",
                row["name"].lower(),
            )
        )

        return jsonify({"list": rows, "total": len(rows)})
    except EspoCRMError as exc:
        return jsonify({"error": str(exc)}), 502


@app.get("/api/leads/<lead_id>")
def lead_detail(lead_id: str):
    try:
        client = crm()
        lead = client.get_lead(lead_id)
        emails = client.lead_emails(lead_id, EMAIL_LINK)
        tasks = client.lead_tasks(lead_id, TASK_LINK)
        decision = followups.decide(lead, emails)

        return jsonify(
            {
                "lead": lead,
                "decision": decision.to_dict(),
                "emails": [
                    {
                        "id": e.get("id"),
                        "subject": e.get("subject"),
                        "status": e.get("status"),
                        "from": e.get("from") or e.get("fromAddress") or e.get("fromString"),
                        "to": e.get("to") or e.get("toAddress") or e.get("toString"),
                        "dateSent": e.get("dateSent"),
                        "createdAt": e.get("createdAt"),
                    }
                    for e in emails
                ],
                "tasks": tasks,
                "crmUrl": f"{ESPOCRM_URL}/#Lead/view/{lead_id}",
            }
        )
    except EspoCRMError as exc:
        return jsonify({"error": str(exc)}), 502


@app.get("/api/leads/<lead_id>/email-draft")
def email_draft(lead_id: str):
    """
    Devuelve un borrador local para la acción que EspoCRM indica.
    No guarda y no envía nada.
    """
    try:
        client = crm()
        lead = client.get_lead(lead_id)
        emails = client.lead_emails(lead_id, EMAIL_LINK)
        decision = followups.decide(lead, emails)

        if decision.action not in {"FIRST_EMAIL", "FOLLOW_UP_1", "FOLLOW_UP_2"}:
            return jsonify(
                {
                    "error": (
                        f"La siguiente acción es '{decision.label}'. "
                        "Solo generamos borradores para First Email, Follow-up #1 o #2."
                    ),
                    "decision": decision.to_dict(),
                }
            ), 409

        if decision.action == "FIRST_EMAIL":
            draft = first_email_ai.generate(lead)
            return jsonify(
                {
                    "draft": draft.to_dict(),
                    "decision": decision.to_dict(),
                    "generatedBy": "ollama",
                    "model": OLLAMA_MODEL,
                }
            )

        draft = drafts.generate(lead, emails, decision.action)

        return jsonify(
            {
                "draft": draft.to_dict(),
                "decision": decision.to_dict(),
                "generatedBy": "template",
            }
        )
    except (EspoCRMError, OllamaError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 502


@app.get("/api/leads/<lead_id>/followup-draft")
def followup_draft_compat(lead_id: str):
    """Compatibilidad temporal con v0.2."""
    return email_draft(lead_id)


if __name__ == "__main__":
    # 0.0.0.0 es necesario para poder exponer Flask desde Docker.
    app.run(host="0.0.0.0", port=8090, debug=False)
