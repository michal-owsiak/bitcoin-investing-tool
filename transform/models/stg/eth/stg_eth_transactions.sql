{{ 
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='hash_key'
    ) 
}}

select
    src.payload:hash::varchar as hash_key,
    src.payload:block_number::number as block_number,
    src.payload:block_timestamp::timestamp_ntz as block_timestamp,
    src.payload:to_address::varchar as to_address,
    src.payload:value::float as value_wei
from 
    {{ source('eth', 'transactions_raw') }} src

{% if is_incremental() %}

    where src.payload:block_timestamp::timestamp_ntz > (
        select max(block_timestamp)
        from {{ this }}
    )

{% endif %}
