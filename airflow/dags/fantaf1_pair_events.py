import json
from datetime import datetime
import subprocess

from airflow.providers.standard.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.providers.standard.sensors.date_time import DateTimeSensorAsync
from airflow.sdk import PokeReturnValue, dag, task
from airflow.sdk.exceptions import AirflowFailException, AirflowSkipException

MANAGE = ["python", "/opt/fantaf1/manage.py"]

# Results publication delay budget, measured from the first poke
WAIT_FOR_RESULTS = dict(poke_interval=15 * 60, timeout=36 * 3600, mode="reschedule")


def run_manage(*args: str) -> subprocess.CompletedProcess:
    """Lancia un comando manage.py e ne stampa l'output nei log del task."""
    result = subprocess.run([*MANAGE, *args], capture_output=True, text=True)
    print(result.stdout)
    print(result.stderr)
    return result


def mark(ev: dict, status: str, error: str = ""):
    run_manage(
        "mark_event", "--status-id", str(ev["status_id"]), "--status", status, "--error", error
    ).check_returncode()


def run_steps(ev: dict, steps: list[list[str]]) -> PokeReturnValue:
    """
    Run the event commands in order and record the outcome on EventProcessingStatus.
    Return code 3 means "results not published yet": the sensor pokes again later.
    """
    if ev["status"] == "processed":
        print("Already processed, nothing to do")
        return PokeReturnValue(is_done=True)

    for step in steps:
        result = run_manage(*step)
        if result.returncode == 3:
            mark(ev, "waiting")
            return PokeReturnValue(is_done=False)
        if result.returncode != 0:
            mark(ev, "error", f"{step[0]} failed (rc {result.returncode}), see Airflow task log")
            # A bug does not fix itself: fail now instead of poking for 36h
            raise AirflowFailException(f"{step[0]} failed (rc {result.returncode})")

    mark(ev, "processed")
    return PokeReturnValue(is_done=True)


def event_args(ev: dict) -> list[str]:
    return ["--season", str(ev["season"]), "--round", str(ev["round"]), "--type", ev["type"]]


@dag(
    # No schedule: every run triggers the next one, the first one is started by hand
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["fantaf1"],
)
def fantaf1_pair_events():

    @task
    def plan_pair() -> dict:
        # Next qualifying + race pair with something left to process
        result = run_manage("next_pair_events")
        if result.returncode == 99:
            # Nothing left (e.g. season over): the chain stops here
            raise AirflowSkipException("No events left to process")
        result.check_returncode()
        return json.loads(result.stdout.strip().splitlines()[-1])

    @task.sensor(**WAIT_FOR_RESULTS)
    def process_quali(pair: dict) -> PokeReturnValue:
        ev = pair["qualifying"]
        return run_steps(ev, [
            ["insert_quali_result", *event_args(ev)],
            # The official grid (penalties included) is published by OpenF1
            ["insert_starting_grid", *event_args(ev)],
        ])

    @task.sensor(**WAIT_FOR_RESULTS)
    def process_race(pair: dict) -> PokeReturnValue:
        ev = pair["race"]
        steps = [
            ["consolidate_player_credits", *event_args(ev)],
            ["insert_race_result", *event_args(ev)],
        ]
        # Standings are updated once per weekend, after the regular race
        if ev["type"] == "regular":
            steps.append(
                ["insert_round_driver_standings", "--season", str(ev["season"]), "--round", str(ev["round"])]
            )
        steps.append(["compute_race_score", *event_args(ev)])
        return run_steps(ev, steps)

    # The triggerer holds a timer until eligible_after: no worker slot, no polling.
    # target_time is rendered from plan_pair's XCom (no timeout: deferred sensors
    # can wait through the summer break)
    wait_quali = DateTimeSensorAsync(
        task_id="wait_quali",
        target_time="{{ ti.xcom_pull(task_ids='plan_pair')['qualifying']['eligible_after'] }}",
    )
    wait_race = DateTimeSensorAsync(
        task_id="wait_race",
        target_time="{{ ti.xcom_pull(task_ids='plan_pair')['race']['eligible_after'] }}",
    )
    # Runs only if the whole pair succeeded: a failure stops the chain, visible in red
    trigger_next = TriggerDagRunOperator(
        task_id="trigger_next", trigger_dag_id="fantaf1_pair_events"
    )

    pair = plan_pair()
    pair >> wait_quali >> process_quali(pair) >> wait_race >> process_race(pair) >> trigger_next


fantaf1_pair_events()
