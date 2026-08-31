from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, jsonify
from services.espocrm import EspoCRMClient, EspoCRMError
from services.followup_service import FollowupService

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
app = Flask(__name__, static_folder="static", static_url_path="")

ESPOCRM_URL = os.getenv("ESPOCRM_URL", "http://localhost:8080")
ESPOCRM_API_KEY = os.getenv("ESPOCRM_API_KEY", "")
OUR_EMAIL = os.getenv("OUR_EMAIL", "contact@nmdasolutions.com")
EMAIL_LINK = os.getenv("ESPOCRM_EMAIL_LINK", "emails")
TASK_LINK = os.getenv("ESPOCRM_TASK_LINK", "tasks")
LEAD_STATUSES = {x.strip() for x in os.getenv("LEAD_STATUSES", "Assigned,In Process").split(",") if x.strip()}
MAX_LEADS = int(os.getenv("MAX_LEADS", "200"))

followups = FollowupService(
    OUR_EMAIL,
    int(os.getenv("FOLLOWUP_1_AFTER_DAYS", "3")),
    int(os.getenv("FOLLOWUP_2_AFTER_DAYS", "3")),
    int(os.getenv("RECYCLE_AFTER_DAYS", "3")),
)


def crm() -> EspoCRMClient:
    if not ESPOCRM_API_KEY:
        raise EspoCRMError("Falta ESPOCRM_API_KEY. Copia .env.example como .env y configura tu API Key.")
    return EspoCRMClient(ESPOCRM_URL, ESPOCRM_API_KEY)


@app.get("/")
def index():
    return app.send_static_file("index.html")


@app.get("/api/health")
def health():
    try:
        crm().health()
        return jsonify({"ok": True, "crmUrl": ESPOCRM_URL, "ourEmail": OUR_EMAIL})
    except EspoCRMError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 502


@app.get("/api/leads")
def leads():
    try:
        client = crm()
        all_leads = client.list_leads(MAX_LEADS)
        selected = [lead for lead in all_leads if not LEAD_STATUSES or lead.get("status") in LEAD_STATUSES]
        rows = []
        for lead in selected:
            lead_id = lead["id"]
            emails = client.lead_emails(lead_id, EMAIL_LINK)
            tasks = client.lead_tasks(lead_id, TASK_LINK)
            decision = followups.decide(lead, emails)
            open_tasks = [t for t in tasks if str(t.get("status") or "").lower() not in {"completed", "canceled", "cancelled"}]
            rows.append({
                "id": lead_id,
                "name": lead.get("name") or lead.get("accountName") or "(Sin nombre)",
                "company": lead.get("accountName") or lead.get("cCompany") or lead.get("companyName") or "",
                "email": lead.get("emailAddress") or "",
                "status": lead.get("status") or "",
                "modifiedAt": lead.get("modifiedAt"),
                "decision": decision.to_dict(),
                "openTasks": [{"id": t.get("id"), "name": t.get("name"), "status": t.get("status"), "dateEnd": t.get("dateEnd")} for t in open_tasks[:5]],
            })
        rows.sort(key=lambda r: (0 if r["decision"]["action"] == "REVIEW_RESPONSE" else 1, 0 if r["decision"]["due"] else 1, r["decision"]["next_action_at"] or "9999", r["name"].lower()))
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
        return jsonify({
            "lead": lead,
            "decision": decision.to_dict(),
            "emails": [{"id": e.get("id"), "subject": e.get("subject"), "status": e.get("status"), "from": e.get("from") or e.get("fromAddress") or e.get("fromString"), "to": e.get("to") or e.get("toAddress") or e.get("toString"), "dateSent": e.get("dateSent"), "createdAt": e.get("createdAt")} for e in emails],
            "tasks": tasks,
            "crmUrl": f"{ESPOCRM_URL}/#Lead/view/{lead_id}",
        })
    except EspoCRMError as exc:
        return jsonify({"error": str(exc)}), 502


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8090, debug=True)
