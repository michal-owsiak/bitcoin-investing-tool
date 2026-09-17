{{ 
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key='HASH_KEY'
    ) 
}}


with source_data as (
    select *
    from {{ source('blockchain', 'transactions') }}

    {% if is_incremental() %}

        where block_timestamp > (
            select max(block_timestamp)
            from {{ this }}
        )

    {% endif %}
),

deduplicated_data as (
    select *
    from source_data
    qualify row_number() over (
        partition by hash_key 
        order by block_timestamp desc
    ) = 1
)

select *
from deduplicated_data
