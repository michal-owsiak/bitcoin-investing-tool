import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from client_binance import fetch_klines
from client_snowflake import get_connection, get_max_open_time, load_to_snowflake


env_path = Path(__file__).resolve().parents[1] / '.env'
load_dotenv(dotenv_path=env_path)

def main():
    conn = get_connection()

    try:
        max_time = get_max_open_time(conn)
        print('MAX TIME:', max_time)

        if max_time is None:
            start_ms = None
            print('No existing data found -> full fetch')
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

if __name__ == '__main__':
    main()
    