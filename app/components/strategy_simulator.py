import json
import math
import re

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from components.theme_toggle import is_dark_theme
from logic.backtest import (
    RECURRING_FREQUENCIES,
    STRATEGIES,
    calculate_backtest,
    prepare_backtest_data,
)


STRATEGY_DESCRIPTIONS = {
    'Hold until today': 'Buy at the selected bullish flip and hold until the latest available close.',
    'Exit on next bearish flip': 'Buy at the selected bullish flip and sell at the first subsequent bearish flip.',
    'Follow all signals': 'Sell on bearish flips and reinvest all proceeds on subsequent bullish flips.',
    'Follow signals, never sell at a loss': (
        'Follow all signals, but skip any bearish flip that closes below the entry price '
        'and keep holding until a later bearish flip exits at or above it.'
    ),
}
DEFAULT_BACKTEST_ENTRY_DATE = '2020-08-02'
DEFAULT_INVESTMENT = '1,000.00'
DEFAULT_RECURRING_AMOUNT = '100.00'
# Set by utils.url_state to a (timeframe, 'YYYY-MM-DD') entry date restored from the URL.
PENDING_URL_ENTRY_KEY = '_backtest_entry_from_url'
# Matches --dark-background in main.css; the grid otherwise keeps Streamlit's stock dark background.
DARK_TABLE_BACKGROUND = '#161b22'

# Runs in the parent Streamlit page: when the simulator results change, numbers count
# from their previous values to the new ones instead of switching instantly.
COUNT_UP_SCRIPT = '''
(() => {
  if (window.__btcCountUpInstalled) return;
  window.__btcCountUpInstalled = true;
  const ROOT_SELECTOR = '.st-key-backtest_results';
  const DURATION_MS = 700;
  const DECIMAL_NUMBER = /([+-]?)(\\d{1,3}(?:,\\d{3})+|\\d+)\\.(\\d{2})/g;
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const previousValues = new Map();
  const writtenText = new WeakMap();
  const activeAnimations = new WeakMap();

  function parseTokens(node) {
    const text = node.nodeValue;
    const tokens = [...text.matchAll(DECIMAL_NUMBER)].map(match => ({
      index: match.index,
      length: match[0].length,
      value: Number(match[0].replace(/,/g, '')),
      signed: match[1] !== '',
      decimals: 2,
    }));
    const trimmed = text.trim();
    if (!tokens.length && node.parentElement?.tagName === 'STRONG' && /^\\d+$/.test(trimmed)) {
      tokens.push({index: text.indexOf(trimmed), length: trimmed.length, value: Number(trimmed), signed: false, decimals: 0});
    }
    return tokens;
  }

  function formatValue(value, token) {
    const sign = value < 0 ? '-' : token.signed ? '+' : '';
    return sign + Math.abs(value).toLocaleString('en-US', {
      minimumFractionDigits: token.decimals,
      maximumFractionDigits: token.decimals,
    });
  }

  function renderText(text, tokens, values) {
    let output = '';
    let last = 0;
    tokens.forEach((token, index) => {
      output += text.slice(last, token.index) + formatValue(values[index], token);
      last = token.index + token.length;
    });
    return output + text.slice(last);
  }

  function animate(node, text, tokens, fromValues) {
    const start = performance.now();
    const step = now => {
      if (activeAnimations.get(node) !== step) return;
      const progress = Math.min(1, (now - start) / DURATION_MS);
      const eased = 1 - (1 - progress) ** 3;
      const values = tokens.map((token, index) => fromValues[index] + (token.value - fromValues[index]) * eased);
      const next = progress < 1 ? renderText(text, tokens, values) : text;
      writtenText.set(node, next);
      node.nodeValue = next;
      if (progress < 1) requestAnimationFrame(step);
    };
    activeAnimations.set(node, step);
    requestAnimationFrame(step);
  }

  function scan() {
    const root = document.querySelector(ROOT_SELECTOR);
    if (!root) return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let position = 0;
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const tokens = parseTokens(node);
      if (!tokens.length) continue;
      const key = position++;
      if (writtenText.get(node) === node.nodeValue) continue;
      const values = tokens.map(token => token.value);
      const fromValues = previousValues.get(key);
      previousValues.set(key, values);
      activeAnimations.delete(node);
      if (
        reduceMotion || !fromValues || fromValues.length !== values.length
        || fromValues.every((value, index) => value === values[index])
      ) continue;
      animate(node, node.nodeValue, tokens, fromValues);
    }
  }

  let scanQueued = false;
  new MutationObserver(() => {
    if (scanQueued) return;
    scanQueued = true;
    requestAnimationFrame(() => {
      scanQueued = false;
      scan();
    });
  }).observe(document.body, {subtree: true, childList: true, characterData: true});
  scan();
})();
'''


