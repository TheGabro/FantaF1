from datetime import timedelta

import pendulum

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG


with DAG(
    dag_id="fantaf1_retry_demo",
    description="Dimostrazione del meccanismo di retry di Airflow",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    schedule=None,
    catchup=False,
    tags=["fantaf1", "learning", "retry"],
) as dag:
    retry_once = BashOperator(
        task_id="retry_once",
        bash_command="""
            if [ "{{ ti.try_number }}" -lt 2 ]; then
                echo "Primo tentativo: fallimento volontario"
                exit 1
            fi

            echo "Retry riuscito"
        """,
        retries=1,
        retry_delay=timedelta(seconds=30),
    )