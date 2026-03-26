import pandas as pd
import plotly.graph_objects as go
import datetime as dt
from .helpers import add_supertrend_fill_segments


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
        go.Bar(
            x=price_df['OPEN_TIME'],
            y=price_df['VOLUME'],
            name='Volume',
            yaxis='y2',
            opacity=0.22,
            marker=dict(
                color='#94a3b8'
            ),
            hovertemplate=(
                'Date: %{x|%Y-%m-%d}<br>'
                'Volume: %{y:,.2f}'
                '<extra></extra>'
            )
        )
    )

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

    add_supertrend_fill_segments(
        fig=fig,
        price_df=price_df,
        trend_col='IS_BULL_TREND',
        line_color='green',
        fill_color='rgba(0, 180, 0, 0.10)',
        trace_name='Bullish Supertrend'
    )

    add_supertrend_fill_segments(
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
        height=800,
        xaxis=dict(
            range=[start, end + padding]
        ),
        yaxis=dict(
            range=[y_min, y_max + (y_range * 0.18)]
        ),
        yaxis2=dict(
            title='Volume',
            overlaying='y',
            side='right',
            showgrid=False
        ),
        hoverlabel=dict(
            font_size=13,
            font_family='Geist'
        ),
        barmode='overlay'
    )

    return fig
