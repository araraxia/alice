from pathlib import Path
from functools import wraps
import sys, os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import re
import signal

ROOT_DIR = Path(__file__).resolve().parent.parent.parent  # /
SRC_DIR = ROOT_DIR / "src"
TMP_DIR = ROOT_DIR / "tmp" / "notion_uploads"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

notion_url_regex = r"https:\/\/[\w\-\.]+amazonaws\.com\/[\w\-]{36}\/[\w\-]{36}.*Token.*"
cpu_cores = os.cpu_count() or 4
max_workers = min(32, cpu_cores * 5)

from NotionApiHelper import NotionApiHelper
from extras.gcloud_helper import GCloudBucket
from extras.helpers import determine_file_type_from_response
from extras.sql_helper import (
    init_psql_connection,
    init_psql_connection_pool,
    create_cursor,
    get_all_records,
    update_existing_record,
    delete_record,
)
from loggers.logger import MenoLogger

log = MenoLogger(
    log_name="backup_notion_uploads",
    logs_dir=ROOT_DIR / "logs",
    info_file="backup_notion_info.log",
    error_file="backup_notion_error.log",
    backup_count=7,
).get_logger()
stop_request = False


def event_handler(sig, frame):
    global stop_request
    log.info("Signal received, stopping new requests...")
    stop_request = True


signal.signal(signal.SIGINT, event_handler)


def get_current_records(schema_name: str, table_name: str):
    conn = init_psql_connection(db="meno_db")
    cursor = create_cursor(conn)
    records = get_all_records(
        cursor=cursor,
        connection=conn,
        database="meno_db",
        schema=schema_name,
        table=table_name,
    )
    cursor.close()
    conn.close()
    return records


def find_notion_urls(records) -> list[list]:
    urls_to_download = []

    for record in records:
        notion_id = record.get("uuid", "N/A").replace("-", "")
        url_list = record.get("files", [])
        url_package = []
        for url in url_list:
            match = re.search(notion_url_regex, url)
            if match:
                schema = record.get("schema", "N/A")
                table = record.get("table", "N/A")
                column = record.get("column", {})
                url_package.append((notion_id, schema, table, column, url))
        if url_package:
            urls_to_download.append(url_package)

    return urls_to_download


def _delete_record_from_db(notion_id, column_name):
    delete_record(
        cursor=create_cursor(init_psql_connection(db="meno_db")),
        connection=init_psql_connection(db="meno_db"),
        database="meno_db",
        log=log,
        schema_name="meta",
        table_name="notion_url_rehost",
        columns=["uuid", "column"],
        values=[notion_id, column_name],
    )


def _handle_download_response(response, file_url, file_name):
    """
    Handle the response from downloading a file.
    Args:
        response (requests.Response): The response object from requests.get()
        file_url (str): The original file URL
        file_name (str): The intended local file name
        notion_id (str): The Notion record ID
        column (str): The column name in the database
    Returns:
        bool: True if download and save successful, False otherwise.
    """
    if response.status_code == 200:
        mime_type, extension = determine_file_type_from_response(file_url, response)
        file_path = TMP_DIR / f"{file_name}{extension}"
        if os.path.exists(file_path):
            log.info(f"File {file_name} already exists, overwriting.")
            os.remove(file_path)
        with open(file_path, "wb") as f:
            f.write(response.content)
        log.info(f"Downloaded {file_url} to {file_name}")
        return file_path
    else:
        log.error(f"Failed to download {file_url}")
        raise ValueError(
            f"Failed to download {file_url} with status code {response.status_code}"
        )


def _download_file(url_package):
    """
    Downloads a file from a URL and saves it to a temporary location.
    Args:
        url_package (tuple): A tuple containing (notion_id, schema, table, column, file_url)
    Returns:
        str: The local file path if successful, None otherwise.
    """
    if stop_request:
        return None

    file_names = []
    index = 0
    for url in url_package:
        notion_id, schema, table, column, file_url = url
        file_name = f"{notion_id}__{schema}__{table}__{column}__{index}"
        try:
            response = requests.get(file_url)
            file_path = _handle_download_response(
                response, file_url, file_name, notion_id, column
            )
            if file_path:
                file_names.append(str(file_path))
        except Exception as e:
            log.error(f"Error downloading {file_url}: {e}")
        index += 1
    _delete_record_from_db(notion_id, column)
    return file_names if file_names else None


