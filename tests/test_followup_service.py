from datetime import datetime, timezone
from services.followup_service import FollowupService

NOW=datetime(2026,8,31,18,0,tzinfo=timezone.utc)
S=FollowupService("contact@nmdasolutions.com",3,3,3)
def mail(date,sender="contact@nmdasolutions.com",status="Sent"):
    return {"from":sender,"to":"prospect@example.com","status":status,"dateSent":date}
def test_first(): assert S.decide({},[],NOW).action=="FIRST_EMAIL"
def test_f1(): assert S.decide({},[mail("2026-08-26 10:00:00")],NOW).action=="FOLLOW_UP_1"
def test_f2(): assert S.decide({},[mail("2026-08-24 10:00:00"),mail("2026-08-27 10:00:00")],NOW).action=="FOLLOW_UP_2"
def test_recycle(): assert S.decide({},[mail("2026-08-20 10:00:00"),mail("2026-08-24 10:00:00"),mail("2026-08-27 10:00:00")],NOW).action=="RECYCLE"
def test_response():
    emails=[mail("2026-08-24 10:00:00"),{"from":"lead@example.com","to":"contact@nmdasolutions.com","status":"Archived","dateSent":"2026-08-25 10:00:00"}]
    assert S.decide({},emails,NOW).action=="REVIEW_RESPONSE"
