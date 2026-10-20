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
        response = self._client.put(
            f"/v1/connections/{update.client_id}/status",
            json=update.payload(),
            headers={"X-Request-Id": str(update.correlation_id)},
        )
        response.raise_for_status()
