{% macro create_latest_version_view() %}

    {% if model.get('version') and model.get('version') == model.get('latest_version') %}

        {% set new_relation = this.incorporate(path={"identifier": model['name']}) %}

        {% set existing_relation = load_relation(new_relation) %}

        {% if existing_relation and not existing_relation.is_view %}
            {{ drop_relation_if_exists(existing_relation) }}
        {% endif %}
        
        {% set create_view_sql -%}
            create or replace view {{ new_relation }}
              as select * from {{ this }}
        {%- endset %}
        
        {% do log("Creating view " ~ new_relation ~ " pointing to " ~ this, info = true) if execute %}
        
        {{ return(create_view_sql) }}
        
    {% else %}
    
        select 1 as id
    
    {% endif %}

{% endmacro %}