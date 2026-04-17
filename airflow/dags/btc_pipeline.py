import os
import subprocess
from airflow.sdk import dag, task 
from datetime import datetime
from pathlib import Path
from datetime import timedelta
from shared.snowflake_client import get_connection
from ingestion.load_binance_ohlc import run_ingestion


project_root = Path(__file__).resolve().parents[1]


@dag(
    dag_id='btc_pipeline',
    schedule='0 */4 * * *',
    start_date=datetime(2026, 4, 1),
    catchup=False
)
def btc_pipeline():

    @task(
        retries=3,
        retry_delay=timedelta(minutes=2),
        retry_exponential_backoff=True
    )
    def run_snowflake_task():
        task_name = os.getenv('LOAD_TASK')
        warehouse = os.getenv('SNOWFLAKE_WAREHOUSE')
        database = os.getenv('SNOWFLAKE_DATABASE')
        schema = os.getenv('SNOWFLAKE_RAW_SCHEMA')

        query = f'execute task {task_name}'

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(f'use warehouse {warehouse}')
                cur.execute(f'use database {database}')
                cur.execute(f'use schema {schema}')
                cur.execute(query)
                print(f"Executed Snowflake task '{task_name}'")
        finally:
            cur.close()
            conn.close()

    @task(
        retries=3,
        retry_delay=timedelta(minutes=2),
        retry_exponential_backoff=True
    )
    def run_binance_ingestion():
        run_ingestion()
        print(f'Completed Binance OHLC ingestion')

    AIRFLOW_ROOT = Path('/opt/airflow')
    DBT_DIR = AIRFLOW_ROOT / 'dbt'

    @task(
        retries=3,
        retry_delay=timedelta(minutes=2),
        retry_exponential_backoff=True,
    )
    def run_dbt():
        print(f'DBT_DIR={DBT_DIR}')
        print(f'DBT_DIR exists={DBT_DIR.exists()}')
        print(f'dbt_project exists={(DBT_DIR / 'dbt_project.yml').exists()}')
        print(f'profiles exists={(DBT_DIR / 'profiles.yml').exists()}')

        result = subprocess.run(
            [
                '/home/airflow/.local/bin/dbt',
                'run',
                '--project-dir', str(DBT_DIR),
                '--profiles-dir', str(DBT_DIR),
            ],
            cwd=str(DBT_DIR),
            capture_output=True,
            text=True,
        )

        print('DBT RETURN CODE')
        print(result.returncode)
        print('DBT STDOUT')
        print(result.stdout)
        print('DBT STDERR')
        print(result.stderr)

        if result.returncode != 0:
            raise Exception(
                f'DBT FAILED:\nreturn code={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}'
        )

    run_snowflake_task() >> run_binance_ingestion() >> run_dbt()

btc_pipeline()
