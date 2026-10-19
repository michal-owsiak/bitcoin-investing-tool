from pathlib import Path
import unittest
from unittest.mock import patch

import pyarrow.ipc
from streamlit.testing.v1 import AppTest


APP_PATH = str(Path(__file__).resolve().parents[1] / 'app')
APP = f'''
import sys
sys.path.insert(0, {APP_PATH!r})
import pandas as pd
import streamlit as st
from components.backtest_calculator import (
    _default_entry_index,
    get_selected_backtest_trades,
    render_backtest_calculator,
)

timeframe = st.selectbox('Timeframe', ['1W', '1D'], key='test_timeframe')
data = pd.DataFrame({{
    'OPEN_TIME': pd.date_range('2024-01-01', periods=4),
    'CLOSE_TIME': pd.date_range('2024-01-02', periods=4),
    'CLOSE': [100., 150., 120., 180.],
    'SIGNAL_FLIP_UP': [True, False, True, False],
    'SIGNAL_FLIP_DOWN': [False, True, False, False],
}})
if timeframe == '1D':
    data = data.iloc[:2]
selected_trades = get_selected_backtest_trades(data, timeframe)
st.session_state['chart_trade_count'] = len(selected_trades)
chart_col, spacer_col, whale_col = st.columns([4, 0.2, 0.8])
with chart_col:
    render_backtest_calculator(data, timeframe)
'''


