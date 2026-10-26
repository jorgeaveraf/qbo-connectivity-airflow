from dataclasses import dataclass
from os import environ


@dataclass(frozen=True)
class ServiceSettings:
    qbo_gateway_base_url: str
    qbo_gateway_api_key: str
    automation_gateway_base_url: str
    automation_gateway_api_key: str
    notification_ledger_url: str
    notification_router_api_key: str
    notification_slack_destination_id: str
    request_timeout_seconds: float

    @classmethod
    def from_environment(cls) -> "ServiceSettings":
        return cls(
            qbo_gateway_base_url=environ.get("QBO_GATEWAY_BASE_URL", ""),
            qbo_gateway_api_key=environ.get("QBO_GATEWAY_API_KEY", ""),
            automation_gateway_base_url=environ.get("AUTOMATION_GATEWAY_BASE_URL", ""),
            automation_gateway_api_key=environ.get("AUTOMATION_GATEWAY_API_KEY", ""),
            notification_ledger_url=environ.get("NOTIFICATION_LEDGER_URL", ""),
            notification_router_api_key=environ.get("NOTIFICATION_ROUTER_API_KEY", ""),
            notification_slack_destination_id=environ.get(
                "QBO_DISCONNECT_SLACK_DESTINATION_ID", ""
            ),
            request_timeout_seconds=float(environ.get("REQUEST_TIMEOUT_SECONDS", "30")),
        )

    def validate_runtime(self) -> None:
        required = {
            "QBO_GATEWAY_BASE_URL": self.qbo_gateway_base_url,
            "QBO_GATEWAY_API_KEY": self.qbo_gateway_api_key,
            "AUTOMATION_GATEWAY_BASE_URL": self.automation_gateway_base_url,
            "AUTOMATION_GATEWAY_API_KEY": self.automation_gateway_api_key,
            "NOTIFICATION_LEDGER_URL": self.notification_ledger_url,
            "NOTIFICATION_ROUTER_API_KEY": self.notification_router_api_key,
            "QBO_DISCONNECT_SLACK_DESTINATION_ID": self.notification_slack_destination_id,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"Missing required service settings: {', '.join(missing)}")
        if self.request_timeout_seconds <= 0:
            raise ValueError("REQUEST_TIMEOUT_SECONDS must be greater than zero")