def parse_investment(value):
    value = value.strip()
    if not re.fullmatch(r'(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]{1,2})?', value):
        raise ValueError('Enter an amount such as 1,000.00 or 1000.00 (up to two decimal places).')
    investment = float(value.replace(',', ''))
    if not math.isfinite(investment) or investment < 0.01:
        raise ValueError('Investment must be finite and at least 0.01 USDT.')
    return investment


def format_investment_input(key='backtest_investment_text'):
    try:
        investment = parse_investment(st.session_state[key])
    except ValueError:
        return
    st.session_state[key] = f'{investment:,.2f}'


def change_investment(amount, key='backtest_investment_text'):
    try:
        investment = parse_investment(st.session_state[key])
    except ValueError:
        return
    investment = max(0.01, investment + amount)
    if math.isfinite(investment):
        st.session_state[key] = f'{investment:,.2f}'


def _render_amount_input(label, text_key, default, container_key, button_keys, noun):
    """A USDT text input with -/+ 100 buttons overlaid on its right edge."""
    decrease_key, increase_key = button_keys
    with st.container(key=container_key):
        if text_key not in st.session_state:
            st.session_state[text_key] = default
        text = st.text_input(
            label, key=text_key, on_change=format_investment_input, args=(text_key,),
        )
        try:
            current = parse_investment(text)
        except ValueError:
            current = None
        with st.container(key=f'{container_key}_decrease'):
            st.button(
                '', icon=':material/remove:', key=decrease_key,
                help=f'Decrease {noun} by 100 USDT',
                on_click=change_investment, args=(-100.0, text_key),
                disabled=current is None or current <= 0.01,
            )
        with st.container(key=f'{container_key}_increase'):
            st.button(
                '', icon=':material/add:', key=increase_key,
                help=f'Increase {noun} by 100 USDT',
                on_click=change_investment, args=(100.0, text_key),
                disabled=current is None,
            )
    return text


def _render_count_up_script():
    script = json.dumps(COUNT_UP_SCRIPT).replace('</', '<\\/')
    with st.container(key='backtest_count_up'):
        components.html(
            '<script>'
            'const script = window.parent.document.createElement("script");'
            f'script.textContent = {script};'
            'window.parent.document.head.appendChild(script);'
            '</script>',
            height=0,
        )


def _recurring_buy_inputs():
    """Returns (amount, frequency); frequency is None while recurring buys are switched off."""
    if not st.session_state.get('backtest_recurring_enabled', False):
        return 0.0, None
    amount = parse_investment(
        st.session_state.get('backtest_recurring_amount_text', DEFAULT_RECURRING_AMOUNT)
    )
    frequency = st.session_state.get('backtest_recurring_frequency', next(iter(RECURRING_FREQUENCIES)))
    return amount, frequency


