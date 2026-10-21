import json
import math
import re

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from logic.backtest import STRATEGIES, calculate_backtest, prepare_backtest_data


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


def format_investment_input():
    try:
        investment = parse_investment(st.session_state['backtest_investment_text'])
    except ValueError:
        return
    st.session_state['backtest_investment_text'] = f'{investment:,.2f}'


def change_investment(amount):
    try:
        investment = parse_investment(st.session_state['backtest_investment_text'])
    except ValueError:
        return
    investment = max(0.01, investment + amount)
    if math.isfinite(investment):
        st.session_state['backtest_investment_text'] = f'{investment:,.2f}'


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


def _default_entry_index(entry_options):
    preferred_index = next((
        index for index, entry_date in enumerate(entry_options)
        if pd.Timestamp(entry_date).strftime('%Y-%m-%d') == DEFAULT_BACKTEST_ENTRY_DATE
    ), None)
    return preferred_index if preferred_index is not None else max(0, len(entry_options) - 1)


def get_selected_backtest_trades(price_df, timeframe):
    try:
        data = prepare_backtest_data(price_df)
    except ValueError:
        return []

    bullish = data[data['SIGNAL_FLIP_UP']].sort_values('CLOSE_TIME', ascending=False)
    if bullish.empty:
        return []

    entry_options = bullish['CLOSE_TIME'].map(lambda date: date.isoformat()).tolist()
    default_entry = entry_options[_default_entry_index(entry_options)]
    entry_key = f'backtest_entry_v2_{timeframe}'
    entry_date = st.session_state.get(entry_key, default_entry)
    if entry_date not in entry_options:
        entry_date = default_entry
    strategy = st.session_state.get('backtest_strategy', STRATEGIES[0])
    investment_text = st.session_state.get('backtest_investment_text', '1,000.00')

    try:
        investment = parse_investment(investment_text)
        result = calculate_backtest(data, entry_date, investment, strategy)
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

    entry_col, amount_col, strategy_col = st.columns(3)
    with entry_col:
        entry_date = st.selectbox(
            'Bullish flip date',
            options=bullish['CLOSE_TIME'].map(lambda date: date.isoformat()).tolist(),
            index=_default_entry_index(
                bullish['CLOSE_TIME'].map(lambda date: date.isoformat()).tolist()
            ),
            format_func=lambda date: pd.Timestamp(date).strftime('%Y-%m-%d'),
            key=f'backtest_entry_v2_{timeframe}',
        )
    with amount_col:
        with st.container(key='backtest_investment_control'):
            if 'backtest_investment_text' not in st.session_state:
                st.session_state['backtest_investment_text'] = '1,000.00'
            investment_text = st.text_input(
                'Investment (USDT)',
                key='backtest_investment_text', on_change=format_investment_input,
            )
            try:
                current_investment = parse_investment(investment_text)
            except ValueError:
                current_investment = None
            with st.container(key='backtest_investment_decrease'):
                st.button(
                    '', icon=':material/remove:', key='backtest_decrease',
                    help='Decrease investment by 100 USDT',
                    on_click=change_investment, args=(-100.0,),
                    disabled=current_investment is None or current_investment <= 0.01,
                )
            with st.container(key='backtest_investment_increase'):
                st.button(
                    '', icon=':material/add:', key='backtest_increase',
                    help='Increase investment by 100 USDT',
                    on_click=change_investment, args=(100.0,),
                    disabled=current_investment is None,
                )
    with strategy_col:
        strategy = st.selectbox('Strategy', STRATEGIES, key='backtest_strategy')
    st.caption(f'Strategy: {STRATEGY_DESCRIPTIONS[strategy]}')

    try:
        investment = parse_investment(investment_text)
        result = calculate_backtest(data, entry_date, investment, strategy)
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
            'Annualized return (CAGR)',
            f'{cagr:+,.2f}%' if cagr is not None else 'N/A (<1Y)',
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

        investment_details = (
            f"Invested: **{result['investment']:,.2f} USDT** | "
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

        if strategy in {'Follow all signals', 'Follow signals, never sell at a loss'}:
            position = 'BTC (open)' if result['position_open'] else 'Cash (USDT)'
            st.caption(
                f"Closed trades: **{result['closed_trades']}** | Position: **{position}**"
            )
    _render_count_up_script()

    with st.expander('Trade details', expanded=True):
        trades = pd.DataFrame(result['trades'])
        for column in ['entry_date', 'exit_date']:
            trades[column] = pd.to_datetime(trades[column], utc=True).dt.strftime('%Y-%m-%d')
        trades = trades.rename(columns={
            'entry_date': 'Entry date', 'entry_price': 'Entry price (USDT)',
            'exit_date': 'Exit date', 'exit_price': 'Exit price (USDT)',
            'value': 'Portfolio value (USDT)', 'status': 'Status',
            'trade_return_pct': 'Trade return (%)',
            'cumulative_return_pct': 'Cumulative return (%)',
        })
        price_columns = ['Entry price (USDT)', 'Exit price (USDT)', 'Portfolio value (USDT)']
        return_columns = ['Trade return (%)', 'Cumulative return (%)']
        styled_trades = (
            trades.style.format(na_rep='-')
            .format('{:,.2f}', subset=price_columns, na_rep='-')
            .format('{:+,.2f}%', subset=return_columns)
            .map(lambda value: 'color: #23a88e' if value >= 0 else 'color: #f14c4a', subset=return_columns)
            .map(lambda value: 'color: #999999' if pd.isna(value) else '', subset=['Exit date', 'Exit price (USDT)'])
        )
        with st.container(key='backtest_trade_details'):
            st.dataframe(styled_trades, hide_index=True, use_container_width=True)

    st.caption(
        'Trades are simulated at the signal candle\'s closing price (UTC). '
        'Results exclude fees, slippage and taxes. Historical results do not predict future returns.'
    )