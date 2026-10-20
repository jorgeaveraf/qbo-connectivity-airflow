from dataclasses import dataclass
from os import environ


@dataclass(frozen=True)
class ServiceSettings:
    qbo_gateway_base_url: str
    qbo_gateway_api_key: str
    automation_gateway_base_url: str
    automation_gateway_api_key: str
    request_timeout_seconds: float
    qbo_check_max_attempts: int
    qbo_check_retry_delay_seconds: float

    @classmethod
    def from_environment(cls) -> "ServiceSettings":
        return cls(
            qbo_gateway_base_url=environ.get("QBO_GATEWAY_BASE_URL", ""),
            qbo_gateway_api_key=environ.get("QBO_GATEWAY_API_KEY", ""),
            automation_gateway_base_url=environ.get("AUTOMATION_GATEWAY_BASE_URL", ""),
            automation_gateway_api_key=environ.get("AUTOMATION_GATEWAY_API_KEY", ""),
            request_timeout_seconds=float(environ.get("REQUEST_TIMEOUT_SECONDS", "30")),
            qbo_check_max_attempts=int(environ.get("QBO_CHECK_MAX_ATTEMPTS", "3")),
            qbo_check_retry_delay_seconds=float(
                environ.get("QBO_CHECK_RETRY_DELAY_SECONDS", "5")
            ),
        )

    def validate_runtime(self) -> None:
        required = {
            "QBO_GATEWAY_BASE_URL": self.qbo_gateway_base_url,
            "QBO_GATEWAY_API_KEY": self.qbo_gateway_api_key,
            "AUTOMATION_GATEWAY_BASE_URL": self.automation_gateway_base_url,
            "AUTOMATION_GATEWAY_API_KEY": self.automation_gateway_api_key,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"Missing required service settings: {', '.join(missing)}")
        if self.request_timeout_seconds <= 0:
            raise ValueError("REQUEST_TIMEOUT_SECONDS must be greater than zero")
        if self.qbo_check_max_attempts < 1:
            raise ValueError("QBO_CHECK_MAX_ATTEMPTS must be at least one")
        if self.qbo_check_retry_delay_seconds < 0:
            raise ValueError("QBO_CHECK_RETRY_DELAY_SECONDS cannot be negative")
