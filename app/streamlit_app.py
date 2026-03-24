import streamlit as st
from client_snowflake import read_price_supertrend, read_halvings


st.set_page_config(page_title="BTC Investing Tool", layout="wide")

st.title("BTC Investing Tool")

interval = st.sidebar.selectbox(
    "Interval",
    options=["1D", "1W"],
    index=0
)

price_df = read_price_supertrend(interval=interval, limit=500)
halvings_df = read_halvings()

st.subheader("Price data preview")
st.dataframe(price_df, use_container_width=True)

st.subheader("Halvings preview")
st.dataframe(halvings_df, use_container_width=True)
