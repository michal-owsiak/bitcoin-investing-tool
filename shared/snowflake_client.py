import os
from pathlib import Path
from dotenv import load_dotenv
import snowflake.connector
from cryptography.hazmat.primitives import serialization


try:
    import streamlit as st
except Exception:
    st = None


load_dotenv(Path(__file__).resolve().parents[1] / '.env')


def get_secret(name, default=None):
    if st is not None:
        try:
            if name in st.secrets:
                return st.secrets[name]
        except Exception:
            pass

    value = os.getenv(name, default)
    if value is None:
        raise KeyError(f"Missing secret/env: {name}")
    return value


def get_connection():
    private_key_path = get_secret("SNOWFLAKE_PRIVATE_KEY").strip()

    if private_key_path.startswith('"') and private_key_path.endswith('"'):
        private_key_path = private_key_path[1:-1]
    if private_key_path.startswith("'") and private_key_path.endswith("'"):
        private_key_path = private_key_path[1:-1]

    with open(private_key_path, "rb") as key_file:
        p_key = serialization.load_pem_private_key(
            key_file.read(),
            password=None,
        )

    pkb = p_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    pkb = p_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    return snowflake.connector.connect(
        user=get_secret("SNOWFLAKE_USER"),
        account=get_secret("SNOWFLAKE_ACCOUNT"),
        private_key=pkb,
        warehouse=get_secret("SNOWFLAKE_WAREHOUSE"),
        database=get_secret("SNOWFLAKE_DATABASE"),
        schema=get_secret("SNOWFLAKE_DBT_SCHEMA"),
        role=get_secret("SNOWFLAKE_ROLE", None),
    )
