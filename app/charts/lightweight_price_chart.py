import json

import pandas as pd


CHART_LIBRARY_URL = (
    'https://unpkg.com/lightweight-charts@4.2.3/dist/'
    'lightweight-charts.standalone.production.js'
)
CHART_HEIGHT = 660
CHART_TITLE = 'BTC Price (USDT) with Supertrend'
CHART_LEGEND_HTML = '''
<div role="group" aria-label="Chart legend" style="display:flex;flex-wrap:wrap;align-items:center;gap:6px 16px;margin:0 0 5px;color:inherit;font:11px Geist,Arial,sans-serif;">
  <span style="display:inline-flex;align-items:center;gap:5px;"><span style="width:0;height:0;border-left:6px solid transparent;border-right:6px solid transparent;border-bottom:10px solid #159b87;"></span>Bullish flip</span>
  <span style="display:inline-flex;align-items:center;gap:5px;"><span style="width:0;height:0;border-left:6px solid transparent;border-right:6px solid transparent;border-top:10px solid #e4474d;"></span>Bearish flip</span>
  <span style="display:inline-flex;align-items:center;gap:5px;"><span style="padding:2px 5px;border-radius:3px;background:#159b87;color:#fff;font-size:9px;">BUY</span>Selected strategy buy</span>
  <span style="display:inline-flex;align-items:center;gap:5px;"><span style="padding:2px 5px;border-radius:3px;background:#e4474d;color:#fff;font-size:9px;">SELL</span>Selected strategy sell</span>
  <span style="display:inline-flex;align-items:center;gap:5px;"><span style="width:14px;border-top:1px dashed currentColor;"></span>Halving</span>
  <span style="display:inline-flex;align-items:center;gap:5px;"><span style="width:14px;border-top:2px dotted #d49c4a;"></span>Expected halving</span>
  __PI_CYCLE_LEGEND__
</div>
'''
PI_CYCLE_LEGEND_HTML = '''
<span style="display:inline-flex;align-items:center;gap:16px;white-space:nowrap;font:inherit;line-height:inherit;">
<span style="display:inline-flex;align-items:center;gap:5px;font:inherit;line-height:inherit;"><span style="width:14px;border-top:2px solid var(--pi-cycle-111-color,#d97706);"></span>111DMA</span>
<span style="display:inline-flex;align-items:center;gap:5px;font:inherit;line-height:inherit;"><span style="width:14px;border-top:2px solid var(--pi-cycle-350-color,#2e78a8);"></span>350DMA x 2</span>
<span style="display:inline-flex;align-items:center;gap:5px;font:inherit;line-height:inherit;"><span style="width:8px;height:8px;background:var(--pi-cycle-signal-color,#bd6661);border-radius:1px;"></span>Pi Cycle Top</span>
</span>
'''


def _as_bool(value, default=False):
    if pd.isna(value):
        return default
    if isinstance(value, str):
        return value.strip().lower() in {'true', '1', 'yes'}
    return bool(value)


def _chart_data(price_df, halvings_df):
    required = {
        'OPEN_TIME', 'CLOSE_TIME', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'VOLUME',
        'SUPERTREND_VALUE', 'IS_BULL_TREND', 'IS_BEAR_TREND',
        'SIGNAL_FLIP_UP', 'SIGNAL_FLIP_DOWN',
    }
    missing = required.difference(price_df.columns)
    if missing:
        raise ValueError(f'Chart data is missing required columns: {sorted(missing)}')

    df = price_df.copy()
    df['OPEN_TIME'] = pd.to_datetime(df['OPEN_TIME'], errors='coerce', utc=True)
    df['CLOSE_TIME'] = pd.to_datetime(df['CLOSE_TIME'], errors='coerce', utc=True)
    for column in ['OPEN', 'HIGH', 'LOW', 'CLOSE', 'VOLUME', 'SUPERTREND_VALUE']:
        df[column] = pd.to_numeric(df[column], errors='coerce')

    df = (
        df.dropna(subset=['OPEN_TIME', 'CLOSE_TIME', 'OPEN', 'HIGH', 'LOW', 'CLOSE'])
        .sort_values('OPEN_TIME')
        .drop_duplicates(subset=['OPEN_TIME'])
        .reset_index(drop=True)
    )
    if df.empty:
        raise ValueError('No valid candles are available for the chart.')

    candles = []
    halvings = []
    for row in df.itertuples(index=False):
        timestamp = int(row.OPEN_TIME.timestamp())
        candles.append({
            'time': timestamp,
            'closeTime': int(row.CLOSE_TIME.timestamp()),
            'open': float(row.OPEN),
            'high': float(row.HIGH),
            'low': float(row.LOW),
            'close': float(row.CLOSE),
            'closeDate': row.CLOSE_TIME.strftime('%Y-%m-%d'),
            'supertrend': (
                float(row.SUPERTREND_VALUE)
                if pd.notna(row.SUPERTREND_VALUE) else None
            ),
            'bullTrend': bool(row.IS_BULL_TREND),
            'bearTrend': bool(row.IS_BEAR_TREND),
            'bullFlip': bool(row.SIGNAL_FLIP_UP),
            'bearFlip': bool(row.SIGNAL_FLIP_DOWN),
            'volume': float(row.VOLUME) if pd.notna(row.VOLUME) else 0.0,
        })

    if halvings_df is not None and not halvings_df.empty and 'HALVING_DATE' in halvings_df:
        candle_times = [candle['time'] for candle in candles]
        halving_rows = halvings_df.copy()
        halving_rows['HALVING_DATE'] = pd.to_datetime(
            halving_rows['HALVING_DATE'], errors='coerce', utc=True,
        )
        latest_candle_time = candle_times[-1]

        for _, row in halving_rows.dropna(subset=['HALVING_DATE']).iterrows():
            halving_date = row['HALVING_DATE']
            halving_time = int(halving_date.timestamp())
            projected = _as_bool(
                row.get('IS_PROJECTED'),
                default=halving_time > latest_candle_time,
            )
            if projected:
                halvings.append({
                    'time': halving_time,
                    'label': f'Expected halving {halving_date:%Y-%m-%d}',
                    'projected': True,
                })
                continue

            if halving_time <= latest_candle_time:
                marker_time = next(
                    (time for time in candle_times if time >= halving_time),
                    candle_times[-1],
                )
                halvings.append({
                    'time': marker_time,
                    'label': f'Halving {halving_date:%Y-%m-%d}',
                    'projected': False,
                })

    halvings.sort(key=lambda halving: halving['time'])
    return candles, halvings


