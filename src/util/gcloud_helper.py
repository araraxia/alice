from google.cloud import storage
from src.util.independant_logger import Logger


class GCloudBucket:
    def __init__(
        self, bucket_name: str, credentials_path: str = "conf/cred/gcloud_service.json"
    ):
        self.logger = Logger(
            log_name="GCloudBucket",
            log_dir="logs/gcloud_helper",
            log_file="gcloud_bucket.log",
            log_level=10,
            file_level=20,
            console_level=10,
        )
        self.log = self.logger.get_logger()
        self.bucket_name = bucket_name
        self.credentials_path = credentials_path
        try:
            self.client = storage.Client.from_service_account_json(credentials_path)
            self.bucket = self.client.bucket(bucket_name)
            self.log.debug("GCloudBucket initialized")
        except Exception as e:
            self.log.error(f"Failed to initialize GCloudBucket: {e}", exc_info=True)
            raise e

    def upload_to_bucket(self, source_file: str, destination_blob: str):
        """Uploads a file to the GCloud bucket."""
        self.log.debug(f"Uploading {source_file} to {destination_blob}")
        blob = self.bucket.blob(destination_blob)
        try:
            blob.upload_from_filename(source_file)
            self.log.info(f"File {source_file} uploaded to {destination_blob}.")
        except Exception as e:
            self.log.error(
                f"Failed to upload {source_file} to {destination_blob}: {e}",
                exc_info=True,
            )
            raise e
