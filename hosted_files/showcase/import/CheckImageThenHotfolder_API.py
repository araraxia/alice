# Streamlined version for API endpoint usage only
# Handles GCloud blob image preflighting without hotfolder/file system dependencies

from pathlib import Path
import os

ROOT_DIR = Path(__file__).resolve().parent.parent.parent  # /menoapi
src_path = ROOT_DIR / "src"
if str(src_path) not in os.sys.path:
    os.sys.path.insert(0, str(src_path))

from loggers.logger import MenoLogger
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=ROOT_DIR.parent / ".env")

from NotionApiHelper import NotionApiHelper
from extras.preflight_helper import PreflightHelper
from extras.image_preflight_engine import ImgManip
from extras import sql_helper
from extras.gcloud_helper import GCloudBucket
from extras.helpers import send_discord_warning
from extras.service_account_helper import authenticate_service_account
from PIL import Image
import json
import warnings
import requests
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from io import BytesIO

# Initialize logger
menologger = MenoLogger(
    log_name="CheckImageThenHotfolder_API",
    logs_dir=str(ROOT_DIR / "logs"),  # Use absolute path to logs directory
    info_file="CheckImageThenHotfolder_API_info.log",
    error_file="CheckImageThenHotfolder_API_error.log",
)
logger = menologger.get_logger()

SYS_CONF_PATH = Path(ROOT_DIR / "conf" / "MOD_System_Conf.json")


