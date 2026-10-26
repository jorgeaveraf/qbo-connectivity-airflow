from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx
import pytest

from qbo_connectivity.domain.models import ConnectionTarget
from qbo_connectivity.integrations.qbo_gateway.client import StoredConnectionState
from qbo_connectivity.services.monitor_connection import monitor_connection

CLIENT_ID = UUID("477751f2-1142-4283-a3c0-387f8aa45fbd")
NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)


class Qbo:
    def __init__(self, previous: bool, result: bool):
        self.previous = previous
        self.result = result

    def get_connection_state(self, **_kwargs):
        return StoredConnectionState(self.previous, NOW - timedelta(hours=1))

    def check_company_info(self, **_kwargs):
        return self.result


class Ledger:
    def __init__(self, last=None, failure=False):
        self.last = last
        self.failure = failure

    def last_sent_at(self, **_kwargs):
        if self.failure:
            raise httpx.ReadTimeout("local ledger unavailable")
        return self.last


class Publisher:
    def __init__(self):
        self.updates = []

    def publish_connection_status(self, update):
        self.updates.append(update)


@pytest.mark.parametrize(
    ("previous", "result", "last", "expected"),
    [
        (True, False, NOW - timedelta(minutes=2), True),
        (False, False, NOW - timedelta(hours=47), False),
        (False, False, NOW - timedelta(hours=49), True),
        (False, False, None, True),
        (False, True, None, None),
    ],
)
def test_airflow_notification_hint(previous, result, last, expected):
    publisher = Publisher()
    update = monitor_connection(
        target=ConnectionTarget(CLIENT_ID, "sandbox"),
        qbo_gateway=Qbo(previous, result),
        automation_gateway=publisher,
        notification_ledger=Ledger(last),
        notification_recipient="D0B3LSR4C1Y",
        now=lambda: NOW,
    )
    assert update.notification_candidate is expected
    assert update.observed_previous_connected is previous
    assert publisher.updates == [update]


def test_failed_ledger_still_publishes_conclusive_status_for_worker_recheck():
    publisher = Publisher()
    update = monitor_connection(
        target=ConnectionTarget(CLIENT_ID, "sandbox"),
        qbo_gateway=Qbo(False, False),
        automation_gateway=publisher,
        notification_ledger=Ledger(failure=True),
        notification_recipient="D0B3LSR4C1Y",
        now=lambda: NOW,
    )
    assert update.notification_candidate is None
    assert publisher.updates == [update]
