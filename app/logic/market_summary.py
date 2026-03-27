import pandas as pd


def calculate_market_summary(price_df):
    df = price_df.copy()

    date_col = 'OPEN_TIME'
    close_col = 'CLOSE'
    supertrend_col = 'SUPERTREND_VALUE'
    trend_col = 'TREND_DIRECTION'

    df[date_col] = pd.to_datetime(df[date_col])
    df[close_col] = pd.to_numeric(df[close_col], errors='coerce')
    df[supertrend_col] = pd.to_numeric(df[supertrend_col], errors='coerce')

    df['flip'] = None
    df.loc[df['SIGNAL_FLIP_UP'] == True, 'flip'] = 'Bullish'
    df.loc[df['SIGNAL_FLIP_DOWN'] == True, 'flip'] = 'Bearish'

    df = df.sort_values(date_col).reset_index(drop=True)

    latest = df.iloc[-1]

    current_price = latest[close_col]
    current_supertrend = latest[supertrend_col]
    current_trend = latest[trend_col]

    flips_df = df[df['flip'].notna()]

    if flips_df.empty:
        return {
            'current_trend': current_trend,
            'last_flip_type': None,
            'last_flip_date': None,
            'days_since_flip': None,
            'return_since_flip': None,
            'distance_to_supertrend_pct': None,
            'entry_price': None,
            'current_price': current_price
        }

    last_flip = flips_df.iloc[-1]

    last_flip_date = last_flip[date_col]
    last_flip_type = last_flip['flip']
    entry_price = last_flip[close_col]

    days_since_flip = (pd.Timestamp.now().normalize() - last_flip_date).days

    return_since_flip = ((current_price / entry_price) - 1) * 100

    distance_to_supertrend_pct = (
        ((current_price - current_supertrend) / current_supertrend) * 100
        if current_supertrend != 0 else None
    )

    return {
        'current_trend': current_trend,
        'last_flip_type': last_flip_type,
        'last_flip_date': last_flip_date,
        'days_since_flip': days_since_flip,
        'return_since_flip': return_since_flip,
        'distance_to_supertrend_pct': distance_to_supertrend_pct,
        'entry_price': entry_price,
        'current_price': current_price
    }