def download_notion_files(urls_to_download):
    if not os.path.exists(TMP_DIR):
        os.makedirs(TMP_DIR, exist_ok=True)

    successful_downloads = []
    failed_downloads = []
    i = 0
    max_len = len(urls_to_download)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = []
        for url_package in urls_to_download:
            results.append(executor.submit(_download_file, url_package))

        for future in as_completed(results):
            if stop_request:
                break

            result = future.result()
            i += 1
            if result:
                log.info(f"{str(i)} of {str(max_len)} - Downloaded files: {result}")
                successful_downloads.append(result)
            else:
                log.error(
                    f"{str(i)} of {str(max_len)} - Failed to download a file package."
                )
                failed_downloads.append(
                    urls_to_download[i - 1]
                )  # Append the original package for reference

    return successful_downloads, failed_downloads


def _upload_file_to_gcs(bucket, file_path, file_name, notion_id, column):
    log.info(f"Uploading {file_name} to GCS")
    blob_name = (
        f"record_assets/{notion_id.replace('-', '')}/{column}/{file_name}".replace(
            " ", "-"
        )
    )
    try:
        blob = bucket.upload_to_bucket(file_path, blob_name)
        blob_url = f"https://storage.googleapis.com/{bucket.bucket_name}/{blob_name}"
        log.info(f"Uploaded {file_name} to GCS as {blob_name}, URL: {blob_url}")
        return blob_url
    except Exception as e:
        log.error(f"Failed to upload {file_name} to GCS: {e}", exc_info=True)
        raise e


