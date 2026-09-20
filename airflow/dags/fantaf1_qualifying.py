import json
from datetime import datetime
import subprocess

from airflow.sdk import dag, task
from airflow.sdk.exceptions import AirflowSkipException

MANAGE = ["python", "/opt/fantaf1/manage.py"]

def run_manage(*args: str) -> subprocess.CompletedProcess:
    """Lancia un comando manage.py e ne stampa l'output nei log del task."""
    result = subprocess.run([*MANAGE, *args], capture_output=True, text=True)
    print(result.stdout)
    print(result.stderr)
    return result


@dag(
    schedule="5-59/15 * * * 5,6",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["fantaf1"],
)
def fantaf1_qualifying():

    @task
    def pick_event() -> dict:
        #il comando viene lanciato direttamente da Airflow
        #e viene gestito in autonomia in base a quanto scritto nel comando scritto in django
        # airflow poi legge l'ultima riga e l'exit code associato
        result = run_manage("next_pending_event", "--event", "qualifying")
        if result.returncode == 99:
            raise AirflowSkipException("No eligible events found")
        result.check_returncode()
        return json.loads(result.stdout.strip().splitlines()[-1])  # l'ultima riga è il JSON che ci interessa

    @task(retries=1)
    def insert_result(ev: dict):
        #leggendo il risultato passatogli in ev 
        # (quando glielo passa è un puntatore, poi diventa non un vero dizionario e si può gesrire come tale)
        result = run_manage(
            "insert_quali_result",
            "--season", str(ev["season"]),
            "--round", str(ev["round"]),
            "--type", str(ev["type"]),
        )
        if result.returncode == 3:
            #se il return code è 3, significa che i risultati dell'evento non sono ancora pronti
            #quindi lanciamo il comando mark_event per segnare lo status come waiting
            #ricordati di gestire tutti i casi in ci la funzione che stia chiamando, 
            # in questo caso insert_result
            run_manage(
                "mark_event",
                "--status-id", ev["status_id"],
                "--status", "waiting",
            )
            raise AirflowSkipException("Qualifying result not ready yet")
        result.check_returncode()

    @task
    def mark_processed(ev: dict):
        run_manage(
            "mark_event",
            "--status-id", str(ev["status_id"]),
            "--status", "processed",
        ).check_returncode()   

    @task(trigger_rule="one_failed")
    def mark_error(evdict, run_id: str | None = None):
        run_manage(
            "mark_event",
            "--status-id", str(ev["status_id"]),
            "--status", "error",
            "--error", f"Airflow run {run_id} failed, see task's log",
        ).check_returncode()

    ev = pick_event()
    inserted = insert_result(ev)
    inserted >> mark_processed(ev)
    inserted >> mark_error(ev)


fantaf1_qualifying()
