import os
from datetime import datetime
import snowflake.connector
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from dotenv import load_dotenv
from prefect import flow, task
from prefect_dbt.cli.commands import trigger_dbt_cli_command
from prefect.client.schedules import CronSchedule


from extract_garmin import main as run_garmin_extraction

load_dotenv()


@task(
    name="Extract Garmin Data",
    retries=3,
    retry_delay_seconds=60,
    description="Invokes the standalone raw Garmin API ingestion script.",
)
def extract_raw_metrics_task():
    print("Initializing standalone Garmin extraction process...")
    run_garmin_extraction()
    print("Raw Garmin extraction and GCS staging complete.")
    return "SUCCESS"


@task(name="Load GCS to Snowflake")
def load_gcs_to_snowflake_task():
    print("Reading private RSA key file for Snowflake JWT authentication...")

    key_path = os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH")
    passphrase = os.getenv("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE")

    with open(key_path, "rb") as key_file:
        p_key = serialization.load_pem_private_key(
            key_file.read(),
            password=passphrase.encode("utf-8") if passphrase else None,
            backend=default_backend(),
        )

    pkb = p_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    print("Connecting to Snowflake raw landing zone...")
    conn = snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        private_key=pkb,
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database="GARMIN_PROJECT",
        schema="RAW",
    )

    copy_sql = """
        COPY INTO garmin_project.raw.src_garmin_overtrain_metrics (raw_json)
        FROM @garmin_project.raw.gcs_garmin_stage/landing/garmin/
        FILE_FORMAT = (FORMAT_NAME = garmin_project.raw.json_file_format)
        ON_ERROR = 'ABORT_STATEMENT';
    """

    try:
        cursor = conn.cursor()
        print("Executing Snowflake stage COPY INTO command...")
        cursor.execute(copy_sql)
        results = cursor.fetchall()

        for row in results:
            print(f"File: {row[0]} | Status: {row[1]} | Loaded: {row[3]} records")

    except Exception as e:
        print(f"Database error during COPY INTO execution: {e}")
        raise e
    finally:
        cursor.close()
        conn.close()
        print("Snowflake connection securely closed.")
    return "SUCCESS"


@task(
    name="Trigger dbt Transformations",
    description="Runs dbt build to transform and test raw staged tables in Snowflake.",
)
def run_dbt_transformations_task():
    print("Triggering dbt model transformations and data quality tests...")
    resolved_profiles_dir = os.path.expanduser("~/.dbt")

    result = trigger_dbt_cli_command(
        command="dbt build",
        project_dir="./garmin_dw",
        profiles_dir=resolved_profiles_dir,
    )
    return result


@flow(
    name="Garmin-Health-Pipeline",
    log_prints=True,
    description="Orchestrates extraction, zero-MFA loading, and dbt modeling rules.",
)
def health_metrics_orchestration_flow():

    extraction_status = extract_raw_metrics_task()

    if extraction_status == "SUCCESS":
        load_status = load_gcs_to_snowflake_task()

        if load_status == "SUCCESS":
            run_dbt_transformations_task()


if __name__ == "__main__":
    # This turns your script into a managed worker with an automated cron schedule
    health_metrics_orchestration_flow.serve(
        name="daily-garmin-sync",
        schedule=CronSchedule(
            cron="0 8 * * *",  # Runs every single day at 5:00 AM
            timezone="America/Detroit",
        ),
    )
