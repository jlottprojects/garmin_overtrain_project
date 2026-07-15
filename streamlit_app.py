import streamlit as st
import snowflake.connector
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="Garmin Strain & Recovery Tracker", page_icon="🏋️‍♂️", layout="wide"
)

# Title & Description
st.title("🏋️‍♂️ Garmin Health & Recovery Analytics")
st.markdown("""
    This dashboard analyzes the relationship between **Workout Strain (Inputs)** 
    and **Autonomic Recovery (Outputs)** by pulling processed data directly from your Snowflake Data Warehouse.
""")


@st.cache_resource
def init_connection():
    return snowflake.connector.connect(**st.secrets["snowflake"])


try:
    conn = init_connection()
except Exception as e:
    st.error(
        f"Failed to connect to Snowflake. Check your secrets.toml file. Error: {e}"
    )
    st.stop()


@st.cache_data(ttl=600)  # Cache data for 10 minutes to avoid redundant Snowflake costs
def get_fact_data():
    query = """
        SELECT 
            source_date as calendar_date,
            user_daily_summary_id,
            total_workout_count,
            total_workout_duration_minutes,
            total_activity_battery_drain,
            activities_performed,
            total_steps,
            active_calories,
            resting_heart_rate,
            avg_stress_level,
            body_battery_charged,
            body_battery_drained,
            rest_stress_duration_minutes,
            net_daily_energy_balance
        FROM GARMIN_PROJECT.DEV.FCT_DAILY_TRAINING_REDINESS
        ORDER BY source_date DESC;
    """
    df = pd.read_sql(query, conn)

    df["CALENDAR_DATE"] = pd.to_datetime(df["CALENDAR_DATE"])
    return df


with st.spinner("Fetching data from Snowflake..."):
    df = get_fact_data()

st.sidebar.header("Dashboard Filters")
days_to_show = st.sidebar.slider(
    "Days to look back", min_value=7, max_value=90, value=30
)
df_filtered = df.head(days_to_show)

st.subheader("Latest Biometrics & Strain Summary")
latest_day = df.iloc[0]

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
with kpi1:
    st.metric(
        label="Resting Heart Rate",
        value=f"{int(latest_day['RESTING_HEART_RATE'])} bpm",
        delta="Lower is better",
        delta_color="inverse",
    )
with kpi2:
    st.metric(
        label="Avg Daily Stress", value=f"{int(latest_day['AVG_STRESS_LEVEL'])}/100"
    )
with kpi3:
    st.metric(
        label="Net Energy Balance",
        value=f"{int(latest_day['NET_DAILY_ENERGY_BALANCE'])} pts",
        delta="Target > 50",
    )
with kpi4:
    st.metric(
        label="Today's Workout Duration",
        value=f"{int(latest_day['TOTAL_WORKOUT_DURATION_MINUTES'])} min",
        delta=latest_day["ACTIVITIES_PERFORMED"],
    )

st.divider()

col1, col2 = st.columns(2)

with col1:
    st.subheader("📈 Workout Volume vs. Next-Day Resting Heart Rate")
    st.markdown("Are heavy training days driving up your morning RHR?")

    fig_rhr = px.scatter(
        df_filtered,
        x="TOTAL_WORKOUT_DURATION_MINUTES",
        y="RESTING_HEART_RATE",
        size="TOTAL_STEPS",
        hover_data=["ACTIVITIES_PERFORMED"],
        trendline="ols",
        labels={
            "TOTAL_WORKOUT_DURATION_MINUTES": "Workout Duration (Minutes)",
            "RESTING_HEART_RATE": "Resting Heart Rate (BPM)",
        },
        color_discrete_sequence=["#FF4B4B"],
    )
    st.plotly_chart(fig_rhr, use_container_width=True)

with col2:
    st.subheader("🔋 Daily Net Energy Balance")
    st.markdown(
        "Your Sleep Charge offset by Workout Drain ($Body\\ Battery\\ Charged + Workout\\ Impact$)"
    )

    fig_energy = px.bar(
        df_filtered,
        x="CALENDAR_DATE",
        y="NET_DAILY_ENERGY_BALANCE",
        color="NET_DAILY_ENERGY_BALANCE",
        color_continuous_scale="RdYlGn",
        labels={
            "CALENDAR_DATE": "Date",
            "NET_DAILY_ENERGY_BALANCE": "Net Energy Balance Points",
        },
    )
    st.plotly_chart(fig_energy, use_container_width=True)
