from __future__ import annotations

from uuid import NAMESPACE_URL, UUID, uuid5

import pendulum
from airflow.sdk import dag, get_current_context, task

from qbo_connectivity.domain.models import ConnectionTarget
from qbo_connectivity.integrations.automation_gateway.client import AutomationGatewayClient
from qbo_connectivity.integrations.notification_ledger import NotificationLedgerClient
from qbo_connectivity.integrations.qbo_gateway.client import QboGatewayClient
from qbo_connectivity.services.monitor_connection import monitor_connection
from qbo_connectivity.services.target_selection import select_targets_for_run
from qbo_connectivity.settings import ServiceSettings


@dag(
    dag_id="qbo_connection_monitor",
    schedule="0 8 * * 1",
    start_date=pendulum.datetime(2026, 10, 27, tz="America/Mexico_City"),
    catchup=False,
    tags=["qbo", "connectivity"],
    default_args={"retries": 0},
    max_active_runs=1,
    max_active_tasks=2,
    description="Check all active QBO connections weekly or on manual trigger.",
)
def qbo_connection_monitor():
    @task
    def list_targets() -> list[dict[str, str]]:
        dag_run = get_current_context()["dag_run"]
        settings = ServiceSettings.from_environment()
        settings.validate_runtime()
        with QboGatewayClient(
            base_url=settings.qbo_gateway_base_url,
            api_key=settings.qbo_gateway_api_key,
            timeout_seconds=settings.request_timeout_seconds,
        ) as qbo_gateway:
            return select_targets_for_run(qbo_gateway.list_connection_targets(), conf=dag_run.conf)

    @task
    def check_and_publish(target_data: dict[str, str]) -> dict[str, str | bool]:
        settings = ServiceSettings.from_environment()
        settings.validate_runtime()
        target = ConnectionTarget(
            client_id=UUID(target_data["client_id"]),
            environment=target_data["environment"],
        )
        run_id = get_current_context()["dag_run"].run_id
        event_id = uuid5(
            NAMESPACE_URL,
            f"qbo.connection_checked.v1:{run_id}:{target.client_id}:{target.environment}",
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
            NotificationLedgerClient(
                url=settings.notification_ledger_url,
                api_key=settings.notification_router_api_key,
                timeout_seconds=settings.request_timeout_seconds,
            ) as notification_ledger,
        ):
            update = monitor_connection(
                target=target,
                qbo_gateway=qbo_gateway,
                automation_gateway=automation_gateway,
                notification_ledger=notification_ledger,
                notification_recipient=settings.notification_slack_destination_id,
                event_id=event_id,
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
