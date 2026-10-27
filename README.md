# QBO Connectivity Airflow

Dedicated Apache Airflow instance for monitoring QBO client connectivity and publishing conclusive observations as jobs to Automation Gateway.

## Current scope

This repository provides the QBO connectivity monitor:

- Apache Airflow 3.3.2 on Python 3.12;
- LocalExecutor;
- dedicated PostgreSQL 17 metadata database;
- API server, scheduler, DAG processor, and triggerer;
- a paused connectivity DAG configured for Mondays at 08:00 in `America/Mexico_City`;
- local unit tests and CI validation;
- CI-gated production delivery from `main`.

Manual runs still require an explicit `client_id` and `environment` and check only that active connection. Scheduled runs select all active client/environment connections returned by QBO Gateway, including both `prod` and `sandbox`, and check CompanyInfo once per target. The DAG remains paused until a separate production activation. No production credentials are included.

## Local startup

Optionally copy `.env.example` to `.env` and replace the local-only defaults.

```bash
docker compose up --build -d
docker compose ps
```

The local Airflow UI/API server is exposed at `http://localhost:8080`. Airflow 3 uses the Simple Auth Manager by default; it is suitable only for local development and must be replaced before deployment.

For the isolated local end-to-end circuit, first start the mock-backed Automation Gateway and worker from `../ingestion-gateway` with `docker compose -f automation_gateway/tests/support/docker-compose.worker.yml up -d --build`. Then start Airflow with `docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build`. This override points Airflow only to the local test services on ports `18091` and `18092`, and exposes its UI at `http://localhost:8081` so the FinOps OAuth return can keep port `8080`. Keep the DAG paused and run it manually with the sandbox client ID `477751f2-1142-4283-a3c0-387f8aa45fbd`. This circuit does not exercise the real QBO Gateway or send Slack messages. The FinOps frontend/backend use their separate local QBO Gateway circuit.

To point that local circuit at the same QBO Gateway used by FinOps, add `-f automation_gateway/tests/support/docker-compose.qbo-local.yml` to the worker stack and `-f docker-compose.qbo-local.yml` to the Airflow stack. For both commands, pass `--env-file ../qbo-gateway/.env` so Compose obtains the local `API_KEY` without copying it into either repository. The notification ledger and router remain local mocks. Keep the DAG paused until a deliberate sandbox test: a run against a real entity can update its saved connection status through the worker.

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
Airflow -> QBO Gateway client detail and CompanyInfo (read-only)
Airflow -> n8n Notification Router webhook (authenticated, read-only sent-delivery lookup)
Airflow -> Automation Gateway generic job -> Redis List -> Automation Worker
Automation Worker -> QBO Gateway existing status endpoint
Automation Worker -> n8n Notification Router (only if eligible)
```

Airflow owns scheduling and a preliminary 48-hour notification hint. The worker
rechecks n8n's sent ledger before delivery and owns the QBO status write. Airflow
does not access the QBO application database directly. The n8n URL configured in
`NOTIFICATION_LEDGER_URL` must point to the router's
`/webhook/automation/notification-ledger/last-sent/v1` endpoint, and
`NOTIFICATION_ROUTER_API_KEY` must use the router webhook API key. Airflow sends
`POST` JSON with `client_id` and `environment`; the response contains
`result_type: "notification_ledger.last_sent.v1"` and `last_notified_at` as an
ISO8601 UTC timestamp or `null`. If the ledger is unavailable or returns an
invalid response, the conclusive status job is still published with an unknown
notification hint; the worker retries its own ledger lookup and never
interprets an error as permission to notify.
`QBO_DISCONNECT_SLACK_DESTINATION_ID` is the DM conversation ID used as the
delivery recipient, so the preliminary ledger lookup matches the worker's
destination. The current configured example is `D0B3LSR4C1Y`.

## Production boundary

Production deployment uses the files under `deploy/`. The Airflow UI/API remains bound to VPS loopback port `8080`; Nginx exposes it at `https://qbo.headquarters.co/airflow/` with FAB authentication. The monitoring DAG is configured for Mondays at 08:00 in `America/Mexico_City` with `catchup=False`, one active run, and at most two active tasks. It remains paused after deployment until the scheduled-target set and notification effects are reviewed. Application releases use immutable commit-SHA images; a successful push to `main` deploys after CI.

## Connectivity rule

```text
CompanyInfo returns 200                               -> publish is_connected=true
QBO Gateway returns 401 with Intuit invalid_grant     -> publish is_connected=false
Other responses, timeouts, or publication failures    -> fail the task; do not change stored status
```

QBO Gateway already records a confirmed OAuth `invalid_grant` as disconnected. Airflow
publishes the observation through Automation Gateway; the worker persists the
observation via QBO Gateway's existing endpoint. QBO Gateway currently maps upstream QBO API errors, including
upstream HTTP 400, to generic HTTP 502. Airflow therefore cannot safely classify those
responses as disconnected. Missing credentials (HTTP 404) are not a disconnected
credential and do not publish a status. QBO Gateway retains its internal retry policy
for upstream 429 and 5xx responses; Airflow makes one CompanyInfo request per task and
does not add another retry layer. Legacy `QBO_CHECK_MAX_ATTEMPTS` and
`QBO_CHECK_RETRY_DELAY_SECONDS` Compose variables are ignored by the application and
can be removed in a later Compose update. Unclassified errors cause no Airflow status
write by the worker; a confirmed `invalid_grant` can still be stored internally by
QBO Gateway before Airflow attempts publication.

For a manual run, provide `{"client_id": "<UUID>", "environment": "sandbox"}` (or `prod`) as the DAG run configuration. Missing or extra fields fail the run before any status is published. Scheduled runs reject target overrides and fail visibly if QBO Gateway returns no active targets.

`tests/support/qbo_mock_app.py` is a local-only CompanyInfo mock used to exercise successful and failed checks without contacting Intuit.
