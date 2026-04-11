import os
import pandas as pd
import snowflake.connector
import streamlit as st
from dotenv import load_dotenv
from pathlib import Path
from snowflake.connector.pandas_tools import write_pandas
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend


load_dotenv(Path(__file__).resolve().parents[2] / '.env')


def get_secret(name, default=None):
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass

    value = os.getenv(name, default)
    if value is None:
        raise KeyError(f'Missing secret/env: {name}')
    return value


def get_connection():
    private_key_pem = get_secret('SNOWFLAKE_PRIVATE_KEY').strip()

    if private_key_pem.startswith('"') and private_key_pem.endswith('"'):
        private_key_pem = private_key_pem[1:-1]
    if private_key_pem.startswith("'") and private_key_pem.endswith("'"):
        private_key_pem = private_key_pem[1:-1]

    private_key_pem = private_key_pem.replace('\\n', '\n')

    p_key = serialization.load_pem_private_key(
        private_key_pem.encode('utf-8'),
        password=None,
        backend=default_backend(),
    )

    pkb = p_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    return snowflake.connector.connect(
        user=get_secret('SNOWFLAKE_USER'),
        account=get_secret('SNOWFLAKE_ACCOUNT'),
        private_key=pkb,
        warehouse=get_secret('SNOWFLAKE_WAREHOUSE'),
        database=get_secret('SNOWFLAKE_DATABASE'),
        schema=get_secret('SNOWFLAKE_DBT_SCHEMA'),
        role=get_secret('SNOWFLAKE_ROLE', None),
    )


def get_max_open_time(conn):
    query = '''
        select 
            max(open_time)
        from 
            BINANCE_BTCUSDT_1D
    '''

    with conn.cursor() as cur:
        cur.execute(f'use warehouse {os.environ['SNOWFLAKE_WAREHOUSE']}')
        cur.execute(f'use database {os.environ['SNOWFLAKE_DATABASE']}')
        cur.execute(f'use schema {os.environ['SNOWFLAKE_RAW_SCHEMA']}')
        cur.execute(query)
        row = cur.fetchone()

    if row is None:
        return None

    return row[0]


def load_to_snowflake(df):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f'use warehouse {os.environ['SNOWFLAKE_WAREHOUSE']}')
            cur.execute(f'use database {os.environ['SNOWFLAKE_DATABASE']}')
            cur.execute(f'use schema {os.environ['SNOWFLAKE_RAW_SCHEMA']}')

        df = df.copy()
        df.columns = [c.upper() for c in df.columns]

        success, nchunks, nrows, _ = write_pandas(
            conn=conn,
            df=df,
            table_name='BINANCE_BTCUSDT_1D',
            database=os.environ['SNOWFLAKE_DATABASE'],
            schema=os.environ['SNOWFLAKE_RAW_SCHEMA'],
            auto_create_table=False,
            overwrite=False,
            use_logical_type=True,
        )
        print(f'Loaded {nrows} rows, success={success}')
    finally:
        conn.close()
