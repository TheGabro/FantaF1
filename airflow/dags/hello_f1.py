from airflow.sdk import dag, task

from datetime import datetime
import logging


@dag(
    schedule= None,        # nessun schedule, si esegue solo manualmente
    start_date= datetime(2026,1,1),     # un datetime nel passato
    catchup=False,
    tags=["fantaf1", "training"],
)
def hello_f1():

    @task
    def say_hello():
        logging.getLogger(__name__).info("Ciao F1!")              # qui il log

    say_hello()          # <-- serve chiamarla, altrimenti il task non esiste

hello_f1()               # <-- serve chiamarlo, altrimenti il DAG non viene registrato
