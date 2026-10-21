from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from qbo_connectivity.domain.models import ConnectionStatusUpdate, ConnectionTarget
from qbo_connectivity.integrations.automation_gateway.client import AutomationGatewayClient
from qbo_connectivity.integrations.qbo_gateway.client import QboGatewayClient


def monitor_connection(
    *,
    target: ConnectionTarget,
    qbo_gateway: QboGatewayClient,
    automation_gateway: AutomationGatewayClient,
    correlation_id: UUID | None = None,
    now: Callable[[], datetime] | None = None,
) -> ConnectionStatusUpdate:
    request_id = correlation_id or uuid4()
    is_connected = qbo_gateway.check_company_info(
        client_id=target.client_id,
        environment=target.environment,
        correlation_id=request_id,
    )

    clock = now or (lambda: datetime.now(UTC))
    update = ConnectionStatusUpdate(
        client_id=target.client_id,
        environment=target.environment,
        is_connected=is_connected,
        checked_at=clock(),
        correlation_id=request_id,
    )
    automation_gateway.publish_connection_status(update)
    return update
