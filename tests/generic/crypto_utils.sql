{% test assert_valid_btc_address(model, column_name) %}

    select *
    from {{ model }}
    where not (
    
        {{ column_name }} like '1%' or
        {{ column_name }} like '3%' or
        {{ column_name }} like 'bc1%'

    )

{% endtest %}
