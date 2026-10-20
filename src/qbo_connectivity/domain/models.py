from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

Environment = Literal["prod", "sandbox"]


@dataclass(frozen=True)
class ConnectionTarget:
    client_id: UUID
    environment: Environment

    def to_dict(self) -> dict[str, str]:
        return {
            "client_id": str(self.client_id),
            "environment": self.environment,
        }


@dataclass(frozen=True)
class ConnectionStatusUpdate:
    client_id: UUID
    environment: Environment
    is_connected: bool
    checked_at: datetime
    correlation_id: UUID
    provider: str = "qbo"

    def payload(self) -> dict[str, str | bool]:
        data = asdict(self)
        data.pop("client_id")
        data["checked_at"] = self.checked_at.isoformat()
        data["correlation_id"] = str(self.correlation_id)
        return data
