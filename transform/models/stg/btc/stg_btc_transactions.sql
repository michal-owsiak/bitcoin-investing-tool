{{ 
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='HASH_KEY'
    ) 
}}

select *
from {{ source('btc', 'transactions') }}

{% if is_incremental() %}

    where block_timestamp > (
        select max(block_timestamp)
        from {{ this }}
    )

{% endif %}
