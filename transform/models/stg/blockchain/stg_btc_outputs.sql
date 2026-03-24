{{
    config(
        materialized='incremental',
        incremental_strategy='append'
    )
}}

with flattened_outputs as (

    select
        stg.hash_key,
        stg.block_number,
        stg.block_timestamp,
        stg.is_coinbase,
        f.value:address::string as output_address,
        f.value:value::float as output_value
    from {{ ref('stg_btc_transactions') }} stg, 
        lateral flatten(input => stg.outputs) f
    where 
        f.value:address is not null

    {% if is_incremental() %}

        and stg.block_timestamp > (
            select max(block_timestamp)
            from {{ this }}
        )

    {% endif %}
)

select 
    hash_key,
    block_number,
    block_timestamp,
    is_coinbase,
    output_address,
    output_value
from flattened_outputs