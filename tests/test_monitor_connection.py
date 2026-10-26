from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest

from qbo_connectivity.domain.models import ConnectionTarget
from qbo_connectivity.integrations.qbo_gateway.client import QboGatewayClient
from qbo_connectivity.services.monitor_connection import monitor_connection

CLIENT_ID = UUID("070b2e37-aa28-4911-b2b2-e493678d38f5")
CORRELATION_ID = UUID("7ac383c5-7d11-488f-8ba8-11bd2c02023d")
CHECKED_AT = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)


class FakeQboGateway:
    def __init__(self, result: bool = True, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls = 0

    def check_company_info(self, **_kwargs) -> bool:
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


class FakeAutomationGateway:
    def __init__(self, error: Exception | None = None) -> None:
        self.published = []
        self.error = error

    def publish_connection_status(self, update) -> None:
        if self.error:
            raise self.error
        self.published.append(update)


class FakeStoredStatus(FakeAutomationGateway):
    """A local stand-in for the stored result, changed only by a status publish."""

    def __init__(self, is_connected: bool, checked_at: datetime) -> None:
        super().__init__()
        self.is_connected = is_connected
        self.checked_at = checked_at

    def publish_connection_status(self, update) -> None:
        super().publish_connection_status(update)
        self.is_connected = update.is_connected
        self.checked_at = update.checked_at


@pytest.mark.parametrize("is_connected", [True, False])
def test_classified_company_info_publishes_status(is_connected: bool) -> None:
    qbo = FakeQboGateway(result=is_connected)
    automation = FakeAutomationGateway()

    update = monitor_connection(
        target=ConnectionTarget(client_id=CLIENT_ID, environment="prod"),
        qbo_gateway=qbo,
        automation_gateway=automation,
        correlation_id=CORRELATION_ID,
        now=lambda: CHECKED_AT,
    )

    assert update.is_connected is is_connected
    assert qbo.calls == 1
    assert automation.published == [update]


def test_failed_company_info_does_not_publish_status_or_retry() -> None:
    qbo = FakeQboGateway(error=RuntimeError("simulated QBO failure"))
    automation = FakeAutomationGateway()

    with pytest.raises(RuntimeError, match="simulated QBO failure"):
        monitor_connection(
            target=ConnectionTarget(client_id=CLIENT_ID, environment="sandbox"),
            qbo_gateway=qbo,
            automation_gateway=automation,
        )

    assert qbo.calls == 1
    assert automation.published == []


@pytest.mark.parametrize("status_code", [429, 502, 503])
def test_transient_error_preserves_previous_status_and_review_time(status_code: int) -> None:
    previous_check = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
    stored = FakeStoredStatus(is_connected=True, checked_at=previous_check)

    with QboGatewayClient(
        base_url="http://qbo.local",
        api_key="local-key",
        timeout_seconds=1,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(status_code, json={"detail": "Simulated error"})
        ),
    ) as qbo:
        with pytest.raises(httpx.HTTPStatusError):
            monitor_connection(
                target=ConnectionTarget(client_id=CLIENT_ID, environment="sandbox"),
                qbo_gateway=qbo,
                automation_gateway=stored,
                now=lambda: CHECKED_AT,
            )

    assert stored.published == []
    assert (stored.is_connected, stored.checked_at) == (True, previous_check)


@pytest.mark.parametrize(
    ("response", "expected_connected"),
    [
        (httpx.Response(200, json={"CompanyInfo": {"CompanyName": "Local"}}), True),
        (
            httpx.Response(
                401,
                json={"details": {"provider": "intuit", "oauth_error": "invalid_grant"}},
            ),
            False,
        ),
    ],
)
def test_classified_check_replaces_previous_status_and_review_time(
    response: httpx.Response, expected_connected: bool
) -> None:
    previous_check = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
    stored = FakeStoredStatus(is_connected=not expected_connected, checked_at=previous_check)

    with QboGatewayClient(
        base_url="http://qbo.local",
        api_key="local-key",
        timeout_seconds=1,
        transport=httpx.MockTransport(lambda _request: response),
    ) as qbo:
        update = monitor_connection(
            target=ConnectionTarget(client_id=CLIENT_ID, environment="sandbox"),
            qbo_gateway=qbo,
            automation_gateway=stored,
            now=lambda: CHECKED_AT,
        )

    assert stored.published == [update]
    assert (stored.is_connected, stored.checked_at) == (expected_connected, CHECKED_AT)


