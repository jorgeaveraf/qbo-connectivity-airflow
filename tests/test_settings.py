import pytest

from qbo_connectivity.settings import ServiceSettings


def test_settings_default_to_disconnected_local_integrations(monkeypatch) -> None:
    for name in (
        "QBO_GATEWAY_BASE_URL",
        "QBO_GATEWAY_API_KEY",
        "AUTOMATION_GATEWAY_BASE_URL",
        "AUTOMATION_GATEWAY_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = ServiceSettings.from_environment()

    assert settings.qbo_gateway_base_url == ""
    assert settings.qbo_gateway_api_key == ""
    assert settings.automation_gateway_base_url == ""
    assert settings.automation_gateway_api_key == ""


def test_settings_read_local_environment(monkeypatch) -> None:
    monkeypatch.setenv("QBO_GATEWAY_BASE_URL", "http://qbo.local")
    monkeypatch.setenv("QBO_GATEWAY_API_KEY", "qbo-local-key")
    monkeypatch.setenv("AUTOMATION_GATEWAY_BASE_URL", "http://automation.local")
    monkeypatch.setenv("AUTOMATION_GATEWAY_API_KEY", "automation-local-key")

    settings = ServiceSettings.from_environment()

    assert settings.qbo_gateway_base_url == "http://qbo.local"
    assert settings.qbo_gateway_api_key == "qbo-local-key"
    assert settings.automation_gateway_base_url == "http://automation.local"
    assert settings.automation_gateway_api_key == "automation-local-key"


def test_runtime_validation_reports_missing_integrations() -> None:
    settings = ServiceSettings(
        qbo_gateway_base_url="",
        qbo_gateway_api_key="",
        automation_gateway_base_url="",
        automation_gateway_api_key="",
        request_timeout_seconds=30,
    )

    with pytest.raises(ValueError, match="Missing required service settings"):
        settings.validate_runtime()


def test_runtime_validation_rejects_invalid_timeout() -> None:
    settings = ServiceSettings(
        qbo_gateway_base_url="http://qbo.local",
        qbo_gateway_api_key="qbo-key",
        automation_gateway_base_url="http://automation.local",
        automation_gateway_api_key="automation-key",
        request_timeout_seconds=0,
    )

    with pytest.raises(ValueError, match="REQUEST_TIMEOUT_SECONDS"):
        settings.validate_runtime()
