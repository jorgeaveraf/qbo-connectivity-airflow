from __future__ import annotations

from datetime import datetime
from uuid import UUID

from airflow.sdk import dag, get_current_context, task

from qbo_connectivity.domain.models import ConnectionTarget
from qbo_connectivity.integrations.automation_gateway.client import AutomationGatewayClient
from qbo_connectivity.integrations.qbo_gateway.client import QboGatewayClient
from qbo_connectivity.services.monitor_connection import monitor_connection
from qbo_connectivity.services.target_selection import require_manual_target, select_active_target
from qbo_connectivity.settings import ServiceSettings


@dag(
    dag_id="qbo_connection_monitor",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["qbo", "connectivity"],
    default_args={"retries": 0},
    max_active_runs=1,
    description="Check one selected QBO connection and publish a successful check.",
)
def qbo_connection_monitor():
    @task
    def list_targets() -> list[dict[str, str]]:
        requested = require_manual_target(get_current_context()["dag_run"].conf)
        settings = ServiceSettings.from_environment()
        settings.validate_runtime()
        with QboGatewayClient(
            base_url=settings.qbo_gateway_base_url,
            api_key=settings.qbo_gateway_api_key,
            timeout_seconds=settings.request_timeout_seconds,
        ) as qbo_gateway:
            return select_active_target(qbo_gateway.list_connection_targets(), requested)

    @task
    def check_and_publish(target_data: dict[str, str]) -> dict[str, str | bool]:
        settings = ServiceSettings.from_environment()
        settings.validate_runtime()
        target = ConnectionTarget(
            client_id=UUID(target_data["client_id"]),
            environment=target_data["environment"],
        )
        with (
            QboGatewayClient(
                base_url=settings.qbo_gateway_base_url,
                api_key=settings.qbo_gateway_api_key,
                timeout_seconds=settings.request_timeout_seconds,
            ) as qbo_gateway,
            AutomationGatewayClient(
                base_url=settings.automation_gateway_base_url,
                api_key=settings.automation_gateway_api_key,
                timeout_seconds=settings.request_timeout_seconds,
            ) as automation_gateway,
        ):
            update = monitor_connection(
                target=target,
                qbo_gateway=qbo_gateway,
                automation_gateway=automation_gateway,
            )
        return {
            "client_id": str(update.client_id),
            "environment": update.environment,
            "is_connected": update.is_connected,
            "checked_at": update.checked_at.isoformat(),
            "correlation_id": str(update.correlation_id),
        }

    check_and_publish.expand(target_data=list_targets())


qbo_connection_monitor()
