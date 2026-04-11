with last_24_hrs as (

    select 
        output_address,
        block_timestamp,
        output_value
    from 
        {{ ref('stg_btc_non_coinbase_transactions') }}
    where 
        block_timestamp > dateadd(hour, -24, current_timestamp())

),

whales as (

    select
        output_address,
        sum(output_value) as total_output_value,
        count(*) as transaction_count
    from 
        last_24_hrs
    group by 
        output_address
    having
        sum(output_value) > 10
)

select
    output_address,
    total_output_value,
    transaction_count
from whales
order by total_output_value desc
