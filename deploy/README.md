# Production deployment

The production stack is intentionally separate from local Docker Compose. It runs an immutable application image, dedicated PostgreSQL metadata database, persistent metadata/log/config volumes, and binds the Airflow UI/API only to VPS loopback port `8080`. Nginx exposes the UI at `https://qbo.headquarters.co/airflow/` after authentication is provisioned.

Before migrations and runtime startup, a one-shot root container limits its work to assigning the persistent log/config volumes to Airflow UID `50000`. Runtime components continue to run unprivileged.

The DAG has `schedule=None` and new DAGs are paused by default. Installing the stack does not enable periodic monitoring.
Manual DAG runs require `client_id` and `environment` (`prod` or `sandbox`) in the run configuration. The selected pair must belong to an active client. A run without an explicit scope fails before publishing any status.

## One-time VPS preparation

1. Create `/root/automations/qbo-connectivity-airflow` owned by root with mode `0700`.
2. Install `docker-compose.production.yml` there as root mode `0644`.
3. Create its private `.env` as root mode `0600`; never commit or print its values.
4. Install `deploy-qbo-connectivity-airflow` at `/usr/local/sbin/` as root mode `0755`.
5. Permit the existing `deploy` SSH user to run only that script without a password.
6. Configure the GitHub `production` environment secrets used by the manual workflow.

The workflow deploys an image but does not update the server-installed Compose file.
When Compose changes, install the reviewed file separately and validate it on the VPS
before dispatching the deployment workflow. Airflow workers need
`AIRFLOW__CORE__EXECUTION_API_SERVER_URL=http://airflow-api-server:8080/airflow/execution/`
to reach the API server on the private Compose network. The production image includes
the FAB auth provider; the production Compose selects FAB instead of Simple Auth Manager.
Back up the Airflow metadata database before changing the auth manager because its
tables require migrations. Provision one Admin account privately before enabling the
Nginx route. Never include its password in a shell command line or committed file.

For the initial FAB/path-prefix cutover, stage the new image with the existing private
Compose configuration first. Back up the metadata database and installed Compose file,
then install the prefixed Compose and restart the Airflow services. Verify the prefixed
loopback health endpoint, an authenticated login, and a manual task run before installing
the Nginx snippets and adding their include to the HTTPS server block. Install the new
deploy script only after the prefixed health endpoint is healthy. The rate-limit snippet
belongs in Nginx's `http` context; the locations snippet belongs only in the HTTPS
`qbo.headquarters.co` server block. Validate with `nginx -t` before reload.

## Runtime boundaries

- The dedicated Nginx `/airflow/` route proxies to the VPS loopback port `8080`.
- Port `8080` remains reachable only from the VPS itself or through an SSH tunnel.
- Airflow reaches QBO Gateway on host port `8000` through `host.docker.internal`.
- Airflow joins the existing `automation-gateway_default` Docker network and reaches Automation Gateway privately as `http://automation-gateway:8000`; port `8002` remains bound to VPS loopback only.
- Airflow owns its metadata PostgreSQL volume; it never connects directly to the QBO application database.

## Rollback boundary

The script records the last healthy application image and restores it when candidate health validation fails. It does not revert Compose configuration or database migrations. Keep a copy of the previously installed Compose file; restore it separately if the prefixed deployment fails. Database migrations are forward-only; take and verify a metadata database backup before adding FAB or upgrading Airflow. The current release fixes Airflow at `3.3.2`.