class ModPreflighterAPI:
    """
    Streamlined ModPreflighter for API usage only.
    Handles GCloud blob image preflighting without file system dependencies.

    API Entry Points:
        api_process_gcloud_blob(blob_path, job_id, product_id, customer_id) -> dict:
            Main API entry point for processing images from GCloud Storage blobs.

        api_process_gdrive_file(file_id, job_id, product_id, customer_id) -> dict:
            API entry point for processing images from Google Drive using internal storage ID.
    """

    def __init__(self):
        # Load system configuration
        with open(SYS_CONF_PATH, "r") as file:
            sys_conf = json.load(file)

        self.CONF = sys_conf["Preflighter"]

        # Initialize helpers
        self.preflight_helper = PreflightHelper()
        self.img_preflight = ImgManip(SYS_CONF_PATH)
        self.gcloud_bucket = None  # Will be initialized when needed
        self.notion = NotionApiHelper()

        # Initialize variables
        self.allow_alter = 0
        self.product_id = ""
        self.product_code = ""
        self.product_record = {}
        self.job_id = ""
        self.internal_storage = ""
        self.file_name = ""
        self.hotfolder = ""
        self.target_xpix = 0
        self.target_ypix = 0

        # Load only required configuration values
        self.HOTFOLDER_PATH = self.CONF["HOTFOLDER_PATH"]
        self.IMAGE_RESIZED_ERROR = self.CONF["IMAGE_RESIZED_ERROR"]
        self.IMAGE_CROPPED_ERROR = self.CONF["IMAGE_CROPPED_ERROR"]
        self.IMAGE_OOS_ERROR = self.CONF["IMAGE_OOS_ERROR"]
        self.STOP_JOB_ERROR = self.CONF["STOP_JOB_ERROR"]
        self.PREFLIGHT_PERM_COL_NAME = self.CONF["PREFLIGHTING_PERM_COLUMN"]
        self.IMG_ALLOWANCE = self.CONF["IMAGE_ALLOWANCE"]
        self.DPI_REQ = int(self.CONF["DPI_REQ"])
        self.PRODUCT_HOTFOLDER_COL_NAME = self.CONF["PRODUCT_HOTFOLDER_COL_NAME"]
        self.PRODUCT_XPIX_COL_NAME = self.CONF["PRODUCT_XPIX_COL_NAME"]
        self.PRODUCT_YPIX_COL_NAME = self.CONF["PRODUCT_YPIX_COL_NAME"]
        self.PRODUCT_IPS_NAME = "Items per Set"
        self.JOB_LOG_COL_NAME = self.CONF["JOB_LOG_COL_NAME"]
        self.job_hrid = ""

        # Suppresses DecompressionBombWarning
        warnings.simplefilter("ignore", Image.DecompressionBombWarning)
        Image.MAX_IMAGE_PIXELS = self.CONF["DECOMP_BOMB_WARNING"]

    ################
    ### Handlers ###
    ################

    def handle_result(self, result: str):
        """
        Handles the result of an image processing operation.
        For API usage, this determines the action based on customer permissions.
        """
        self.img_preflight.image_dpi = (150, 150)

        if result == "invalid size":
            # Image will be resized
            if self.allow_alter == 1:
                result = "resize"
            # Image size does not match target size at required DPI
            elif self.allow_alter == 2:
                result = "invalid size"
            # Image will be cropped without resizing
            elif self.allow_alter == 3:
                result = "crop"
            else:
                self.report_error(
                    self.STOP_JOB_ERROR, "Error with customer preflight permissions."
                )
                raise Exception("Error with customer preflight permissions.")
        elif result == "exit":
            return

        # For API usage, perform the operation based on result
        if result == "valid":
            self.handle_valid_image()
        elif result == "invalid ar":
            self.handle_unfixable_image()
        elif result == "resize":
            self.handle_resizing_image()
        elif result == "crop":
            self.handle_cropping_image()
        elif result == "invalid size":
            self.handle_invalid_image()
        elif result == "return":
            return result
        elif result == "wasatch sent":
            send_discord_warning(
                message=f"Wasatch processing triggered for Job ID {self.job_hrid}. Job sent to RIP.",
                webhook_url=os.getenv("MOD_NOTIFICATIONS_WEBHOOK_URL", ""),
                username="MOD Preflighter",
            )
            return result
        return result

    def handle_unfixable_image(self):
        message = f"Image size {str(self.img_preflight.image_size)} is outside fixable range, cannot proceed with this image. Image must match target size of {str(self.target_size)}."
        logger.info(message)
        raise Exception(message)

    def handle_valid_image(self):
        logger.info(f"Image size is valid. Saving to hotfolder.")
        self.save_image()

    def handle_resizing_image(self):
        logger.info(f"Resizing and moving image to {self.hotfolder}.")
        self.img_preflight.resize_image(self.target_size)
        self.save_image()

    def handle_cropping_image(self):
        logger.info(f"Cropping and moving to {self.hotfolder}.")
        self.img_preflight.crop_image(self.target_size)
        self.save_image()

    def handle_invalid_image(self):
        logger.info(f"Image size does not match target size.")
        raise Exception(
            "Image size does not match target size and the customer preflight permissions do not allow proceeding with this image."
        )

    def save_image(self):
        logger.info(f"Saving image to {self.target_path}.")
        self.img_preflight.save_image(self.target_path)

    def handle_generic_error(self, message: str):
        logger.debug(f"Handling message: {message}")
        notion = NotionApiHelper()
        sys_status_package = notion.selstat_prop_gen(
            prop_name="System status",
            prop_type="select",
            prop_value="Error",
        )
        notion.update_page(pageID=self.job_id, properties=sys_status_package)
        notion.create_page_comment(
            page_id=self.job_id,
            rich_text=f"Error: {message}",
            display_name="MOD Preflighter",
        )
        raise Exception(message)

    ##################################
    ### Image Processing Functions ###
    ##################################

    def process_image_from_gcloud_blob(
        self, blob_path: str, job_id: str, product_id: str = None
    ) -> str:
        """
        Process an image from a GCloud Storage blob path, keeping it in memory.

        Args:
            blob_path (str): Path to the blob in GCloud Storage
            job_id (str): Job ID for this image
            product_id (str, optional): Product ID

        Returns:
            str: Result of image processing ('valid', 'resize', 'crop', 'invalid size', etc.)
        """
        logger.info(f"Processing image from GCloud blob: {blob_path}")

        # Set job_id
        self.job_id = job_id

        try:
            # Get bucket name from environment variable
            bucket_name = os.getenv("GCLOUD_SHORT_LIFE_PRINT_ASSETS_BUCKET")
            if not bucket_name:
                raise ValueError(
                    "GCLOUD_SHORT_LIFE_PRINT_ASSETS_BUCKET environment variable not set"
                )

            # Initialize GCloud bucket if not already done
            if not self.gcloud_bucket or self.gcloud_bucket.bucket_name != bucket_name:
                self.gcloud_bucket = GCloudBucket(bucket_name=bucket_name, log=logger)

            # Get blob metadata to determine content type
            blob = self.gcloud_bucket.get_blob(blob_name=blob_path)
            blob.reload()  # Load blob metadata

            # Determine file extension from content type
            content_type = blob.content_type or ""
            if "image/jpeg" in content_type or "image/jpg" in content_type:
                ext = ".jpg"
            elif "image/png" in content_type:
                ext = ".png"
            elif "image/tiff" in content_type or "image/tif" in content_type:
                ext = ".tif"
            else:
                # Try to get extension from blob path
                ext = os.path.splitext(blob_path)[1]
                if not ext or ext.lower() not in [
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".tif",
                    ".tiff",
                ]:
                    ext = ".jpg"  # Default to jpg

            # Generate filename
            filename = os.path.basename(blob_path)
            if "." not in filename:
                filename += f"{job_id}{ext}"
            if "/o/" in blob_path:
                filename = blob_path.split("/o/")[-1].replace("%2F", "_")
            self.file_name = f"{str(self.file_name)}{ext}"
            self.target_path = self.target_path / self.file_name

            # Download image from GCloud Storage as bytes
            logger.info(f"Downloading blob from GCloud: {blob_path}")
            try:
                blob_bytes = self.gcloud_bucket.download_blob_as_bytes(blob_path)
            except Exception as e:
                raise Exception(f"Failed to download blob from {blob_path}: {e}")

            if not blob_bytes:
                raise Exception(f"Failed to download blob from {blob_path}")

            # Convert bytes to PIL Image
            from io import BytesIO

            image_data = BytesIO(blob_bytes)
            image = Image.open(image_data)

            logger.info(
                f"Image loaded from GCloud blob (size: {image.size}, mode: {image.mode})"
            )

            # Process the image in memory
            try:
                result = self.process_image_in_memory(image, product_id)
            except Exception as e:
                logger.error(f"Error processing image in memory: {e}")
                return "error"

            return result

        except Exception as e:
            logger.error(f"Error processing image from GCloud blob {blob_path}: {e}")
            raise

    def process_image_in_memory(
        self, image: Image.Image, product_id: str = None
    ) -> str:
        """
        Process an image that's already loaded in memory.

        Args:
            image (Image.Image): PIL Image object to process
            product_id (str, optional): Product ID

        Returns:
            str: Result of image processing ('valid', 'resize', 'crop', 'invalid size', etc.)
        """
        # Use the in-memory image directly with img_preflight
        self.img_preflight.image = image
        self.image_size = image.size

        # Check rotation and aspect ratio
        try:
            target_size, target_ar = self.preflight_helper.check_rotation_by_ar(
                *image.size, self.target_xpix, self.target_ypix
            )
        except ValueError as e:
            logger.error(f"Error checking rotation/aspect ratio: {e}", exc_info=True)
            raise e

        # Assign global variables
        self.target_size = target_size
        self.target_ar = target_ar

        # Set image dpi to required DPI
        self.img_preflight.image_dpi = (self.DPI_REQ, self.DPI_REQ)

        # Check if the image is valid
        logger.info(f"Image size: {self.image_size}, target size: {target_size}")
        if self.preflight_helper.validate_image_size(
            self.img_preflight.image, target_size, self.IMG_ALLOWANCE
        ):
            return "valid"
        # Check if the image is not fixable
        elif not self.preflight_helper.validate_image_ar(
            self.img_preflight.image, target_ar, 0.05
        ):
            return "invalid ar"
        # Image is wrong size, but fixable
        else:
            return "invalid size"

    def notion_process_gcloud_blob(
        self, blob_path: str, job_id: str, product_id: str, customer_id: str
    ) -> dict:
        """
        API entry point for processing an image from GCloud Storage blob.
        Validates inputs, retrieves customer preflight permissions, processes the image,
        and handles the result appropriately.

        Args:
            blob_path (str): Path to the blob in GCloud Storage
            job_id (str): Job ID for this image
            product_id (str): Product ID for validation
            customer_id (str): Customer ID to retrieve preflight permissions

        Returns:
            dict: Result dictionary with status and details
        """
        logger.info(f"API entry point: Processing GCloud blob for job {job_id}")

        # Validate required parameters
        if not blob_path:
            raise ValueError("blob_path is required")
        if not job_id:
            raise ValueError("job_id is required")
        if not product_id:
            raise ValueError("product_id is required")
        if not customer_id:
            raise ValueError("customer_id is required")

        try:
            # Retrieve customer record from database
            customer_record = sql_helper.get_record(
                database=os.getenv("CUSTOMERS_DB_NAME", "meno_db"),
                schema=os.getenv("CUSTOMERS_SCHEMA_NAME", "Meno"),
                table=os.getenv("CUSTOMERS_TABLE_NAME", "Customers"),
                column=os.getenv("CUSTOMERS_HRID_COLUMN_NAME", "Customer ID"),
                value=customer_id,
            )
            if not customer_record:
                raise ValueError(f"Customer {customer_id} not found in database")

            # Get preflight permission value from customer record
            perm_value = customer_record.get(self.PREFLIGHT_PERM_COL_NAME)
            if not perm_value:
                logger.warning(
                    f"No preflight permission found for customer {customer_id}, defaulting to 0"
                )
                self.allow_alter = 0
            else:
                # Split by underscore and take first part, convert to int
                try:
                    self.allow_alter = int(str(perm_value).split("_")[0])
                except (ValueError, IndexError) as e:
                    logger.error(
                        f"Error parsing preflight permission '{perm_value}': {e}, defaulting to 0"
                    )
                    self.allow_alter = 0
            logger.info(
                f"Customer {customer_id} preflight permission: {self.allow_alter}"
            )

            # Set product_id and job_id as instance variables
            self.product_id = product_id
            self.job_id = job_id.replace("-", "")

            # Get product record from database
            self.product_record = sql_helper.get_record(
                database=os.getenv("PRODUCTS_DB_NAME", "meno_db"),
                schema=os.getenv("PRODUCTS_SCHEMA_NAME", "Meno"),
                table=os.getenv("PRODUCTS_TABLE_NAME", "Products"),
                column=os.getenv("PRODUCTS_HRID_COLUMN_NAME", "primary_key_id"),
                value=product_id,
            )

            if not self.product_record:
                logger.error(f"Product {product_id} not found in database.")
                self.report_error(
                    self.STOP_JOB_ERROR, f"Product {product_id} not found in database."
                )
                raise Exception(f"Product {product_id} not found in database.")

            # Get Job record from database
            job_record = sql_helper.get_record(
                database=os.getenv("LINE_ITEM_DB_NAME", "meno_db"),
                schema=os.getenv("LINE_ITEM_SCHEMA_NAME", "Meno"),
                table=os.getenv("LINE_ITEM_TABLE_NAME", "Jobs"),
                column=os.getenv("LINE_ITEM_UUID_COLUMN_NAME", "primary_key_id"),
                value=self.job_id,
            )
            if not job_record:
                job_record = sql_helper.get_record(
                    database=os.getenv("LINE_ITEM_DB_NAME", "meno_db"),
                    schema=os.getenv("LINE_ITEM_SCHEMA_NAME", "Meno"),
                    table=os.getenv("REPRINT_ITEM_TABLE_NAME", "Reprints"),
                    column=os.getenv("LINE_ITEM_UUID_COLUMN_NAME", "primary_key_id"),
                    value=self.job_id,
                )

            # Get values directly from database record
            self.hotfolder = self.product_record.get(self.PRODUCT_HOTFOLDER_COL_NAME)
            self.target_xpix = self.product_record.get(self.PRODUCT_XPIX_COL_NAME)
            self.target_ypix = self.product_record.get(self.PRODUCT_YPIX_COL_NAME)
            self.product_code = self.product_record.get(
                os.getenv("PRODUCTS_HRID_COLUMN_NAME", "Product Code")
            )
            self.items_per_set = self.product_record.get(self.PRODUCT_IPS_NAME, 1)
            if not self.items_per_set or self.items_per_set <= 0:
                self.items_per_set = 1

            # Build output paths
            job_hrid = job_record.get(
                os.getenv("LINE_ITEM_HRID_COLUMN_NAME", "ID")
            ).replace("_", "-")
            if not job_hrid:
                job_hrid = "JOB-IDMISSING"

            order_id = job_record.get(
                os.getenv("LINE_ITEM_ORDER_ID_COLUMN_NAME", "Order ID")
            )
            if not order_id:
                order_id = "NoOrderID"

            quantity = job_record.get(
                os.getenv("LINE_ITEM_QUANTITY_COLUMN_NAME", "Quantity"), 1
            )
            if quantity <= 0:
                quantity = 1
            quantity = int(quantity) * int(self.items_per_set)

            if not self.hotfolder:
                logger.error(f"Hotfolder not found for product {product_id}.")
                self.handle_generic_error(
                    f"Hotfolder not found for product {product_id}."
                )
                raise Exception(f"Hotfolder not found for product {product_id}.")

            # Set filename for saving
            file_name = f"PR--{job_hrid}_{self.product_code}_{order_id}_sID{self.internal_storage}_{self.job_id}__{int(quantity)}"
            self.file_name = file_name
            self.target_path = Path(self.HOTFOLDER_PATH) / self.hotfolder

            # Wasatch handling triggers another webhook call, so skip hotfolder saving
            if self.hotfolder == "Wasatch":
                self.job_hrid = job_record.get(
                    os.getenv("LINE_ITEM_HRID_COLUMN_NAME", "Job ID")
                )
                wasatch_url = job_record.get(
                    os.getenv("LINE_ITEM_FBTY_URL_COLUMN_NAME", "FBTY URL")
                )
                try:
                    self.target_path = Path(wasatch_url)
                    response = requests.post(wasatch_url)
                    if response.status_code != 200:
                        raise Exception(
                            f"FBTY URL returned status code {response.status_code}"
                        )
                    return "wasatch sent"
                except Exception as e:
                    logger.error(
                        f"Error retrieving FBTY URL for job {self.job_id}: {e}"
                    )
                    raise e

            try:
                # Process the image from GCloud blob
                result = self.process_image_from_gcloud_blob(
                    blob_path=blob_path, job_id=job_id, product_id=product_id
                )
            except Exception as e:
                logger.error(
                    f"Error processing image from GCloud blob: {e}", exc_info=True
                )
                return {
                    "success": False,
                    "result": None,
                    "message": f"Error processing image: {str(e)}",
                    "allow_alter": self.allow_alter,
                }

            logger.info(f"Image processing result: {result}")

            # Handle the result
            result = self.handle_result(result)

            return {
                "success": True,
                "result": result,
                "message": f"Image processed successfully with result: {result}",
                "allow_alter": self.allow_alter,
            }

        except Exception as e:
            logger.error(
                f"Error in API entry point for job {job_id}: {e}", exc_info=True
            )
            return {
                "success": False,
                "result": None,
                "message": f"Error processing image: {str(e)}",
                "allow_alter": getattr(self, "allow_alter", 0),
            }

    def notion_process_gdrive_file(
        self,
        file_id: str,
        job_id: str,
        product_id: str,
        customer_id: str,
        multiasset: bool = False,
    ) -> dict:
        """
        API entry point for processing an image from Google Drive using internal storage ID.
        Downloads the image from Google Drive, validates inputs, retrieves customer preflight
        permissions, processes the image, and handles the result appropriately.

        Args:
            file_id (str): Google Drive internal storage ID (file ID)
            job_id (str): Job ID for this image
            product_id (str): Product ID for validation
            customer_id (str): Customer ID to retrieve preflight permissions
            multiasset (bool): Whether the file is part of a multi-asset set

        Returns:
            dict: Result dictionary with status and details
        """
        logger.info(f"API entry point: Processing Google Drive file for job {job_id}")

        self.internal_storage = file_id

        # Validate required parameters
        if not file_id:
            raise ValueError("file_id is required")
        if not job_id:
            raise ValueError("job_id is required")
        if not product_id:
            raise ValueError("product_id is required")
        if not customer_id:
            raise ValueError("customer_id is required")

        try:
            # Retrieve customer record from database
            customer_record = sql_helper.get_record(
                database=os.getenv("CUSTOMERS_DB_NAME", "meno_db"),
                schema=os.getenv("CUSTOMERS_SCHEMA_NAME", "Meno"),
                table=os.getenv("CUSTOMERS_TABLE_NAME", "Customers"),
                column=os.getenv("CUSTOMERS_HRID_COLUMN_NAME", "Customer ID"),
                value=customer_id,
            )
            if not customer_record:
                raise ValueError(f"Customer {customer_id} not found in database")

            # Get preflight permission value from customer record
            perm_value = customer_record.get(self.PREFLIGHT_PERM_COL_NAME)
            if not perm_value:
                logger.warning(
                    f"No preflight permission found for customer {customer_id}, defaulting to 0"
                )
                self.allow_alter = 0
            else:
                # Split by underscore and take first part, convert to int
                try:
                    self.allow_alter = int(str(perm_value).split("_")[0])
                except (ValueError, IndexError) as e:
                    logger.error(
                        f"Error parsing preflight permission '{perm_value}': {e}, defaulting to 0"
                    )
                    self.allow_alter = 0
            logger.info(
                f"Customer {customer_id} preflight permission: {self.allow_alter}"
            )

            # Set product_id and job_id as instance variables
            self.product_id = product_id
            self.job_id = job_id.replace("-", "")

            # Get product record from database
            self.product_record = sql_helper.get_record(
                database=os.getenv("PRODUCTS_DB_NAME", "meno_db"),
                schema=os.getenv("PRODUCTS_SCHEMA_NAME", "Meno"),
                table=os.getenv("PRODUCTS_TABLE_NAME", "Products"),
                column=os.getenv("PRODUCTS_HRID_COLUMN_NAME", "primary_key_id"),
                value=product_id,
            )

            if not self.product_record:
                logger.error(f"Product {product_id} not found in database.")
                self.report_error(
                    self.STOP_JOB_ERROR, f"Product {product_id} not found in database."
                )
                raise Exception(f"Product {product_id} not found in database.")

            # Get Job record from database
            job_record = sql_helper.get_record(
                database=os.getenv("LINE_ITEM_DB_NAME", "meno_db"),
                schema=os.getenv("LINE_ITEM_SCHEMA_NAME", "Meno"),
                table=os.getenv("LINE_ITEM_TABLE_NAME", "Jobs"),
                column=os.getenv("LINE_ITEM_UUID_COLUMN_NAME", "primary_key_id"),
                value=self.job_id,
            )
            if not job_record:
                job_record = sql_helper.get_record(
                    database=os.getenv("LINE_ITEM_DB_NAME", "meno_db"),
                    schema=os.getenv("LINE_ITEM_SCHEMA_NAME", "Meno"),
                    table=os.getenv("REPRINT_ITEM_TABLE_NAME", "Reprints"),
                    column=os.getenv("LINE_ITEM_UUID_COLUMN_NAME", "primary_key_id"),
                    value=self.job_id,
                )

            # Get values directly from database record
            self.hotfolder = self.product_record.get(self.PRODUCT_HOTFOLDER_COL_NAME)
            self.target_xpix = self.product_record.get(self.PRODUCT_XPIX_COL_NAME)
            self.target_ypix = self.product_record.get(self.PRODUCT_YPIX_COL_NAME)
            self.product_code = self.product_record.get(
                os.getenv("PRODUCTS_HRID_COLUMN_NAME", "Product Code")
            )
            if not multiasset:
                self.items_per_set = self.product_record.get(self.PRODUCT_IPS_NAME, 1)
            else:
                self.items_per_set = 1

            # Build output paths
            job_hrid = job_record.get(
                os.getenv("LINE_ITEM_HRID_COLUMN_NAME", "ID")
            ).replace("_", "-")
            if not job_hrid:
                job_hrid = "JOB-IDMISSING"

            order_id = job_record.get(
                os.getenv("LINE_ITEM_ORDER_ID_COLUMN_NAME", "Order ID")
            )
            if not order_id:
                order_id = "NoOrderID"

            quantity = job_record.get(
                os.getenv("LINE_ITEM_QUANTITY_COLUMN_NAME", "Quantity"), 1
            )
            if quantity <= 0:
                quantity = 1
            quantity = int(quantity) * int(self.items_per_set)

            if not self.hotfolder:
                logger.error(f"Hotfolder not found for product {product_id}.")
                self.handle_generic_error(
                    f"Hotfolder not found for product {product_id}."
                )
                raise Exception(f"Hotfolder not found for product {product_id}.")

            # Wasatch handling triggers another webhook call, so skip hotfolder saving
            if self.hotfolder == "Wasatch":
                self.job_hrid = job_record.get(
                    os.getenv("LINE_ITEM_HRID_COLUMN_NAME", "Job ID")
                )
                wasatch_url = job_record.get(
                    os.getenv("LINE_ITEM_FBTY_URL_COLUMN_NAME", "FBTY URL")
                )
                try:
                    self.target_path = Path(wasatch_url)
                    response = requests.post(wasatch_url)
                    if response.status_code != 200:
                        raise Exception(
                            f"FBTY URL returned status code {response.status_code}"
                        )
                    return "wasatch sent"
                except Exception as e:
                    logger.error(
                        f"Error retrieving FBTY URL for job {self.job_id}: {e}"
                    )
                    raise e

            try:
                # Authenticate with Google Drive API using service_account_helper
                logger.info("Authenticating with Google Drive API")
                creds = authenticate_service_account()
                drive_service = build("drive", "v3", credentials=creds)

                # Get file metadata to determine content type and name
                logger.info(f"Getting file metadata for file_id: {file_id}")
                file_metadata = (
                    drive_service.files()
                    .get(fileId=file_id, fields="name,mimeType")
                    .execute()
                )

                file_name = file_metadata.get("name", f"{job_id}.jpg")
                mime_type = file_metadata.get("mimeType", "image/jpeg")

                logger.info(f"File name: {file_name}, MIME type: {mime_type}")

                # Download file from Google Drive
                logger.info(f"Downloading file from Google Drive: {file_id}")
                request = drive_service.files().get_media(fileId=file_id)
                file_io = BytesIO()
                downloader = MediaIoBaseDownload(file_io, request)

                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    if status:
                        logger.debug(
                            f"Download progress: {int(status.progress() * 100)}%"
                        )

                file_io.seek(0)
                logger.info(
                    f"Successfully downloaded {len(file_io.getvalue())} bytes from Google Drive"
                )

                # Convert bytes to PIL Image
                image = Image.open(file_io)
                logger.info(
                    f"Image loaded from Google Drive (size: {image.size}, mode: {image.mode})"
                )

                # Set filename for saving
                file_name = f"PR--{job_hrid}_{self.product_code}_{order_id}_sID{self.internal_storage}_{self.job_id}__{int(quantity)}.{file_name.split('.')[-1]}"
                self.file_name = file_name
                self.target_path = (
                    Path(self.HOTFOLDER_PATH) / self.hotfolder / self.file_name
                )

                # Process the image in memory
                result = self.process_image_in_memory(image)

            except Exception as e:
                logger.error(
                    f"Error processing image from Google Drive: {e}", exc_info=True
                )
                self.handle_generic_error(
                    f"Error processing image from Google Drive. Image likely missing or corrupt. {e}"
                )
                return {
                    "success": False,
                    "result": None,
                    "message": f"Error processing image: {str(e)}",
                    "allow_alter": self.allow_alter,
                }

            logger.info(f"Image processing result: {result}")

            # Handle the result
            result = self.handle_result(result)

            return {
                "success": True,
                "result": result,
                "message": f"Image processed successfully with result: {result}",
                "allow_alter": self.allow_alter,
            }

        except Exception as e:
            logger.error(
                f"Error in API entry point for job {job_id}: {e}", exc_info=True
            )
            return {
                "success": False,
                "result": None,
                "message": f"Error processing image: {str(e)}",
                "allow_alter": getattr(self, "allow_alter", 0),
            }


if __name__ == "__main__":
    # Test logger
    logger.info("Logger test: ModPreflighterAPI script loaded successfully")
    logger.warning("Logger test: This is a warning message")
    logger.error("Logger test: This is an error message")
    print("Logger test messages written. Check logs directory for output.")
