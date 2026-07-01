from google.cloud import storage
from pathlib import Path
from io import BytesIO
import os
from urllib.parse import unquote

ROOT_PATH = Path(__file__).resolve().parent.parent.parent  # /menoapi
CRED_PATH = ROOT_PATH / "cred" / "noreply_sa.json"


class GCloudBucket:
    def __init__(self, bucket_name: str, log, credentials_path: str = str(CRED_PATH)):
        self.log = log
        self.bucket_name = bucket_name
        self.credentials_path = credentials_path
        try:
            self.client = storage.Client.from_service_account_json(credentials_path)
            self.bucket = self.client.bucket(bucket_name)
            self.log.debug("GCloudBucket initialized")
        except Exception as e:
            self.log.error(f"Failed to initialize GCloudBucket: {e}", exc_info=True)
            raise e

    def upload_to_bucket(self, source_file: str, destination_blob: str) -> storage.Blob:
        """
        Uploads a file to the GCloud bucket.

        """
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
        return blob

    def upload_bytes_to_bucket(
        self, file_data: bytes, destination_blob: str, content_type: str = None
    ) -> storage.Blob:
        """
        Uploads raw bytes to the GCloud bucket by converting to an in-memory file object.

        Args:
            file_data: Raw bytes of the file to upload
            destination_blob: The destination path/name in the bucket
            content_type: Optional MIME type for the blob (e.g., 'image/png', 'application/pdf')

        Returns:
            storage.Blob: The uploaded blob object
        """
        self.log.debug(f"Uploading {len(file_data)} bytes to {destination_blob}")
        blob = self.bucket.blob(destination_blob)

        # Set content type if provided
        if content_type:
            blob.content_type = content_type

        try:
            # Convert raw bytes to in-memory file object
            file_obj = BytesIO(file_data)
            blob.upload_from_file(file_obj, content_type=content_type)
            self.log.info(f"Uploaded {len(file_data)} bytes to {destination_blob}.")
        except Exception as e:
            self.log.error(
                f"Failed to upload bytes to {destination_blob}: {e}",
                exc_info=True,
            )
            raise e
        return blob

    def get_blob(self, blob_name: str) -> storage.Blob:
        """
        Gets a blob from the GCloud bucket.

        Args:
            blob_name: The name/path of the blob in the bucket

        Returns:
            storage.Blob: The blob object if it exists

        Raises:
            Exception: If the blob doesn't exist or retrieval fails
        """
        # Clean up GCS REST API URL format if present
        if "/o/" in blob_name:
            blob_name = blob_name.split("/o/")[-1]

        # URL-decode the blob path
        blob_name = unquote(blob_name)

        self.log.debug(f"Getting blob: {blob_name}")
        try:
            blob = self.bucket.blob(blob_name)

            # Check if blob exists
            if not blob.exists():
                self.log.error(
                    f"Blob {blob_name} does not exist in bucket {self.bucket_name}"
                )
                raise FileNotFoundError(f"Blob {blob_name} not found")

            self.log.info(f"Successfully retrieved blob: {blob_name}")
            return blob

        except Exception as e:
            self.log.error(f"Failed to get blob {blob_name}: {e}", exc_info=True)
            raise e

    def download_blob_as_bytes(self, blob_path: str) -> bytes:
        """
        Downloads a blob from the GCloud bucket and returns its contents as bytes.

        Args:
            blob_path: The path/name of the blob in the bucket

        Returns:
            bytes: The blob's file contents as raw bytes

        Raises:
            FileNotFoundError: If the blob doesn't exist
            Exception: If download fails
        """
        # Clean up GCS REST API URL format if present
        if "/o/" in blob_path:
            blob_path = blob_path.split("/o/")[-1]

        # URL-decode the blob path
        blob_path = unquote(blob_path)

        self.log.debug(f"Downloading blob as bytes: {blob_path}")
        try:
            blob = self.bucket.blob(blob_path)

            # Check if blob exists
            if not blob.exists():
                self.log.error(
                    f"Blob {blob_path} does not exist in bucket {self.bucket_name}"
                )
                raise FileNotFoundError(f"Blob {blob_path} not found")

            # Download blob contents as bytes
            blob_bytes = blob.download_as_bytes()

            self.log.info(
                f"Successfully downloaded {len(blob_bytes)} bytes from {blob_path}"
            )
            return blob_bytes

        except Exception as e:
            self.log.error(
                f"Failed to download blob {blob_path} as bytes: {e}", exc_info=True
            )
            raise e
