"""Read-only lookup of confirmed deliveries through the authenticated router webhook."""

from datetime import UTC, datetime
from uuid import UUID

import httpx

from qbo_connectivity.domain.models import Environment


class NotificationLedgerClient:
    def __init__(
        self,
        *,
        url: str,
        api_key: str,
        timeout_seconds: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._url = url
        self._client = httpx.Client(
            headers={"X-API-Key": api_key, "Accept": "application/json"},
            timeout=timeout_seconds,
            transport=transport,
        )

    def __enter__(self) -> "NotificationLedgerClient":
        return self

    def __exit__(self, *_args: object) -> None:
        self._client.close()

    def last_sent_at(
        self, *, client_id: UUID, environment: Environment, channel: str, recipient: str
    ) -> datetime | None:
        # The webhook contract scopes the lookup to entity identity. Channel and recipient
        # remain accepted for caller compatibility; the router owns delivery details.
        response = self._client.post(
            self._url,
            json={"client_id": str(client_id), "environment": environment},
        )
        response.raise_for_status()
        data = response.json()
        if (
            not isinstance(data, dict)
            or data.get("result_type") != "notification_ledger.last_sent.v1"
            or "last_notified_at" not in data
        ):
            raise ValueError("Unexpected notification ledger webhook response")
        raw = data["last_notified_at"]
        if raw is None:
            return None
        if not isinstance(raw, str):
            raise ValueError("Notification ledger timestamp must be an ISO8601 string or null")
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("Invalid notification ledger timestamp") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("Notification ledger timestamp has no timezone")
        if parsed.utcoffset().total_seconds() != 0:
            raise ValueError("Notification ledger timestamp is not UTC")
        return parsed.astimezone(UTC)
