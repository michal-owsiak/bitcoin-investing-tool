import pandas as pd
import plotly.graph_objects as go
import datetime as dt


def _add_supertrend_fill_segments(
    fig: go.Figure,
    price_df: pd.DataFrame,
    trend_col: str,
    line_color: str,
    fill_color: str,
    trace_name: str
) -> None:
    df = price_df.copy()

    segment_start = None
    in_segment = False
    legend_shown = False

    for i, is_trend in enumerate(df[trend_col].fillna(False)):
        if is_trend and not in_segment:
            segment_start = i
            in_segment = True

        is_last_row = i == len(df) - 1

        if in_segment and ((not is_trend) or is_last_row):
            segment_end = i if is_last_row and is_trend else i - 1

            segment_df = df.iloc[segment_start:segment_end + 1].copy()

            fig.add_trace(
                go.Scatter(
                    x=segment_df['OPEN_TIME'],
                    y=segment_df['CLOSE'],
                    mode='lines',
                    line=dict(width=0),
                    showlegend=False,
                    hoverinfo='skip'
                )
            )

            fig.add_trace(
                go.Scatter(
                    x=segment_df['OPEN_TIME'],
                    y=segment_df['SUPERTREND_VALUE'],
                    mode='lines',
                    name=trace_name,
                    line=dict(color=line_color, width=0.8),
                    fill='tonexty',
                    fillcolor=fill_color,
                    showlegend=not legend_shown,
                    customdata=segment_df[['TREND_DIRECTION']],
                    hovertemplate=(
                        'Date: %{x|%Y-%m-%d}<br>'
                        'Trend: %{customdata[0]}'
                        '<extra></extra>'
                    )
                )
            )

            legend_shown = True
            in_segment = False
            segment_start = None


