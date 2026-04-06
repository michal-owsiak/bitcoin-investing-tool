import os
import pandas as pd
import snowflake.connector
import streamlit as st
from pathlib import Path
from dotenv import load_dotenv
from cryptography.hazmat.primitives import serialization


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

    private_key_pem = get_secret("SNOWFLAKE_PRIVATE_KEY").strip()

    if "\\n" in private_key_pem:
        private_key_pem = private_key_pem.replace("\\n", "\n")

    private_key_pem = private_key_pem.strip().encode("utf-8")

    p_key = serialization.load_pem_private_key(
        private_key_pem,
        password=None
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

    lines = private_key_pem.splitlines()

    st.write({
        "line_count": len(lines),
        "first_line": lines[0] if lines else None,
        "last_line": lines[-1] if lines else None,
        "contains_backslash_n": "\\n" in private_key_pem,
    })


    return None

def read_price_supertrend(interval: str = '1w', limit: int = 3500) -> pd.DataFrame:
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


def read_whale_inflow() -> pd.DataFrame:
    query = f'''
        select
            output_address,
            total_output_value,
            transaction_count
        from 
            {os.environ['SNOWFLAKE_DATABASE']}.{os.environ['SNOWFLAKE_DBT_SCHEMA']}.MART_BTC_WHALE_ALERT_V2
        order by 
            total_output_value desc
    '''

    conn = get_connection()
    try:
        df = pd.read_sql(query, conn)
    finally:
        conn.close()

    if not df.empty:
        df.columns = [col.lower() for col in df.columns]
        df = df.sort_values('total_output_value', ascending=False).reset_index(drop=True)

    return df
