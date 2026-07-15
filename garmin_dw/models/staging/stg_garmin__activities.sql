with raw_source as (
    select 
        parse_json(raw_json) as clean_json
    from {{ source('garmin_raw', 'src_garmin_overtrain_metrics') }}
),

flattened_events as (
    select
        (clean_json:data:user_summary:calendarDate)::date as date_of_activity,
        (clean_json:data:user_summary:userDailySummaryId)::numeric as user_daily_summary_id,
        f.value as activity_payload
    from raw_source
    cross join lateral flatten(input => clean_json:data:user_summary:bodyBatteryActivityEventList) f
)

select
    user_daily_summary_id,
    (activity_payload:activityId)::numeric as activity_id,
    (activity_payload:activityName)::string as activity_name,
    (activity_payload:activityType)::string as activity_type,
    (activity_payload:eventType)::string as event_type,
    date_of_activity,
    ((activity_payload:durationInMilliseconds)::numeric / 60000) as minutes_of_activity,
    (activity_payload:bodyBatteryImpact)::integer as body_battery_impact,
    (activity_payload:shortFeedback)::string as performance_feedback
from flattened_events
where event_type = 'ACTIVITY'