def _render_recurring_buy_controls():
    # The fields are always rendered and main.css slides them open while the checkbox is
    # checked; that keeps their values when collapsed and lets the section animate.
    with st.container(key='backtest_recurring'):
        with st.container(key='backtest_recurring_toggle'):
            st.checkbox('Add recurring buys', key='backtest_recurring_enabled')
        with st.container(key='backtest_recurring_fields'):
            frequency_col, amount_col, _ = st.columns(3)
            with frequency_col:
                st.selectbox(
                    'Frequency', list(RECURRING_FREQUENCIES), key='backtest_recurring_frequency',
                )
            with amount_col:
                _render_amount_input(
                    'Amount per buy (USDT)', 'backtest_recurring_amount_text', DEFAULT_RECURRING_AMOUNT,
                    'backtest_recurring_amount_control',
                    ('backtest_recurring_decrease', 'backtest_recurring_increase'), 'amount per buy',
                )


def _default_entry_index(entry_options):
    preferred_index = next((
        index for index, entry_date in enumerate(entry_options)
        if pd.Timestamp(entry_date).strftime('%Y-%m-%d') == DEFAULT_BACKTEST_ENTRY_DATE
    ), None)
    return preferred_index if preferred_index is not None else max(0, len(entry_options) - 1)


def default_entry_state_key(timeframe):
    return f'_backtest_default_entry_{timeframe}'


def _apply_url_entry(timeframe, entry_options):
    # The URL leaves the entry date out while it is the default, which depends on the data.
    st.session_state[default_entry_state_key(timeframe)] = (
        entry_options[_default_entry_index(entry_options)][:10]
    )
    pending = st.session_state.get(PENDING_URL_ENTRY_KEY)
    if not pending or pending[0] != timeframe:
        return
    del st.session_state[PENDING_URL_ENTRY_KEY]
    entry_key = f'backtest_entry_v2_{timeframe}'
    match = next((option for option in entry_options if option[:10] == pending[1]), None)
    if match is not None and entry_key not in st.session_state:
        st.session_state[entry_key] = match


def get_selected_backtest_trades(price_df, timeframe):
    try:
        data = prepare_backtest_data(price_df)
    except ValueError:
        return []

    bullish = data[data['SIGNAL_FLIP_UP']].sort_values('CLOSE_TIME', ascending=False)
    if bullish.empty:
        return []

    entry_options = bullish['CLOSE_TIME'].map(lambda date: date.isoformat()).tolist()
    _apply_url_entry(timeframe, entry_options)
    default_entry = entry_options[_default_entry_index(entry_options)]
    entry_key = f'backtest_entry_v2_{timeframe}'
    entry_date = st.session_state.get(entry_key, default_entry)
    if entry_date not in entry_options:
        entry_date = default_entry
    strategy = st.session_state.get('backtest_strategy', STRATEGIES[0])
    investment_text = st.session_state.get('backtest_investment_text', DEFAULT_INVESTMENT)

    try:
        investment = parse_investment(investment_text)
        recurring_amount, recurring_frequency = _recurring_buy_inputs()
        result = calculate_backtest(
            data, entry_date, investment, strategy, recurring_amount, recurring_frequency,
        )
    except ValueError:
        return []
    return result['trades']


