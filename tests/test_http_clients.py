from datetime import datetime
from os import environ
from uuid import UUID

import httpx
import pytest

from qbo_connectivity.domain.models import ConnectionStatusUpdate
from qbo_connectivity.integrations.automation_gateway.client import AutomationGatewayClient
from qbo_connectivity.integrations.qbo_gateway.client import InactiveClientError, QboGatewayClient

CLIENT_ID = UUID("070b2e37-aa28-4911-b2b2-e493678d38f5")


def test_qbo_client_builds_targets_from_active_client_environments() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/clients"
        return httpx.Response(
            200,
            json=[
                {
                    "id": str(CLIENT_ID),
                    "status": "active",
                    "environments": ["prod", "sandbox"],
                }
            ],
        )

    with QboGatewayClient(
        base_url="http://qbo.local",
        api_key="local-key",
        timeout_seconds=1,
        transport=httpx.MockTransport(handler),
    ) as client:
        targets = client.list_connection_targets()

    assert [target.environment for target in targets] == ["prod", "sandbox"]


def test_inactive_client_is_excluded_from_both_environments() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/clients"
        return httpx.Response(
            200,
            json=[{
                "id": str(CLIENT_ID),
                "status": "inactive",
                "environments": ["prod", "sandbox"],
            }],
        )

    with QboGatewayClient(
        base_url="http://qbo.local",
        api_key="local-key",
        timeout_seconds=1,
        transport=httpx.MockTransport(handler),
    ) as client:
        assert client.list_connection_targets() == []


@pytest.mark.parametrize("status,expected", [("active", True), ("inactive", False)])
def test_qbo_client_reads_current_entity_status(status: str, expected: bool) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == f"/clients/{CLIENT_ID}":
            return httpx.Response(200, json={"status": status})
        return httpx.Response(404)

    with QboGatewayClient(
        base_url="http://qbo.local",
        api_key="local-key",
        timeout_seconds=1,
        transport=httpx.MockTransport(handler),
    ) as client:
        assert client.is_active(client_id=CLIENT_ID) is expected


def test_deactivation_during_company_info_is_not_classified_as_disconnection() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == f"/qbo/{CLIENT_ID}/companyinfo":
            return httpx.Response(403, json={"detail": "Client is inactive"})
        assert request.url.path == f"/clients/{CLIENT_ID}"
        return httpx.Response(200, json={"status": "inactive"})

    with QboGatewayClient(
        base_url="http://qbo.local",
        api_key="local-key",
        timeout_seconds=1,
        transport=httpx.MockTransport(handler),
    ) as client:
        with pytest.raises(InactiveClientError):
            client.check_company_info(
                client_id=CLIENT_ID,
                environment="prod",
                correlation_id=UUID("7ac383c5-7d11-488f-8ba8-11bd2c02023d"),
            )


def test_qbo_client_classifies_companyinfo_200_as_connected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/qbo/{CLIENT_ID}/companyinfo"
        assert request.url.params["environment"] == "prod"
        return httpx.Response(200, json={"CompanyInfo": {"CompanyName": "Local"}})

    with QboGatewayClient(
        base_url="http://qbo.local",
        api_key="local-key",
        timeout_seconds=1,
        transport=httpx.MockTransport(handler),
    ) as client:
        assert (
            client.check_company_info(
                client_id=CLIENT_ID,
                environment="prod",
                correlation_id=UUID("7ac383c5-7d11-488f-8ba8-11bd2c02023d"),
            )
            is True
        )


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(401, text="not-json"),
        httpx.Response(401, json={"details": ["invalid_grant"]}),
        httpx.Response(204),
    ],
)
def test_qbo_client_rejects_unrecognized_companyinfo_response(response: httpx.Response) -> None:
    with QboGatewayClient(
        base_url="http://qbo.local",
        api_key="local-key",
        timeout_seconds=1,
        transport=httpx.MockTransport(lambda _request: response),
    ) as client:
        with pytest.raises((httpx.HTTPStatusError, ValueError)):
            client.check_company_info(
                client_id=CLIENT_ID,
                environment="prod",
                correlation_id=UUID("7ac383c5-7d11-488f-8ba8-11bd2c02023d"),
            )


def test_automation_client_publishes_boolean_payload() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(202, json={"accepted": True})

    update = ConnectionStatusUpdate(
        client_id=CLIENT_ID,
        environment="prod",
        is_connected=True,
        checked_at=datetime.fromisoformat("2026-09-29T12:00:00+00:00"),
        correlation_id=UUID("7ac383c5-7d11-488f-8ba8-11bd2c02023d"),
    )
    with AutomationGatewayClient(
        base_url="http://automation.local",
        api_key="local-key",
        timeout_seconds=1,
        transport=httpx.MockTransport(handler),
    ) as client:
        client.publish_connection_status(update)

    request = captured["request"]
    assert request.url.path == "/v1/jobs"
    assert request.method == "POST"
    assert b'"kind":"qbo.connection_checked.v1"' in request.content
    assert b'"is_connected":true' in request.content


def test_automation_client_propagates_http_errors() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "publisher unavailable"})

    update = ConnectionStatusUpdate(
        client_id=CLIENT_ID,
        environment="prod",
        is_connected=False,
        checked_at=datetime.fromisoformat("2026-09-29T12:00:00+00:00"),
        correlation_id=UUID("7ac383c5-7d11-488f-8ba8-11bd2c02023d"),
    )
    with (
        AutomationGatewayClient(
            base_url="http://automation.local",
            api_key="local-key",
            timeout_seconds=1,
            transport=httpx.MockTransport(handler),
        ) as client,
        pytest.raises(httpx.HTTPStatusError),
    ):
        client.publish_connection_status(update)


@pytest.mark.parametrize("is_connected", [True, False])
def test_live_local_automation_gateway_contract(is_connected: bool) -> None:
    base_url = environ.get("LOCAL_AUTOMATION_GATEWAY_URL")
    api_key = environ.get("LOCAL_AUTOMATION_GATEWAY_API_KEY")
    if not base_url or not api_key:
        pytest.skip("local Docker integration endpoint is not configured")

    update = ConnectionStatusUpdate(
        client_id=CLIENT_ID,
        environment="prod",
        is_connected=is_connected,
        checked_at=datetime.fromisoformat("2026-09-29T12:00:00+00:00"),
        correlation_id=UUID("7ac383c5-7d11-488f-8ba8-11bd2c02023d"),
    )
    with AutomationGatewayClient(
        base_url=base_url,
        api_key=api_key,
        timeout_seconds=2,
    ) as client:
        client.publish_connection_status(update)