def _trend_series_segments(candles, trend_key):
    segments = []
    segment = []
    for candle in candles:
        if candle[trend_key] and candle['supertrend'] is not None:
            segment.append({'time': candle['time'], 'value': candle['supertrend']})
        elif segment:
            segments.append(segment)
            segment = []
    if segment:
        segments.append(segment)
    return segments


def _timeline_times(candles, halvings):
    times = {candle['time'] for candle in candles}
    latest_time = candles[-1]['time']
    interval = candles[-1]['time'] - candles[-2]['time'] if len(candles) > 1 else 86400

    for halving in halvings:
        if not halving['projected']:
            continue
        halving_time = halving['time']
        times.add(halving_time)
        if halving_time <= latest_time:
            continue
        next_time = latest_time + interval
        while next_time < halving_time:
            times.add(next_time)
            next_time += interval

    return sorted(times)


def _pi_cycle_series(daily_price_df, chart_candles):
    required = {'OPEN_TIME', 'CLOSE'}
    if (
        daily_price_df is None
        or daily_price_df.empty
        or not required.issubset(daily_price_df.columns)
        or not chart_candles
    ):
        return []

    daily = daily_price_df[['OPEN_TIME', 'CLOSE']].copy()
    daily['OPEN_TIME'] = pd.to_datetime(daily['OPEN_TIME'], errors='coerce', utc=True)
    daily['CLOSE'] = pd.to_numeric(daily['CLOSE'], errors='coerce')
    daily = (
        daily.dropna(subset=['OPEN_TIME', 'CLOSE'])
        .sort_values('OPEN_TIME')
        .drop_duplicates(subset=['OPEN_TIME'])
        .reset_index(drop=True)
    )
    if daily.empty:
        return []

    daily['MA_111'] = daily['CLOSE'].rolling(111, min_periods=111).mean()
    daily['MA_350_X2'] = daily['CLOSE'].rolling(350, min_periods=350).mean() * 2
    daily['PI_TOP_COUNT'] = (
      (daily['MA_111'] > daily['MA_350_X2'])
      & (daily['MA_111'].shift(1) <= daily['MA_350_X2'].shift(1))
    ).fillna(False).astype(int).cumsum()
    target_times = pd.DataFrame({
        'time': [candle['time'] for candle in chart_candles],
        'target_time': pd.to_datetime(
          [candle.get('closeTime', candle['time']) for candle in chart_candles],
          unit='s', utc=True,
        ),
    })
    aligned = pd.merge_asof(
        target_times.sort_values('target_time'),
        daily,
        left_on='target_time',
        right_on='OPEN_TIME',
        direction='backward',
    )
    signal_counts = aligned['PI_TOP_COUNT'].fillna(0).astype(int)
    aligned['piTop'] = signal_counts.diff().fillna(signal_counts).gt(0)
    return [{
        'time': int(row.time),
        'ma111': float(row.MA_111) if pd.notna(row.MA_111) else None,
        'ma350x2': float(row.MA_350_X2) if pd.notna(row.MA_350_X2) else None,
        'piTop': bool(row.piTop),
    } for row in aligned.itertuples(index=False)]


def _backtest_marker_data(candles, trades):
    time_by_close_date = {candle['closeDate']: candle['time'] for candle in candles}
    markers = []
    for trade in trades or []:
        for date_key, side in [('entry_date', 'BUY'), ('exit_date', 'SELL')]:
            event_date = pd.to_datetime(trade.get(date_key), errors='coerce', utc=True)
            if pd.isna(event_date):
                continue
            time = time_by_close_date.get(event_date.strftime('%Y-%m-%d'))
            if time is not None:
                markers.append({'time': time, 'side': side})
    return markers


def _chart_legend_html(pi_cycle_enabled):
    pi_cycle_legend = PI_CYCLE_LEGEND_HTML.replace('\\n', '').strip()
    if not pi_cycle_enabled:
        # Hidden rather than left out, so the legend keeps its height and the chart below
        # doesn't move when Pi Cycle is toggled.
        pi_cycle_legend = pi_cycle_legend.replace('<span style="', '<span style="visibility:hidden;', 1)
    return CHART_LEGEND_HTML.replace('__PI_CYCLE_LEGEND__', pi_cycle_legend)


