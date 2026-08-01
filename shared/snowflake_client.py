import os
from pathlib import Path
from dotenv import load_dotenv
import snowflake.connector
from cryptography.hazmat.primitives import serialization

try:
    import streamlit as st
except Exception:
    st = None


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def get_secret(name, default=None):
    if st is not None:
        try:
            value = st.secrets.get(name)
            if value is not None:
                return value
        except Exception:
            pass

    value = os.getenv(name, default)
    if value is None:
        raise KeyError(f"Missing secret/env: {name}")
    return value


def _private_key_from_pem(pem_text: str) -> bytes:
    pem_text = pem_text.strip()

    if pem_text.startswith('"') and pem_text.endswith('"'):
        pem_text = pem_text[1:-1]
    if pem_text.startswith("'") and pem_text.endswith("'"):
        pem_text = pem_text[1:-1]

    pem_text = pem_text.replace("\\n", "\n")
    pem_text = pem_text.replace("\r\n", "\n").replace("\r", "\n")

    p_key = serialization.load_pem_private_key(
        pem_text.encode("utf-8"),
        password=None,
    )

    return p_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _private_key_from_file(path_str: str) -> bytes:
    with open(path_str, "rb") as key_file:
        p_key = serialization.load_pem_private_key(
            key_file.read(),
            password=None,
        )

    return p_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _get_private_key_bytes() -> bytes:
    private_key_path = os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH")
    if private_key_path:
        possible_path = Path(private_key_path)
        if possible_path.exists() and possible_path.is_file():
            return _private_key_from_file(str(possible_path))

    private_key_value = get_secret("SNOWFLAKE_PRIVATE_KEY")

    if not isinstance(private_key_value, str):
        raise TypeError(
            f"SNOWFLAKE_PRIVATE_KEY must be a string, got {type(private_key_value).__name__}"
        )

    possible_path = Path(private_key_value)
    if possible_path.exists() and possible_path.is_file():
        return _private_key_from_file(str(possible_path))

    return _private_key_from_pem(private_key_value)


def get_connection():
    return snowflake.connector.connect(
        user=get_secret("SNOWFLAKE_USER"),
        account=get_secret("SNOWFLAKE_ACCOUNT"),
        private_key=_get_private_key_bytes(),
        warehouse=get_secret("SNOWFLAKE_WAREHOUSE"),
        database=get_secret("SNOWFLAKE_DATABASE"),
        schema=get_secret("SNOWFLAKE_PROD_SCHEMA"),
        role=get_secret("SNOWFLAKE_ROLE", None),
    )