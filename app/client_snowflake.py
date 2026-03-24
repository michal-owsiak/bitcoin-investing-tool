import os
import pandas as pd
import snowflake.connector
from pathlib import Path
from dotenv import load_dotenv
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend


env_path = Path(__file__).resolve().parents[1] / '.env'
load_dotenv(dotenv_path=env_path)


def get_connection():
    with open(os.environ['SNOWFLAKE_PRIVATE_KEY_PATH'], 'rb') as key_file:
        p_key = serialization.load_pem_private_key(
            key_file.read(),
            password=None,
            backend=default_backend()
        )

    pkb = p_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    return snowflake.connector.connect(
        user=os.environ['SNOWFLAKE_USER'],
        account=os.environ['SNOWFLAKE_ACCOUNT'],
        private_key=pkb,
        warehouse=os.environ['SNOWFLAKE_WAREHOUSE'],
        database=os.environ['SNOWFLAKE_DATABASE'],
        schema=os.environ['SNOWFLAKE_DBT_SCHEMA'],
        role=os.environ.get('SNOWFLAKE_ROLE'),
    )


def read_price_supertrend(interval: str = '1w', limit: int = 500) -> pd.DataFrame:
    query = f'''
        select *
        from 
            {os.environ['SNOWFLAKE_DATABASE']}.{os.environ['SNOWFLAKE_DBT_SCHEMA']}.MART_BTC_PRICE_SUPERTREND_{interval.upper()}
        order by 
            open_time desc
        limit {limit}
    '''

    conn = get_connection()
    try:
        df = pd.read_sql(query, conn)
    finally:
        conn.close()

    if not df.empty:
        df = df.sort_values('OPEN_TIME').reset_index(drop=True)

    return df


def read_halvings() -> pd.DataFrame:
    query = f'''
        select *
        from 
            {os.environ['SNOWFLAKE_DATABASE']}.{os.environ['SNOWFLAKE_DBT_SCHEMA']}.MART_BTC_HALVINGS
        order by 
            halving_date
    '''

    conn = get_connection()
    try:
        df = pd.read_sql(query, conn)
    finally:
        conn.close()

    return df

