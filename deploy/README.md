# Airflow production cutover

Deploy Gateway v2 first and confirm its API, Redis, and worker are healthy. Airflow stays on its existing PostgreSQL volume and loopback port 8080. The new release joins `automation-gateway-v2_default` and sends jobs to `http://automation-gateway-v2:8000`. QBO Gateway and its database are outside this rollout.

## One-time preparation before merging to main

The VPS already has the root-owned Airflow directory, `deploy` user, Docker Compose, and sudo permission for `/usr/local/sbin/deploy-qbo-connectivity-airflow`. Keep these. Install the reviewed new script at that existing path.

Keep `/root/automations/qbo-connectivity-airflow/.env` root-owned and mode 600. Add the new notification ledger, router key, and Slack destination values from `deploy/qbo-connectivity-airflow.env.example`; set `AUTOMATION_GATEWAY_BASE_URL=http://automation-gateway-v2:8000`. Check the private Gateway v2 network exists. The GitHub `production` environment needs the existing SSH secrets; remove manual environment reviewers if main must deploy automatically. Require the CI job on protected main.

`develop` and pull requests run CI only. A successful push to `main` builds and publishes the immutable Airflow image, then deploys it. Actions passes its short-lived GHCR token over SSH stdin; the script stores Docker authentication only in a temporary root-owned directory. The script checks Gateway v2, extracts the production Compose from the image, backs up the Airflow metadata database, verifies the dump, preserves the first release as `docker-compose.legacy.yml` and `.release.legacy.env`, runs the pinned Airflow 3.3.2 migration, recreates runtime services, checks API and process health, and records the image. A failed candidate restores the previous Compose and image. The script never deletes the metadata volume. Database migrations are forward-only: inspect the backup in `backups/` before any version or schema upgrade and do not treat image rollback as database rollback.

The DAG has a weekly Monday 08:00 `America/Mexico_City` schedule but remains paused during deployment. Confirm the current active `prod` and `sandbox` targets, notification behavior, and next scheduled time before deliberately unpausing it. Scoped manual runs remain available with explicit `client_id` and `environment`. Retire the old Gateway in a separate change.
