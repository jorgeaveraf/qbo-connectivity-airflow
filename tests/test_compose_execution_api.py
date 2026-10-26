"""Keep task workers pointed at the API server in both Docker deployments."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXECUTION_API_URL = "http://airflow-api-server:8080/execution/"
PRODUCTION_EXECUTION_API_URL = "http://airflow-api-server:8080/airflow/execution/"
AIRFLOW_SERVICES = (
    "airflow-api-server",
    "airflow-scheduler",
    "airflow-dag-processor",
    "airflow-triggerer",
)


@pytest.mark.parametrize("production", [False, True], ids=["local", "production"])
def test_airflow_services_use_internal_execution_api(production: bool) -> None:
    if shutil.which("docker") is None:
        pytest.skip("Docker Compose CLI is not installed")

    command = ["docker", "compose"]
    environment = os.environ.copy()
    if production:
        environment.update(
            AIRFLOW_IMAGE="ghcr.io/example/qbo-connectivity-airflow:" + "0" * 40,
            AIRFLOW_ENV_FILE="qbo-connectivity-airflow.env.example",
        )
        command.extend(["--env-file", "deploy/qbo-connectivity-airflow.env.example"])
        compose_file = "deploy/docker-compose.production.yml"
    else:
        compose_file = "docker-compose.yml"
    command.extend(["--file", compose_file, "config", "--format", "json"])

    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=environment,
    )
    services = json.loads(result.stdout)["services"]
    for service_name in AIRFLOW_SERVICES:
        assert services[service_name]["environment"]["AIRFLOW__CORE__EXECUTION_API_SERVER_URL"] == (
            PRODUCTION_EXECUTION_API_URL if production else EXECUTION_API_URL
        )
        if production:
            assert services[service_name]["environment"]["AIRFLOW__API__BASE_URL"] == (
                "https://qbo.headquarters.co/airflow"
            )
            assert services[service_name]["environment"]["AIRFLOW__CORE__AUTH_MANAGER"] == (
                "airflow.providers.fab.auth_manager.fab_auth_manager.FabAuthManager"
            )
