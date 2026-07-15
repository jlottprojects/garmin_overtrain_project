with raw_source as (
    select 
        parse_json(raw_json) as clean_json
    from {{ source('garmin_raw', 'src_garmin_overtrain_metrics') }}
),

daily_metrics as (
    select
        
        (clean_json:data:user_summary:calendarDate)::date as source_date,
        (clean_json:data:user_summary:userProfileId)::numeric as user_profile_id,
        (clean_json:data:user_summary:userDailySummaryId)::numeric as user_daily_summary_id,
        (clean_json:data:user_summary:restingHeartRate)::integer as resting_heart_rate,
        (clean_json:data:user_summary:minHeartRate)::integer as min_heart_rate,
        (clean_json:data:user_summary:maxHeartRate)::integer as max_heart_rate,
        (clean_json:data:user_summary:averageStressLevel)::integer as avg_stress_level,
        ((clean_json:data:user_summary:restStressDuration)::numeric / 60) as rest_stress_duration_minutes,
        ((clean_json:data:user_summary:activityStressDuration)::numeric / 60) as activity_stress_duration_minutes,
        (clean_json:data:user_summary:bodyBatteryChargedValue)::integer as body_battery_charged,
        (clean_json:data:user_summary:bodyBatteryDrainedValue)::integer as body_battery_drained,
        (clean_json:data:user_summary:activeKilocalories)::numeric as active_calories,
        (clean_json:data:user_summary:bmrKilocalories)::numeric as bmr_calories,
        (clean_json:data:user_summary:totalSteps)::integer as total_steps
        
    from raw_source
)

select * from daily_metrics