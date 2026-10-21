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

The DAG requires an explicit `client_id` and `environment` in each manual run, checks that the requested connection belongs to an active client, then checks CompanyInfo once through QBO Gateway. No production credentials are included and the schedule remains disabled.

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

Airflow owns scheduling. It does not access the QBO application database directly.

## Production boundary

Production deployment uses the files under `deploy/`. The Airflow UI/API remains bound to VPS loopback port `8080`; Nginx exposes it at `https://qbo.headquarters.co/airflow/` with FAB authentication. The monitoring DAG remains manually triggered with no schedule. Application releases use immutable commit-SHA images; production delivery can run only manually from `main` after the one-time VPS preparation documented in `deploy/README.md`.

## Connectivity rule

```text
CompanyInfo returns 200                               -> publish is_connected=true
QBO Gateway returns 401 with Intuit invalid_grant     -> publish is_connected=false
Other responses, timeouts, or publication failures    -> fail the task; do not change stored status
```

QBO Gateway already records a confirmed OAuth `invalid_grant` as disconnected. Airflow
publishes the same result through Automation Gateway so the monitor run verifies that
publication succeeded. QBO Gateway currently maps upstream QBO API errors, including
upstream HTTP 400, to generic HTTP 502. Airflow therefore cannot safely classify those
responses as disconnected. Missing credentials (HTTP 404) are not a disconnected
credential and do not publish a status. QBO Gateway retains its internal retry policy
for upstream 429 and 5xx responses; Airflow makes one CompanyInfo request per task and
does not add another retry layer. Legacy `QBO_CHECK_MAX_ATTEMPTS` and
`QBO_CHECK_RETRY_DELAY_SECONDS` Compose variables are ignored by the application and
can be removed in a later Compose update. Unclassified errors cause no Airflow status
write; a confirmed `invalid_grant` can still be stored by QBO Gateway before Airflow
attempts publication.

For a manual run, provide `{"client_id": "<UUID>", "environment": "sandbox"}` (or `prod`) as the DAG run configuration. Missing or extra fields fail the run before any status is published. Broad scheduled runs require a separate reviewed change.

`tests/support/qbo_mock_app.py` is a local-only CompanyInfo mock used to exercise successful and failed checks without contacting Intuit.
