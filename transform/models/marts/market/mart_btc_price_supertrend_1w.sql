{{
    config(
        materialized='table'
    )
}}

with base as (

    select
        symbol,
        interval,
        open_time,
        close_time,
        open,
        high,
        low,
        close,
        volume,
        number_of_trades,
        supertrend_value,
        trend_direction,
        lag(trend_direction) over (
            partition by symbol, interval
            order by open_time
        ) as prev_trend_direction
    from 
        {{ ref('int_btc_supertrend_1w') }}

)

select
    symbol,
    interval,
    open_time,
    close_time,
    open,
    high,
    low,
    close,
    volume,
    number_of_trades,
    supertrend_value,
    trend_direction,
    case
        when trend_direction = 'Bullish' then true
        else false
    end as is_bull_trend,
    case
        when trend_direction = 'Bearish' then true
        else false
    end as is_bear_trend,
    case
        when prev_trend_direction = 'Bearish'
            and trend_direction = 'Bullish'
        then true
        else false
    end as signal_flip_up,
    case
        when prev_trend_direction = 'Bullish'
            and trend_direction = 'Bearish'
        then true
        else false
    end as signal_flip_down
from 
    base
order by 
    open_time desc