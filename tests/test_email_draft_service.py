from services.email_draft_service import EmailDraftService

SERVICE = EmailDraftService("contact@nmdasolutions.com")


def test_first_email_uses_company_and_services():
    lead = {
        "name": "CS Congress Services",
        "accountName": "CS Congress Services",
        "cServices": ["Congresos", "Convenciones", "Eventos corporativos"],
    }
    draft = SERVICE.generate(lead, [], "FIRST_EMAIL")
    assert draft.action == "FIRST_EMAIL"
    assert "CS Congress Services" in draft.body
    assert "Congresos" in draft.body
    assert "NMDA Events" in draft.body


def test_first_email_uses_first_name_when_available():
    lead = {
        "firstName": "Mauro",
        "lastName": "Tanaka",
        "accountName": "Tanaka Producciones",
    }
    draft = SERVICE.generate(lead, [], "FIRST_EMAIL")
    assert draft.body.startswith("Hola Mauro,")


def test_followup_subject_uses_original_thread():
    lead = {"accountName": "Of Course"}
    emails = [
        {
            "from": "contact@nmdasolutions.com",
            "to": "hola@ofcourse.mx",
            "status": "Sent",
            "subject": "Una idea para sus eventos",
            "dateSent": "2026-08-20 10:00:00",
        }
    ]
    draft = SERVICE.generate(lead, emails, "FOLLOW_UP_1")
    assert draft.subject == "Re: Una idea para sus eventos"
