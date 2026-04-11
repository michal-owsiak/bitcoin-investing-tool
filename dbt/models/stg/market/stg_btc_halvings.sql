{{
    config(
        materialized='view'
    )
}}

select
    cast(nr as int) as halving_number,
    cast(date as date) as halving_date,
    cast(btc_from as float) as btc_from,
    cast(btc_to as float) as btc_to,
    cast(historical as boolean) as is_historical,
    cast(projected as boolean) as is_projected 
from 
    {{ ref('btc_halvings') }}

    