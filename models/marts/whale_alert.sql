select
    output_address,
    sum(output_value) as total_sent,
    count(*) as transaction_count
from {{ ref('stg_btc_transactions') }}
where output_value > 10
group by output_address
order by total_sent desc