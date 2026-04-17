{{
    config(
        materialized='table'
    )
}}

with daily as (

    select
        *,
        date_trunc('week', open_time) as week_start
    from 
        {{ ref('stg_binance_btcusdt_1d') }}

),

ranked as (

    select
        *,
        row_number() over (
            partition by week_start
            order by open_time asc
        ) as day_of_the_week
    from daily

),

weekly_base as (

    select
        symbol,
        week_start,
        max(high) as high,
        min(low) as low,
        sum(volume) as volume,
        sum(number_of_trades) as number_of_trades,
        max(ingested_at) as ingested_at
    from ranked
    group by symbol, week_start

),

weekly_open as (

    select
        symbol,
        week_start,
        open
    from ranked
    where day_of_the_week = 1

),

weekly_close as (

    select
        symbol,
        week_start,
        close
    from ranked
    where day_of_the_week = 7

)

select
    b.symbol,
    '1w' as interval,
    b.week_start as open_time,
    dateadd(
        millisecond, -1, dateadd(day, 7, b.week_start)
    ) as close_time,
    o.open,
    b.high,
    b.low,
    c.close,
    b.volume,
    b.number_of_trades,
    b.ingested_at
from 
    weekly_base b
    left join weekly_open o
        on b.symbol = o.symbol
        and b.week_start = o.week_start
    left join weekly_close c
        on b.symbol = c.symbol
        and b.week_start = c.week_start
where 
    c.close is not null
order by 
    open_time desc

