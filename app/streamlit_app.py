import streamlit as st
from client_snowflake import read_price_supertrend, read_halvings, read_whale_inflow
from charts import build_price_supertrend_chart, build_whale_inflow_monitor
from utils import load_css


load_css('styles/main.css')
st.set_page_config(page_title='Bitcoin Investing Tool', layout='wide')


@st.cache_data(ttl=3600)
def get_price_data(timeframe):
    return read_price_supertrend(timeframe)

@st.cache_data
def get_halvings_data():
    return read_halvings()

@st.cache_data(ttl=3600)
def get_whale_inflow_data():
    return read_whale_inflow()


st.title('Bitcoin Investing Tool')

timeframe = st.sidebar.radio(
    'Timeframe',
    options=['1W', '1D'],
    index=0
)

price_df = get_price_data(timeframe)
halvings_df = get_halvings_data()
whales_df = get_whale_inflow_data()

price_fig = build_price_supertrend_chart(price_df, halvings_df)
whale_fig = build_whale_inflow_monitor(whales_df)


col_1, col_2, col_3 = st.columns([4, 0.2, 0.8])

with col_1:
    st.plotly_chart(price_fig, use_container_width=True)

with col_2:
    st.write('')

with col_3:
    st.subheader('BTC Whale Inflow Monitor (24h)')

    st.metric('Whale addresses (> 10 BTC inflow)', len(whales_df))
    st.metric('Total BTC inflow', f"{whales_df['total_output_value'].sum():,.2f}")
    st.metric('Avg inflow / address', f"{whales_df['total_output_value'].mean():,.2f}")

    st.plotly_chart(whale_fig, use_container_width=True)


st.markdown(
    '''
        <div class='footer'>
            © 2026 Michał Owsiak - Bitcoin Investing Tool
        </div>
    ''',
    unsafe_allow_html=True
)
