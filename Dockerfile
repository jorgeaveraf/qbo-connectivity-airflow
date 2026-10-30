FROM apache/airflow:3.3.2-python3.12

COPY --chown=airflow:root requirements.txt /opt/airflow/requirements.txt
RUN pip install --no-cache-dir -r /opt/airflow/requirements.txt \
    && pip check

COPY --chown=airflow:root dags /opt/airflow/dags
COPY --chown=airflow:root plugins /opt/airflow/plugins
COPY --chown=airflow:root src /opt/airflow/src
COPY --chown=airflow:root deploy/docker-compose.production.yml /opt/airflow/deploy/docker-compose.production.yml

ENV PYTHONPATH=/opt/airflow/src
