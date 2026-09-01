from services.followup_draft_service import FollowupDraftService


SERVICE = FollowupDraftService("contact@nmdasolutions.com")


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


def test_person_name_uses_singular_greeting():
    lead = {"firstName": "Mauro", "lastName": "Tanaka", "name": "Mauro Tanaka"}
    emails = [sent("NMDA Events", "2026-08-20 10:00:00")]
    draft = SERVICE.generate(lead, emails, "FOLLOW_UP_1")
    assert draft.body.startswith("Hola Mauro,")
    assert "mostrarte" in draft.body
