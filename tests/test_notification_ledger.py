from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest

from qbo_connectivity.integrations.notification_ledger import NotificationLedgerClient

CLIENT_ID = UUID("477751f2-1142-4283-a3c0-387f8aa45fbd")
URL = "http://router.local/webhook/automation/notification-ledger/last-sent/v1"


def test_posts_entity_lookup_with_router_webhook_key():
    requests = []

    def handler(request):
        requests.append(request)
        assert request.method == "POST"
        assert request.headers["X-API-Key"] == "router-webhook-key"
        assert request.read() == (
            b'{"client_id":"477751f2-1142-4283-a3c0-387f8aa45fbd",'
            b'"environment":"sandbox"}'
        )
        return httpx.Response(
            200,
            json={
                "result_type": "notification_ledger.last_sent.v1",
                "last_notified_at": "2026-10-22T12:00:00Z",
            },
        )

    with NotificationLedgerClient(
        url=URL,
        api_key="router-webhook-key",
        timeout_seconds=1,
        transport=httpx.MockTransport(handler),
    ) as ledger:
        result = ledger.last_sent_at(
            client_id=CLIENT_ID, environment="sandbox", channel="slack", recipient="D0B3LSR4C1Y"
        )

    assert result == datetime(2026, 10, 22, 12, 0, tzinfo=UTC)
    assert len(requests) == 1


def test_null_timestamp_means_no_confirmed_delivery():
    with NotificationLedgerClient(
        url=URL,
        api_key="router-webhook-key",
        timeout_seconds=1,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "result_type": "notification_ledger.last_sent.v1",
                    "last_notified_at": None,
                },
            )
        ),
    ) as ledger:
        result = ledger.last_sent_at(
            client_id=CLIENT_ID, environment="prod", channel="slack", recipient="D0B3LSR4C1Y"
        )

    assert result is None


@pytest.mark.parametrize(
    "payload, message",
    [
        ({"result_type": "wrong", "last_notified_at": None}, "webhook response"),
        (
            {"result_type": "notification_ledger.last_sent.v1"},
            "webhook response",
        ),
        (
            {"result_type": "notification_ledger.last_sent.v1", "last_notified_at": 123},
            "ISO8601 string or null",
        ),
        (
            {
                "result_type": "notification_ledger.last_sent.v1",
                "last_notified_at": "2026-10-22T12:00:00",
            },
            "no timezone",
        ),
        (
            {
                "result_type": "notification_ledger.last_sent.v1",
                "last_notified_at": "2026-10-22T12:00:00+01:00",
            },
            "not UTC",
        ),
        (
            {
                "result_type": "notification_ledger.last_sent.v1",
                "last_notified_at": "not-a-date",
            },
            "Invalid notification ledger timestamp",
        ),
    ],
)
def test_malformed_webhook_response_fails_closed(payload, message):
    with NotificationLedgerClient(
        url=URL,
        api_key="router-webhook-key",
        timeout_seconds=1,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)),
    ) as ledger:
        with pytest.raises(ValueError, match=message):
            ledger.last_sent_at(
                client_id=CLIENT_ID,
                environment="sandbox",
                channel="slack",
                recipient="D0B3LSR4C1Y",
            )
