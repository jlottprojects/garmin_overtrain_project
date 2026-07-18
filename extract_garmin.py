import os
import json
import logging
import argparse
from datetime import datetime, timedelta
from dotenv import load_dotenv
from garminconnect import Garmin
from google.cloud import storage

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()

GARMIN_EMAIL = os.getenv("GARMIN_EMAIL")
GARMIN_PASSWORD = os.getenv("GARMIN_PASSWORD")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
TOKEN_STORE_DIR = os.path.expanduser("~/.garminconnect")


def init_garmin_client():
    """
    Initializes and authenticates the Garmin Connect client.
    Uses the modern token cache location to prevent aggressive API rate-limiting.
    """
    if not GARMIN_EMAIL or not GARMIN_PASSWORD:
        raise ValueError(
            "Missing GARMIN_EMAIL or GARMIN_PASSWORD in environment variables."
        )

    logger.info(f"Initializing Garmin Client for user: {GARMIN_EMAIL}")

    try:
        client = Garmin(email=GARMIN_EMAIL, password=GARMIN_PASSWORD)
        os.makedirs(TOKEN_STORE_DIR, exist_ok=True)
        client.login(tokenstore=TOKEN_STORE_DIR)

        logger.info("Garmin Connect authentication successful.")
        return client

    except Exception as e:
        logger.error(f"Failed to authenticate with Garmin Connect API: {e}")
        raise


def extract_health_data(client, target_date):
    """
    Extracts summary health metrics for a target date and returns the dictionary.
    No local files are written.
    """
    date_str = target_date.strftime("%Y-%m-%d")
    logger.info(f"Extracting Garmin health metrics for date: {date_str}")

    payload = {
        "metadata": {
            "extracted_at": datetime.utcnow().isoformat() + "Z",
            "target_date": date_str,
        },
        "data": {},
    }

    try:
        payload["data"]["user_summary"] = client.get_user_summary(date_str)
        payload["data"]["sleep_data"] = client.get_sleep_data(date_str)
        payload["data"]["activities"] = client.get_activities_by_date(
            date_str, date_str
        )

        return payload

    except Exception as e:
        logger.error(f"Error extracting data from Garmin API: {e}")
        raise


def upload_payload_to_gcs(bucket_name, payload, destination_blob_name):
    """
    Streams a dictionary payload as an in-memory JSON object directly to GCS.
    """
    if not bucket_name:
        raise ValueError(
            "GCS_BUCKET_NAME is not set. Check your environment configuration."
        )

    logger.info(f"Initializing GCS Client for bucket target: {bucket_name}")
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)

        logger.info(
            f"Streaming payload directly to memory -> gs://{bucket_name}/{destination_blob_name}"
        )

        json_data = json.dumps(payload, indent=4)
        blob.upload_from_string(json_data, content_type="application/json")

        logger.info("Google Cloud Storage upload complete.")

    except Exception as e:
        logger.error(f"Failed to upload object to Google Cloud Storage: {e}")
        raise


def run_pipeline(target_date):
    """
    Orchestrates the in-memory Extract-Load lifecycle loop.
    """
    date_str = target_date.strftime("%Y-%m-%d")
    year_str = target_date.strftime("%Y")
    month_str = target_date.strftime("%m")

    logger.info(f"--- Starting Pipeline for Date: {date_str} ---")

    garmin_client = init_garmin_client()

    payload = extract_health_data(garmin_client, target_date)

    gcs_destination_path = (
        f"landing/garmin/year={year_str}/month={month_str}/date={date_str}/metrics.json"
    )

    upload_payload_to_gcs(
        bucket_name=GCS_BUCKET_NAME,
        payload=payload,
        destination_blob_name=gcs_destination_path,
    )
    logger.info(f"--- Pipeline successfully completed for Date: {date_str} ---")


def main(start_date=None, end_date=None):
    """
    Main entry point for both standalone execution and orchestrator imports.
    If called without arguments, defaults to pulling yesterday's metrics (standard pipeline run).
    """
    if start_date:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = (
            datetime.strptime(end_date, "%Y-%m-%d")
            if end_date
            else (datetime.today() - timedelta(days=1))
        )

        logger.info(
            f"Running in BACKFILL MODE from {start_date} to {end.strftime('%Y-%m-%d')}"
        )

        current_date = start
        while current_date <= end:
            try:
                run_pipeline(current_date)
            except Exception as e:
                logger.error(
                    f"Backfill failed for {current_date.strftime('%Y-%m-%d')}, continuing loop. Error: {e}"
                )

            current_date += timedelta(days=1)

    else:
        # Default daily automation behavior
        yesterday = datetime.today() - timedelta(days=1)
        run_pipeline(yesterday)


if __name__ == "__main__":
    # This block handles parsing CLI flags when running the file directly
    parser = argparse.ArgumentParser(description="Garmin Data Pipeline Extract & Load")
    parser.add_argument(
        "--start_date", type=str, help="Backfill start date (YYYY-MM-DD)"
    )
    parser.add_argument("--end_date", type=str, help="Backfill end date (YYYY-MM-DD)")
    args = parser.parse_args()

    # Pass the parsed CLI args into our main function
    main(start_date=args.start_date, end_date=args.end_date)