HTML_TEMPLATE = r'''<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="__CHART_LIBRARY_URL__"></script>
<style>
* { box-sizing: border-box; }
html, body { width: 100%; height: 100%; margin: 0; overflow: hidden; }
body { --chart-background: #fbfbfb; --chart-foreground: #3e4144; --chart-muted: #6b7280; --chart-grid: rgba(62,65,68,.07); --chart-border: rgba(62,65,68,.18); font-family: Geist, Arial, sans-serif; color: var(--chart-foreground); background: transparent; }
body.dark-theme { --chart-background: #161b22; --chart-foreground: #e6e9ef; --chart-muted: #aab4c2; --chart-grid: rgba(214,222,232,.09); --chart-border: rgba(214,222,232,.2); }
#chart-shell { position: relative; width: 100%; background: var(--chart-background); height: calc(100% - 18px); opacity: 0; transition: opacity .15s ease-out; }
#chart-shell.ready { opacity: 1; }
#chart { position: relative; z-index: 1; width: 100%; height: 100%; }
#trend-fill { position: absolute; z-index: 1; pointer-events: none; overflow: hidden; }
#hover-band { display: none; position: absolute; z-index: 0; opacity: .16; pointer-events: none; }
#hover-legend { display: none; position: absolute; z-index: 3; top: 4px; left: 6px; max-width: calc(100% - 90px); padding: 2px 6px; border-radius: 4px; background: color-mix(in srgb, var(--chart-background) 80%, transparent); color: var(--chart-muted); font-size: 13px; line-height: 1.5; pointer-events: none; }
#hover-legend > div { display: flex; flex-wrap: wrap; column-gap: 12px; }
#hover-legend span { white-space: nowrap; }
#hover-legend strong { color: var(--chart-foreground); font-weight: 600; }
#hover-legend .up { color: #159b87; }
#hover-legend .down { color: #e4474d; }
#chart-credit { position: absolute; right: 8px; bottom: 3px; z-index: 2; color: var(--chart-muted); font-size: 10px; }
#chart-credit a { color: inherit; text-decoration: underline; }
</style>
</head>
<body>
<div id="chart-shell">
  <div id="hover-band"></div>
  <div id="chart"></div>
  <svg id="trend-fill" aria-hidden="true"></svg>
  <div id="hover-legend"><div id="hover-legend-prices"></div><div id="hover-legend-details"></div></div>
  <div id="chart-credit">Charting by <a href="https://www.tradingview.com/" target="_blank" rel="noreferrer">TradingView</a></div>
</div>
<script>
(() => {
  if (!window.LightweightCharts) {
    document.getElementById('chart').textContent = 'Unable to load Lightweight Charts. Check browser access to unpkg.com.';
    document.getElementById('chart-shell').classList.add('ready');
    return;
  }
  const candles = __CANDLE_DATA__;
  const halvings = __HALVING_DATA__;
  // Trade markers come from the parent page (see render_trade_marker_bridge), so changing the
  // simulator inputs leaves this iframe's HTML unchanged and Streamlit doesn't remount the chart.
  let tradeMarkers = [];
  try {
    tradeMarkers = window.parent.__btcTradeMarkers || [];
  } catch (_) {}
  const piCycleSeries = __PI_CYCLE_SERIES__;
  const timelineTimes = __TIMELINE_DATA__;
  const bullishSegments = __BULLISH_SEGMENTS__;
  const bearishSegments = __BEARISH_SEGMENTS__;
  const rowsByTime = new Map(candles.map(row => [row.time, row]));
  const piCycleByTime = new Map(piCycleSeries.map(row => [row.time, row]));
  const container = document.getElementById('chart');
  const hoverLegend = document.getElementById('hover-legend');
  const hoverLegendPrices = document.getElementById('hover-legend-prices');
  const hoverLegendDetails = document.getElementById('hover-legend-details');
  const trendFill = document.getElementById('trend-fill');
  const hoverBand = document.getElementById('hover-band');
  const bullishColor = '#159b87';
  const bearishColor = '#e4474d';

  function colorChannels(color) {
    const channels = color.match(/[\d.]+/g)?.map(Number);
    return channels && channels.length >= 3 ? channels : null;
  }

  function relativeLuminance(channels) {
    const linear = channels.slice(0, 3).map(channel => {
      const normalized = channel / 255;
      return normalized <= 0.04045
        ? normalized / 12.92
        : ((normalized + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
  }

  function detectHostTheme() {
    try {
      const parentDocument = window.parent.document;
      const candidates = [
        parentDocument.querySelector('[data-testid="stApp"]'),
        parentDocument.querySelector('[data-testid="stAppViewContainer"]'),
        parentDocument.body,
      ];
      for (const candidate of candidates) {
        if (!candidate) continue;
        const hostStyle = window.parent.getComputedStyle(candidate);
        if (!colorChannels(hostStyle.backgroundColor)) continue;
        // The mode is read from the text color, so CSS keyed on btc-dark-theme may restyle the
        // background; the class is set before reading the final background.
        const foregroundChannels = colorChannels(hostStyle.color);
        const dark = foregroundChannels
          ? relativeLuminance(foregroundChannels) > 0.38
          : relativeLuminance(colorChannels(hostStyle.backgroundColor)) < 0.38;
        parentDocument.body.classList.toggle('btc-dark-theme', dark);
        const channels = colorChannels(hostStyle.backgroundColor);
        if ((channels[3] ?? 1) < 0.05) continue;
        return {
          dark,
          background: `rgb(${channels.slice(0, 3).map(Math.round).join(', ')})`,
          foreground: hostStyle.color,
        };
      }
    } catch (_) {}
    const dark = window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false;
    return {
      dark,
      background: dark ? '#161b22' : '#ffffff',
      foreground: dark ? '#e6e9ef' : '#3e4144',
    };
  }

  function paletteForTheme(host) {
    return host.dark ? {
      background: host.background, foreground: host.foreground || '#e6e9ef', muted: '#aab4c2',
      grid: 'rgba(214,222,232,.09)', border: 'rgba(214,222,232,.2)',
      bullishFill: 'rgba(21,155,135,.2)', bearishFill: 'rgba(228,71,77,.2)', hoverBand: '#8b95a5',
      historicalLine: 'rgba(174,187,201,.82)', historicalLabel: '#b6c1ce',
      expectedLine: 'rgba(224,169,85,.98)', expectedLabel: '#e0a955',
      piCycle111: '#f2a15c', piCycle350: '#69b7d8', piCycleSignal: 'rgba(240,128,124,.98)',
    } : {
      background: host.background, foreground: host.foreground || '#3e4144', muted: '#6b7280',
      grid: 'rgba(62,65,68,.07)', border: 'rgba(62,65,68,.18)',
      bullishFill: 'rgba(21,155,135,.13)', bearishFill: 'rgba(228,71,77,.13)', hoverBand: '#6b7280',
      historicalLine: 'rgba(82,96,112,.88)', historicalLabel: '#526070',
      expectedLine: 'rgba(157,96,27,.92)', expectedLabel: '#9d601b',
      piCycle111: '#d97706', piCycle350: '#2e78a8', piCycleSignal: 'rgba(212,72,80,.98)',
    };
  }

  function applyDocumentPalette(palette, dark) {
    const properties = {
      '--chart-background': palette.background,
      '--chart-foreground': palette.foreground,
      '--chart-muted': palette.muted,
      '--chart-grid': palette.grid,
      '--chart-border': palette.border,
    };
    for (const [name, value] of Object.entries(properties)) {
      document.body.style.setProperty(name, value);
    }
    document.body.classList.toggle('dark-theme', dark);
    try {
      window.parent.document.body.classList.toggle('btc-dark-theme', dark);
    } catch (_) {}
  }

  let hostTheme = detectHostTheme();
  let darkTheme = hostTheme.dark;
  let palette = paletteForTheme(hostTheme);
  applyDocumentPalette(palette, darkTheme);
  const chart = LightweightCharts.createChart(container, {
    width: container.clientWidth,
    height: container.clientHeight,
    layout: { background: { color: 'transparent' }, textColor: palette.muted, fontFamily: 'Geist, Arial, sans-serif', attributionLogo: false },
    grid: { vertLines: { color: palette.grid }, horzLines: { color: palette.grid } },
    // The hover band marks the hovered candle, so the vertical crosshair line is hidden.
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal, vertLine: { visible: false } },
    rightPriceScale: { borderColor: palette.border, scaleMargins: {top: 0.22, bottom: 0.15} },
    leftPriceScale: { visible: false, borderVisible: false, scaleMargins: {top: 0.82, bottom: 0} },
    timeScale: { borderColor: palette.border, timeVisible: false, rightOffset: 5, fixLeftEdge: true },
    localization: { locale: 'en-US' },
    handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
    handleScale: { axisPressedMouseMove: true, mouseWheel: true, pinch: true },
  });

  function timeToLogical(time) {
    const index = timelineTimes.findIndex(candidate => candidate === time);
    return index >= 0 ? index : null;
  }

  const candleSeries = chart.addCandlestickSeries({
    upColor: bullishColor, downColor: bearishColor, borderVisible: false,
    wickUpColor: bullishColor, wickDownColor: bearishColor, priceLineVisible: false,
  });
  const candleTimesWithPrices = new Set(candles.map(row => row.time));
  const candleData = candles.map(({time, open, high, low, close}) => ({time, open, high, low, close}));
  candleData.push(...timelineTimes
    .filter(time => !candleTimesWithPrices.has(time))
    .map(time => ({time})));
  candleData.sort((left, right) => left.time - right.time);
  candleSeries.setData(candleData);

  let hoveredCandleTime = null;
  function setHoveredCandle(row) {
    hoveredCandleTime = row && row.open !== null && row.open !== undefined ? row.time : null;
  }

  // A full-height band behind the hovered candle, as wide as the candle body. The chart canvas
  // is transparent so the band can sit underneath it without tinting the candle.
  function positionHoverBand() {
    const timeScale = chart.timeScale();
    const x = hoveredCandleTime === null ? null : timeScale.timeToCoordinate(hoveredCandleTime);
    const logical = hoveredCandleTime === null ? null : timeToLogical(hoveredCandleTime);
    if (x === null || logical === null) {
      hoverBand.style.display = 'none';
      return;
    }
    const barSpacing = timeScale.logicalToCoordinate(logical + 1) - timeScale.logicalToCoordinate(logical);
    const width = Math.max(1, barSpacing * 0.8);
    hoverBand.style.left = `${parseFloat(trendFill.style.left || '0') + x - width / 2}px`;
    hoverBand.style.top = trendFill.style.top;
    hoverBand.style.width = `${width}px`;
    hoverBand.style.height = trendFill.style.height;
    hoverBand.style.background = palette.hoverBand;
    hoverBand.style.display = 'block';
  }

  const trendSeriesList = [];
  for (const [segments, color] of [
    [bullishSegments, bullishColor],
    [bearishSegments, bearishColor],
  ]) {
    for (const segment of segments) {
      const trendSeries = chart.addLineSeries({
        color, lineWidth: 1, priceLineVisible: false,
        lastValueVisible: false, crosshairMarkerVisible: false,
      });
      trendSeries.setData(segment);
      trendSeriesList.push(trendSeries);
    }
  }

  const ma111Data = piCycleSeries
    .filter(row => row.ma111 !== null)
    .map(row => ({time: row.time, value: row.ma111}));
  const ma350x2Data = piCycleSeries
    .filter(row => row.ma350x2 !== null)
    .map(row => ({time: row.time, value: row.ma350x2}));
  if (ma111Data.length) {
    const ma111Series = chart.addLineSeries({
      color: palette.piCycle111, lineWidth: 1, priceLineVisible: false,
      lastValueVisible: false, crosshairMarkerVisible: false,
      // Left out of autoscaling so toggling Pi Cycle keeps the price scale unchanged.
      autoscaleInfoProvider: () => null,
    });
    ma111Series.setData(ma111Data);
  }
  if (ma350x2Data.length) {
    const ma350x2Series = chart.addLineSeries({
      color: palette.piCycle350, lineWidth: 1, priceLineVisible: false,
      lastValueVisible: false, crosshairMarkerVisible: false,
      // Left out of autoscaling so toggling Pi Cycle keeps the price scale unchanged.
      autoscaleInfoProvider: () => null,
    });
    ma350x2Series.setData(ma350x2Data);
  }

  const volumeSeries = chart.addHistogramSeries({
    priceScaleId: 'volume', priceFormat: {type: 'volume'},
    lastValueVisible: false, priceLineVisible: false,
  });
  volumeSeries.setData(candles.map(row => ({
    time: row.time,
    value: row.volume,
    color: row.close >= row.open ? 'rgba(21,155,135,.34)' : 'rgba(228,71,77,.34)',
  })));
  chart.priceScale('volume').applyOptions({
    scaleMargins: {top: 0.82, bottom: 0}, visible: false,
  });

  function syncOverlayBounds() {
    const paneCanvas = container.querySelector('canvas');
    if (!paneCanvas) return;
    const chartBounds = container.getBoundingClientRect();
    const paneBounds = paneCanvas.getBoundingClientRect();
    trendFill.style.left = `${paneBounds.left - chartBounds.left}px`;
    trendFill.style.top = `${paneBounds.top - chartBounds.top}px`;
    trendFill.style.width = `${paneBounds.width}px`;
    trendFill.style.height = `${paneBounds.height}px`;
    trendFill.setAttribute('viewBox', `0 0 ${paneBounds.width} ${paneBounds.height}`);
  }

  function drawTrendFill() {
    syncOverlayBounds();
    positionHoverBand();
    savePriceRange();
    trendFill.replaceChildren();
    const range = chart.timeScale().getVisibleLogicalRange();
    if (!range) return;
    const start = Math.max(0, Math.floor(range.from));
    const end = Math.min(timelineTimes.length - 1, Math.ceil(range.to));
    const trends = [
      {active: row => row.bullTrend, color: palette.bullishFill},
      {active: row => row.bearTrend, color: palette.bearishFill},
    ];

    for (const trend of trends) {
      let segment = [];
      const appendSegment = () => {
        if (segment.length >= 2) {
          const closePoints = segment.map(point => `${point.x} ${point.closeY}`);
          const trendPoints = [...segment].reverse().map(point => `${point.x} ${point.trendY}`);
          const polygon = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
          polygon.setAttribute('points', [...closePoints, ...trendPoints].join(','));
          polygon.setAttribute('fill', trend.color);
          trendFill.appendChild(polygon);
        }
        segment = [];
      };

      for (let index = start; index <= end; index += 1) {
        const row = rowsByTime.get(timelineTimes[index]);
        if (!row || !trend.active(row) || row.supertrend === null) {
          appendSegment();
          continue;
        }
        const x = chart.timeScale().logicalToCoordinate(index);
        const closeY = candleSeries.priceToCoordinate(row.close);
        const trendY = candleSeries.priceToCoordinate(row.supertrend);
        if (x === null || closeY === null || trendY === null) {
          appendSegment();
          continue;
        }
        segment.push({x, closeY, trendY});
      }
      appendSegment();
    }

    for (let index = start; index <= end; index += 1) {
      const row = rowsByTime.get(timelineTimes[index]);
      if (!row || (!row.bullFlip && !row.bearFlip)) continue;
      const x = chart.timeScale().logicalToCoordinate(index);
      if (x === null) continue;
      const size = 9;
      const markerY = 67;
      const markerX = Math.max(size, Math.min(x, trendFill.clientWidth - size));
      const points = row.bullFlip
        ? `${markerX},${markerY - size} ${markerX - size},${markerY + size} ${markerX + size},${markerY + size}`
        : `${markerX - size},${markerY - size} ${markerX + size},${markerY - size} ${markerX},${markerY + size}`;
      const marker = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
      marker.setAttribute('points', points);
      marker.setAttribute('fill', row.bullFlip ? bullishColor : bearishColor);
      marker.setAttribute('stroke', palette.background);
      marker.setAttribute('stroke-width', '1');
      trendFill.appendChild(marker);
    }

    for (const halving of halvings) {
      const index = timeToLogical(halving.time);
      if (index === null) continue;
      const x = chart.timeScale().logicalToCoordinate(index);
      if (x === null) continue;
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', x);
      line.setAttribute('x2', x);
      line.setAttribute('y1', 48);
      line.setAttribute('y2', trendFill.clientHeight - 1);
      line.setAttribute('stroke', halving.projected ? palette.expectedLine : palette.historicalLine);
      line.setAttribute('stroke-width', '1');
      line.setAttribute('stroke-dasharray', halving.projected ? '2 3' : '5 5');
      trendFill.appendChild(line);
      const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      const labelOnLeft = x > trendFill.clientWidth - 145;
      label.setAttribute('x', labelOnLeft ? x - 5 : x + 5);
      label.setAttribute('y', 40);
      label.setAttribute('text-anchor', labelOnLeft ? 'end' : 'start');
      label.setAttribute('fill', halving.projected ? palette.expectedLabel : palette.historicalLabel);
      label.setAttribute('font-size', '11');
      label.textContent = halving.label;
      trendFill.appendChild(label);
    }

    for (const signal of piCycleSeries) {
      if (!signal.piTop) continue;
      const index = timeToLogical(signal.time);
      if (index === null) continue;
      const x = chart.timeScale().logicalToCoordinate(index);
      if (x === null) continue;
      const labelOnLeft = x > trendFill.clientWidth - 105;
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', x);
      line.setAttribute('x2', x);
      line.setAttribute('y1', 58);
      line.setAttribute('y2', trendFill.clientHeight - 1);
      line.setAttribute('stroke', palette.piCycleSignal);
      line.setAttribute('stroke-width', '1.5');
      line.setAttribute('stroke-dasharray', '2 4');
      trendFill.appendChild(line);
      const marker = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      marker.setAttribute('x', x - 4);
      marker.setAttribute('y', '47');
      marker.setAttribute('width', '8');
      marker.setAttribute('height', '8');
      marker.setAttribute('fill', palette.piCycleSignal);
      marker.setAttribute('rx', '1');
      trendFill.appendChild(marker);
      const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      label.setAttribute('x', labelOnLeft ? x - 9 : x + 9);
      label.setAttribute('y', '55');
      label.setAttribute('text-anchor', labelOnLeft ? 'end' : 'start');
      label.setAttribute('fill', palette.piCycleSignal);
      label.setAttribute('font-size', '10');
      label.textContent = 'Pi Cycle Top';
      trendFill.appendChild(label);
    }

    // Leaving badges get their own lanes so the remaining badges don't shift when they finish.
    const badgeLaneRightEdges = [];
    const exitingLaneRightEdges = [];
    const now = performance.now();
    const exitingMarkers = [...markerTransitions.values()]
      .filter(transition => !transition.entering)
      .map(transition => transition.event);
    for (const event of [...tradeMarkers, ...exitingMarkers]) {
      const index = timeToLogical(event.time);
      if (index === null || index < start || index > end) continue;
      const x = chart.timeScale().logicalToCoordinate(index);
      if (x === null) continue;
      const transition = markerTransitions.get(markerKey(event));
      const exiting = transition && !transition.entering;
      const lanes = exiting ? exitingLaneRightEdges : badgeLaneRightEdges;
      const isBuy = event.side === 'BUY';
      const width = isBuy ? 34 : 39;
      const badgeX = Math.max(2, Math.min(x - width / 2, trendFill.clientWidth - width - 2));
      let lane = lanes.findIndex(rightEdge => rightEdge + 4 <= badgeX);
      if (lane < 0) lane = lanes.length;
      lanes[lane] = badgeX + width;
      const y = 86 + lane * 20;
      const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      if (transition) {
        const {opacity, scale, offsetY} = markerAnimationFrame(transition, now);
        const centerX = badgeX + width / 2;
        const centerY = y + 9;
        group.setAttribute('opacity', opacity);
        group.setAttribute(
          'transform',
          `translate(${centerX} ${centerY + offsetY}) scale(${scale}) translate(${-centerX} ${-centerY})`,
        );
      }
      const badge = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      badge.setAttribute('x', badgeX);
      badge.setAttribute('y', y);
      badge.setAttribute('width', width);
      badge.setAttribute('height', 18);
      badge.setAttribute('rx', 3);
      badge.setAttribute('fill', isBuy ? bullishColor : bearishColor);
      group.appendChild(badge);
      const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      label.setAttribute('x', badgeX + width / 2);
      label.setAttribute('y', y + 12.75);
      label.setAttribute('text-anchor', 'middle');
      label.setAttribute('fill', '#ffffff');
      label.setAttribute('font-size', '10');
      label.setAttribute('font-weight', '600');
      label.textContent = event.side;
      group.appendChild(label);
      trendFill.appendChild(group);
    }
  }

  // When the strategy changes, new badges pop in and removed ones shrink away; badges present in
  // both strategies stay still. The overlay is redrawn on every pointer move, so the animation is
  // computed per frame rather than left to CSS.
  const MARKER_ENTER_MS = 380;
  const MARKER_EXIT_MS = 220;
  const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
  const markerTransitions = new Map();
  let markerAnimationRunning = false;

  function markerKey(event) {
    return `${event.time}:${event.side}`;
  }

  function markerAnimationFrame(transition, now) {
    const duration = transition.entering ? MARKER_ENTER_MS : MARKER_EXIT_MS;
    const progress = Math.min(1, (now - transition.start) / duration);
    if (!transition.entering) {
      return {opacity: 1 - progress, scale: 1 - 0.3 * progress, offsetY: 0};
    }
    // Ease-out-back: a slight overshoot so the badge settles into place.
    const overshoot = 1.7;
    const t = progress - 1;
    const eased = 1 + (overshoot + 1) * t ** 3 + overshoot * t ** 2;
    return {opacity: Math.min(1, progress * 2.5), scale: 0.55 + 0.45 * eased, offsetY: -6 * (1 - eased)};
  }

  function runMarkerAnimation() {
    if (markerAnimationRunning) return;
    markerAnimationRunning = true;
    const step = () => {
      const now = performance.now();
      for (const [key, transition] of markerTransitions) {
        const duration = transition.entering ? MARKER_ENTER_MS : MARKER_EXIT_MS;
        if (now - transition.start >= duration) markerTransitions.delete(key);
      }
      drawTrendFill();
      if (markerTransitions.size) {
        requestAnimationFrame(step);
      } else {
        markerAnimationRunning = false;
      }
    };
    requestAnimationFrame(step);
  }

  let fillUpdateQueued = false;
  const scheduleTrendFill = () => {
    if (fillUpdateQueued) return;
    fillUpdateQueued = true;
    requestAnimationFrame(() => {
      fillUpdateQueued = false;
      drawTrendFill();
    });
  };
  chart.timeScale().subscribeVisibleLogicalRangeChange(scheduleTrendFill);
  container.addEventListener('pointermove', scheduleTrendFill, {passive: true});
  container.addEventListener('wheel', scheduleTrendFill, {passive: true});
  container.addEventListener('pointerup', scheduleTrendFill, {passive: true});

  // Dragging the chart pans the price scale only while auto-scale is off, so it is switched off
  // when a drag starts in the pane and back on if the drag stayed horizontal. Double-clicking
  // the price axis restores auto-scale after a vertical pan.
  const VERTICAL_PAN_THRESHOLD_PX = 6;
  let dragStartY = null;
  let autoScaleBeforeDrag = true;
  container.addEventListener('pointerdown', event => {
    if (event.button !== 0 || event.pointerType === 'touch') return;
    const paneBounds = trendFill.getBoundingClientRect();
    if (
      event.clientX < paneBounds.left || event.clientX > paneBounds.right
      || event.clientY < paneBounds.top || event.clientY > paneBounds.bottom
    ) return;
    const priceScale = chart.priceScale('right');
    autoScaleBeforeDrag = priceScale.options().autoScale;
    dragStartY = event.clientY;
    priceScale.applyOptions({autoScale: false});
  }, {capture: true, passive: true});
  window.addEventListener('pointerup', event => {
    if (dragStartY === null) return;
    if (autoScaleBeforeDrag && Math.abs(event.clientY - dragStartY) < VERTICAL_PAN_THRESHOLD_PX) {
      chart.priceScale('right').applyOptions({autoScale: true});
    }
    dragStartY = null;
  }, {passive: true});
  window.__btcSetTradeMarkers = markers => {
    if (!reduceMotion) {
      const start = performance.now();
      const nextKeys = new Set(markers.map(markerKey));
      const previousKeys = new Set(tradeMarkers.map(markerKey));
      for (const event of markers) {
        if (!previousKeys.has(markerKey(event))) {
          markerTransitions.set(markerKey(event), {entering: true, start});
        }
      }
      for (const event of tradeMarkers) {
        if (!nextKeys.has(markerKey(event))) {
          markerTransitions.set(markerKey(event), {entering: false, start, event});
        }
      }
    }
    tradeMarkers = markers;
    if (markerTransitions.size) runMarkerAnimation();
    scheduleTrendFill();
  };

  function syncChartTheme() {
    const nextTheme = detectHostTheme();
    if (
      nextTheme.dark === hostTheme.dark
      && nextTheme.background === hostTheme.background
      && nextTheme.foreground === hostTheme.foreground
    ) return;
    hostTheme = nextTheme;
    darkTheme = hostTheme.dark;
    palette = paletteForTheme(hostTheme);
    applyDocumentPalette(palette, darkTheme);
    chart.applyOptions({
      layout: {textColor: palette.muted},
      grid: {vertLines: {color: palette.grid}, horzLines: {color: palette.grid}},
      rightPriceScale: {borderColor: palette.border},
      timeScale: {borderColor: palette.border},
    });
    scheduleTrendFill();
  }
  setInterval(syncChartTheme, 1000);

  function formatPrice(value) {
    return Number(value).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
  }

  // Hovered-candle values in a compact strip at the top left, so nothing covers the candles
  // around the cursor; the hover band shows which candle they belong to.
  chart.subscribeCrosshairMove(param => {
    scheduleTrendFill();
    if (!param.time || !param.point || param.point.x < 0 || param.point.y < 0) {
      hoverLegend.style.display = 'none';
      setHoveredCandle(null);
      positionHoverBand();
      return;
    }
    const row = rowsByTime.get(Number(param.time));
    setHoveredCandle(row);
    positionHoverBand();
    if (!row || row.open === null || row.open === undefined) {
      hoverLegend.style.display = 'none';
      return;
    }
    const change = row.open ? (row.close - row.open) / row.open * 100 : 0;
    const direction = row.close >= row.open ? 'up' : 'down';
    hoverLegendPrices.innerHTML = [
      `<span>${row.closeDate}</span>`,
      ...[['O', row.open], ['H', row.high], ['L', row.low], ['C', row.close]]
        .map(([label, value]) => `<span>${label} <strong class="${direction}">${formatPrice(value)}</strong></span>`),
      `<span><strong class="${direction}">${change >= 0 ? '+' : ''}${change.toFixed(2)}%</strong></span>`,
    ].join('');

    const details = [
      ['Supertrend', row.supertrend === null || row.supertrend === undefined ? null : formatPrice(row.supertrend)],
      ['Trend', row.bullTrend ? 'Bullish' : row.bearTrend ? 'Bearish' : null],
      ['Signal', row.bullFlip ? 'Bullish flip' : row.bearFlip ? 'Bearish flip' : null],
      ['Vol', row.volume === null || row.volume === undefined ? null
        : Number(row.volume).toLocaleString('en-US', {notation: 'compact', maximumFractionDigits: 2})],
    ];
    const piCycleRow = piCycleByTime.get(Number(param.time));
    if (piCycleRow?.ma111 !== null && piCycleRow?.ma111 !== undefined) {
      details.push(['111DMA', formatPrice(piCycleRow.ma111)]);
    }
    if (piCycleRow?.ma350x2 !== null && piCycleRow?.ma350x2 !== undefined) {
      details.push(['350DMA x 2', formatPrice(piCycleRow.ma350x2)]);
    }
    if (piCycleRow?.piTop) {
      details.push(['Pi Cycle Top', '111DMA crossed above 350DMA x 2']);
    }
    hoverLegendDetails.innerHTML = details
      .filter(([, value]) => value !== null)
      .map(([label, value]) => `<span>${label} <strong>${value}</strong></span>`)
      .join('');
    hoverLegend.style.display = 'block';
  });

  // Keep the user's zoom/scroll across Streamlit reruns (e.g. toggling Pi Cycle), per timeframe.
  const candleInterval = candles.length > 1 ? candles[1].time - candles[0].time : 0;
  const rangeStorageKey = `btc-price-chart-range:${candleInterval}`;
  let savedRange = null;
  try {
    savedRange = JSON.parse(window.sessionStorage.getItem(rangeStorageKey));
  } catch (_) {}
  chart.timeScale().subscribeVisibleLogicalRangeChange(range => {
    if (!range) return;
    try {
      window.sessionStorage.setItem(rangeStorageKey, JSON.stringify({from: range.from, to: range.to}));
    } catch (_) {}
  });

  // The vertical position is kept too. Lightweight Charts 4 has no setter for the price range,
  // so a restored range is fed through autoscale for the first render and then frozen by
  // switching auto-scale off.
  const priceRangeStorageKey = `${rangeStorageKey}:price`;
  let savedPriceRange = null;
  try {
    savedPriceRange = JSON.parse(window.sessionStorage.getItem(priceRangeStorageKey));
  } catch (_) {}
  let lastSavedPriceRange = null;
  let restoringPriceRange = false;

  function savePriceRange() {
    if (restoringPriceRange) return;
    const height = parseFloat(trendFill.style.height);
    if (!height) return;
    const autoScale = chart.priceScale('right').options().autoScale;
    const from = candleSeries.coordinateToPrice(height);
    const to = candleSeries.coordinateToPrice(0);
    const next = JSON.stringify(autoScale ? {autoScale} : {autoScale, from, to});
    if (next === lastSavedPriceRange || (!autoScale && (from === null || to === null))) return;
    lastSavedPriceRange = next;
    try {
      window.sessionStorage.setItem(priceRangeStorageKey, next);
    } catch (_) {}
  }

  function restorePriceRange() {
    const {from, to} = savedPriceRange || {};
    if (savedPriceRange?.autoScale !== false || !Number.isFinite(from) || !Number.isFinite(to) || to <= from) {
      return;
    }
    // Autoscale fits the range between the scale margins, so widen it back to the full pane.
    const {top, bottom} = chart.priceScale('right').options().scaleMargins;
    const span = to - from;
    const fixedRange = {priceRange: {minValue: from + span * bottom, maxValue: to - span * top}};
    restoringPriceRange = true;
    trendSeriesList.forEach(series => series.applyOptions({autoscaleInfoProvider: () => null}));
    candleSeries.applyOptions({autoscaleInfoProvider: () => fixedRange});
  }

  function freezeRestoredPriceRange() {
    if (!restoringPriceRange) return;
    chart.priceScale('right').applyOptions({autoScale: false});
    trendSeriesList.forEach(series => series.applyOptions({autoscaleInfoProvider: undefined}));
    candleSeries.applyOptions({autoscaleInfoProvider: undefined});
    restoringPriceRange = false;
  }

  restorePriceRange();
  const firstVisibleCandle = candles[Math.max(0, candles.length - 400)];
  const firstVisibleIndex = timeToLogical(firstVisibleCandle.time);
  const projectedHalvingIndexes = halvings
    .filter(item => item.projected)
    .map(item => timeToLogical(item.time));
  if (Number.isFinite(savedRange?.from) && Number.isFinite(savedRange?.to) && savedRange.to > savedRange.from) {
    chart.timeScale().setVisibleLogicalRange(savedRange);
  } else if (projectedHalvingIndexes.length) {
    const projectedEnd = Math.max(
      timelineTimes.length + 5,
      ...projectedHalvingIndexes.map(index => index + 5),
    );
    chart.timeScale().setVisibleLogicalRange({
      from: firstVisibleIndex,
      to: projectedEnd,
    });
  } else if (candles.length <= 400) {
    chart.timeScale().fitContent();
  } else {
    chart.timeScale().setVisibleLogicalRange({
      from: firstVisibleIndex,
      to: timelineTimes.length + 5,
    });
  }
  drawTrendFill();
  const syncChartSize = () => {
    const width = Math.floor(container.clientWidth);
    const height = Math.floor(container.clientHeight);
    if (!width || !height) return;
    chart.applyOptions({width, height});
    scheduleTrendFill();
  };
  const chartResizeObserver = new ResizeObserver(syncChartSize);
  chartResizeObserver.observe(container);
  window.addEventListener('resize', syncChartSize, {passive: true});
  // Reveal only after the chart has been sized to its final frame, so a fresh iframe
  // never flashes its first, mis-sized render.
  requestAnimationFrame(() => {
    syncChartSize();
    requestAnimationFrame(() => {
      freezeRestoredPriceRange();
      document.getElementById('chart-shell').classList.add('ready');
    });
  });
})();
</script>
</body>
</html>'''


