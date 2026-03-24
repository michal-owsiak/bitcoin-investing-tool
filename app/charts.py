import pandas as pd
import plotly.graph_objects as go
import datetime as dt


def _add_supertrend_fill_segments(fig: go.Figure, price_df: pd.DataFrame, trend_col: str, line_color: str, fill_color: str, trace_name: str) -> None:
    df = price_df.copy()

    segment_start = None
    in_segment = False

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
                    line=dict(color=line_color, width=1),
                    fill='tonexty',
                    fillcolor=fill_color,
                    showlegend=(segment_start == df.index[0])
                )
            )

            in_segment = False
            segment_start = None


def build_price_supertrend_chart(price_df: pd.DataFrame, halvings_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()

    price_df = price_df.copy()
    price_df = price_df.sort_values('OPEN_TIME').reset_index(drop=True)

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
            whiskerwidth=0
        )
    )

    _add_supertrend_fill_segments(
        fig=fig,
        price_df=price_df,
        trend_col='IS_BULL_TREND',
        line_color='green',
        fill_color='rgba(0, 180, 0, 0.10)',
        trace_name='Supertrend'
    )

    _add_supertrend_fill_segments(
        fig=fig,
        price_df=price_df,
        trend_col='IS_BEAR_TREND',
        line_color='red',
        fill_color='rgba(255, 0, 0, 0.10)',
        trace_name='Supertrend'
    )

    if halvings_df is not None and not halvings_df.empty:
        halvings_df = halvings_df.copy()
        halvings_df['HALVING_DATE'] = pd.to_datetime(halvings_df['HALVING_DATE'])

        y_max = price_df['HIGH'].max()

        for _, row in halvings_df.iterrows():
            halving_dt = row['HALVING_DATE']

            fig.add_vline(
                x=halving_dt,
                line_width=1,
                line_dash='dash',
                line_color='gray'
            )

            if halving_dt <= dt.datetime.now():
                fig.add_annotation(
                    x=halving_dt,
                    y=y_max,
                    text=f'Halving {halving_dt.date()}',
                    showarrow=False,
                    yshift=60,
                    font=dict(size=14)
                )
            else:
                fig.add_annotation(
                    x=halving_dt,
                    y=y_max,
                    text=f'Expected halving {halving_dt.date()}',
                    showarrow=False,
                    yshift=60,
                    font=dict(size=14)
                )


    start = price_df['OPEN_TIME'].iloc[-400]
    end = price_df['OPEN_TIME'].iloc[-1]

    padding = (end - start) * 0.07

    fig.update_layout(
        title={
            'text': 'BTC Price with Supertrend',
            'font': {'size': 28} 
        },
        xaxis_title='Date',
        yaxis_title='Price',
        xaxis_rangeslider_visible=True,
        template='plotly_white',
        height=1000,
        xaxis=dict(
            range=[start, end + padding]
        )
    )


    return fig