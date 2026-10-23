import re

import streamlit as st

from components.strategy_simulator import (
    DEFAULT_INVESTMENT,
    DEFAULT_RECURRING_AMOUNT,
    PENDING_URL_ENTRY_KEY,
    default_entry_state_key,
    parse_investment,
)
from logic.backtest import RECURRING_FREQUENCIES, STRATEGIES


# Widget values mirrored into the URL query string so they survive a page reload, such as the
# one the theme toggle triggers to apply the new theme, and can be shared as a link. Parameters
# use short names and readable values, and are left out while they hold the default.
DEFAULT_TIMEFRAME = '1W'
STRATEGY_SLUGS = {
    'Follow signals, never sell at a loss': 'never-sell-at-loss',
    'Follow all signals': 'follow-all',
    'Hold until today': 'hold',
    'Exit on next bearish flip': 'exit-next-bearish',
}
FREQUENCY_SLUGS = {
    'Weekly': 'weekly',
    'Every 2 weeks': 'biweekly',
    'Monthly': 'monthly',
}
PARAMS = ('tf', 'pi', 'entry', 'amount', 'strategy', 'dca', 'dca_freq', 'dca_amount')
_RESTORED_FLAG = '_url_state_restored'


def _parse_amount(text):
    try:
        return parse_investment(text)
    except ValueError:
        return None


def _encode_amount(text):
    amount = _parse_amount(text)
    return None if amount is None else f'{amount:.2f}'.rstrip('0').rstrip('.')


def _restore_amount(param, key):
    amount = _parse_amount(st.query_params.get(param, ''))
    if amount is not None:
        st.session_state[key] = f'{amount:,.2f}'


def _restore_choice(param, key, slugs):
    names = {slug: name for name, slug in slugs.items()}
    name = names.get(st.query_params.get(param))
    if name is not None:
        st.session_state[key] = name


def restore_widget_state():
    if st.session_state.get(_RESTORED_FLAG):
        return
    st.session_state[_RESTORED_FLAG] = True

    timeframe = st.query_params.get('tf', DEFAULT_TIMEFRAME)
    if timeframe not in {'1W', '1D'}:
        timeframe = DEFAULT_TIMEFRAME
    st.session_state['chart_timeframe'] = timeframe
    st.session_state['show_pi_cycle_top'] = st.query_params.get('pi') == '1'
    st.session_state['backtest_recurring_enabled'] = st.query_params.get('dca') == '1'
    _restore_choice('strategy', 'backtest_strategy', STRATEGY_SLUGS)
    _restore_choice('dca_freq', 'backtest_recurring_frequency', FREQUENCY_SLUGS)
    _restore_amount('amount', 'backtest_investment_text')
    _restore_amount('dca_amount', 'backtest_recurring_amount_text')
    # Entry options depend on the loaded price data, so the simulator matches the date to an
    # option itself.
    entry = st.query_params.get('entry', '')
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', entry):
        st.session_state[PENDING_URL_ENTRY_KEY] = (timeframe, entry)


def save_widget_state():
    timeframe = st.session_state.get('chart_timeframe', DEFAULT_TIMEFRAME)
    entry = st.session_state.get(f'backtest_entry_v2_{timeframe}')
    default_entry = st.session_state.get(default_entry_state_key(timeframe))
    strategy = st.session_state.get('backtest_strategy', STRATEGIES[0])
    frequency = st.session_state.get('backtest_recurring_frequency', next(iter(RECURRING_FREQUENCIES)))
    values = {
        'tf': None if timeframe == DEFAULT_TIMEFRAME else timeframe,
        'pi': '1' if st.session_state.get('show_pi_cycle_top') else None,
        'entry': None if not entry or entry[:10] == default_entry else entry[:10],
        'amount': _encode_amount(st.session_state.get('backtest_investment_text', DEFAULT_INVESTMENT)),
        'strategy': None if strategy == STRATEGIES[0] else STRATEGY_SLUGS.get(strategy),
        'dca': '1' if st.session_state.get('backtest_recurring_enabled') else None,
        'dca_freq': (
            None if frequency == next(iter(RECURRING_FREQUENCIES)) else FREQUENCY_SLUGS.get(frequency)
        ),
        'dca_amount': _encode_amount(
            st.session_state.get('backtest_recurring_amount_text', DEFAULT_RECURRING_AMOUNT)
        ),
    }
    for param, default in [
        ('amount', _encode_amount(DEFAULT_INVESTMENT)),
        ('dca_amount', _encode_amount(DEFAULT_RECURRING_AMOUNT)),
    ]:
        if values[param] == default:
            values[param] = None
        elif values[param] is None:
            # An amount that doesn't parse yet keeps the last valid one in the URL.
            values[param] = st.query_params.get(param)
    if PENDING_URL_ENTRY_KEY in st.session_state:
        # The simulator didn't get to match the restored date, so keep it for the next run.
        values['entry'] = st.query_params.get('entry')

    for param in [*st.query_params.keys()]:
        if param not in PARAMS:
            del st.query_params[param]
    for param, value in values.items():
        if value is None:
            if param in st.query_params:
                del st.query_params[param]
        elif st.query_params.get(param) != value:
            st.query_params[param] = value
