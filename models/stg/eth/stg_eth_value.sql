{{config(
    materialized='view'
)}}

select 
    hash_key,
    block_number,
    block_timestamp,
    to_address,
    value_wei / 1e18 as value_eth
from {{ ref('stg_eth_base') }}
