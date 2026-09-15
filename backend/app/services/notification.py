"""Notification service — architecture supports browser/push/mobile/email/sms.
Backend decides when to trigger; frontend displays notification status.
"""
from datetime import datetime, timezone
from typing import List

from ..logging_conf import log


class NotificationService:
    def __init__(self):
        self.pending: List[dict] = []

    def notify(self, alert: dict, target: str = "browser"):
        self.pending.append({
            "alert": alert,
            "target": target,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
        })

    def flush(self) -> List[dict]:
        out = self.pending[:]
        self.pending.clear()
        return out

    def health(self) -> dict:
        return {"pending": len(self.pending), "total_sent": 0}


notification_service = NotificationService()