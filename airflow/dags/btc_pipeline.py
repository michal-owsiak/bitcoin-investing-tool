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
                print(f'Executed Snowflake task "{task_name}"')
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

    @task(
        retries=3,
        retry_delay=timedelta(minutes=2),
        retry_exponential_backoff=True
    )
    def run_dbt():
        result = subprocess.run(
            ['dbt', 'run', '--profiles-dir', str(project_root / 'dbt')],
            cwd=(project_root / 'dbt'),
            capture_output=True,
            text=True
        )

        print(result.stdout)

        if result.returncode != 0:
            print(result.stderr)
            raise Exception(f'dbt run failed: {result.stderr}')


    run_snowflake_task() >> run_binance_ingestion() >> run_dbt()

btc_pipeline()
