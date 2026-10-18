import unittest

import pandas as pd

from app.charts.price_supertrend_chart import build_price_supertrend_chart


class PriceSupertrendChartTests(unittest.TestCase):
    def test_candles_and_flips_hover_close_dates_without_moving_positions(self):
        for interval_days in [1, 7]:
            with self.subTest(interval_days=interval_days):
                opens = pd.date_range('2024-01-01', periods=3, freq=f'{interval_days}D')
                closes = opens + pd.Timedelta(days=interval_days) - pd.Timedelta(milliseconds=1)
                data = pd.DataFrame({
                    'OPEN_TIME': opens,
                    'CLOSE_TIME': closes,
                    'OPEN': [100., 110., 120.],
                    'HIGH': [120., 130., 140.],
                    'LOW': [90., 100., 110.],
                    'CLOSE': [110., 120., 130.],
                    'VOLUME': [10., 20., 30.],
                    'NUMBER_OF_TRADES': [100, 200, 300],
                    'SUPERTREND_VALUE': [90., 140., 100.],
                    'TREND_DIRECTION': ['Bullish', 'Bearish', 'Bullish'],
                    'IS_BULL_TREND': [True, False, True],
                    'IS_BEAR_TREND': [False, True, False],
                    'SIGNAL_FLIP_UP': [False, False, True],
                    'SIGNAL_FLIP_DOWN': [False, True, False],
                })
                original = data.copy(deep=True)
                figure = build_price_supertrend_chart(data, pd.DataFrame())
                traces = {trace.name: trace for trace in figure.data}

                for name, indices, date_label in [
                    ('BTC Hover', [0, 1, 2], 'Close date'),
                    ('Bullish Flip', [2], 'Candle close date'),
                    ('Bearish Flip', [1], 'Candle close date'),
                ]:
                    trace = traces[name]
                    self.assertIn(date_label + ': %{text}', trace.hovertemplate)
                    self.assertNotIn('%{x', trace.hovertemplate)
                    self.assertEqual(list(trace.text), closes[indices].strftime('%Y-%m-%d').tolist())
                    self.assertEqual(pd.to_datetime(trace.x).tolist(), opens[indices].tolist())

                self.assertEqual(traces['Bullish Flip'].customdata[0][0], 130.)
                self.assertEqual(traces['Bearish Flip'].customdata[0][0], 120.)
                self.assertEqual(traces['BTC Hover'].customdata[0][3], 110.)
                pd.testing.assert_frame_equal(data, original)


if __name__ == '__main__':
    unittest.main()