def test_invalid_grant_publishes_disconnected_once() -> None:
    automation = FakeAutomationGateway()
    calls = 0

    def invalid_grant(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            401,
            json={
                "code": 401,
                "details": {"provider": "intuit", "oauth_error": "invalid_grant"},
            },
        )

    with QboGatewayClient(
        base_url="http://qbo.local",
        api_key="local-key",
        timeout_seconds=1,
        transport=httpx.MockTransport(invalid_grant),
    ) as qbo:
        update = monitor_connection(
            target=ConnectionTarget(client_id=CLIENT_ID, environment="prod"),
            qbo_gateway=qbo,
            automation_gateway=automation,
            correlation_id=CORRELATION_ID,
            now=lambda: CHECKED_AT,
        )

    assert calls == 1
    assert update.is_connected is False
    assert automation.published == [update]


@pytest.mark.parametrize(
    ("status_code", "payload"),
    [
        (400, {"detail": "Invalid request"}),
        (401, {"details": {"provider": "intuit", "oauth_error": "other_error"}}),
        (401, {"details": {"provider": "other", "oauth_error": "invalid_grant"}}),
        (401, {"detail": "Unauthorized"}),
        (404, {"message": "Credential not found"}),
        (429, {"detail": "Rate limited"}),
        (502, {"detail": "QuickBooks API error"}),
        (503, {"detail": "Unavailable"}),
    ],
)
def test_unclassified_http_error_does_not_publish_or_retry(
    status_code: int, payload: dict[str, object]
) -> None:
    automation = FakeAutomationGateway()
    calls = 0

    def failed(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status_code, json=payload)

    with QboGatewayClient(
        base_url="http://qbo.local",
        api_key="local-key",
        timeout_seconds=1,
        transport=httpx.MockTransport(failed),
    ) as qbo:
        with pytest.raises(httpx.HTTPStatusError):
            monitor_connection(
                target=ConnectionTarget(client_id=CLIENT_ID, environment="prod"),
                qbo_gateway=qbo,
                automation_gateway=automation,
            )

    assert calls == 1
    assert automation.published == []


def test_timeout_does_not_publish_or_retry() -> None:
    previous_check = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)
    automation = FakeStoredStatus(is_connected=False, checked_at=previous_check)
    calls = 0

    def timed_out(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("simulated timeout")

    with QboGatewayClient(
        base_url="http://qbo.local",
        api_key="local-key",
        timeout_seconds=1,
        transport=httpx.MockTransport(timed_out),
    ) as qbo:
        with pytest.raises(httpx.ReadTimeout):
            monitor_connection(
                target=ConnectionTarget(client_id=CLIENT_ID, environment="prod"),
                qbo_gateway=qbo,
                automation_gateway=automation,
            )

    assert calls == 1
    assert automation.published == []
    assert (automation.is_connected, automation.checked_at) == (False, previous_check)


def test_publication_failure_is_not_reported_as_success() -> None:
    qbo = FakeQboGateway(result=False)
    automation = FakeAutomationGateway(error=RuntimeError("publisher unavailable"))

    with pytest.raises(RuntimeError, match="publisher unavailable"):
        monitor_connection(
            target=ConnectionTarget(client_id=CLIENT_ID, environment="prod"),
            qbo_gateway=qbo,
            automation_gateway=automation,
        )

    assert qbo.calls == 1
    assert automation.published == []
