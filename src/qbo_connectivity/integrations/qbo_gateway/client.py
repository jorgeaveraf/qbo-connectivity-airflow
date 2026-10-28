from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import httpx

from qbo_connectivity.domain.models import ConnectionTarget, Environment


@dataclass(frozen=True)
class StoredConnectionState:
    is_connected: bool
    checked_at: datetime | None


class InactiveClientError(RuntimeError):
    """The entity was deactivated after this DAG run selected its targets."""


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

    def is_active(self, *, client_id: UUID) -> bool:
        response = self._client.get(f"/clients/{client_id}")
        response.raise_for_status()
        status = response.json().get("status")
        if status not in {"active", "inactive"}:
            raise ValueError("QBO Gateway client detail has no valid status")
        return status == "active"

    def get_connection_state(
        self, *, client_id: UUID, environment: Environment
    ) -> StoredConnectionState:
        response = self._client.get(f"/clients/{client_id}")
        response.raise_for_status()
        credentials = response.json().get("credentials")
        if not isinstance(credentials, list):
            raise ValueError("QBO Gateway client detail has no credentials list")
        matches = [c for c in credentials if c.get("environment") == environment]
        if len(matches) != 1 or not isinstance(matches[0].get("is_connected"), bool):
            raise ValueError("QBO Gateway has no unique connection state for target")
        raw_checked_at = matches[0].get("connection_checked_at")
        checked_at = (
            datetime.fromisoformat(raw_checked_at.replace("Z", "+00:00"))
            if raw_checked_at
            else None
        )
        if checked_at is not None and (checked_at.tzinfo is None or checked_at.utcoffset() is None):
            raise ValueError("QBO Gateway connection_checked_at must have a timezone")
        return StoredConnectionState(is_connected=matches[0]["is_connected"], checked_at=checked_at)

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

        if response.status_code == 403 and not self.is_active(client_id=client_id):
            raise InactiveClientError("Entity was deactivated during its connection check")

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
