terraform {
  required_version = ">= 1.0.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    snowflake = {
      source  = "Snowflake-Labs/snowflake"
      version = "~> 0.94"
    }
  }
}

# 1. Configure the Providers
provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

provider "snowflake" {

  role = "ACCOUNTADMIN" # Needed to set up initial storage integrations
}

# 2. Create the Raw Landing GCS Bucket
resource "google_storage_bucket" "garmin_landing_zone" {
  name          = "${var.gcp_project_id}-garmin-raw-landing"
  location      = var.gcp_region
  force_destroy = true

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 90 # Move historical data to cheaper storage or archive after 90 days
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }
}

# 3. Create a Service Account for your Python Script
resource "google_service_account" "pipeline_loader" {
  account_id   = "garmin-pipeline-loader"
  display_name = "Garmin Ingestion Pipeline Service Account"
}

# Grant the Python script permission to write data to the bucket
resource "google_storage_bucket_iam_member" "loader_writer" {
  bucket = google_storage_bucket.garmin_landing_zone.name
  role   = "roles/storage.objectCreator"
  member = google_service_account.pipeline_loader.member
}

# 4. Snowflake Storage Integration Infrastructure
resource "snowflake_storage_integration" "gcs_integration" {
  name    = "GCS_GARMIN_INTEGRATION"
  comment = "Secure integration linking Snowflake to our raw Garmin GCS bucket"
  type    = "EXTERNAL_STAGE"

  enabled                   = true
  storage_provider          = "GCS"
  storage_allowed_locations = ["gcs://${google_storage_bucket.garmin_landing_zone.name}/"]
}
