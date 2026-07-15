{{ config(
    materialized='table'
) }}

with staging_summary as (
    select * from {{ ref('stg_garmin__user_metrics') }}
),

staging_activities as (
    select * from {{ ref('stg_garmin__activities') }}
),

daily_activity_aggregates as (
    select
        user_daily_summary_id,
        date_of_activity,
        count(activity_id) as total_workout_count,
        sum(minutes_of_activity) as total_workout_duration_minutes,
        sum(body_battery_impact) as total_activity_battery_drain,
        listagg(activity_name, ', ') as activities_performed
    from staging_activities
    group by 1, 2
)

select
    s.source_date,
    s.user_daily_summary_id,
    coalesce(a.total_workout_count, 0) as total_workout_count,
    coalesce(a.total_workout_duration_minutes, 0) as total_workout_duration_minutes,
    coalesce(a.total_activity_battery_drain, 0) as total_activity_battery_drain,
    coalesce(a.activities_performed, 'No Workout') as activities_performed,
    s.total_steps,
    s.active_calories,
    s.resting_heart_rate,
    s.avg_stress_level,
    s.body_battery_charged,
    s.body_battery_drained,
    s.rest_stress_duration_minutes,
    (s.body_battery_charged + coalesce(a.total_activity_battery_drain, 0)) as net_daily_energy_balance

from staging_summary s
left join daily_activity_aggregates a 
    on s.user_daily_summary_id = a.user_daily_summary_id