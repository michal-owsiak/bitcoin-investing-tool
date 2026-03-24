import streamlit as st
from client_snowflake import read_price_supertrend, read_halvings
from charts import build_price_supertrend_chart


st.set_page_config(page_title='Bitcoin Investing Tool', layout='wide')

st.markdown(
    '''
    <style>

    @import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&display=swap');

    html, body, [data-testid='stAppViewContainer'], [data-testid='stSidebar'], 
    [data-testid='stMarkdownContainer'],
    [data-testid='stText'] {
        font-family: 'Geist', sans-serif !important;
    }

    *:not(i):not(svg) {
        font-family: 'Geist', sans-serif !important;
    }

    .block-container {
        padding-top: 2rem !important;
    }
    
    section[data-testid='stSidebar'] {
        width: 200px !important;
    }

    section[data-testid='stSidebar'] > div {
        width: 200px !important;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        height: 100vh;
    }

    section[data-testid='stSidebar'] div[data-testid='stRadio'] > label p {
        font-size: 24px !important;
        font-weight: 700 !important;
        text-align: center;
    }

    section[data-testid='stSidebar'] div[role='radiogroup'] {
        display: flex;
        flex-direction: column;
        align-items: center;
    }

    section[data-testid='stSidebar'] div[role='radiogroup'] label p {
        font-size: 18px;
        text-align: center;
    }

    </style>
    ''',
    unsafe_allow_html=True
)

@st.cache_data(ttl=3600)
def get_price_data(timeframe):
    return read_price_supertrend(timeframe)


@st.cache_data
def get_halvings_data():
    return read_halvings()


st.title('Bitcoin Investing Tool')

timeframe = st.sidebar.radio(
    'Timeframe',
    options=['1W', '1D'],
    index=0
)

price_df = get_price_data(timeframe)
halvings_df = get_halvings_data()

fig = build_price_supertrend_chart(price_df, halvings_df)

st.plotly_chart(fig, use_container_width=True)


st.markdown(
    '''
    <style>
    .footer {
        position: fixed;
        bottom: 10px;
        left: 0;
        width: 100%;
        text-align: center;
        font-size: 12px;
        color: #9aa0a6;
        opacity: 0.7;
        pointer-events: none;
    }
    </style>

    <div class='footer'>
        © 2026 Michał Owsiak - Bitcoin Investing Tool
    </div>
    ''',
    unsafe_allow_html=True
)