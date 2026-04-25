import os
import subprocess
from airflow.sdk import dag, task 
from datetime import datetime
from pathlib import Path
from datetime import timedelta
from shared.snowflake_client import get_connection
from ingestion.load_binance_ohlc import run_ingestion


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
    def dbt_run():
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

        print(f'DBT RUN RETURN CODE: {result.returncode}')
        print(result.stdout)

        if result.returncode != 0:
            raise Exception(
                f'DBT RUN FAILED:\nreturn code={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}'
            )
        
    
    @task(
        retries=3,
        retry_delay=timedelta(minutes=2),
        retry_exponential_backoff=True,
    )
    def dbt_test():
        result = subprocess.run(
            [
                '/home/airflow/.local/bin/dbt',
                'test',
                '--project-dir', str(DBT_DIR),
                '--profiles-dir', str(DBT_DIR),
            ],
            cwd=str(DBT_DIR),
            capture_output=True,
            text=True,
        )

        print(f'DBT TEST RETURN CODE: {result.returncode}')
        print(result.stdout)

        if result.returncode != 0:
            raise Exception(
                f'DBT TEST FAILED:\nreturn code={result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}'
            )
        

    blockchain_ingestion = run_snowflake_task()
    binance_ingestion = run_binance_ingestion()
    dbt_run_task = dbt_run()
    dbt_test_task = dbt_test()


    blockchain_ingestion >> binance_ingestion >> dbt_run_task >> dbt_test_task


btc_pipeline()
