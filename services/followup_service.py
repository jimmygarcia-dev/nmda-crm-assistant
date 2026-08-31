from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def add_business_days(start: datetime, days: int) -> datetime:
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current


def _flatten(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.lower()
    if isinstance(value, dict):
        return " ".join(_flatten(v) for v in value.values())
    if isinstance(value, Iterable):
        return " ".join(_flatten(v) for v in value)
    return str(value).lower()


def _sender(email: dict[str, Any]) -> str:
    for key in ("from", "fromAddress", "fromString", "senderAddress"):
        if email.get(key):
            return _flatten(email.get(key))
    return ""


def _recipients(email: dict[str, Any]) -> str:
    parts = []
    for key in ("to", "toAddress", "toString", "toAddressList", "cc", "ccAddressList"):
        if email.get(key):
            parts.append(_flatten(email.get(key)))
    return " ".join(parts)


def _email_dt(email: dict[str, Any]) -> datetime | None:
    for key in ("dateSent", "sentAt", "createdAt", "modifiedAt"):
        dt = _parse_dt(email.get(key))
        if dt:
            return dt
    return None


def _looks_sent(email: dict[str, Any], our_email: str) -> bool:
    status = str(email.get("status") or "").lower()
    return our_email in _sender(email) or status == "sent"


def _looks_received(email: dict[str, Any], our_email: str) -> bool:
    sender = _sender(email)
    recipients = _recipients(email)
    status = str(email.get("status") or "").lower()
    if our_email in sender:
        return False
    if our_email in recipients:
        return True
    return status in {"archived", "received"} and bool(sender)


@dataclass
class FollowupDecision:
    action: str
    label: str
    reason: str
    outbound_count: int
    inbound_count: int
    last_contact_at: str | None
    next_action_at: str | None
    due: bool
    replied: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FollowupService:
    def __init__(self, our_email: str, followup_1_days: int = 3, followup_2_days: int = 3, recycle_days: int = 3):
        self.our_email = our_email.strip().lower()
        self.followup_1_days = followup_1_days
        self.followup_2_days = followup_2_days
        self.recycle_days = recycle_days

    def decide(self, lead: dict[str, Any], emails: list[dict[str, Any]], now: datetime | None = None) -> FollowupDecision:
        now = now or datetime.now(timezone.utc)
        sent = [e for e in emails if _looks_sent(e, self.our_email)]
        received = [e for e in emails if _looks_received(e, self.our_email)]
        sent.sort(key=lambda e: _email_dt(e) or datetime.min.replace(tzinfo=timezone.utc))
        received.sort(key=lambda e: _email_dt(e) or datetime.min.replace(tzinfo=timezone.utc))
        last_sent = _email_dt(sent[-1]) if sent else None
        last_received = _email_dt(received[-1]) if received else None
        replied = bool(last_received and (not last_sent or last_received >= last_sent))

        if replied:
            return FollowupDecision("REVIEW_RESPONSE", "Revisar respuesta", "Hay un correo entrante posterior al último envío.", len(sent), len(received), _iso(last_sent), None, True, True)
        if len(sent) == 0:
            return FollowupDecision("FIRST_EMAIL", "First Email", "No se detectaron correos salientes relacionados con el lead.", 0, len(received), None, None, True, False)
        if len(sent) == 1:
            return self._dated("FOLLOW_UP_1", "Follow-up #1", "Se detectó First Email, pero todavía no un primer seguimiento.", len(sent), len(received), last_sent, add_business_days(last_sent, self.followup_1_days), now)
        if len(sent) == 2:
            return self._dated("FOLLOW_UP_2", "Follow-up #2", "Se detectaron First Email + Follow-up #1.", len(sent), len(received), last_sent, add_business_days(last_sent, self.followup_2_days), now)
        return self._dated("RECYCLE", "Recycled", "Ya se detectaron 3 o más correos salientes; no conviene seguir enviando.", len(sent), len(received), last_sent, add_business_days(last_sent, self.recycle_days), now)

    def _dated(self, action: str, label: str, reason: str, outbound_count: int, inbound_count: int, last_contact: datetime, next_dt: datetime, now: datetime) -> FollowupDecision:
        return FollowupDecision(action, label, reason, outbound_count, inbound_count, _iso(last_contact), _iso(next_dt), now >= next_dt, False)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None
