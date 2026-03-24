{% macro build_supertrend(source_relation, interval_label, atr_period=10, multiplier=3) %}

    with base as (

        select
            symbol,
            '{{ interval_label }}' as interval,
            open_time,
            close_time,
            open,
            high,
            low,
            close,
            volume,
            number_of_trades,
            ingested_at,
            lag(close) over (
                partition by symbol
                order by open_time
            ) as prev_close
        from 
            {{ source_relation }}

    ),

    tr_calc as (

        select
            *,
            greatest(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            ) as tr
        from base

    ),

    atr_calc as (

        select
            *,
            avg(tr) over (
                partition by symbol
                order by open_time
                rows between {{ atr_period - 1 }} preceding and current row
            ) as atr,
            (high + low) / 2 as hl2
        from tr_calc

    ),

    bands as (

        select
            *,
            hl2 + ({{ multiplier }} * atr) as basic_upper_band,
            hl2 - ({{ multiplier }} * atr) as basic_lower_band,
            row_number() over (
                partition by symbol
                order by open_time
            ) as rn
        from atr_calc
        where atr is not null

    ),

    recursive_st as (

        select
            symbol,
            interval,
            open_time,
            close_time,
            open,
            high,
            low,
            close,
            volume,
            number_of_trades,
            ingested_at,
            prev_close,
            tr,
            atr,
            hl2,
            basic_upper_band,
            basic_lower_band,
            basic_upper_band as final_upper_band,
            basic_lower_band as final_lower_band,
            basic_lower_band as supertrend_value,
            'Bullish' as trend_direction,
            rn
        from bands
        where rn = 1

        union all

        select
            b.symbol,
            b.interval,
            b.open_time,
            b.close_time,
            b.open,
            b.high,
            b.low,
            b.close,
            b.volume,
            b.number_of_trades,
            b.ingested_at,
            b.prev_close,
            b.tr,
            b.atr,
            b.hl2,
            b.basic_upper_band,
            b.basic_lower_band,

            case
                when b.basic_upper_band < r.final_upper_band
                    or r.close > r.final_upper_band
                then b.basic_upper_band
                else r.final_upper_band
            end as final_upper_band,

            case
                when b.basic_lower_band > r.final_lower_band
                    or r.close < r.final_lower_band
                then b.basic_lower_band
                else r.final_lower_band
            end as final_lower_band,

            case
                when r.supertrend_value = r.final_upper_band
                    and b.close <= (
                        case
                            when b.basic_upper_band < r.final_upper_band
                                or r.close > r.final_upper_band
                            then b.basic_upper_band
                            else r.final_upper_band
                        end
                    )
                then (
                    case
                        when b.basic_upper_band < r.final_upper_band
                            or r.close > r.final_upper_band
                        then b.basic_upper_band
                        else r.final_upper_band
                    end
                )

                when r.supertrend_value = r.final_upper_band
                    and b.close > (
                        case
                            when b.basic_upper_band < r.final_upper_band
                                or r.close > r.final_upper_band
                            then b.basic_upper_band
                            else r.final_upper_band
                        end
                    )
                then (
                    case
                        when b.basic_lower_band > r.final_lower_band
                            or r.close < r.final_lower_band
                        then b.basic_lower_band
                        else r.final_lower_band
                    end
                )

                when r.supertrend_value = r.final_lower_band
                    and b.close >= (
                        case
                            when b.basic_lower_band > r.final_lower_band
                                or r.close < r.final_lower_band
                            then b.basic_lower_band
                            else r.final_lower_band
                        end
                    )
                then (
                    case
                        when b.basic_lower_band > r.final_lower_band
                            or r.close < r.final_lower_band
                        then b.basic_lower_band
                        else r.final_lower_band
                    end
                )

                else (
                    case
                        when b.basic_upper_band < r.final_upper_band
                            or r.close > r.final_upper_band
                        then b.basic_upper_band
                        else r.final_upper_band
                    end
                )
            end as supertrend_value,

            case
                when r.supertrend_value = r.final_upper_band
                    and b.close > (
                        case
                            when b.basic_upper_band < r.final_upper_band
                                or r.close > r.final_upper_band
                            then b.basic_upper_band
                            else r.final_upper_band
                        end
                    )
                then 'Bullish'

                when r.supertrend_value = r.final_lower_band
                    and b.close < (
                        case
                            when b.basic_lower_band > r.final_lower_band
                                or r.close < r.final_lower_band
                            then b.basic_lower_band
                            else r.final_lower_band
                        end
                    )
                then 'Bearish'

                else r.trend_direction
            end as trend_direction,

            b.rn
        from bands b
        join recursive_st r
            on b.symbol = r.symbol
        and b.rn = r.rn + 1

    )

    select
        symbol,
        interval,
        open_time,
        close_time,
        open,
        high,
        low,
        close,
        volume,
        number_of_trades,
        ingested_at,
        tr,
        atr,
        basic_upper_band,
        basic_lower_band,
        final_upper_band,
        final_lower_band,
        supertrend_value,
        trend_direction
    from 
        recursive_st
    order by 
        open_time desc

{% endmacro %}