import math

import pandas as pd


STRATEGIES = (
    'Follow signals, never sell at a loss',
    'Follow all signals',
    'Hold until today',
    'Exit on next bearish flip',
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


RECURRING_FREQUENCIES = {
    'Weekly': pd.DateOffset(weeks=1),
    'Every 2 weeks': pd.DateOffset(weeks=2),
    'Monthly': pd.DateOffset(months=1),
}


def _years_between(start, end):
    return (end - start).total_seconds() / (365.2425 * 86400)


def _annualized_return_pct(deposits, period_end, final_value):
    """Money-weighted annual return (IRR) of deposits [(date, amount)] grown to final_value."""
    first_date, first_amount = deposits[0]
    if len(deposits) == 1:
        period_years = _years_between(first_date, period_end)
        return (final_value / first_amount) ** (1 / period_years) * 100 - 100

    def future_value(rate):
        return sum(
            amount * (1 + rate) ** _years_between(date, period_end)
            for date, amount in deposits
        )

    # future_value grows with the rate, so bisect for the rate that reaches final_value.
    low, high = -0.9999, 1.0
    while future_value(high) < final_value:
        high *= 2
        if high > 1e6:
            return None
    for _ in range(200):
        middle = (low + high) / 2
        if future_value(middle) < final_value:
            low = middle
        else:
            high = middle
    return (low + high) / 2 * 100


def calculate_backtest(
    price_df, entry_date, investment, strategy,
    recurring_amount=0.0, recurring_frequency=None,
):
    if not math.isfinite(investment) or investment <= 0:
        raise ValueError('Investment must be finite and greater than zero.')
    if strategy not in STRATEGIES:
        raise ValueError('Unknown backtest strategy.')
    recurring = recurring_frequency is not None
    if recurring:
        if recurring_frequency not in RECURRING_FREQUENCIES:
            raise ValueError('Unknown recurring buy frequency.')
        if not math.isfinite(recurring_amount) or recurring_amount <= 0:
            raise ValueError('Recurring buy amount must be finite and greater than zero.')

    df = prepare_backtest_data(price_df)
    entry_date = pd.to_datetime(entry_date, utc=True)
    entries = df[(df['CLOSE_TIME'] == entry_date) & df['SIGNAL_FLIP_UP']]
    if entries.empty:
        raise ValueError('Select an available bullish flip.')

    entry = entries.iloc[0]
    latest = df.iloc[-1]
    subsequent = df[df['CLOSE_TIME'] > entry_date]
    btc = float(investment) / float(entry['CLOSE'])
    cash = 0.0
    # USDT spent on the BTC currently held; average cost = cost_basis / btc.
    cost_basis = float(investment)
    total_invested = float(investment)
    deposits = [(entry['CLOSE_TIME'], float(investment))]
    next_deposit_date = entry['CLOSE_TIME'] + RECURRING_FREQUENCIES[recurring_frequency] if recurring else None
    execution_count = 1
    trades = []
    # Kept apart from trades, which also drive the BUY/SELL markers on the price chart.
    recurring_buys = []
    current_entry = entry

    if strategy == 'Hold until today' and not recurring:
        subsequent = subsequent.iloc[:0]

    for _, candle in subsequent.iterrows():
        price = float(candle['CLOSE'])
        while recurring and next_deposit_date <= candle['CLOSE_TIME']:
            recurring_buys.append({
                'date': candle['CLOSE_TIME'],
                'price': price,
                'amount': recurring_amount,
                # False while the strategy holds cash: the deposit waits for the next bullish flip.
                'bought_btc': btc > 0,
            })
            if btc > 0:
                btc += recurring_amount / price
                cost_basis += recurring_amount
            else:
                cash += recurring_amount
            total_invested += recurring_amount
            deposits.append((candle['CLOSE_TIME'], recurring_amount))
            next_deposit_date += RECURRING_FREQUENCIES[recurring_frequency]

        if strategy == 'Hold until today':
            continue
        sell_blocked = (
            strategy == 'Follow signals, never sell at a loss'
            and btc > 0
            and price < cost_basis / btc
            and not math.isclose(price, cost_basis / btc)
        )
        if btc > 0 and candle['SIGNAL_FLIP_DOWN'] and not sell_blocked:
            cash += btc * price
            trades.append({
                'entry_date': current_entry['CLOSE_TIME'],
                'entry_price': float(current_entry['CLOSE']),
                'average_cost': cost_basis / btc,
                'exit_date': candle['CLOSE_TIME'],
                'exit_price': price,
                'value': cash,
                'trade_return_pct': (price * btc / cost_basis - 1) * 100,
                'cumulative_return_pct': (cash / total_invested - 1) * 100,
                'status': 'Closed',
            })
            btc = 0.0
            cost_basis = 0.0
            execution_count += 1
            if strategy == 'Exit on next bearish flip':
                break
        elif btc == 0 and candle['SIGNAL_FLIP_UP']:
            btc = cash / price
            cost_basis = cash
            cash = 0.0
            current_entry = candle
            execution_count += 1

    final_value = cash + btc * float(latest['CLOSE'])
    if not math.isfinite(final_value):
        raise ValueError('The calculated portfolio value is too large.')

    period_end = latest['CLOSE_TIME']
    if (
        strategy == 'Exit on next bearish flip'
        and trades
        and trades[-1]['exit_date'] is not None
    ):
        period_end = trades[-1]['exit_date']
    entry_time = entry['CLOSE_TIME']
    annualized_return_pct = None
    if period_end >= entry_time + pd.DateOffset(years=1) and final_value > 0:
        annualized_return_pct = _annualized_return_pct(deposits, period_end, final_value)

    if btc > 0:
        trades.append({
            'entry_date': current_entry['CLOSE_TIME'],
            'entry_price': float(current_entry['CLOSE']),
            'average_cost': cost_basis / btc,
            'exit_date': None,
            'exit_price': None,
            'value': final_value,
            'trade_return_pct': (float(latest['CLOSE']) * btc / cost_basis - 1) * 100,
            'cumulative_return_pct': (final_value / total_invested - 1) * 100,
            'status': 'Open',
        })

    return {
        'investment': float(investment),
        'total_invested': total_invested,
        'recurring_buys': len(recurring_buys),
        'recurring_buys_in_cash': sum(not buy['bought_btc'] for buy in recurring_buys),
        'recurring_buy_log': recurring_buys,
        'entry_date': entry['CLOSE_TIME'],
        'entry_price': float(entry['CLOSE']),
        'latest_date': latest['CLOSE_TIME'],
        'latest_price': float(latest['CLOSE']),
        'final_value': final_value,
        'profit': final_value - total_invested,
        'return_pct': (final_value / total_invested - 1) * 100,
        'annualized_return_pct': annualized_return_pct,
        'closed_trades': sum(trade['status'] == 'Closed' for trade in trades),
        'execution_count': execution_count,
        'position_open': btc > 0,
        'awaiting_exit': strategy == 'Exit on next bearish flip' and btc > 0,
        'trades': trades,
    }
