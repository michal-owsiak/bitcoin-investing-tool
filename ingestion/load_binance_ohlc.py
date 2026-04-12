import sys
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parents[1]
env_path = project_root / '.env'
load_dotenv(dotenv_path=env_path)

sys.path.append(str(project_root))
from shared.snowflake_client import get_connection
from ingestion.binance_client import fetch_klines
from ingestion.snowflake_service import get_max_open_time, load_to_snowflake


def run_ingestion():
    conn = get_connection()

    try:
        max_time = get_max_open_time(conn)
        print('MAX TIME:', max_time)

        if max_time is None:
            start_ms = None
            print('No existing data found -> running full fetch')
        else:
            max_time = pd.to_datetime(max_time)
            start_ms = int(max_time.timestamp() * 1000) + 1
    finally:
        conn.close()

    df = fetch_klines(start_time=start_ms)

    if df.empty:
        print('No new data')
        return
    
    load_to_snowflake(df)
