from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime

def hello():
    print("Hello World 🚀")


with DAG(
    dag_id="test_crypto_pipeline",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
) as dag:

    task1 = PythonOperator(
        task_id="say_hello",
        python_callable=hello
    )

    task1