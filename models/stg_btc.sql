{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='HASH_KEY'
) }}

select *
from {{ source('btc', 'btc') }}

{% if is_incremental() %}

where BLOCK_TIMESTAMP >= (
    select max(BLOCK_TIMESTAMP)
    from {{ this }}
)

{% endif %}
