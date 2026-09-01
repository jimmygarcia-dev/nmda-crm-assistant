from services.email_draft_service import EmailDraftService

SERVICE = EmailDraftService("contact@nmdasolutions.com")


def sent(subject, date):
    return {
        "from": "contact@nmdasolutions.com",
        "to": "lead@example.com",
        "status": "Sent",
        "subject": subject,
        "dateSent": date,
    }


def test_followup_2_keeps_original_subject():
    lead = {"name": "Of Course", "accountName": "Of Course"}
    emails = [
        sent("Una idea para complementar la experiencia de sus eventos", "2026-08-20 10:00:00"),
        sent("Re: Una idea para complementar la experiencia de sus eventos", "2026-08-26 10:00:00"),
    ]
    draft = SERVICE.generate(lead, emails, "FOLLOW_UP_2")
    assert draft.subject == "Re: Una idea para complementar la experiencia de sus eventos"
    assert "por última vez" in draft.body
    assert "Hola equipo de Of Course," in draft.body
