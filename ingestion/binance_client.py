import pandas as pd
import requests


BINANCE_URL = 'https://api.binance.com/api/v3/klines'


def fetch_klines(symbol='BTCUSDT', interval='1d', start_time=None):
    params = {
        'symbol': symbol,
        'interval': interval,
        'limit': 1000,
    }

    if start_time is not None:
        params['startTime'] = start_time

    r = requests.get(BINANCE_URL, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()

    if not data:
        return pd.DataFrame()

    cols = [
        'open_time',
        'open',
        'high',
        'low',
        'close',
        'volume',
        'close_time',
        'quote_asset_volume',
        'number_of_trades',
        'taker_buy_base_asset_volume',
        'taker_buy_quote_asset_volume',
        'ignore',
    ]

    df = pd.DataFrame(data, columns=cols)

    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms', utc=True).dt.tz_localize(None)
    df['close_time'] = pd.to_datetime(df['close_time'], unit='ms', utc=True).dt.tz_localize(None)

    numeric_cols = [
        'open',
        'high',
        'low',
        'close',
        'volume',
        'quote_asset_volume',
        'taker_buy_base_asset_volume',
        'taker_buy_quote_asset_volume',
    ]

    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors='coerce')

    df['number_of_trades'] = pd.to_numeric(df['number_of_trades'], errors='coerce')
    df['symbol'] = symbol
    df['interval'] = interval
    df['ingested_at'] = pd.Timestamp.utcnow().tz_localize(None)

    now_utc = pd.Timestamp.utcnow().tz_localize(None)
    df = df[df['close_time'] <= now_utc]

    return df.drop(columns=['ignore'])
