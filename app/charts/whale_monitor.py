import pandas as pd
import plotly.graph_objects as go


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
                color='#23a88e'
            ),
            text=[f'{x/1000:.1f}k' for x in df['total_output_value']],
            textposition='inside',
            insidetextanchor='middle',
            customdata=df[['transaction_count']],
            hovertemplate=(
                'BTC Inflow: %{x:,.4f}<br>'
                'Transactions: %{customdata[0]}'
                '<extra></extra>'
            )
        )
    )

    fig.update_layout(
        xaxis_title='Inflow (BTC)',
        yaxis_title='',
        height=400,
        font=dict(
            family='Archivo',
            size=12
        ),
        margin=dict(l=0, r=50, t=0, b=50),
        yaxis=dict(
            automargin=True
        ),
        bargap=0.3,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
    )

    fig.update_xaxes(
        showgrid=True,
        gridwidth=1,
        griddash="dot",
        gridcolor="rgba(120, 120, 120, 0.3)"
    )

    return fig