class BacktestUITests(unittest.TestCase):
    def app(self, latest_entry=True):
        app = AppTest.from_string(APP).run()
        self.assertFalse(app.exception)
        if latest_entry:
            app.selectbox(key='backtest_entry_v2_1W').select_index(0).run()
            self.assertFalse(app.exception)
        return app

    def test_default_entry_prefers_august_2020_when_available(self):
        app_source = APP.replace(
            "pd.date_range('2024-01-02', periods=4)",
            "pd.to_datetime(['2020-08-02', '2020-08-03', '2020-08-04', '2020-08-05'])",
        )
        app = AppTest.from_string(app_source).run()
        self.assertFalse(app.exception)
        self.assertEqual(
            app.selectbox(key='backtest_entry_v2_1W').value,
            '2020-08-02T00:00:00+00:00',
        )

    def test_cagr_shows_na_for_period_shorter_than_one_year(self):
        app = self.app(latest_entry=False)
        self.assertEqual(app.metric[1].label, 'Annualized return (CAGR)')
        self.assertEqual(app.metric[1].value, 'N/A (<1Y)')

    def test_amount_and_entry_update_hold_result(self):
        app = self.app()
        app.selectbox(key='backtest_strategy').select('Hold until today').run()
        self.assertEqual(app.metric[0].value, '1,500.00')
        app.text_input[0].set_value('2000').run()
        self.assertEqual(app.text_input[0].value, '2,000.00')
        self.assertEqual(app.metric[0].value, '3,000.00')
        app.selectbox(key='backtest_entry_v2_1W').select_index(1).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, '3,600.00')

    def test_strategy_order_and_follow_all_signals_default(self):
        app = self.app(latest_entry=False)
        strategy = app.selectbox(key='backtest_strategy')
        self.assertEqual(strategy.options, [
            'Follow all signals', 'Hold until today', 'Exit on next bearish flip',
        ])
        self.assertEqual(strategy.value, 'Follow all signals')
        self.assertEqual(app.selectbox(key='backtest_entry_v2_1W').value, '2024-01-02T00:00:00+00:00')
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, '2,250.00')

    def test_chart_trade_highlights_follow_backtest_selection(self):
        app = self.app(latest_entry=False)
        self.assertEqual(app.session_state['chart_trade_count'], 2)

        app.selectbox(key='backtest_entry_v2_1W').select_index(0).run()
        self.assertEqual(app.session_state['chart_trade_count'], 1)

        app.selectbox(key='backtest_strategy').select('Hold until today').run()
        self.assertEqual(app.session_state['chart_trade_count'], 1)

    def test_changing_strategy_preserves_selected_entry_date(self):
        app = self.app(latest_entry=False)
        for entry_index in [1, 0]:
            app.selectbox(key='backtest_entry_v2_1W').select_index(entry_index).run()
            entry_date = app.selectbox(key='backtest_entry_v2_1W').value
            for strategy in ['Hold until today', 'Exit on next bearish flip', 'Follow all signals']:
                with self.subTest(entry_index=entry_index, strategy=strategy):
                    app.selectbox(key='backtest_strategy').select(strategy).run()
                    self.assertFalse(app.exception)
                    self.assertEqual(app.selectbox(key='backtest_entry_v2_1W').value, entry_date)

    def test_investment_accepts_and_formats_grouped_amounts(self):
        app = self.app()
        self.assertEqual(app.text_input[0].value, '1,000.00')
        for entered, formatted, portfolio in [
            ('12345.67', '12,345.67', '18,518.51'),
            ('1,234,567.80', '1,234,567.80', '1,851,851.70'),
            (' 2500.5 ', '2,500.50', '3,750.75'),
            ('0.01', '0.01', '0.01'),
        ]:
            with self.subTest(entered=entered):
                app.text_input[0].set_value(entered).run()
                self.assertFalse(app.exception)
                self.assertEqual(app.text_input[0].value, formatted)
                self.assertEqual(app.metric[0].value, portfolio)

    def test_existing_investment_state_does_not_show_duplicate_value_warning(self):
        with patch('streamlit.elements.lib.policies._shown_default_value_warning', False):
            app = AppTest.from_string(APP)
            app.session_state['backtest_investment_text'] = '12,000.00'
            app.run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.warning), 0)
            self.assertEqual(app.text_input[0].value, '12,000.00')

            app.text_input[0].set_value('15000').run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.warning), 0)
            self.assertEqual(app.text_input[0].value, '15,000.00')

            app.button(key='backtest_increase').click().run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.warning), 0)
            self.assertEqual(app.text_input[0].value, '15,100.00')

    def test_invalid_investment_shows_warning_without_results(self):
        app = self.app()
        for entered in ['', '0', '-10', '1,23', '1.000,00', 'NaN', '1,000.001']:
            with self.subTest(entered=entered):
                app.text_input[0].set_value(entered).run()
                self.assertFalse(app.exception)
                self.assertEqual(len(app.warning), 1)
                self.assertEqual(len(app.metric), 0)
                self.assertEqual(len(app.dataframe), 0)
        app.text_input[0].set_value('1000').run()
        self.assertEqual(len(app.warning), 0)
        self.assertEqual(app.metric[0].value, '1,500.00')

    def test_investment_buttons_preserve_format_and_recalculate(self):
        app = self.app()
        app.button(key='backtest_increase').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.text_input[0].value, '1,100.00')
        self.assertEqual(app.metric[0].value, '1,650.00')
        app.button(key='backtest_decrease').click().run()
        self.assertEqual(app.text_input[0].value, '1,000.00')
        app.text_input[0].set_value('12345.67').run()
        app.button(key='backtest_increase').click().run()
        self.assertEqual(app.text_input[0].value, '12,445.67')

    def test_decrease_button_respects_minimum_investment(self):
        app = self.app()
        app.text_input[0].set_value('50').run()
        app.button(key='backtest_decrease').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.text_input[0].value, '0.01')
        self.assertTrue(app.button(key='backtest_decrease').disabled)
        self.assertFalse(app.button(key='backtest_increase').disabled)
        app.button(key='backtest_increase').click().run()
        self.assertEqual(app.text_input[0].value, '100.01')

    def test_investment_buttons_disabled_for_invalid_amount(self):
        app = self.app()
        app.text_input[0].set_value('invalid').run()
        self.assertFalse(app.exception)
        self.assertTrue(app.button(key='backtest_decrease').disabled)
        self.assertTrue(app.button(key='backtest_increase').disabled)

    def test_portfolio_table_formats_two_decimal_places(self):
        app = self.app()
        displayed = pyarrow.ipc.open_stream(app.dataframe[0].proto.styler.display_values).read_pandas()
        self.assertEqual(displayed.iloc[0]['Portfolio value (USDT)'], '1,500.00')
        self.assertEqual(displayed.iloc[0]['Entry price (USDT)'], '120.00')
        self.assertEqual(displayed.iloc[0]['Exit date'], '-')
        self.assertEqual(displayed.iloc[0]['Exit price (USDT)'], '-')
        self.assertIn('color: #999999', app.dataframe[0].proto.styler.styles)

    def test_table_shows_trade_and_compounded_returns(self):
        app = self.app()
        app.selectbox(key='backtest_entry_v2_1W').select_index(1).run()
        app.selectbox(key='backtest_strategy').select('Follow all signals').run()
        self.assertFalse(app.exception)
        displayed = pyarrow.ipc.open_stream(app.dataframe[0].proto.styler.display_values).read_pandas()
        self.assertEqual(displayed['Trade return (%)'].tolist(), ['+50.00%', '+50.00%'])
        self.assertEqual(displayed['Cumulative return (%)'].tolist(), ['+50.00%', '+125.00%'])
        self.assertEqual(app.dataframe[0].value['Status'].tolist(), ['Closed', 'Open'])
        self.assertIn('color: #23a88e', app.dataframe[0].proto.styler.styles)

    def test_table_formats_negative_returns(self):
        app = AppTest.from_string(APP.replace('120., 180.', '120., 60.')).run()
        app.selectbox(key='backtest_entry_v2_1W').select_index(0).run()
        self.assertFalse(app.exception)
        displayed = pyarrow.ipc.open_stream(app.dataframe[0].proto.styler.display_values).read_pandas()
        self.assertEqual(displayed.iloc[0]['Trade return (%)'], '-50.00%')
        self.assertEqual(displayed.iloc[0]['Cumulative return (%)'], '-50.00%')
        self.assertIn('color: #f14c4a', app.dataframe[0].proto.styler.styles)

    def test_market_summary_only_shrinks_headings_and_colored_values(self):
        app = AppTest.from_string(APP + '''
from components.dashboard_sections import render_market_summary
render_market_summary({
    'current_trend': 'Bullish',
    'last_flip_date': pd.Timestamp('2024-01-01'),
    'days_since_flip': 3,
    'return_since_flip': 50,
    'distance_to_supertrend_pct': 20,
    'entry_price': 100,
    'current_price': 150,
})
''').run()
        self.assertFalse(app.exception)
        summary = '\n'.join(
            item.value for item in app.markdown
            if 'font-size:12px' in item.value or 'market-summary-label' in item.value
        )
        self.assertIn('Trend', summary)
        self.assertIn('Change', summary)
        self.assertIn('Distance to Supertrend', summary)
        self.assertEqual(summary.count('font-size:17px;'), 3)
        self.assertNotIn('color:#3a3a3a', summary)
        self.assertIn('.market-summary-detail {', (Path(APP_PATH) / 'styles' / 'main.css').read_text())
        css = (Path(APP_PATH) / 'styles' / 'main.css').read_text()
        self.assertIn('font-size: 13px;', css)
        self.assertIn('body.btc-dark-theme [data-testid="stMetricLabel"]', css)
        self.assertIn('.st-key-market_summary h3 {\n    font-size: 16.15px !important;', css)
        self.assertNotIn('.st-key-market_summary p', css)
        self.assertNotIn('.st-key-market_summary [data-testid="stMetric', css)
        self.assertEqual(len(app.warning), 1)

    def test_exit_without_bearish_flip_displays_open_position(self):
        app = self.app()
        app.selectbox(key='backtest_strategy').select('Exit on next bearish flip').run()
        self.assertFalse(app.exception)
        self.assertIn('No subsequent bearish flip', app.info[0].value)
        self.assertEqual(app.metric[0].value, '1,500.00')

    def test_exit_and_follow_display_expected_results(self):
        app = self.app()
        app.selectbox(key='backtest_entry_v2_1W').select_index(1).run()
        app.selectbox(key='backtest_strategy').select('Exit on next bearish flip').run()
        self.assertEqual(app.metric[0].value, '1,500.00')
        self.assertTrue(any('Exit: **2024-01-03** at **150.00 USDT**' in item.value for item in app.caption))
        app.selectbox(key='backtest_strategy').select('Follow all signals').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, '2,250.00')
        self.assertEqual(len(app.dataframe[0].value), 2)
        self.assertTrue(app.expander[0].proto.expanded)

    def test_entry_and_exit_dates_use_exact_candle_closes(self):
        app = AppTest.from_string(APP.replace(
            'pd.date_range(\'2024-01-02\', periods=4)',
            "pd.date_range('2024-01-01 23:59:59.999', periods=4)",
        )).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key='backtest_entry_v2_1W').label, 'Bullish flip date')
        self.assertEqual(app.selectbox(key='backtest_entry_v2_1W').options, ['2024-01-03', '2024-01-01'])
        app.selectbox(key='backtest_entry_v2_1W').select_index(1).run()
        app.selectbox(key='backtest_strategy').select('Exit on next bearish flip').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, '1,500.00')
        trade = app.dataframe[0].value.iloc[0]
        self.assertEqual(trade['Entry date'], '2024-01-01')
        self.assertEqual(trade['Exit date'], '2024-01-02')

    def test_trade_details_are_expanded_for_every_strategy(self):
        for strategy in ['Hold until today', 'Exit on next bearish flip', 'Follow all signals']:
            with self.subTest(strategy=strategy):
                app = self.app()
                app.selectbox(key='backtest_strategy').select(strategy).run()
                self.assertFalse(app.exception)
                self.assertEqual(len(app.dataframe), 1)
                self.assertTrue(app.expander[0].proto.expanded)
                self.assertEqual(app.dataframe[0].value.iloc[0]['Status'], 'Open')
                app.selectbox(key='backtest_entry_v2_1W').select_index(1).run()
                self.assertFalse(app.exception)
                self.assertEqual(len(app.dataframe), 1)
                self.assertTrue(app.expander[0].proto.expanded)
                expected_status = 'Open' if strategy == 'Hold until today' else 'Closed'
                self.assertEqual(app.dataframe[0].value.iloc[0]['Status'], expected_status)

    def test_strategy_prefix_and_compact_investment_details(self):
        app = self.app()
        app.selectbox(key='backtest_entry_v2_1W').select_index(1).run()
        for strategy in ['Hold until today', 'Exit on next bearish flip', 'Follow all signals']:
            with self.subTest(strategy=strategy):
                app.selectbox(key='backtest_strategy').select(strategy).run()
                self.assertFalse(app.exception)
                self.assertTrue(any(item.value.startswith('Strategy: ') for item in app.caption))
                details = [item.value for item in app.caption if item.value.startswith('Invested:')]
                self.assertEqual(len(details), 1)
                expected = 'Exit:' if strategy == 'Exit on next bearish flip' else 'Latest close:'
                self.assertIn('  \n' + expected, details[0])
                self.assertNotIn('\n\n', details[0])
                self.assertIn('Invested: **1,000.00 USDT**', details[0])
                self.assertIn('Entry: **2024-01-02** at **100.00 USDT**', details[0])
                if strategy != 'Exit on next bearish flip':
                    self.assertIn('Latest close: **2024-01-05** | BTC: **180.00 USDT**', details[0])
                if strategy == 'Follow all signals':
                    self.assertTrue(any(
                        item.value == 'Closed trades: **1** | Position: **BTC (open)**'
                        for item in app.caption
                    ))
                self.assertFalse(any('Buy / sell executions:' in item.value for item in app.caption))

    def test_profit_and_return_use_market_status_colors(self):
        for latest_price, color, profit, return_pct in [
            (180, '#23a88e', '+500.00', '+50.00%'),
            (60, '#f14c4a', '-500.00', '-50.00%'),
            (120, '#23a88e', '+0.00', '+0.00%'),
        ]:
            with self.subTest(latest_price=latest_price):
                app = AppTest.from_string(APP.replace(
                    '120., 180.', f'120., {latest_price}.',
                )).run()
                app.selectbox(key='backtest_entry_v2_1W').select_index(0).run()
                self.assertFalse(app.exception)
                results = [item.value for item in app.markdown if f'color:{color};' in item.value]
                self.assertEqual(len(results), 2)
                self.assertIn(profit, results[0])
                self.assertIn(return_pct, results[1])

    def test_timeframe_change_uses_available_entry(self):
        app = self.app()
        app.selectbox(key='test_timeframe').select('1D').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, '1,500.00')
        self.assertEqual(len(app.selectbox(key='backtest_entry_v2_1D').options), 1)

    def test_no_bullish_flips(self):
        app = AppTest.from_string(APP.replace(
            "render_backtest_calculator(data, timeframe)",
            "data['SIGNAL_FLIP_UP'] = False\nrender_backtest_calculator(data, timeframe)",
        )).run()
        self.assertFalse(app.exception)
        self.assertIn('No bullish flips', app.info[0].value)
        self.assertEqual(len(app.metric), 0)

    def test_empty_data(self):
        app = AppTest.from_string(APP.replace(
            'render_backtest_calculator(data, timeframe)',
            'render_backtest_calculator(data.iloc[:0], timeframe)',
        )).run()
        self.assertFalse(app.exception)
        self.assertIn('No price data', app.info[0].value)


if __name__ == '__main__':
    unittest.main()