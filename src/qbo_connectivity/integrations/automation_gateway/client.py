import httpx

from qbo_connectivity.domain.models import ConnectionStatusUpdate


class AutomationGatewayClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"X-API-Key": api_key, "Accept": "application/json"},
            timeout=timeout_seconds,
            transport=transport,
        )

    def __enter__(self) -> "AutomationGatewayClient":
        return self

    def __exit__(self, *_args) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def publish_connection_status(self, update: ConnectionStatusUpdate) -> None:
        response = self._client.post(
            "/v1/jobs",
            json={
                "event_id": str(update.event_id or update.correlation_id),
                "kind": "qbo.connection_checked.v1",
                "payload": {
                    "client_id": str(update.client_id),
                    **update.payload(),
                    "notification": {
                        "candidate": update.notification_candidate,
                        "observed_previous_connected": update.observed_previous_connected,
                    },
                },
            },
            headers={"X-Request-Id": str(update.correlation_id)},
        )
        response.raise_for_status()
