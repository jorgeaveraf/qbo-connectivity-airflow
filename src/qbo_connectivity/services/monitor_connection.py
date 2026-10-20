from collections.abc import Callable
from datetime import UTC, datetime
from time import sleep
from uuid import UUID, uuid4

from qbo_connectivity.domain.models import ConnectionStatusUpdate, ConnectionTarget
from qbo_connectivity.integrations.automation_gateway.client import AutomationGatewayClient
from qbo_connectivity.integrations.qbo_gateway.client import QboGatewayClient


def monitor_connection(
    *,
    target: ConnectionTarget,
    qbo_gateway: QboGatewayClient,
    automation_gateway: AutomationGatewayClient,
    max_attempts: int,
    retry_delay_seconds: float,
    correlation_id: UUID | None = None,
    now: Callable[[], datetime] | None = None,
    sleeper: Callable[[float], None] = sleep,
) -> ConnectionStatusUpdate:
    request_id = correlation_id or uuid4()
    for attempt in range(1, max_attempts + 1):
        try:
            qbo_gateway.check_company_info(
                client_id=target.client_id,
                environment=target.environment,
                correlation_id=request_id,
            )
            break
        except Exception:
            if attempt == max_attempts:
                raise
            sleeper(retry_delay_seconds)

    clock = now or (lambda: datetime.now(UTC))
    update = ConnectionStatusUpdate(
        client_id=target.client_id,
        environment=target.environment,
        is_connected=True,
        checked_at=clock(),
        correlation_id=request_id,
    )
    automation_gateway.publish_connection_status(update)
    return update
