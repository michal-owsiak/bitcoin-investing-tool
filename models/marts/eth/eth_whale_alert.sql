with whales as (
    
    select
        to_address,
        sum(value_eth) as total_sent,
        count(*) as transaction_count
    from {{ ref('stg_eth_value') }}
    where value_eth >= 100
    group by to_address

)

select 
    to_address,
    total_sent,
    transaction_count
from whales 
order by total_sent desc
