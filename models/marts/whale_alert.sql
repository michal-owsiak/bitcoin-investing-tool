with whales as (

    select
        output_address,
        sum(output_value) as total_sent,
        count(*) as transaction_count
    from {{ ref('stg_btc_transactions') }}
    where output_value > 10
    group by output_address

),

latest_price as (

    select
        price
    from {{ ref('btc_usd_max') }}
    where to_date(replace(snapped_at, 'UTC', '')) = current_date()

)

select
    w.output_address,
    w.total_sent,
    w.transaction_count,
    (lp.price * w.total_sent) as current_value_usd
from whales w
cross join latest_price lp
order by w.total_sent desc