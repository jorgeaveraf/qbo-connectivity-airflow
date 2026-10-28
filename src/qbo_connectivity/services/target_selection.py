from collections.abc import Mapping

from qbo_connectivity.domain.models import ConnectionTarget


def select_targets_for_run(
    targets: list[ConnectionTarget], *, conf: Mapping[str, object] | None
) -> list[dict[str, str]]:
    if conf:
        raise ValueError(
            "This DAG checks all active QBO targets; run configuration is not supported"
        )

    selected = sorted(set(targets), key=lambda target: (str(target.client_id), target.environment))
    return [target.to_dict() for target in selected]
