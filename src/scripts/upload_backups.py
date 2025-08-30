#!/usr/bin/env python3
import os, sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

from src.util.gcloud_helper import GCloudBucket

BACKUP_PATH = "/home/aria/Backups_Local/"
BUCKET_NAME = "alice-api-backups"

files = [
    file
    for file in os.listdir(BACKUP_PATH)
    if os.path.isfile(os.path.join(BACKUP_PATH, file))
]

gcloud_bucket = GCloudBucket(bucket_name=BUCKET_NAME)

for file in files:
    destination_blob = f"backups/{os.path.basename(file)}"
    file_path = os.path.join(BACKUP_PATH, file)
    try:
        gcloud_bucket.upload_to_bucket(file_path, destination_blob)
        print(f"Successfully uploaded {file_path} to {destination_blob}")
        os.remove(file_path)
    except Exception as e:
        print(f"Failed to upload {file_path} to {destination_blob}: {e}", exc_info=True)

print(f"Backup upload process completed.")