import os
from pathlib import Path
from dotenv import load_dotenv
import snowflake.connector


try:
    import streamlit as st
except Exception:
    st = None


def get_secret(name, default=None):
    if st is not None:
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
    return snowflake.connector.connect(
        user=get_secret("SNOWFLAKE_USER"),
        account=get_secret("SNOWFLAKE_ACCOUNT"),
        private_key_file=get_secret("SNOWFLAKE_PRIVATE_KEY_PATH"),
        warehouse=get_secret("SNOWFLAKE_WAREHOUSE"),
        database=get_secret("SNOWFLAKE_DATABASE"),
        schema=get_secret("SNOWFLAKE_DBT_SCHEMA"),
        role=get_secret("SNOWFLAKE_ROLE", None),
    )
