import math

import pandas as pd


STRATEGIES = (
    'Hold until today',
    'Exit on next bearish flip',
    'Follow all signals',
)


def prepare_backtest_data(price_df):
    required = ['OPEN_TIME', 'CLOSE_TIME', 'CLOSE', 'SIGNAL_FLIP_UP', 'SIGNAL_FLIP_DOWN']
    if not set(required).issubset(price_df.columns):
        raise ValueError('Backtest data is missing required columns.')

    df = price_df[required].copy()
    if df.empty:
        raise ValueError('No price data is available for backtesting.')

    for column in ['OPEN_TIME', 'CLOSE_TIME']:
        df[column] = pd.to_datetime(df[column], errors='coerce', utc=True)
    df['CLOSE'] = pd.to_numeric(df['CLOSE'], errors='coerce')

    if df[['OPEN_TIME', 'CLOSE_TIME', 'CLOSE']].isna().any().any():
        raise ValueError('Backtest data contains missing or invalid dates or prices.')
    if not df['CLOSE'].map(math.isfinite).all() or (df['CLOSE'] <= 0).any():
        raise ValueError('Backtest prices must be finite and greater than zero.')
    if df['OPEN_TIME'].duplicated().any() or df['CLOSE_TIME'].duplicated().any():
        raise ValueError('Backtest data contains duplicate candles.')

    for column in ['SIGNAL_FLIP_UP', 'SIGNAL_FLIP_DOWN']:
        if df[column].isna().any() or not df[column].isin([True, False]).all():
            raise ValueError('Backtest signals must be boolean values.')
        df[column] = df[column].astype(bool)
    if (df['SIGNAL_FLIP_UP'] & df['SIGNAL_FLIP_DOWN']).any():
        raise ValueError('A candle cannot contain both a bullish and bearish flip.')

    return df.sort_values('CLOSE_TIME').reset_index(drop=True)


def calculate_backtest(price_df, entry_date, investment, strategy):
    if not math.isfinite(investment) or investment <= 0:
        raise ValueError('Investment must be finite and greater than zero.')
    if strategy not in STRATEGIES:
        raise ValueError('Unknown backtest strategy.')

    df = prepare_backtest_data(price_df)
    entry_date = pd.to_datetime(entry_date, utc=True)
    entries = df[(df['CLOSE_TIME'] == entry_date) & df['SIGNAL_FLIP_UP']]
    if entries.empty:
        raise ValueError('Select an available bullish flip.')

    entry = entries.iloc[0]
    latest = df.iloc[-1]
    subsequent = df[df['CLOSE_TIME'] > entry_date]
    cash = float(investment)
    btc = cash / float(entry['CLOSE'])
    cash = 0.0
    execution_count = 1
    trades = []
    current_entry = entry

    if strategy == 'Exit on next bearish flip':
        subsequent = subsequent[subsequent['SIGNAL_FLIP_DOWN']].head(1)
    elif strategy == 'Hold until today':
        subsequent = subsequent.iloc[:0]

    for _, candle in subsequent.iterrows():
        if btc > 0 and candle['SIGNAL_FLIP_DOWN']:
            cash = btc * float(candle['CLOSE'])
            trades.append({
                'entry_date': current_entry['CLOSE_TIME'],
                'entry_price': float(current_entry['CLOSE']),
                'exit_date': candle['CLOSE_TIME'],
                'exit_price': float(candle['CLOSE']),
                'value': cash,
                'trade_return_pct': (float(candle['CLOSE']) / float(current_entry['CLOSE']) - 1) * 100,
                'cumulative_return_pct': (cash / investment - 1) * 100,
                'status': 'Closed',
            })
            btc = 0.0
            execution_count += 1
        elif btc == 0 and candle['SIGNAL_FLIP_UP']:
            btc = cash / float(candle['CLOSE'])
            cash = 0.0
            current_entry = candle
            execution_count += 1

    final_value = cash + btc * float(latest['CLOSE'])
    if not math.isfinite(final_value):
        raise ValueError('The calculated portfolio value is too large.')
    if btc > 0:
        trades.append({
            'entry_date': current_entry['CLOSE_TIME'],
            'entry_price': float(current_entry['CLOSE']),
            'exit_date': None,
            'exit_price': None,
            'value': final_value,
            'trade_return_pct': (float(latest['CLOSE']) / float(current_entry['CLOSE']) - 1) * 100,
            'cumulative_return_pct': (final_value / investment - 1) * 100,
            'status': 'Open',
        })

    return {
        'investment': float(investment),
        'entry_date': entry['CLOSE_TIME'],
        'entry_price': float(entry['CLOSE']),
        'latest_date': latest['CLOSE_TIME'],
        'latest_price': float(latest['CLOSE']),
        'final_value': final_value,
        'profit': final_value - investment,
        'return_pct': (final_value / investment - 1) * 100,
        'closed_trades': sum(trade['status'] == 'Closed' for trade in trades),
        'execution_count': execution_count,
        'position_open': btc > 0,
        'awaiting_exit': strategy == 'Exit on next bearish flip' and btc > 0,
        'trades': trades,
    }