import unittest

import pandas as pd

from app.logic.backtest import calculate_backtest, prepare_backtest_data


class BacktestTests(unittest.TestCase):
    def setUp(self):
        self.data = pd.DataFrame({
            'OPEN_TIME': pd.date_range('2024-01-01', periods=6),
            'CLOSE_TIME': pd.date_range('2024-01-02', periods=6),
            'CLOSE': [100.0, 150.0, 120.0, 240.0, 200.0, 250.0],
            'SIGNAL_FLIP_UP': [True, False, True, False, True, False],
            'SIGNAL_FLIP_DOWN': [False, True, False, True, False, False],
        })

    def calculate(self, strategy, entry_date='2024-01-02', data=None):
        return calculate_backtest(
            self.data if data is None else data, entry_date, 1000, strategy
        )

    def test_hold_values_btc_at_latest_close(self):
        result = self.calculate('Hold until today')
        self.assertEqual(result['final_value'], 2500)
        self.assertEqual(result['profit'], 1500)
        self.assertEqual(result['return_pct'], 150)
        self.assertEqual(result['closed_trades'], 0)
        self.assertEqual(result['trades'][0]['trade_return_pct'], 150)
        self.assertEqual(result['trades'][0]['cumulative_return_pct'], result['return_pct'])
        self.assertIsNone(result['annualized_return_pct'])
        self.assertTrue(result['position_open'])

    def test_annualized_return_uses_elapsed_years(self):
        data = pd.DataFrame({
            'OPEN_TIME': pd.to_datetime(['2020-01-01', '2021-12-31'], utc=True),
            'CLOSE_TIME': pd.to_datetime(['2020-01-02', '2022-01-01'], utc=True),
            'CLOSE': [100.0, 200.0],
            'SIGNAL_FLIP_UP': [True, False],
            'SIGNAL_FLIP_DOWN': [False, False],
        })

        result = self.calculate('Hold until today', '2020-01-02', data)
        elapsed_days = (result['latest_date'] - result['entry_date']).total_seconds() / 86400
        expected = (2 ** (365.2425 / elapsed_days) - 1) * 100

        self.assertAlmostEqual(result['annualized_return_pct'], expected)

    def test_exit_uses_first_subsequent_bearish_flip(self):
        result = self.calculate('Exit on next bearish flip')
        self.assertEqual(result['final_value'], 1500)
        self.assertEqual(result['closed_trades'], 1)
        self.assertEqual(result['execution_count'], 2)
        self.assertEqual(result['trades'][0]['exit_price'], 150)
        self.assertEqual(result['trades'][0]['trade_return_pct'], 50)
        self.assertEqual(result['trades'][0]['cumulative_return_pct'], 50)
        self.assertEqual(result['entry_date'], pd.Timestamp('2024-01-02', tz='UTC'))
        self.assertEqual(result['trades'][0]['entry_date'], result['entry_date'])
        self.assertEqual(result['trades'][0]['exit_date'], pd.Timestamp('2024-01-03', tz='UTC'))
        self.assertFalse(result['position_open'])

    def test_exit_without_bearish_marks_open_position(self):
        result = self.calculate('Exit on next bearish flip', '2024-01-06')
        self.assertTrue(result['awaiting_exit'])
        self.assertEqual(result['final_value'], 1250)
        self.assertIsNone(result['trades'][0]['exit_date'])

    def test_follow_reinvests_and_values_open_position(self):
        result = self.calculate('Follow all signals')
        self.assertEqual(result['final_value'], 3750)
        self.assertEqual(result['closed_trades'], 2)
        self.assertEqual(result['execution_count'], 5)
        self.assertEqual([trade['value'] for trade in result['trades']], [1500, 3000, 3750])
        self.assertEqual([trade['trade_return_pct'] for trade in result['trades']], [50, 100, 25])
        self.assertEqual([trade['cumulative_return_pct'] for trade in result['trades']], [50, 200, 275])
        self.assertEqual(result['trades'][-1]['cumulative_return_pct'], result['return_pct'])
        self.assertEqual(
            [trade['entry_date'] for trade in result['trades']],
            pd.to_datetime(['2024-01-02', '2024-01-04', '2024-01-06'], utc=True).tolist(),
        )

    def test_follow_ends_in_cash_without_using_later_prices(self):
        data = self.data.copy()
        data.loc[4, 'SIGNAL_FLIP_UP'] = False
        result = self.calculate('Follow all signals', data=data)
        self.assertEqual(result['final_value'], 3000)
        self.assertFalse(result['position_open'])

    def test_trade_and_cumulative_returns_include_losses_and_reinvestment(self):
        data = self.data.copy()
        data['CLOSE'] = [100., 50., 100., 200., 200., 100.]
        result = self.calculate('Follow all signals', data=data)
        self.assertEqual([trade['trade_return_pct'] for trade in result['trades']], [-50, 100, -50])
        self.assertEqual([trade['cumulative_return_pct'] for trade in result['trades']], [-50, 0, -50])
        self.assertEqual(result['trades'][-1]['cumulative_return_pct'], result['return_pct'])

    def test_only_selected_entry_and_later_signals_are_used(self):
        result = self.calculate('Follow all signals', '2024-01-04')
        self.assertAlmostEqual(result['final_value'], 2500)
        self.assertEqual(result['closed_trades'], 1)

    def test_unsorted_data_is_sorted_without_mutating_input(self):
        data = self.data.iloc[::-1].copy()
        original = data.copy(deep=True)
        self.assertEqual(self.calculate('Follow all signals', data=data)['final_value'], 3750)
        pd.testing.assert_frame_equal(data, original)

    def test_negative_return(self):
        data = self.data.iloc[:2].copy()
        data.loc[1, 'CLOSE'] = 50
        result = self.calculate('Exit on next bearish flip', data=data)
        self.assertEqual(result['profit'], -500)
        self.assertEqual(result['return_pct'], -50)

    def test_invalid_investment_strategy_and_entry(self):
        for amount in [0, -1, float('nan'), float('inf')]:
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                calculate_backtest(self.data, '2024-01-02', amount, 'Hold until today')
        with self.assertRaises(ValueError):
            self.calculate('Unknown')
        with self.assertRaises(ValueError):
            self.calculate('Hold until today', '2024-01-03')
        with self.assertRaises(ValueError):
            self.calculate('Hold until today', '2024-01-01')

    def test_invalid_data_is_rejected(self):
        for price in [0, -1, None, float('inf')]:
            data = self.data.copy()
            data.loc[0, 'CLOSE'] = price
            with self.subTest(price=price), self.assertRaises(ValueError):
                prepare_backtest_data(data)
        for data in [self.data.iloc[:0], self.data.drop(columns='CLOSE'),
                     pd.concat([self.data, self.data.iloc[:1]])]:
            with self.assertRaises(ValueError):
                prepare_backtest_data(data)

    def test_conflicting_signals_are_rejected(self):
        data = self.data.copy()
        data.loc[0, 'SIGNAL_FLIP_DOWN'] = True
        with self.assertRaises(ValueError):
            prepare_backtest_data(data)

    def test_single_latest_bullish_candle(self):
        result = self.calculate('Follow all signals', '2024-01-06', self.data.iloc[4:5])
        self.assertEqual(result['final_value'], 1000)
        self.assertEqual(result['return_pct'], 0)


if __name__ == '__main__':
    unittest.main()