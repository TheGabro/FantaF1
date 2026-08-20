import pendulum

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG


with DAG(
    dag_id="fantaf1_hello",
    description="Primo DAG di prova per FantaF1",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    schedule=None,
    catchup=False,
    tags=["fantaf1", "learning"],
) as dag:
    say_hello = BashOperator(
        task_id="say_hello",
        bash_command='echo "Ciao da Airflow: il DAG FantaF1 funziona!"',
    )
    
    finish = BashOperator(
        task_id="finish",
        bash_command='echo "DAG FantaF1 completato!"',
    )
    
    say_hello >> finish