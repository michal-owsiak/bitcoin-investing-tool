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
from charts import build_price_supertrend_chart, build_whale_inflow_monitor
from components.dashboard_sections import (
    render_market_summary
)

st.set_page_config(page_title='Bitcoin Investing Tool', layout='wide')

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_css('../styles/main.css')


header_col_1, header_col_2 = st.columns([5, 1.7])

with header_col_1:
    st.title('Bitcoin Investing Tool')

with header_col_2:
    timeframe = st.segmented_control(
        label="",
        options=['1W', '1D'],
        default='1W'
    )

price_df = get_price_data(timeframe)
halvings_df = get_halvings_data()
whales_df = get_whale_inflow_data()

price_fig = build_price_supertrend_chart(price_df, halvings_df)
whale_fig = build_whale_inflow_monitor(whales_df)
summary = calculate_market_summary(price_df)


col_1, col_2, col_3 = st.columns([4, 0.2, 0.8])

with col_1:
    st.plotly_chart(price_fig, use_container_width=True)

with col_2:
    st.write('')

with col_3:
    st.subheader('BTC Whale Inflow Monitor (24h)')

    st.metric('Whale addresses (>10 BTC inflow)', len(whales_df))
    st.metric('Total BTC inflow', f'{whales_df['total_output_value'].sum():,.2f}')
    st.metric('Avg inflow / address', f'{whales_df['total_output_value'].mean():,.2f}')

    st.markdown(
        '''
            <h4 style>
                Top Whale Inflows
            </h4>    
        ''',
        unsafe_allow_html=True
    )

    st.plotly_chart(whale_fig, use_container_width=True)


st.markdown('---')

render_market_summary(summary)

st.markdown(
    '''
        <div class='footer'>
            © 2026 Michał Owsiak - Bitcoin Investing Tool
            <br/>
            <br/>
        </div>
    ''',
    unsafe_allow_html=True
)
