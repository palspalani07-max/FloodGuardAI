import pytest

from app.services.notification import NotificationService


def test_notify_queues_and_flush():
    svc = NotificationService()
    svc.notify({"alert_id": "a1", "severity": "CRITICAL"}, target="browser")
    out = svc.flush()
    assert len(out) == 1
    assert out[0]["status"] == "pending"
    assert out[0]["target"] == "browser"
    # flushed -> empty
    assert svc.flush() == []


def test_health():
    svc = NotificationService()
    svc.notify({"alert_id": "a1"})
    h = svc.health()
    assert h["pending"] == 1
    assert "total_sent" in h