def render_strategy_simulator(price_df, timeframe):
    st.subheader('Supertrend Strategy Simulator')
    st.caption('Backtest an investment from a historical Supertrend bullish flip.')

    try:
        data = prepare_backtest_data(price_df)
    except ValueError as error:
        st.info(str(error))
        return

    bullish = data[data['SIGNAL_FLIP_UP']].sort_values('CLOSE_TIME', ascending=False)
    if bullish.empty:
        st.info('No bullish flips are available for this timeframe.')
        return

    entry_options = bullish['CLOSE_TIME'].map(lambda date: date.isoformat()).tolist()
    _apply_url_entry(timeframe, entry_options)
    entry_key = f'backtest_entry_v2_{timeframe}'
    # A date restored from the URL may no longer be a bullish flip after a data refresh.
    if entry_key in st.session_state and st.session_state[entry_key] not in entry_options:
        del st.session_state[entry_key]
    entry_col, amount_col, strategy_col = st.columns(3)
    with entry_col:
        entry_date = st.selectbox(
            'Bullish flip date',
            options=entry_options,
            # With a value already in Session State, a non-zero index triggers Streamlit's
            # "default value and Session State" warning.
            index=0 if entry_key in st.session_state else _default_entry_index(entry_options),
            format_func=lambda date: pd.Timestamp(date).strftime('%Y-%m-%d'),
            key=entry_key,
        )
    with amount_col:
        investment_text = _render_amount_input(
            'Investment (USDT)', 'backtest_investment_text', DEFAULT_INVESTMENT,
            'backtest_investment_control', ('backtest_decrease', 'backtest_increase'), 'investment',
        )
    with strategy_col:
        strategy = st.selectbox('Strategy', STRATEGIES, key='backtest_strategy')
    st.caption(f'Strategy: {STRATEGY_DESCRIPTIONS[strategy]}')
    _render_recurring_buy_controls()

    try:
        investment = parse_investment(investment_text)
        recurring_amount, recurring_frequency = _recurring_buy_inputs()
        result = calculate_backtest(
            data, entry_date, investment, strategy, recurring_amount, recurring_frequency,
        )
    except ValueError as error:
        st.warning(str(error))
        return

    with st.container(key='backtest_results'):
        if result['awaiting_exit']:
            st.info('No subsequent bearish flip yet. The position is open; its value below uses the latest available close, not a completed sale.')

        value_col, profit_col, return_col, cagr_col = st.columns(4)
        value_col.metric('Portfolio value (USDT)', f"{result['final_value']:,.2f}")
        cagr = result['annualized_return_pct']
        cagr_col.metric(
            'Annualized return (IRR)' if recurring_frequency else 'Annualized return (CAGR)',
            f'{cagr:+,.2f}%' if cagr is not None else 'N/A (<1Y)',
            help=(
                'Money-weighted: each recurring buy counts only from the date it was made.'
                if recurring_frequency else None
            ),
        )
        for column, label, value, suffix in [
            (profit_col, 'Profit / loss (USDT)', result['profit'], ''),
            (return_col, 'Return', result['return_pct'], '%'),
        ]:
            color = '#23a88e' if value >= 0 else '#f14c4a'
            column.markdown(
                f"<div style='font-size:14px;'>{label}</div>"
                f"<div style='font-size:21px; font-weight:600; color:{color};'>"
                f"{value:+,.2f}{suffix}</div>",
                unsafe_allow_html=True,
            )

        invested = f"Invested: **{result['total_invested']:,.2f} USDT**"
        if recurring_frequency:
            invested += (
                f" ({result['investment']:,.2f} initial + "
                f"{result['total_invested'] - result['investment']:,.2f} recurring)"
            )
        investment_details = (
            f"{invested} | "
            f"Entry: **{result['entry_date']:%Y-%m-%d}** "
            f"at **{result['entry_price']:,.2f} USDT**"
        )
        if strategy == 'Exit on next bearish flip' and not result['position_open']:
            trade = result['trades'][0]
            valuation_details = (
                f"Exit: **{trade['exit_date']:%Y-%m-%d}** "
                f"at **{trade['exit_price']:,.2f} USDT**"
            )
        else:
            valuation_details = (
                f"Latest close: **{result['latest_date']:%Y-%m-%d}** | "
                f"BTC: **{result['latest_price']:,.2f} USDT**"
            )
        st.caption(f'{investment_details}  \n{valuation_details}')

        follows_signals = strategy in {'Follow all signals', 'Follow signals, never sell at a loss'}
        activity = []
        if follows_signals:
            activity.append(f"Closed trades: **{result['closed_trades']}**")
        if recurring_frequency:
            recurring_buys = f"Recurring buys: **{result['recurring_buys']}**"
            if result['recurring_buys_in_cash']:
                recurring_buys += (
                    f" ({result['recurring_buys_in_cash']} held as cash until a bullish flip)"
                )
            activity.append(recurring_buys)
        if follows_signals:
            position = 'BTC (open)' if result['position_open'] else 'Cash (USDT)'
            activity.append(f'Position: **{position}**')
        if activity:
            st.caption(' | '.join(activity))
    _render_count_up_script()

    with st.expander('Trade details', expanded=True):
        trades = pd.DataFrame(result['trades'])
        if not recurring_frequency:
            # Without recurring buys the average cost always equals the entry price.
            trades = trades.drop(columns='average_cost')
        for column in ['entry_date', 'exit_date']:
            trades[column] = pd.to_datetime(trades[column], utc=True).dt.strftime('%Y-%m-%d')
        trades = trades.rename(columns={
            'entry_date': 'Entry date', 'entry_price': 'Entry price (USDT)',
            'average_cost': 'Avg cost (USDT)',
            'exit_date': 'Exit date', 'exit_price': 'Exit price (USDT)',
            'value': 'Portfolio value (USDT)', 'status': 'Status',
            'trade_return_pct': 'Trade return (%)',
            'cumulative_return_pct': 'Cumulative return (%)',
        })
        price_columns = [
            column for column in
            ['Entry price (USDT)', 'Avg cost (USDT)', 'Exit price (USDT)', 'Portfolio value (USDT)']
            if column in trades.columns
        ]
        return_columns = ['Trade return (%)', 'Cumulative return (%)']
        styled_trades = (
            trades.style.format(na_rep='-')
            .format('{:,.2f}', subset=price_columns, na_rep='-')
            .format('{:+,.2f}%', subset=return_columns)
            .map(lambda value: 'color: #23a88e' if value >= 0 else 'color: #f14c4a', subset=return_columns)
            .map(lambda value: 'color: #999999' if pd.isna(value) else '', subset=['Exit date', 'Exit price (USDT)'])
        )
        dark_theme = is_dark_theme()
        if dark_theme:
            styled_trades = styled_trades.set_properties(**{'background-color': DARK_TABLE_BACKGROUND})
        with st.container(key='backtest_trade_details'):
            # The grid keeps its column widths when the same table gains the Avg cost column;
            # nesting it one level deeper in recurring mode makes Streamlit mount a fresh grid.
            table_container = st.container() if recurring_frequency else st
            table_container.dataframe(styled_trades, hide_index=True, use_container_width=True)

        if recurring_frequency and result['recurring_buy_log']:
            # A separate table: as rows of the trades table, recurring buys would leave most
            # columns empty, which Streamlit renders as "None".
            recurring_buys = pd.DataFrame(result['recurring_buy_log'])
            recurring_buys = pd.DataFrame({
                'Date': recurring_buys['date'].dt.strftime('%Y-%m-%d'),
                'Price (USDT)': recurring_buys['price'],
                'Amount (USDT)': recurring_buys['amount'],
                'Status': recurring_buys['bought_btc'].map({True: 'Bought BTC', False: 'Held as cash'}),
            })
            styled_recurring_buys = (
                recurring_buys.style
                .format('{:,.2f}', subset=['Price (USDT)', 'Amount (USDT)'])
                .map(lambda value: 'color: #999999' if value == 'Held as cash' else '', subset=['Status'])
            )
            if dark_theme:
                styled_recurring_buys = styled_recurring_buys.set_properties(
                    **{'background-color': DARK_TABLE_BACKGROUND}
                )
            st.markdown('**Recurring buys**')
            with st.container(key='backtest_recurring_buy_details'):
                st.dataframe(styled_recurring_buys, hide_index=True, use_container_width=True)

    recurring_note = (
        'Recurring buys execute at the close of the first candle on or after each scheduled date; '
        'while the strategy holds cash they wait for the next bullish flip. '
        if recurring_frequency else ''
    )
    st.caption(
        'Trades are simulated at the signal candle\'s closing price (UTC). '
        f'{recurring_note}'
        'Results exclude fees, slippage and taxes. Historical results do not predict future returns.'
    )