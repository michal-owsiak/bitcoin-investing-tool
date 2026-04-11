{{
    config(
        materialized='table'
    )
}}

{{ 
    build_supertrend(
        ref('stg_binance_btcusdt_1d'),
        '1d',
        10,
        3
    ) 
}}
