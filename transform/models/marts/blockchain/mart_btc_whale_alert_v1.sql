with whales as (

    select
        output_address,
        sum(output_value) as total_sent,
        count(*) as transaction_count
    from {{ ref('stg_btc_non_coinbase_transactions') }}
    where output_value > 10
    group by output_address

)

select
    w.output_address,
    w.total_sent,
    w.transaction_count,
    {{ convert_to_usd('w.total_sent') }} as current_value_usd
from whales w
order by w.total_sent desc