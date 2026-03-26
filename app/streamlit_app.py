import streamlit as st
import pandas as pd
from services.snowflake_service import read_price_supertrend, read_halvings, read_whale_inflow
from charts import build_price_supertrend_chart, build_whale_inflow_monitor
from utils import load_css


load_css('styles/main.css')
st.set_page_config(page_title='Bitcoin Investing Tool', layout='wide')


@st.cache_data(ttl=3600, show_spinner='Loading BTC market data...')
def get_price_data(timeframe):
    return read_price_supertrend(timeframe)

@st.cache_data(show_spinner='Loading halving history...')
def get_halvings_data():
    return read_halvings()

@st.cache_data(ttl=3600, show_spinner='Fetching whale inflow..')
def get_whale_inflow_data():
    return read_whale_inflow()


def calculate_market_summary(price_df):
    df = price_df.copy()

    date_col = 'OPEN_TIME'
    close_col = 'CLOSE'
    supertrend_col = 'SUPERTREND_VALUE'
    trend_col = 'TREND_DIRECTION'

    df[date_col] = pd.to_datetime(df[date_col])
    df[close_col] = pd.to_numeric(df[close_col], errors='coerce')
    df[supertrend_col] = pd.to_numeric(df[supertrend_col], errors='coerce')

    df['flip'] = None
    df.loc[df['SIGNAL_FLIP_UP'] == True, 'flip'] = 'Bullish'
    df.loc[df['SIGNAL_FLIP_DOWN'] == True, 'flip'] = 'Bearish'

    df = df.sort_values(date_col).reset_index(drop=True)

    latest = df.iloc[-1]

    current_date = latest[date_col]
    current_price = latest[close_col]
    current_supertrend = latest[supertrend_col]
    current_trend = latest[trend_col]

    flips_df = df[df['flip'].notna()]

    if flips_df.empty:
        return {
            'current_trend': current_trend,
            'last_flip_type': None,
            'last_flip_date': None,
            'days_since_flip': None,
            'return_since_flip': None,
            'distance_to_supertrend_pct': None,
            'entry_price': None,
            'current_price': current_price
        }

    last_flip = flips_df.iloc[-1]

    last_flip_date = last_flip[date_col]
    last_flip_type = last_flip['flip']
    entry_price = last_flip[close_col]

    days_since_flip = (pd.Timestamp.now().normalize() - last_flip_date).days

    return_since_flip = ((current_price / entry_price) - 1) * 100

    distance_to_supertrend_pct = (
        ((current_price - current_supertrend) / current_supertrend) * 100
        if current_supertrend != 0 else None
    )

    return {
        'current_trend': current_trend,
        'last_flip_type': last_flip_type,
        'last_flip_date': last_flip_date,
        'days_since_flip': days_since_flip,
        'return_since_flip': return_since_flip,
        'distance_to_supertrend_pct': distance_to_supertrend_pct,
        'entry_price': entry_price,
        'current_price': current_price
    }


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

    st.plotly_chart(whale_fig, use_container_width=True)


st.markdown('---')

bottom_col_1, bottom_col_2, bottom_col_3 = st.columns([1, 1, 0.5])

with bottom_col_1:
    st.subheader('Market Status')

    trend_raw = str(summary['current_trend']).lower()

    if trend_raw == 'bullish':
        trend_text = 'BULLISH'
        trend_color = '#23a88e'
    elif trend_raw == 'bearish':
        trend_text = 'BEARISH'
        trend_color = '#f14c4a'
    else:
        trend_text = trend_raw.upper()
        trend_color = '#999999'

    st.markdown(f'''
        <div style='font-size:12px; color:##23a88e;'>Trend</div>
        <div style='font-size:20px; font-weight:600; color:{trend_color};'>
            {trend_text}
        </div>
    ''', unsafe_allow_html=True)


    if summary['last_flip_date'] is not None:
        st.write('')
        st.markdown(f'''
            <div style='font-size:13px; color:#3a3a3a; line-height:1.4;'>
                Last flip date: <strong>{summary['last_flip_date'].date()}</strong>
            </div>
            <div style='font-size:13px; color:#3a3a3a; line-height:1.4;'>
                Days since flip: <strong>{summary['days_since_flip']}</strong>
            </div>
        ''', unsafe_allow_html=True)
    else:
        st.write('Last flip date: **N/A**')
        st.write('Days since flip: **N/A**')

with bottom_col_2:
    st.subheader('Since Last Flip')

    if summary['return_since_flip'] is not None:
        ret = summary['return_since_flip']

        if ret is not None:
            ret_color = '#23a88e' if ret >= 0 else '#f14c4a'

            st.markdown(f'''
            <div style='font-size:12px; color:##23a88e;'>Return</div>
            <div style='font-size:20px; font-weight:600; color:{ret_color};'>
                {ret:.2f}%
            </div>
            ''', unsafe_allow_html=True)
        else:
            st.write('Return: N/A')
    else:
        st.metric('Return', 'N/A')
    
    st.write('')
    st.markdown(f'''
    <div style='font-size:13px; color:#3a3a3a; line-height:1.4;'>
        Entry price: <strong>{summary['entry_price']:,.2f}</strong>
    </div>
    <div style='font-size:13px; color:#3a3a3a; line-height:1.4;'>
        Current price: <strong>{summary['current_price']:,.2f}</strong>
    </div>
    ''', unsafe_allow_html=True)

with bottom_col_3:
    st.subheader('Market Stretch')

    dist = summary['distance_to_supertrend_pct']

    if dist is not None:
        dist_color = '#23a88e' if dist >= 0 else '#f14c4a'

        st.markdown(f'''
            <div style='font-size:12px; color:#6b7280;'>Distance to Supertrend</div>
            <div style='font-size:20px; font-weight:600; color:{dist_color};'>
                {dist:.2f}%
            </div>
        ''', unsafe_allow_html=True)

        st.write('')

        abs_dist = abs(dist)
        if abs_dist > 15:
            st.warning('⚠️ Market extended')
        elif abs_dist > 8:
            st.info('Moderately extended')
        else:
            st.success('Healthy range')
    else:
        st.write('Distance to Supertrend: N/A')


st.markdown(
    '''
        <div class='footer'>
            © 2026 Michał Owsiak - Bitcoin Investing Tool
        </div>
    ''',
    unsafe_allow_html=True
)
