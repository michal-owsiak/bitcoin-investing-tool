{{
    config(
        materialized='incremental',
        incremental_strategy='append'
    )
}}

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
    ingested_at
from 
    {{ source('binance', 'binance_btcusdt_1d') }}

{% if is_incremental() %}

    where open_time > (
        select max(open_time)
        from {{ this }}
    )

{% endif %}