def build_price_supertrend_chart(price_df: pd.DataFrame, halvings_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()

    price_df = price_df.copy()
    price_df = price_df.sort_values('OPEN_TIME').reset_index(drop=True)

    start = price_df['OPEN_TIME'].iloc[-400]
    end = price_df['OPEN_TIME'].iloc[-1]
    padding = (end - start) * 0.07

    y_min = price_df['LOW'].min()
    y_max = price_df['HIGH'].max()
    y_range = y_max - y_min

    flip_up_y = y_max + (y_range * 0.05)
    flip_down_y = y_max + (y_range * 0.10)

    fig.add_trace(
        go.Candlestick(
            x=price_df['OPEN_TIME'],
            open=price_df['OPEN'],
            high=price_df['HIGH'],
            low=price_df['LOW'],
            close=price_df['CLOSE'],
            name='BTC Price',
            increasing_fillcolor='#26a69a',
            increasing_line_color='#26a69a',
            decreasing_fillcolor='#ef5350',
            decreasing_line_color='#ef5350',
            whiskerwidth=0,
            customdata=price_df[['OPEN', 'HIGH', 'LOW', 'CLOSE', 'VOLUME', 'NUMBER_OF_TRADES']],
            hovertemplate=(
                'Date: %{x|%Y-%m-%d}<br>'
                'Open: $%{customdata[0]:,.2f}<br>'
                'High: $%{customdata[1]:,.2f}<br>'
                'Low: $%{customdata[2]:,.2f}<br>'
                'Close: $%{customdata[3]:,.2f}<br>'
                'Volume: %{customdata[4]:,.2f}<br>'
                'Trades: %{customdata[5]:,.0f}'
                '<extra></extra>'
            )
        )
    )

    _add_supertrend_fill_segments(
        fig=fig,
        price_df=price_df,
        trend_col='IS_BULL_TREND',
        line_color='green',
        fill_color='rgba(0, 180, 0, 0.10)',
        trace_name='Bullish Supertrend'
    )

    _add_supertrend_fill_segments(
        fig=fig,
        price_df=price_df,
        trend_col='IS_BEAR_TREND',
        line_color='red',
        fill_color='rgba(255, 0, 0, 0.10)',
        trace_name='Bearish Supertrend'
    )

    flip_up_df = price_df[price_df['SIGNAL_FLIP_UP'] == True].copy()
    flip_down_df = price_df[price_df['SIGNAL_FLIP_DOWN'] == True].copy()

    if not flip_up_df.empty:
        fig.add_trace(
            go.Scatter(
                x=flip_up_df['OPEN_TIME'],
                y=[flip_up_y] * len(flip_up_df),
                mode='markers',
                name='Bullish Flip',
                marker=dict(
                    symbol='triangle-up',
                    size=14,
                    color='green',
                    line=dict(width=0)
                ),
                customdata=flip_up_df[['CLOSE']],
                hovertemplate=(
                    'Bullish Flip<br>'
                    'Date: %{x|%Y-%m-%d}<br>'
                    'Close: $%{customdata[0]:,.2f}'
                    '<extra></extra>'
                )
            )
        )

    if not flip_down_df.empty:
        fig.add_trace(
            go.Scatter(
                x=flip_down_df['OPEN_TIME'],
                y=[flip_down_y] * len(flip_down_df),
                mode='markers',
                name='Bearish Flip',
                marker=dict(
                    symbol='triangle-down',
                    size=14,
                    color='red',
                    line=dict(width=0)
                ),
                customdata=flip_down_df[['CLOSE']],
                hovertemplate=(
                    'Bearish Flip<br>'
                    'Date: %{x|%Y-%m-%d}<br>'
                    'Close: $%{customdata[0]:,.2f}'
                    '<extra></extra>'
                )
            )
        )

    if halvings_df is not None and not halvings_df.empty:
        halvings_df = halvings_df.copy()
        halvings_df['HALVING_DATE'] = pd.to_datetime(halvings_df['HALVING_DATE'])

        for _, row in halvings_df.iterrows():
            halving_dt = row['HALVING_DATE']

            fig.add_shape(
                type='line',
                x0=halving_dt,
                x1=halving_dt,
                y0=y_min,
                y1=y_max + (y_range * 0.15),  
                xref='x',
                yref='y',
                line=dict(
                    color='gray',
                    width=1,
                    dash='dash'
                )
            )

            if halving_dt <= dt.datetime.now():
                fig.add_annotation(
                    x=halving_dt,
                    y=y_max + (y_range * 0.18),
                    text=f'Halving {halving_dt.date()}',
                    showarrow=False,
                    font=dict(size=14)
                )
            else:
                fig.add_annotation(
                    x=halving_dt,
                    y=y_max + (y_range * 0.18),
                    text=f'Expected halving {halving_dt.date()}',
                    showarrow=False,
                    font=dict(size=14)
                )

    fig.update_layout(
        font=dict(
            family='Geist',
            size=13,
        ),
        title={
            'text': 'BTC Price with Supertrend',
            'font': dict(
                family='Geist',
                size=22,
            ),
            'x': 0.5,
            'xanchor': 'center'
        },
        xaxis_title='Date',
        yaxis_title='Price',
        xaxis_rangeslider_visible=True,
        template='plotly_white',
        height=1000,
        xaxis=dict(
            range=[start, end + padding]
        ),
        yaxis=dict(
            range=[y_min, y_max + (y_range * 0.18)]
        ),
        hoverlabel=dict(
            font_size=13,
            font_family='Geist'
        )
    )

    return fig


def build_whale_inflow_monitor(whales_df: pd.DataFrame) -> go.Figure:
    df = whales_df.copy()

    if df.empty:
        return go.Figure()

    df = df.sort_values('total_output_value', ascending=False).head(10).copy()
    df['whale_label'] = [f'Whale #{i+1}' for i in range(len(df))]
    df = df.iloc[::-1]

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=df['total_output_value'],
            y=df['whale_label'],
            orientation='h',
            marker=dict(
                color="#23a88e"
            ),
            customdata=df[['output_address', 'transaction_count']],
            hovertemplate=(
                'Address: %{customdata[0]}<br>'
                'BTC Inflow: %{x:,.4f}<br>'
                'Transactions: %{customdata[1]}'
                '<extra></extra>'
            )
        )
    )

    fig.update_layout(
        title={
            'text': 'Top Whale Inflows',
            'x': 0.5,
            'xanchor': 'center'
        },
        xaxis_title='Inflow (BTC)',
        yaxis_title='',
        template='plotly_white',
        height=450,
        font=dict(
            family='Geist',
            size=12,
        ),
        margin=dict(l=0, r=50, t=100, b=50),
        yaxis=dict(
            automargin=True
        ),
        bargap=0.2,
  
    )

    return fig