def _script_json(value):
  return (
    json.dumps(value, separators=(',', ':'))
    .replace('<', '\\u003c')
    .replace('>', '\\u003e')
    .replace('&', '\\u0026')
  )


def build_lightweight_chart_html(price_df, halvings_df, pi_cycle_df=None):
  candles, halvings = _chart_data(price_df, halvings_df)
  timeline = _timeline_times(candles, halvings)
  pi_cycle_series = _pi_cycle_series(pi_cycle_df, candles)
  replacements = {
    '__CHART_LIBRARY_URL__': CHART_LIBRARY_URL,
    '__CANDLE_DATA__': _script_json(candles),
    '__HALVING_DATA__': _script_json(halvings),
    '__PI_CYCLE_SERIES__': _script_json(pi_cycle_series),
    '__TIMELINE_DATA__': _script_json(timeline),
    '__BULLISH_SEGMENTS__': _script_json(_trend_series_segments(candles, 'bullTrend')),
    '__BEARISH_SEGMENTS__': _script_json(_trend_series_segments(candles, 'bearTrend')),
  }
  html = HTML_TEMPLATE
  for placeholder, value in replacements.items():
    html = html.replace(placeholder, value)
  return html


def render_lightweight_price_chart(price_df, halvings_df, backtest_trades=None, pi_cycle_df=None):
    import streamlit as st
    import streamlit.components.v1 as components

    html = build_lightweight_chart_html(price_df, halvings_df, pi_cycle_df)
    st.markdown(_chart_legend_html(pi_cycle_df is not None), unsafe_allow_html=True)
    components.html(html, height=CHART_HEIGHT + 18, scrolling=False)
    candles, _ = _chart_data(price_df, halvings_df)
    render_trade_marker_bridge(_backtest_marker_data(candles, backtest_trades))


def render_trade_marker_bridge(markers):
    import streamlit as st
    import streamlit.components.v1 as components

    # A hidden iframe that hands the BUY/SELL markers to the chart iframe: it stores them on the
    # parent page for a chart that is still loading and pushes them to one that is already drawn.
    markers_json = _script_json(markers)
    with st.container(key='price_chart_marker_bridge'):
        components.html(
            '<script>'
            'const host = window.parent;'
            f'host.__btcTradeMarkers = {markers_json};'
            'for (const frame of host.document.querySelectorAll("iframe")) {'
            '  try { frame.contentWindow.__btcSetTradeMarkers?.(host.__btcTradeMarkers); } catch (_) {}'
            '}'
            '</script>',
            height=0,
        )