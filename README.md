# QBO Connectivity Airflow

Dedicated Apache Airflow instance for monitoring QBO client connectivity and publishing the latest boolean result to Automation Gateway.

## Current scope

This repository currently provides the local monitoring implementation:

- Apache Airflow 3.3.2 on Python 3.12;
- LocalExecutor;
- dedicated PostgreSQL 17 metadata database;
- API server, scheduler, DAG processor, and triggerer;
- a paused, manually triggered connectivity DAG;
- local unit tests and CI validation;
- a separate, manually triggered production delivery path.

The DAG requires an explicit `client_id` and `environment` in each manual run, checks that the requested connection belongs to an active client, then checks CompanyInfo with bounded retries. No production credentials are included and the schedule remains disabled.

## Local startup

Optionally copy `.env.example` to `.env` and replace the local-only defaults.

```bash
docker compose up --build -d
docker compose ps
```

The local Airflow UI/API server is exposed at `http://localhost:8080`. Airflow 3 uses the Simple Auth Manager by default; it is suitable only for local development and must be replaced before deployment.

Stop the local stack without deleting metadata:

```bash
docker compose down
```

Deleting the volume is intentionally not part of the normal workflow.

## Validation

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
python -m ruff check src tests dags
docker compose config --quiet
```

The Compose regression test checks that every Airflow runtime service points to the
internal Execution API. For an end-to-end local run, use the isolated mock services in
`tests/support/docker-compose.integration.yml`; they replace both external gateways
and never publish to QBO or the production database.

## Planned data flow

```text
Airflow -> QBO Gateway CompanyInfo
Airflow -> Automation Gateway connection status
```

Airflow owns scheduling and retries. It does not access the QBO application database directly.

## Production boundary

Production deployment uses the files under `deploy/`. The Airflow UI/API binds only to VPS loopback port `8080`, has no Nginx route, and the monitoring DAG remains manually triggered with no schedule. Application releases use immutable commit-SHA images; production delivery can run only manually from `main` after the one-time VPS preparation documented in `deploy/README.md`.

## Connectivity rule

```text
CompanyInfo succeeds within the configured attempts -> publish is_connected=true
All configured attempts fail                         -> fail the task; do not change stored status
```

QBO Gateway already records a confirmed OAuth `invalid_grant` as disconnected. Its CompanyInfo endpoint currently reports other QBO errors as a generic HTTP 502, so Airflow cannot safely interpret a failed request as a confirmed disconnection. Failure to check or publish the result fails the Airflow task without publishing a false status. The task uses Airflow retries.

For a manual run, provide `{"client_id": "<UUID>", "environment": "sandbox"}` (or `prod`) as the DAG run configuration. Missing or extra fields fail the run before any status is published. Broad scheduled runs require a separate reviewed change.

`tests/support/qbo_mock_app.py` is a local-only CompanyInfo mock used to exercise successful and failed checks without contacting Intuit.
