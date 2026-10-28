from uuid import UUID

import pytest

from qbo_connectivity.domain.models import ConnectionTarget
from qbo_connectivity.services.target_selection import select_targets_for_run

CLIENT_ID = UUID("070b2e37-aa28-4911-b2b2-e493678d38f5")
OTHER_ID = UUID("e10c2f93-6250-4302-a4f8-cc59209ef4be")


@pytest.mark.parametrize("conf", [None, {}])
def test_manual_and_scheduled_runs_select_all_active_environments_once(
    conf: dict[str, object] | None,
) -> None:
    targets = [
        ConnectionTarget(client_id=OTHER_ID, environment="sandbox"),
        ConnectionTarget(client_id=CLIENT_ID, environment="sandbox"),
        ConnectionTarget(client_id=CLIENT_ID, environment="prod"),
        ConnectionTarget(client_id=CLIENT_ID, environment="prod"),
    ]

    assert select_targets_for_run(targets, conf=conf) == [
        {"client_id": str(CLIENT_ID), "environment": "prod"},
        {"client_id": str(CLIENT_ID), "environment": "sandbox"},
        {"client_id": str(OTHER_ID), "environment": "sandbox"},
    ]


@pytest.mark.parametrize(
    "conf",
    [
        {"client_id": str(CLIENT_ID), "environment": "prod"},
        {"environment": "sandbox"},
        {"all": True},
    ],
)
def test_run_rejects_target_overrides(conf: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="run configuration is not supported"):
        select_targets_for_run(
            [ConnectionTarget(client_id=CLIENT_ID, environment="prod")], conf=conf
        )


@pytest.mark.parametrize("conf", [None, {}])
def test_run_has_no_tasks_when_no_active_targets(conf: dict[str, object] | None) -> None:
    assert select_targets_for_run([], conf=conf) == []
