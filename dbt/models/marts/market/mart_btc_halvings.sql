{{
    config(
        materialized='table'
    )
}}

with min_historical_data as (

    select 
        min(open_time) as min_open_time
    from 
        {{ ref('mart_btc_price_supertrend_1d') }}

)

select
    halving_number,
    halving_date,
    btc_from,
    btc_to,
    is_historical,
    is_projected
from 
    {{ ref('stg_btc_halvings') }}
where 
    halving_date > (
        select min_open_time
        from min_historical_data
    )
