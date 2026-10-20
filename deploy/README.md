# Production deployment

The production stack is intentionally separate from local Docker Compose. It runs an immutable application image, dedicated PostgreSQL metadata database, persistent metadata/log/config volumes, and binds the Airflow UI/API only to VPS loopback port `8080`.

The DAG has `schedule=None` and new DAGs are paused by default. Installing the stack does not enable periodic monitoring.

## One-time VPS preparation

1. Create `/root/automations/qbo-connectivity-airflow` owned by root with mode `0700`.
2. Install `docker-compose.production.yml` there as root mode `0644`.
3. Create its private `.env` as root mode `0600`; never commit or print its values.
4. Install `deploy-qbo-connectivity-airflow` at `/usr/local/sbin/` as root mode `0755`.
5. Permit the existing `deploy` SSH user to run only that script without a password.
6. Configure the GitHub `production` environment secrets used by the manual workflow.

## Runtime boundaries

- No Nginx route is created.
- Port `8080` is reachable only from the VPS itself or through an SSH tunnel.
- Airflow reaches QBO Gateway on host port `8000` and Automation Gateway on host port `8002` through `host.docker.internal`.
- Airflow owns its metadata PostgreSQL volume; it never connects directly to the QBO application database.

## Rollback boundary

The script records the last healthy application image and restores it when candidate health validation fails. Database migrations are forward-only; before an Airflow version upgrade, take and verify a metadata database backup. The current release fixes Airflow at `3.3.2`, so ordinary application releases do not change the metadata schema.
