import streamlit as st
from pathlib import Path
from dotenv import load_dotenv
from utils.load_css import load_css
from services.data_loader import (
    get_price_data,
    get_halvings_data,
    get_whale_inflow_data,
)
from logic.market_summary import calculate_market_summary
from components.strategy_simulator import (
    get_selected_backtest_trades,
    render_strategy_simulator,
)
from charts import build_whale_inflow_monitor
from charts.lightweight_price_chart import CHART_TITLE, render_lightweight_price_chart
from components.dashboard_sections import (
    render_market_summary
)

st.set_page_config(
    page_title='BIT — Bitcoin Investing Tool',
    page_icon=str(Path(__file__).resolve().parents[1] / 'assets' / 'brand' / 'icon.png'),
    layout='wide',
)

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_css('../styles/main.css')


st.markdown("""
<h1 class="bit-title">
    BIT <span class="bit-dash">——</span> Bitcoin Investing Tool
</h1>

<style>
.bit-title {
    font-size: 2.5rem;
    font-weight: 700;
}

.bit-dash {
    background: linear-gradient(90deg, #e4474d, #159b87);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
</style>
""", unsafe_allow_html=True)


col_1, col_2, col_3 = st.columns([4, 0.2, 0.8])
if st.session_state.get('chart_timeframe') not in {'1W', '1D'}:
    st.session_state['chart_timeframe'] = '1W'
with col_1:
    timeframe_col, title_col, pi_cycle_col = st.columns([1.5, 3, 1.5])
    with timeframe_col:
        timeframe = st.segmented_control(
            label='Timeframe',
            options=['1W', '1D'],
            key='chart_timeframe',
        )
    with title_col:
        st.markdown(
            f'<div style="padding-top:31px;text-align:center;font-family:Archivo,Arial,sans-serif;font-size:19px;font-weight:700;line-height:22px;">{CHART_TITLE}</div>',
            unsafe_allow_html=True,
        )
    with pi_cycle_col:
        show_pi_cycle = st.toggle(
            'Pi Cycle Top Indicator',
            key='show_pi_cycle_top',
            help='Overlay the 111-day SMA and twice the 350-day SMA, calculated from daily closes.',
        )

price_df = get_price_data(timeframe)
halvings_df = get_halvings_data()
whales_df = get_whale_inflow_data()

whale_fig = build_whale_inflow_monitor(whales_df)
summary = calculate_market_summary(price_df)

backtest_trades = get_selected_backtest_trades(price_df, timeframe)
pi_cycle_df = None
if show_pi_cycle:
    pi_cycle_df = price_df if timeframe == '1D' else get_price_data('1D')

with col_1:
    render_lightweight_price_chart(price_df, halvings_df, backtest_trades, pi_cycle_df)
    render_strategy_simulator(price_df, timeframe)

with col_2:
    st.write('')

with col_3:
    st.markdown(
        "<div class='whale-monitor-heading'>"
        "<h3>BTC Whale Inflow Monitor</h3>"
        '</div>',
        unsafe_allow_html=True,
    )

    st.metric('Whale addresses (>10 BTC inflow)', len(whales_df))
    st.metric('Total BTC inflow', f'{whales_df['total_output_value'].sum():,.2f}')
    st.metric('Avg inflow / address', f'{whales_df['total_output_value'].mean():,.2f}')

    st.markdown(
        "<div class='whale-top-inflows-heading'>"
        "<h4>Top Whale Inflows (daily)</h4>"
        '</div>',
        unsafe_allow_html=True
    )

    st.plotly_chart(whale_fig, use_container_width=True, key='whale_inflow_plot')


st.markdown('---')

render_market_summary(summary)

st.markdown(
    '''
        <div class='footer'>
            © 2026 Michał Owsiak | BIT
        </div>
    ''',
    unsafe_allow_html=True
)
