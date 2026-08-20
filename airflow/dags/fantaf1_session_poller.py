import pendulum

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG


with DAG(
    dag_id="fantaf1_session_poller",
    description="Controlla le sessioni F1 che potrebbero richiedere elaborazione",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    schedule="*/15 * * * *", # ogni 15 minuti
    catchup=False,
    max_active_runs=1, #se quello prima non è finito, non ne parte un altro
    tags=["fantaf1", "polling", "learning"],
) as dag:
    list_due_sessions = BashOperator(
        task_id="list_due_sessions",
        bash_command="cd /opt/fantaf1 && python manage.py list_due_sessions",
    )