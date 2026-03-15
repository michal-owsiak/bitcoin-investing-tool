{{config(
    materialized='ephemeral'
) }}

select *
from 
    {{ ref('stg_btc_outputs') }}
where
    is_coinbase = false