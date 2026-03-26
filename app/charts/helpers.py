import pandas as pd
import plotly.graph_objects as go


def add_supertrend_fill_segments(
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
