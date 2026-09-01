from datetime import datetime, timezone

from services.followup_service import FollowupService


NOW = datetime(2026, 8, 31, 18, 0, tzinfo=timezone.utc)
SERVICE = FollowupService("contact@nmdasolutions.com", 3, 3, 3)


def mail(date, sender="contact@nmdasolutions.com", status="Sent"):
    return {
        "from": sender,
        "to": "prospect@example.com",
        "status": status,
        "dateSent": date,
    }


def test_first_email_when_no_outbound():
    assert SERVICE.decide({}, [], NOW).action == "FIRST_EMAIL"


def test_followup_1_after_first_email():
    assert SERVICE.decide({}, [mail("2026-08-26 10:00:00")], NOW).action == "FOLLOW_UP_1"


def test_followup_2_after_two_outbound():
    emails = [mail("2026-08-24 10:00:00"), mail("2026-08-27 10:00:00")]
    assert SERVICE.decide({}, emails, NOW).action == "FOLLOW_UP_2"


def test_recycle_after_three_outbound():
    emails = [
        mail("2026-08-20 10:00:00"),
        mail("2026-08-24 10:00:00"),
        mail("2026-08-27 10:00:00"),
    ]
    assert SERVICE.decide({}, emails, NOW).action == "RECYCLE"
