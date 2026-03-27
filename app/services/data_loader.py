import streamlit as st
from services.snowflake_service import (
    read_price_supertrend,
    read_halvings,
    read_whale_inflow,
)


@st.cache_data(ttl=3600, show_spinner="Loading BTC market data...")
def get_price_data(timeframe):
    return read_price_supertrend(timeframe)


@st.cache_data(show_spinner="Loading halving history...")
def get_halvings_data():
    return read_halvings()


@st.cache_data(ttl=3600, show_spinner="Fetching whale inflow...")
def get_whale_inflow_data():
    return read_whale_inflow()
