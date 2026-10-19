import json

import pandas as pd


CHART_LIBRARY_URL = (
    'https://unpkg.com/lightweight-charts@4.2.3/dist/'
    'lightweight-charts.standalone.production.js'
)
CHART_HEIGHT = 750
CHART_TITLE = 'BTC Price (USDT) with Supertrend'
CHART_LEGEND_HTML = '''
<div role="group" aria-label="Chart legend" style="display:flex;flex-wrap:wrap;align-items:center;gap:6px 16px;margin:0 0 5px;color:inherit;font:11px Geist,Arial,sans-serif;">
  <span style="display:inline-flex;align-items:center;gap:5px;"><span style="width:0;height:0;border-left:6px solid transparent;border-right:6px solid transparent;border-bottom:10px solid #159b87;"></span>Bullish flip</span>
  <span style="display:inline-flex;align-items:center;gap:5px;"><span style="width:0;height:0;border-left:6px solid transparent;border-right:6px solid transparent;border-top:10px solid #e4474d;"></span>Bearish flip</span>
  <span style="display:inline-flex;align-items:center;gap:5px;"><span style="padding:2px 5px;border-radius:3px;background:#159b87;color:#fff;font-size:9px;">BUY</span>Selected strategy buy</span>
  <span style="display:inline-flex;align-items:center;gap:5px;"><span style="padding:2px 5px;border-radius:3px;background:#e4474d;color:#fff;font-size:9px;">SELL</span>Selected strategy sell</span>
  <span style="display:inline-flex;align-items:center;gap:5px;"><span style="width:14px;border-top:1px dashed currentColor;"></span>Halving</span>
  <span style="display:inline-flex;align-items:center;gap:5px;"><span style="width:14px;border-top:2px dotted #d49c4a;"></span>Expected halving</span>
</div>
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


HTML_TEMPLATE = r'''<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="__CHART_LIBRARY_URL__"></script>
<style>
* { box-sizing: border-box; }
html, body { width: 100%; height: 100%; margin: 0; overflow: hidden; }
body { --chart-background: #fbfbfb; --chart-foreground: #3e4144; --chart-muted: #6b7280; --chart-grid: rgba(62,65,68,.07); --chart-border: rgba(62,65,68,.18); --tooltip-background: rgba(251,251,251,.96); --tooltip-shadow: 0 2px 8px rgba(0,0,0,.08); font-family: Geist, Arial, sans-serif; color: var(--chart-foreground); background: var(--chart-background); }
body.dark-theme { --chart-background: #0e1117; --chart-foreground: #e6e9ef; --chart-muted: #aab4c2; --chart-grid: rgba(214,222,232,.09); --chart-border: rgba(214,222,232,.2); --tooltip-background: rgba(25,30,39,.98); --tooltip-shadow: 0 2px 10px rgba(0,0,0,.38); }
#chart-shell { position: relative; width: 100%; height: __CHART_HEIGHT__px; }
#chart { width: 100%; height: 100%; }
#trend-fill { position: absolute; z-index: 1; pointer-events: none; overflow: hidden; }
#tooltip { display: none; position: absolute; z-index: 3; max-width: 220px; padding: 8px 10px; border: 1px solid var(--chart-border); border-radius: 4px; background: var(--tooltip-background); box-shadow: var(--tooltip-shadow); font-size: 12px; line-height: 1.5; pointer-events: none; }
#tooltip-date { margin-bottom: 3px; color: var(--chart-muted); }
#tooltip-values { display: flex; flex-direction: column; gap: 2px; }
#tooltip-values span { white-space: nowrap; }
#tooltip-values strong { color: var(--chart-foreground); font-weight: 600; }
#chart-credit { position: absolute; right: 8px; bottom: 3px; z-index: 2; color: var(--chart-muted); font-size: 10px; }
#chart-credit a { color: inherit; text-decoration: underline; }
</style>
</head>
<body>
<div id="chart-shell">
  <div id="chart"></div>
  <svg id="trend-fill" aria-hidden="true"></svg>
  <div id="tooltip"><div id="tooltip-date"></div><div id="tooltip-values"></div></div>
  <div id="chart-credit">Charting by <a href="https://www.tradingview.com/" target="_blank" rel="noreferrer">TradingView</a></div>
</div>
<script>
(() => {
  if (!window.LightweightCharts) {
    document.getElementById('chart').textContent = 'Unable to load Lightweight Charts. Check browser access to unpkg.com.';
    return;
  }
  const candles = __CANDLE_DATA__;
  const halvings = __HALVING_DATA__;
  const tradeMarkers = __TRADE_MARKER_DATA__;
  const timelineTimes = __TIMELINE_DATA__;
  const bullishSegments = __BULLISH_SEGMENTS__;
  const bearishSegments = __BEARISH_SEGMENTS__;
  const rowsByTime = new Map(candles.map(row => [row.time, row]));
  const container = document.getElementById('chart');
  const tooltip = document.getElementById('tooltip');
  const tooltipDate = document.getElementById('tooltip-date');
  const tooltipValues = document.getElementById('tooltip-values');
  const trendFill = document.getElementById('trend-fill');
  const bullishColor = '#159b87';
  const bearishColor = '#e4474d';

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
        const background = hostStyle.backgroundColor;
        const channels = background.match(/[\d.]+/g)?.map(Number);
        if (!channels || channels.length < 3 || (channels[3] ?? 1) < 0.05) continue;
        const linear = channels.slice(0, 3).map(channel => {
          const normalized = channel / 255;
          return normalized <= 0.04045
            ? normalized / 12.92
            : ((normalized + 0.055) / 1.055) ** 2.4;
        });
        return {
          dark: 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2] < 0.38,
          background: `rgb(${channels.slice(0, 3).map(Math.round).join(', ')})`,
          foreground: hostStyle.color,
        };
      }
    } catch (_) {}
    const dark = window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false;
    return {
      dark,
      background: dark ? '#0e1117' : '#ffffff',
      foreground: dark ? '#e6e9ef' : '#3e4144',
    };
  }

  function paletteForTheme(host) {
    return host.dark ? {
      background: host.background, foreground: host.foreground || '#e6e9ef', muted: '#aab4c2',
      grid: 'rgba(214,222,232,.09)', border: 'rgba(214,222,232,.2)',
      tooltipBackground: 'rgba(25,30,39,.98)', tooltipShadow: '0 2px 10px rgba(0,0,0,.38)',
      bullishFill: 'rgba(21,155,135,.2)', bearishFill: 'rgba(228,71,77,.2)',
      historicalLine: 'rgba(174,187,201,.82)', historicalLabel: '#b6c1ce',
      expectedLine: 'rgba(224,169,85,.98)', expectedLabel: '#e0a955',
    } : {
      background: host.background, foreground: host.foreground || '#3e4144', muted: '#6b7280',
      grid: 'rgba(62,65,68,.07)', border: 'rgba(62,65,68,.18)',
      tooltipBackground: host.background, tooltipShadow: '0 2px 8px rgba(0,0,0,.08)',
      bullishFill: 'rgba(21,155,135,.13)', bearishFill: 'rgba(228,71,77,.13)',
      historicalLine: 'rgba(82,96,112,.88)', historicalLabel: '#526070',
      expectedLine: 'rgba(157,96,27,.92)', expectedLabel: '#9d601b',
    };
  }

  function applyDocumentPalette(palette, dark) {
    const properties = {
      '--chart-background': palette.background,
      '--chart-foreground': palette.foreground,
      '--chart-muted': palette.muted,
      '--chart-grid': palette.grid,
      '--chart-border': palette.border,
      '--tooltip-background': palette.tooltipBackground,
      '--tooltip-shadow': palette.tooltipShadow,
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
    layout: { background: { color: palette.background }, textColor: palette.muted, fontFamily: 'Geist, Arial, sans-serif', attributionLogo: false },
    grid: { vertLines: { color: palette.grid }, horzLines: { color: palette.grid } },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
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
    }
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
      const size = 7;
      const markerY = 66;
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

    const badgeLaneRightEdges = [];
    for (const event of tradeMarkers) {
      const index = timeToLogical(event.time);
      if (index === null || index < start || index > end) continue;
      const x = chart.timeScale().logicalToCoordinate(index);
      if (x === null) continue;
      const isBuy = event.side === 'BUY';
      const width = isBuy ? 31 : 35;
      const badgeX = Math.max(2, Math.min(x - width / 2, trendFill.clientWidth - width - 2));
      let lane = badgeLaneRightEdges.findIndex(rightEdge => rightEdge + 4 <= badgeX);
      if (lane < 0) lane = badgeLaneRightEdges.length;
      badgeLaneRightEdges[lane] = badgeX + width;
      const y = 86 + lane * 18;
      const badge = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      badge.setAttribute('x', badgeX);
      badge.setAttribute('y', y);
      badge.setAttribute('width', width);
      badge.setAttribute('height', 16);
      badge.setAttribute('rx', 3);
      badge.setAttribute('fill', isBuy ? bullishColor : bearishColor);
      trendFill.appendChild(badge);
      const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      label.setAttribute('x', badgeX + width / 2);
      label.setAttribute('y', y + 11.5);
      label.setAttribute('text-anchor', 'middle');
      label.setAttribute('fill', '#ffffff');
      label.setAttribute('font-size', '9');
      label.setAttribute('font-weight', '600');
      label.textContent = event.side;
      trendFill.appendChild(label);
    }
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
      layout: {background: {color: palette.background}, textColor: palette.muted},
      grid: {vertLines: {color: palette.grid}, horzLines: {color: palette.grid}},
      rightPriceScale: {borderColor: palette.border},
      timeScale: {borderColor: palette.border},
    });
    scheduleTrendFill();
  }
  setInterval(syncChartTheme, 1000);

  chart.subscribeCrosshairMove(param => {
    scheduleTrendFill();
    if (!param.time || !param.point || param.point.x < 0 || param.point.y < 0) {
      tooltip.style.display = 'none';
      return;
    }
    const row = rowsByTime.get(Number(param.time));
    if (!row) { tooltip.style.display = 'none'; return; }
    tooltipDate.textContent = 'Candle close: ' + row.closeDate;
    tooltipValues.innerHTML = [
      ['Open', row.open], ['High', row.high], ['Low', row.low], ['Close', row.close],
      ['Supertrend', row.supertrend],
      ['Trend', row.bullTrend ? 'Bullish' : row.bearTrend ? 'Bearish' : 'N/A'],
      ['Signal', row.bullFlip ? 'Bullish flip' : row.bearFlip ? 'Bearish flip' : null],
      ['Volume', row.volume],
    ].map(([label, value]) => {
      if (value === null || value === undefined) return '';
      const priceLabels = ['Open', 'High', 'Low', 'Close', 'Supertrend'];
      const formatted = priceLabels.includes(label)
        ? Number(value).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' USDT'
        : label === 'Volume'
          ? Number(value).toLocaleString('en-US', {maximumFractionDigits: 2})
          : value;
      return `<span>${label}: <strong>${formatted}</strong></span>`;
    }).join('');
    tooltip.style.display = 'block';
    const gap = 12;
    const left = param.point.x + tooltip.offsetWidth + gap <= container.clientWidth
      ? param.point.x + gap
      : param.point.x - tooltip.offsetWidth - gap;
    const top = param.point.y + tooltip.offsetHeight + gap <= container.clientHeight
      ? param.point.y + gap
      : param.point.y - tooltip.offsetHeight - gap;
    tooltip.style.left = left + 'px';
    tooltip.style.top = Math.max(8, Math.min(top, container.clientHeight - tooltip.offsetHeight - 8)) + 'px';
  });

  const firstVisibleCandle = candles[Math.max(0, candles.length - 400)];
  const firstVisibleIndex = timeToLogical(firstVisibleCandle.time);
  const projectedHalvingIndexes = halvings
    .filter(item => item.projected)
    .map(item => timeToLogical(item.time));
  if (projectedHalvingIndexes.length) {
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
  new ResizeObserver(entries => {
    const box = entries[0].contentRect;
    chart.applyOptions({width: Math.floor(box.width), height: Math.floor(box.height)});
    scheduleTrendFill();
  }).observe(container);
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


def build_lightweight_chart_html(price_df, halvings_df, backtest_trades=None):
  candles, halvings = _chart_data(price_df, halvings_df)
  timeline = _timeline_times(candles, halvings)
  trade_markers = _backtest_marker_data(candles, backtest_trades)
  replacements = {
    '__CHART_LIBRARY_URL__': CHART_LIBRARY_URL,
    '__CHART_HEIGHT__': str(CHART_HEIGHT),
    '__CANDLE_DATA__': _script_json(candles),
    '__HALVING_DATA__': _script_json(halvings),
    '__TRADE_MARKER_DATA__': _script_json(trade_markers),
    '__TIMELINE_DATA__': _script_json(timeline),
    '__BULLISH_SEGMENTS__': _script_json(_trend_series_segments(candles, 'bullTrend')),
    '__BEARISH_SEGMENTS__': _script_json(_trend_series_segments(candles, 'bearTrend')),
  }
  html = HTML_TEMPLATE
  for placeholder, value in replacements.items():
    html = html.replace(placeholder, value)
  return html


def render_lightweight_price_chart(price_df, halvings_df, backtest_trades=None):
    import streamlit as st
    import streamlit.components.v1 as components

    html = build_lightweight_chart_html(price_df, halvings_df, backtest_trades)
    st.markdown(CHART_LEGEND_HTML, unsafe_allow_html=True)
    components.html(html, height=CHART_HEIGHT + 18, scrolling=False)