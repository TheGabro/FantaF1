import pendulum

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG


with DAG(
    dag_id="fantaf1_django_check",
    description="Verifica che Airflow possa eseguire un comando Django",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    schedule=None,
    catchup=False,
    tags=["fantaf1", "django", "learning"],
) as dag:
    django_check = BashOperator(
        task_id="django_check",
        bash_command="cd /opt/fantaf1 && python manage.py check",
    )