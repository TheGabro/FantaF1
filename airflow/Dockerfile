FROM apache/airflow:3.3.1-python3.12

COPY --chown=airflow:root airflow/requirements-airflow.txt /opt/fantaf1/requirements.txt
RUN pip install --no-cache-dir "apache-airflow==${AIRFLOW_VERSION}" -r /opt/fantaf1/requirements.txt

COPY --chown=airflow:root . /opt/fantaf1
