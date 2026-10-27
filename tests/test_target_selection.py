from uuid import UUID

import pytest

from qbo_connectivity.domain.models import ConnectionTarget
from qbo_connectivity.services.target_selection import (
    require_manual_target,
    select_active_target,
    select_targets_for_run,
)

CLIENT_ID = UUID("070b2e37-aa28-4911-b2b2-e493678d38f5")


def test_manual_run_selects_only_requested_active_environment() -> None:
    requested = require_manual_target({"client_id": str(CLIENT_ID), "environment": "sandbox"})
    active = [
        ConnectionTarget(client_id=CLIENT_ID, environment="prod"),
        requested,
        ConnectionTarget(
            client_id=UUID("e10c2f93-6250-4302-a4f8-cc59209ef4be"), environment="sandbox"
        ),
    ]

    assert select_active_target(active, requested) == [requested.to_dict()]


@pytest.mark.parametrize(
    "conf",
    [
        None,
        {},
        {"environment": "prod"},
        {"client_id": str(CLIENT_ID)},
        {"client_id": str(CLIENT_ID), "environment": "production"},
        {"client_id": "invalid", "environment": "prod"},
        {"client_id": str(CLIENT_ID), "environment": "prod", "all": True},
    ],
)
def test_manual_run_rejects_missing_or_invalid_scope(conf: dict[str, object] | None) -> None:
    with pytest.raises(ValueError):
        require_manual_target(conf)


def test_manual_run_rejects_client_environment_not_active() -> None:
    requested = require_manual_target({"client_id": str(CLIENT_ID), "environment": "sandbox"})

    with pytest.raises(ValueError, match="not an active QBO target"):
        select_active_target([ConnectionTarget(client_id=CLIENT_ID, environment="prod")], requested)


def test_scheduled_run_selects_all_active_environments_once() -> None:
    other_id = UUID("e10c2f93-6250-4302-a4f8-cc59209ef4be")
    targets = [
        ConnectionTarget(client_id=other_id, environment="sandbox"),
        ConnectionTarget(client_id=CLIENT_ID, environment="sandbox"),
        ConnectionTarget(client_id=CLIENT_ID, environment="prod"),
        ConnectionTarget(client_id=CLIENT_ID, environment="prod"),
    ]

    assert select_targets_for_run(targets, run_type="scheduled", conf=None) == [
        {"client_id": str(CLIENT_ID), "environment": "prod"},
        {"client_id": str(CLIENT_ID), "environment": "sandbox"},
        {"client_id": str(other_id), "environment": "sandbox"},
    ]


def test_manual_run_still_selects_only_one_target() -> None:
    targets = [
        ConnectionTarget(client_id=CLIENT_ID, environment="prod"),
        ConnectionTarget(client_id=CLIENT_ID, environment="sandbox"),
    ]

    assert select_targets_for_run(
        targets,
        run_type="manual",
        conf={"client_id": str(CLIENT_ID), "environment": "sandbox"},
    ) == [{"client_id": str(CLIENT_ID), "environment": "sandbox"}]


@pytest.mark.parametrize(
    ("run_type", "conf", "targets"),
    [
        ("manual", None, [ConnectionTarget(client_id=CLIENT_ID, environment="prod")]),
        (
            "scheduled",
            {"client_id": str(CLIENT_ID)},
            [ConnectionTarget(client_id=CLIENT_ID, environment="prod")],
        ),
        ("scheduled", None, []),
        ("backfill", None, [ConnectionTarget(client_id=CLIENT_ID, environment="prod")]),
    ],
)
def test_run_selection_fails_closed(
    run_type: str, conf: dict[str, object] | None, targets: list[ConnectionTarget]
) -> None:
    with pytest.raises(ValueError):
        select_targets_for_run(targets, run_type=run_type, conf=conf)
