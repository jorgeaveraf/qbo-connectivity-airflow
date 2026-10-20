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
    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    def check_company_info(self, **_kwargs) -> None:
        self.calls += 1
        if self.calls <= self.failures:
            raise RuntimeError("simulated QBO failure")


class FakeAutomationGateway:
    def __init__(self, error: Exception | None = None) -> None:
        self.published = []
        self.error = error

    def publish_connection_status(self, update) -> None:
        if self.error:
            raise self.error
        self.published.append(update)


def test_successful_company_info_publishes_true() -> None:
    qbo = FakeQboGateway(failures=0)
    automation = FakeAutomationGateway()

    update = monitor_connection(
        target=ConnectionTarget(client_id=CLIENT_ID, environment="prod"),
        qbo_gateway=qbo,
        automation_gateway=automation,
        max_attempts=3,
        retry_delay_seconds=0,
        correlation_id=CORRELATION_ID,
        now=lambda: CHECKED_AT,
        sleeper=lambda _seconds: None,
    )

    assert update.is_connected is True
    assert qbo.calls == 1
    assert automation.published == [update]


def test_exhausted_company_info_attempts_do_not_publish_status() -> None:
    qbo = FakeQboGateway(failures=3)
    automation = FakeAutomationGateway()

    with pytest.raises(RuntimeError, match="simulated QBO failure"):
        monitor_connection(
            target=ConnectionTarget(client_id=CLIENT_ID, environment="sandbox"),
            qbo_gateway=qbo,
            automation_gateway=automation,
            max_attempts=3,
            retry_delay_seconds=0,
            correlation_id=CORRELATION_ID,
            now=lambda: CHECKED_AT,
            sleeper=lambda _seconds: None,
        )

    assert qbo.calls == 3
    assert automation.published == []


def test_qbo_gateway_502_does_not_publish_disconnected() -> None:
    automation = FakeAutomationGateway()
    calls = 0

    def unavailable(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(502, json={"detail": "QuickBooks API error"})

    with QboGatewayClient(
        base_url="http://qbo.local",
        api_key="local-key",
        timeout_seconds=1,
        transport=httpx.MockTransport(unavailable),
    ) as qbo:
        with pytest.raises(httpx.HTTPStatusError):
            monitor_connection(
                target=ConnectionTarget(client_id=CLIENT_ID, environment="prod"),
                qbo_gateway=qbo,
                automation_gateway=automation,
                max_attempts=2,
                retry_delay_seconds=0,
                sleeper=lambda _seconds: None,
            )

    assert calls == 2
    assert automation.published == []


def test_publication_failure_is_not_reported_as_disconnected() -> None:
    qbo = FakeQboGateway(failures=0)
    automation = FakeAutomationGateway(error=RuntimeError("publisher unavailable"))

    try:
        monitor_connection(
            target=ConnectionTarget(client_id=CLIENT_ID, environment="prod"),
            qbo_gateway=qbo,
            automation_gateway=automation,
            max_attempts=3,
            retry_delay_seconds=0,
            correlation_id=CORRELATION_ID,
            now=lambda: CHECKED_AT,
            sleeper=lambda _seconds: None,
        )
    except RuntimeError as exc:
        assert str(exc) == "publisher unavailable"
    else:
        raise AssertionError("publication failure must propagate to Airflow")
