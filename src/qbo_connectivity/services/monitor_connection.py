from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx

from qbo_connectivity.domain.models import ConnectionStatusUpdate, ConnectionTarget
from qbo_connectivity.integrations.automation_gateway.client import AutomationGatewayClient
from qbo_connectivity.integrations.notification_ledger import NotificationLedgerClient
from qbo_connectivity.integrations.qbo_gateway.client import QboGatewayClient


def monitor_connection(
    *,
    target: ConnectionTarget,
    qbo_gateway: QboGatewayClient,
    automation_gateway: AutomationGatewayClient,
    notification_ledger: NotificationLedgerClient | None = None,
    notification_recipient: str | None = None,
    event_id: UUID | None = None,
    correlation_id: UUID | None = None,
    now: Callable[[], datetime] | None = None,
) -> ConnectionStatusUpdate:
    request_id = correlation_id or uuid4()
    previous_state = None
    if notification_ledger is not None:
        if not notification_recipient:
            raise ValueError("notification_recipient is required with a notification ledger")
        previous_state = qbo_gateway.get_connection_state(
            client_id=target.client_id, environment=target.environment
        )
    is_connected = qbo_gateway.check_company_info(
        client_id=target.client_id,
        environment=target.environment,
        correlation_id=request_id,
    )

    clock = now or (lambda: datetime.now(UTC))
    checked_at = clock()
    candidate = None
    if not is_connected and notification_ledger is not None:
        if previous_state and previous_state.is_connected:
            candidate = True
        else:
            try:
                last_sent_at = notification_ledger.last_sent_at(
                    client_id=target.client_id,
                    environment=target.environment,
                    channel="slack",
                    recipient=notification_recipient,
                )
                candidate = last_sent_at is None or checked_at - last_sent_at >= timedelta(hours=48)
            except (httpx.HTTPError, ValueError):
                # Persist the conclusive connection check; the worker must re-evaluate
                # an unknown notification decision before sending anything.
                candidate = None
    update = ConnectionStatusUpdate(
        client_id=target.client_id,
        environment=target.environment,
        is_connected=is_connected,
        checked_at=checked_at,
        correlation_id=request_id,
        event_id=event_id or request_id,
        notification_candidate=candidate,
        observed_previous_connected=previous_state.is_connected if previous_state else None,
    )
    automation_gateway.publish_connection_status(update)
    return update
