from collections.abc import Mapping
from uuid import UUID

from qbo_connectivity.domain.models import ConnectionTarget


def require_manual_target(conf: Mapping[str, object] | None) -> ConnectionTarget:
    """Require an explicit client and environment for every manual DAG run."""
    if not conf or set(conf) != {"client_id", "environment"}:
        raise ValueError("Manual runs require only client_id and environment")

    client_id = conf["client_id"]
    environment = conf["environment"]
    if not isinstance(client_id, str) or not isinstance(environment, str):
        raise ValueError("client_id and environment must be strings")
    if environment not in {"prod", "sandbox"}:
        raise ValueError("environment must be prod or sandbox")
    try:
        parsed_client_id = UUID(client_id)
    except ValueError as exc:
        raise ValueError("client_id must be a UUID") from exc

    return ConnectionTarget(client_id=parsed_client_id, environment=environment)


def select_active_target(
    targets: list[ConnectionTarget], requested: ConnectionTarget
) -> list[dict[str, str]]:
    if requested not in targets:
        raise ValueError("Requested client/environment is not an active QBO target")
    return [requested.to_dict()]
