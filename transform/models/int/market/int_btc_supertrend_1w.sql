{{
    config(
        materialized='table'
    )
}}

{{ 
    build_supertrend(
        ref('int_btc_price_1w'),
        '1w',
        10,
        3
    ) 
}}
