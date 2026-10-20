import unittest

import pandas as pd

from app.charts.lightweight_price_chart import (
    CHART_LEGEND_HTML,
    CHART_TITLE,
    PI_CYCLE_LEGEND_HTML,
    _chart_legend_html,
    _chart_data,
    _backtest_marker_data,
    _pi_cycle_series,
    _timeline_times,
    _trend_series_segments,
    build_lightweight_chart_html,
)


class LightweightPriceChartTests(unittest.TestCase):
    def setUp(self):
        self.data = pd.DataFrame({
            'OPEN_TIME': pd.to_datetime(['2024-01-02', '2024-01-01']),
            'CLOSE_TIME': pd.to_datetime(['2024-01-02 23:59:59', '2024-01-01 23:59:59']),
            'OPEN': [110.0, 100.0],
            'HIGH': [125.0, 115.0],
            'LOW': [105.0, 95.0],
            'CLOSE': [120.0, 110.0],
            'VOLUME': [25.0, 15.0],
            'SUPERTREND_VALUE': [100.0, 90.0],
            'IS_BULL_TREND': [True, True],
            'IS_BEAR_TREND': [False, False],
            'SIGNAL_FLIP_UP': [True, False],
            'SIGNAL_FLIP_DOWN': [False, False],
        })
        self.halvings = pd.DataFrame({'HALVING_DATE': ['2024-01-01']})

    def test_chart_data_is_sorted_and_keeps_candle_close_dates(self):
        candles, halvings = _chart_data(self.data, self.halvings)

        self.assertEqual([candle['close'] for candle in candles], [110.0, 120.0])
        self.assertEqual([candle['closeDate'] for candle in candles], [
            '2024-01-01', '2024-01-02',
        ])
        self.assertEqual(candles[0]['volume'], 15.0)
        self.assertEqual(candles[1]['supertrend'], 100.0)
        self.assertEqual([candle['bullFlip'] for candle in candles], [False, True])
        self.assertEqual(halvings, [{
            'time': candles[0]['time'],
            'label': 'Halving 2024-01-01',
            'projected': False,
        }])

    def test_historical_halving_uses_nearest_candle_time_without_gap(self):
        halvings = pd.DataFrame({'HALVING_DATE': ['2024-01-01 12:00:00']})

        candles, chart_halvings = _chart_data(self.data, halvings)
        timeline = _timeline_times(candles, chart_halvings)

        self.assertEqual(chart_halvings[0]['time'], candles[1]['time'])
        self.assertEqual(timeline, [candle['time'] for candle in candles])

    def test_backtest_buy_and_sell_dates_map_to_candle_times(self):
        candles, _ = _chart_data(self.data, None)
        trades = [{
            'entry_date': pd.Timestamp('2024-01-01 23:59:59', tz='UTC'),
            'exit_date': pd.Timestamp('2024-01-02 23:59:59', tz='UTC'),
        }]

        self.assertEqual(_backtest_marker_data(candles, trades), [
            {'time': candles[0]['time'], 'side': 'BUY'},
            {'time': candles[1]['time'], 'side': 'SELL'},
        ])

    def test_pi_cycle_uses_daily_sma_and_aligns_to_candle_close(self):
        daily_times = pd.date_range('2020-01-01', periods=400, tz='UTC')
        daily = pd.DataFrame({
            'OPEN_TIME': daily_times,
            'CLOSE': range(1, 401),
        })
        chart_candles = [
            {
                'time': int(daily_times[index].timestamp()),
                'closeTime': int(daily_times[index].timestamp()),
            }
            for index in [108, 349, 399]
        ]

        series = _pi_cycle_series(daily, chart_candles)

        self.assertEqual(series[0]['ma111'], None)
        self.assertEqual(series[0]['ma350x2'], None)
        self.assertEqual(series[1]['ma111'], 295.0)
        self.assertEqual(series[1]['ma350x2'], 351.0)
        self.assertFalse(series[1]['piTop'])
        self.assertEqual(series[2]['ma111'], 345.0)
        self.assertEqual(series[2]['ma350x2'], 451.0)

    def test_pi_cycle_top_signal_is_detected_from_daily_cross(self):
        daily_times = pd.date_range('2020-01-01', periods=400, tz='UTC')
        daily = pd.DataFrame({
            'OPEN_TIME': daily_times,
            'CLOSE': [1.0] * 350 + [10.0] * 50,
        })
        chart_candles = [{
            'time': int(daily_times[index].timestamp()),
            'closeTime': int(daily_times[index].timestamp()),
        } for index in [349, 399]]

        series = _pi_cycle_series(daily, chart_candles)

        self.assertFalse(series[0]['piTop'])
        self.assertTrue(series[1]['piTop'])

    def test_chart_legend_explains_flip_trade_and_halving_markers(self):
        for label in [
            'Bullish flip', 'Bearish flip', 'Selected strategy buy',
            'Selected strategy sell', 'Halving', 'Expected halving',
        ]:
            with self.subTest(label=label):
                self.assertIn(label, CHART_LEGEND_HTML)
        self.assertIn('border-top:2px dotted #d49c4a', CHART_LEGEND_HTML)
        self.assertIn('color:inherit', CHART_LEGEND_HTML)
        self.assertIn('Pi Cycle Top', PI_CYCLE_LEGEND_HTML)
        self.assertEqual(PI_CYCLE_LEGEND_HTML.count('font:inherit;line-height:inherit'), 4)
        self.assertIn('width:8px;height:8px;background:var(--pi-cycle-signal-color', PI_CYCLE_LEGEND_HTML)

    def test_pi_cycle_legend_items_stay_inline_with_base_legend(self):
        legend = _chart_legend_html(True)

        self.assertIn('111DMA', legend)
        self.assertIn('350DMA x 2', legend)
        self.assertIn('Pi Cycle Top', legend)
        self.assertNotIn('<p>', legend)
        self.assertEqual(legend.count('<div role="group"'), 1)

    def test_html_embeds_chart_data_and_tradingview_attribution(self):
        html = build_lightweight_chart_html(self.data, self.halvings)

        self.assertIn('lightweight-charts@4.2.3', html)
        self.assertEqual(CHART_TITLE, 'BTC Price (USDT) with Supertrend')
        self.assertNotIn('chart-title', html)
        self.assertIn('Candle close: ', html)
        self.assertIn("const priceLabels = ['Open', 'High', 'Low', 'Close', 'Supertrend', '111DMA', '350DMA x 2']", html)
        self.assertIn("+ ' USDT'", html)
        self.assertNotIn("'$' + Number(value)", html)
        self.assertIn("row.bullFlip ? 'Bullish flip'", html)
        self.assertIn('const markerY = 66', html)
        self.assertIn("marker.setAttribute('fill', row.bullFlip ? bullishColor : bearishColor)", html)
        self.assertNotIn('setMarkers', html)
        self.assertIn('scaleMargins: {top: 0.22, bottom: 0.15}', html)
        self.assertIn('#tooltip-values { display: flex; flex-direction: column;', html)
        self.assertIn('tooltip.style.top', html)
        self.assertIn('const tradeMarkers = []', html)
        self.assertIn('const piCycleSeries = []', html)
        self.assertIn('color: palette.piCycle111', html)
        self.assertIn('color: palette.piCycle350', html)
        self.assertIn('color: palette.piCycle111, lineWidth: 1', html)
        self.assertIn('color: palette.piCycle350, lineWidth: 1', html)
        self.assertIn("piCycleSignal: 'rgba(212,72,80,.98)'", html)
        self.assertIn("piCycleSignal: 'rgba(240,128,124,.98)'", html)
        self.assertIn('if (!signal.piTop) continue', html)
        self.assertIn('const index = timeToLogical(signal.time);\n      if (index === null) continue;', html)
        self.assertIn("line.setAttribute('stroke-dasharray', '2 4')", html)
        self.assertIn("line.setAttribute('y1', 58)", html)
        self.assertIn("marker.setAttribute('width', '8')", html)
        self.assertIn("label.textContent = 'Pi Cycle Top'", html)
        self.assertIn('label.setAttribute(\'fill\', palette.piCycleSignal)', html)
        self.assertIn("label.textContent = event.side", html)
        self.assertIn("label.setAttribute('font-weight', '600')", html)
        self.assertIn("label.setAttribute('font-size', '9')", html)
        self.assertIn('const badgeLaneRightEdges = []', html)
        self.assertIn('const halvings = ', html)
        self.assertIn("createElementNS('http://www.w3.org/2000/svg', 'line')", html)
        self.assertIn('function detectHostTheme()', html)
        self.assertIn('background.match(/[\\d.]+/g)', html)
        self.assertIn('function paletteForTheme(host)', html)
        self.assertIn('background: host.background', html)
        self.assertIn('function applyDocumentPalette(palette, dark)', html)
        self.assertIn("window.parent.document.body.classList.toggle('btc-dark-theme', dark)", html)
        self.assertIn('setInterval(syncChartTheme, 1000)', html)
        self.assertIn('const chartResizeObserver = new ResizeObserver(syncChartSize)', html)
        self.assertIn('requestAnimationFrame(syncChartSize)', html)
        self.assertIn("line.setAttribute('stroke-dasharray', halving.projected ? '2 3' : '5 5')", html)
        self.assertIn('Halving 2024-01-01', html)
        self.assertIn('Charting by', html)
        self.assertIn('https://www.tradingview.com/', html)
        self.assertIn('attributionLogo: false', html)
        self.assertIn('Charting by <a', html)
        self.assertIn("priceScaleId: 'volume'", html)
        self.assertIn("chart.priceScale('volume').applyOptions", html)

    def test_projected_halving_is_kept_beyond_latest_candle(self):
        halvings = pd.DataFrame({
            'HALVING_DATE': ['2024-01-01', '2028-04-15'],
            'IS_HISTORICAL': [True, False],
            'IS_PROJECTED': [False, True],
        })
        candles, projected = _chart_data(self.data, halvings)

        self.assertEqual(len(candles), 2)
        self.assertEqual(len(projected), 2)
        self.assertEqual(projected[1]['label'], 'Expected halving 2028-04-15')
        self.assertGreater(projected[1]['time'], candles[-1]['time'])
        self.assertTrue(projected[1]['projected'])

        html = build_lightweight_chart_html(self.data, halvings)
        self.assertIn('Expected halving 2028-04-15', html)
        self.assertIn('chart.timeScale().setVisibleLogicalRange', html)
        self.assertIn('const timelineTimes = ', html)
        self.assertIn('logicalToCoordinate(index)', html)
        self.assertIn('candleData.push(...timelineTimes', html)

    def test_timeline_ignores_historical_times_and_extends_projected_times(self):
        candles, halvings = _chart_data(
            self.data,
            pd.DataFrame({
                'HALVING_DATE': ['2024-01-01', '2024-01-05'],
                'IS_PROJECTED': [False, True],
            }),
        )

        timeline = _timeline_times(candles, [
            {'time': candles[0]['time'] + 12 * 60 * 60, 'projected': False},
            halvings[1],
        ])
        self.assertEqual(timeline, [
            candles[0]['time'],
            candles[1]['time'],
            candles[1]['time'] + 24 * 60 * 60,
            candles[1]['time'] + 2 * 24 * 60 * 60,
            halvings[1]['time'],
        ])

    def test_supertrend_lines_split_at_regime_changes(self):
        data = self.data.copy()
        data['IS_BULL_TREND'] = [True, False]
        data['IS_BEAR_TREND'] = [False, True]
        candles, _ = _chart_data(data, self.halvings)

        bullish = _trend_series_segments(candles, 'bullTrend')
        bearish = _trend_series_segments(candles, 'bearTrend')

        self.assertEqual(bullish, [
            [{'time': candles[1]['time'], 'value': 100.0}],
        ])
        self.assertEqual(bearish, [
            [{'time': candles[0]['time'], 'value': 90.0}],
        ])

    def test_missing_chart_columns_are_reported(self):
        with self.assertRaisesRegex(ValueError, 'missing required columns'):
            _chart_data(self.data.drop(columns='VOLUME'), self.halvings)

    def test_empty_chart_data_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'No valid candles'):
            _chart_data(self.data.iloc[:0], self.halvings)


if __name__ == '__main__':
    unittest.main()