from uuid import UUID

import httpx

from qbo_connectivity.domain.models import ConnectionTarget, Environment


class QboGatewayClient:
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

    def __enter__(self) -> "QboGatewayClient":
        return self

    def __exit__(self, *_args) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def list_connection_targets(self) -> list[ConnectionTarget]:
        response = self._client.get("/clients", params={"summary": "true"})
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("QBO Gateway clients response must be a list")

        targets: list[ConnectionTarget] = []
        for client in payload:
            if client.get("status") != "active":
                continue
            client_id = UUID(client["id"])
            for environment in client.get("environments", []):
                if environment not in {"prod", "sandbox"}:
                    continue
                targets.append(
                    ConnectionTarget(
                        client_id=client_id,
                        environment=environment,
                    )
                )
        return targets

    def check_company_info(
        self,
        *,
        client_id: UUID,
        environment: Environment,
        correlation_id: UUID,
    ) -> bool:
        response = self._client.get(
            f"/qbo/{client_id}/companyinfo",
            params={"environment": environment},
            headers={"X-Request-Id": str(correlation_id)},
        )
        if response.status_code == 200:
            return True

        if response.status_code == 401:
            try:
                payload = response.json()
            except ValueError:
                payload = None
            if isinstance(payload, dict):
                details = payload.get("details")
                if (
                    isinstance(details, dict)
                    and details.get("provider") == "intuit"
                    and details.get("oauth_error") == "invalid_grant"
                ):
                    return False

        response.raise_for_status()
        raise ValueError(f"Unexpected CompanyInfo response status: {response.status_code}")