def _handle_conn_cursor(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        connection_pool = kwargs.pop("connection_pool")
        conn = None
        cursor = None
        try:
            conn = connection_pool.getconn()
            cursor = create_cursor(conn)
            return func(*args, **kwargs, conn=conn, cursor=cursor)
        finally:
            if cursor:
                cursor.close()
            if conn:
                connection_pool.putconn(conn)

    return wrapper


def _update_sql_record(cursor, conn, schema, table, column, url_package, notion_id):
    try:
        log.info(f"Updating database for {notion_id}:{column} with URL: {url_package}")
        update_existing_record(
            cursor=cursor,
            connection=conn,
            database="meno_db",
            schema=schema,
            table=table,
            update_columns=[column],
            update_values=[url_package],
            where_column="primary_key_id",
            where_value=notion_id.replace("-", ""),
        )
        log.info(f"Database updated for {notion_id}:{column}")
    except Exception as e:
        conn.rollback()
        log.error(
            f"Failed to update database for {notion_id}:{column}: {e}", exc_info=True
        )
        raise e


def _store_notion_update_record(conn, cursor, notion_id, column, schema, urls):
    try:
        log.info(
            f"Storing Notion update record for {notion_id}:{column} with URLs: {urls}"
        )
        update_existing_record(
            cursor=cursor,
            connection=conn,
            database="meno_db",
            schema="meta",
            table="notion_url_rehost",
            update_columns=["uuid", "column", "schema", "urls"],
            update_values=[notion_id, column, schema, urls],
            where_column="uuid",
            where_value=notion_id,
        )
        log.info(f"Notion update record stored for {notion_id}:{column}")
    except Exception as e:
        log.error(
            f"Failed to store Notion update record for {notion_id}:{column}: {e}",
            exc_info=True,
        )


def update_notion_records():
    import time

    connection = init_psql_connection(db="meno_db")
    cursor = create_cursor(connection)

    records = get_all_records(
        cursor=cursor,
        connection=connection,
        database="meno_db",
        schema_name="meta",
        table_name="notion_url_new",
    )

    for record in records:
        notion_id = record.get("uuid", "N/A").replace("-", "")
        schema = record.get("schema", "N/A")
        column = record.get("column", "N/A")
        url_package = record.get("urls", [])
        file_names = []
        for url in url_package:
            file_name = url.split("/")[-1]
            file_names.append(file_name)

        if schema == "Planet":
            notion = NotionApiHelper(header_path="src/headers_pts.json")
        else:
            notion = NotionApiHelper()

        file_package = notion.generate_property_body(
            prop_name=column,
            prop_type="files",
            prop_value=file_names,
            prop_value2=url_package,
        )
        log.info(f"Updating notion page {notion_id}:{column} for {file_names}")
        page = notion.update_page(notion_id, file_package)
        if page:
            log.info(f"Notion page {notion_id}:{column} updated for {file_names}")
        else:
            raise ValueError(
                f"Bad/no response from Notion API for {notion_id}:{column} Page: {page}"
            )
        time.sleep(0.34)  # To respect Notion's rate limit of 3 requests per second


def _delete_tmp_file(file_package):
    for file_path in file_package:
        try:
            os.remove(file_path)
            log.info(f"Removed local file {file_path}")
        except Exception as e:
            log.error(f"Failed to remove local file {file_path}: {e}", exc_info=True)
            raise e


@_handle_conn_cursor
def file_upload_process(bucket, file_package, conn, cursor):
    """
    Begins the upload process for a file.
    Args:
        bucket (GCloudBucket): The GCloudBucket instance.
        file_path (str): The local file path to upload.
        connection_pool: The connection pool for database connections.
    Returns:
        str: The file path if successful, None otherwise.
    """
    if stop_request:
        return None

    log.debug(f"Processing files: {file_package}")
    notion_id, schema, table, column = Path(file_package[0]).stem.split("__")[:4]
    if not all([notion_id, schema, table, column]):
        log.error(f"Invalid file name format: {file_package}, skipping upload.")
        return None
    new_urls = []
    file_names = []
    for file_path in file_package:
        file_name = Path(file_path).name
        blob_url = _upload_file_to_gcs(bucket, file_path, file_name, notion_id, column)
        if blob_url:
            new_urls.append(blob_url)
            file_names.append(file_name)
    if not new_urls:
        log.error(f"Failed to upload any files in package: {file_package}")
        return None

    _update_sql_record(cursor, conn, schema, table, column, new_urls, notion_id)
    _store_notion_update_record(notion_id, column, schema, new_urls)
    _delete_tmp_file(file_package)
    return file_package


def upload_files_to_gcs(file_paths: list):
    log.debug("Starting upload to GCS")
    bucket = GCloudBucket(bucket_name="meno-order-extended-life-assets", log=log)
    connection_pool = init_psql_connection_pool(
        db="meno_db", max_connections=max_workers
    )
    i = 0
    max_len = len(file_paths)
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = []
            path_package = []
            last_uuid = None
            last_column = None
            file_paths.sort()  # Ensure files are processed in order
            for index, file_path in enumerate(file_paths):
                # Group files by notion_id and column
                file_name = Path(file_path).name
                notion_id = file_name.split("__")[0]
                column = file_name.split("__")[3]
                if notion_id == last_uuid and column == last_column:
                    path_package.append(file_path)
                else:
                    path_package = [file_path]
                    last_uuid = notion_id
                    last_column = column

                # Get the next file to check if it's the same record/column
                if index + 1 < len(file_paths):
                    next_file = file_paths[index + 1]
                    next_file_name = Path(next_file).name
                    next_notion_id = next_file_name.split("__")[0]
                    next_column = next_file_name.split("__")[3]
                    if next_notion_id == last_uuid and next_column == last_column:
                        log.info(
                            f"{str(index)} of {str(max_len)} - Continuing to group files for {notion_id}:{column}"
                        )
                        continue

                log.debug(f"Submitting upload task for {file_path}")
                future = executor.submit(
                    file_upload_process,
                    bucket,
                    path_package,
                    connection_pool=connection_pool,
                )
                results.append(future)
            for future in as_completed(results):
                if stop_request:
                    break

                i += 1
                try:
                    result = future.result()  # To raise exceptions if any occurred
                    if result:
                        log.info(
                            f"{str(i)} of {str(max_len)} - Uploaded and processed file: {result}"
                        )
                    else:
                        log.error(
                            f"{str(i)} of {str(max_len)} - Failed to upload/process a file."
                        )
                except Exception as e:
                    log.error(
                        f"{str(i)} of {str(max_len)} - Exception during upload/process: {e}",
                        exc_info=True,
                    )

    finally:
        # Close all connections in the pool
        if connection_pool:
            connection_pool.closeall()
            log.debug("Connection pool closed")


def get_files_in_directory(directory: str = str(TMP_DIR)):
    log.info(f"Getting file paths in directory: {directory}")
    return [
        f"{str(TMP_DIR)}/{f}"
        for f in os.listdir(directory)
        if os.path.isfile(os.path.join(directory, f))
    ]


def get_files():
    global stop_request
    log.info("Starting Notion uploads backup process")
    records = get_current_records(schema_name="meta", table_name="notion_url_rehost")
    urls_to_download = find_notion_urls(records)
    log.info(f"Found {len(urls_to_download)} Notion URLs to download")
    successful_downloads, failed_downloads = download_notion_files(urls_to_download)
    log.info(f"Successfully downloaded {len(successful_downloads)} files")
    log.error(f"Failed to download {len(failed_downloads)} files")
    log.error(f"Failed downloads: {failed_downloads}")
    if stop_request:
        log.error("Process interrupted, skipping upload to GCS.")
        input("Press enter to continue...")
        stop_request = False
    upload_files_to_gcs(get_files_in_directory())
    if stop_request:
        log.error("Process interrupted during upload.")
        return
    log.info("Files backed up, updating Notion records.")
    update_notion_records()
    log.info("Notion uploads backup process completed.")


if __name__ == "__main__":
    try:
        get_files()
    except Exception as e:
        log.error(f"Error in get_files: {e}", exc_info=True)
        sys.exit(1)
