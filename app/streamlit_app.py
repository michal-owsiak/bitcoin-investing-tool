import streamlit as st
from client_snowflake import read_price_supertrend, read_halvings
from charts import build_price_supertrend_chart


st.set_page_config(page_title='Bitcoin Investing Tool', layout='wide')

st.markdown(
    '''
    <style>
    section[data-testid='stSidebar'] {
        width: 200px !important;
    }

    section[data-testid='stSidebar'] > div {
        width: 200px !important;
        display: flex;
        flex-direction: column;
        justify-content: center;   /* pion */
        align-items: center;       /* poziom */
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
        font-size: 18px !important;
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
