import streamlit as st

def render_market_summary(summary):
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
            <div style='font-size:12px;'>Trend</div>
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
                <div style='font-size:12px'>Return</div>
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