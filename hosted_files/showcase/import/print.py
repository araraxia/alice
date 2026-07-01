import os
import win32ui  # type: ignore
import win32print  # type: ignore
import json
import requests
import tempfile
import mimetypes
import time
import urllib3
from io import BytesIO

from pdf2image import convert_from_path, convert_from_bytes
from PIL import Image, ImageWin


class printerHandler:
    """A class to handle printing PDF files and images on Windows systems.

    Attributes:
        printer_name (str): The name of the printer to use.
        poppler_path (str): The path to the Poppler binaries for PDF rendering.
        page_width (float): The width of the page in inches.
        page_height (float): The height of the page in inches.
        margin_left (float): The left margin in inches.
        margin_top (float): The top margin in inches.
        margin_right (float): The right margin in inches.
        margin_bottom (float): The bottom margin in inches.
        orientation (str): The orientation of the page, either "portrait" or "landscape".
    """

    def __init__(
        self,
        printer_name: str,
        poppler_path: str = r"C:\Code\Poppler\Library\bin",
        raster_dpi: int = 300,
        page_width: float = 8.5,
        page_height: float = 11.0,
        margin_left: float = 0.25,
        margin_top: float = 0.25,
        margin_right: float = 0.25,
        margin_bottom: float = 0.25,
        orientation: str = "portrait",
        fit_to_page: bool = True,
    ):
        self.printer_name = printer_name
        self.poppler_path = poppler_path
        self.raster_dpi = raster_dpi

        self.page_width = page_width
        self.page_height = page_height

        self.margin_left = margin_left
        self.margin_top = margin_top
        self.margin_right = margin_right
        self.margin_bottom = margin_bottom

        self.orientation = orientation.lower()
        self.fit_to_page = fit_to_page

        self.get_device_properties()

    def get_device_properties(self):
        # Create a device context for the printer
        hdc = win32ui.CreateDC()
        hdc.CreatePrinterDC(self.printer_name)
        self.hdc = hdc

        # Get the device capabilities for DPI
        self.device_dpi_x = hdc.GetDeviceCaps(88)
        self.device_dpi_y = hdc.GetDeviceCaps(90)

        if self.raster_dpi > self.device_dpi_x or self.raster_dpi > self.device_dpi_y:
            self.raster_dpi = min(self.device_dpi_x, self.device_dpi_y)

    def print_images(
        self,
        images: list[Image.Image],
        page_width: float = None,
        page_height: float = None,
        doc_name: str = "PDF Document",
    ):
        if not page_width:
            page_width = self.page_width
        if not page_height:
            page_height = self.page_height

        if not images:
            raise ValueError("Could not rasterize PDF file into images.")

        # Adjust orientation and fit to page for each image
        for i, image in enumerate(images):
            image = self._adjust_orientation(image)
            if self.fit_to_page:
                image = self._fit_to_page(image)
            images[i] = image

        # Create a device context for the printer
        hdc = win32ui.CreateDC()
        hdc.CreatePrinterDC(self.printer_name)

        # Calculate full page dimensions in pixels
        full_page_width_px = int(page_width * self.device_dpi_x)
        full_page_height_px = int(page_height * self.device_dpi_y)

        # Calculate margin offsets in pixels
        margin_left_px = int(self.margin_left * self.device_dpi_x)
        margin_top_px = int(self.margin_top * self.device_dpi_y)
        margin_right_px = int(self.margin_right * self.device_dpi_x)
        margin_bottom_px = int(self.margin_bottom * self.device_dpi_y)

        # Calculate printable area dimensions in pixels
        printable_width_px = full_page_width_px - margin_left_px - margin_right_px
        printable_height_px = full_page_height_px - margin_top_px - margin_bottom_px

        # Start print job in spooler
        hdc.StartDoc(doc_name)

        # Iterate through images
        for i, image in enumerate(images):
            # Create a page in the current job
            hdc.StartPage()

            # Create a device-independent bitmap (DIB) from the image
            dib = ImageWin.Dib(image)
            # Draw the image starting at the margin offset
            dib.draw(
                hdc.GetHandleOutput(),
                (
                    margin_left_px,
                    margin_top_px,
                    margin_left_px + printable_width_px,
                    margin_top_px + printable_height_px,
                ),
            )
            hdc.EndPage()

        # Execute the document and delete the DC
        hdc.EndDoc()
        hdc.DeleteDC()

    def print_pdf_file(
        self,
        pdf_file_path: str,
        page_width: float,
        page_height: float,
        raster_dpi: int = 202,
    ):
        """
        Print a PDF file from a given path.
        Args:
            pdf_file_path (str): The path to the PDF file.
            page_width (float): The width of the page in inches.
            page_height (float): The height of the page in inches.
            raster_dpi (int): The DPI for rasterizing the PDF pages. Default is 202.
        """
        images = convert_from_path(
            pdf_file_path,
            poppler_path=self.poppler_path,
            dpi=raster_dpi,
        )

        self.print_images(
            images=images,
            page_width=page_width,
            page_height=page_height,
            doc_name=os.path.basename(pdf_file_path),
        )

    def print_pdf_io(
        self,
        pdf_file_io: bytes,
        page_width: float,
        page_height: float,
        raster_dpi: int = 202,
        doc_name: str = "PDF Document",
    ):
        """
        Print a PDF file from a BytesIO object.
        Args:
            pdf_file_io (bytes): The PDF file as a BytesIO object.
            page_width (float): The width of the page in inches.
            page_height (float): The height of the page in inches.
            raster_dpi (int): The DPI for rasterizing the PDF pages. Default is 202.
            doc_name (str): The name of the document to print.
        """
        images = convert_from_bytes(
            pdf_file_io,
            poppler_path=self.poppler_path,
            dpi=raster_dpi,
        )

        self.print_images(
            images=images,
            page_width=page_width,
            page_height=page_height,
            doc_name=doc_name,
        )

    def _rotate_image(
        self,
        image: Image.Image,
        angle: float,
        expand: bool = True,
    ) -> Image.Image:
        """
        Rotate an image by a specified angle.
        Args:
            image (Image.Image): The image to rotate.
            angle (float): The angle to rotate the image, in degrees.
            expand (bool): Whether to expand the output image to hold the whole rotated image.
        Returns:
            Image.Image: The rotated image.
        """
        return image.rotate(angle, expand=expand)

    def _make_portrait(
        self,
        image: Image.Image,
    ) -> Image.Image:
        """
        Rotate an image to portrait orientation if it is in landscape.
        Args:
            image (Image.Image): The image to rotate.
        """
        if image.width > image.height:
            return self._rotate_image(image, angle=90)
        return image

    def _make_landscape(
        self,
        image: Image.Image,
    ) -> Image.Image:
        """
        Rotate an image to landscape orientation if it is in portrait.
        Args:
            image (Image.Image): The image to rotate.
        """
        if image.height > image.width:
            return self._rotate_image(image, angle=90)
        return image

    def _adjust_orientation(
        self,
        image: Image.Image,
    ) -> Image.Image:
        """
        Adjust the orientation of an image based on the printerHandler's orientation setting.
        Args:
            image (Image.Image): The image to adjust.
        """
        if self.orientation == "portrait":
            return self._make_portrait(image)
        elif self.orientation == "landscape":
            return self._make_landscape(image)
        else:
            raise ValueError(
                "Invalid orientation setting. Use 'portrait' or 'landscape'."
            )

    def _fit_to_page(
        self,
        image: Image.Image,
    ) -> Image.Image:
        """
        Resize an image to fit within the page dimensions while maintaining aspect ratio.
        Args:
            image (Image.Image): The image to resize.
        """
        # Calculate the maximum width and height based on margins
        max_width = (
            self.page_width - self.margin_left - self.margin_right
        ) * self.raster_dpi  # Assuming 300 DPI
        max_height = (
            self.page_height - self.margin_top - self.margin_bottom
        ) * self.raster_dpi  # Assuming 300 DPI

        # Get current image size
        img_width, img_height = image.size

        # Calculate scaling factor
        width_ratio = max_width / img_width
        height_ratio = max_height / img_height
        scaling_factor = min(width_ratio, height_ratio)

        # Calculate new size
        new_width = int(img_width * scaling_factor)
        new_height = int(img_height * scaling_factor)

        return image.resize((new_width, new_height), Image.LANCZOS)

    def get_print_queue(self) -> list[dict]:
        """Get the current print queue for the configured printer.

        Returns:
            list[dict]: A list of dictionaries containing information about each job in the queue.
                Each dictionary contains:
                - job_id (int): The unique identifier for the print job
                - document (str): The name of the document being printed
                - status (str): The current status of the job
                - user (str): The username who submitted the job
                - pages (int): Number of pages in the document
                - size (int): Size of the print job in bytes
                - submitted (str): Time when the job was submitted
                - priority (int): Priority of the print job
        """
        try:
            # Open the printer
            printer_handle = win32print.OpenPrinter(self.printer_name)

            # Get all jobs in the queue (level 2 provides detailed information)
            jobs = win32print.EnumJobs(printer_handle, 0, -1, 2)

            # Convert job information to a list of dictionaries
            queue_items = []
            for job in jobs:
                queue_items.append(
                    {
                        "job_id": job["JobId"],
                        "document": job.get("pDocument", "Unknown Document"),
                        "status": self._get_job_status_string(job.get("Status", 0)),
                        "user": job.get("pUserName", "Unknown User"),
                        "pages": job.get("TotalPages", 0),
                        "size": job.get("Size", 0),
                        "submitted": job.get("Submitted", "Unknown Time"),
                        "priority": job.get("Priority", 0),
                    }
                )
                print(f"{job}\n\n")

            # Close the printer handle
            win32print.ClosePrinter(printer_handle)

            return queue_items

        except Exception as e:
            raise Exception(f"Failed to retrieve print queue: {str(e)}")

    def _get_job_status_string(self, status_code: int) -> str:
        """Convert numeric job status code to a human-readable string.

        Args:
            status_code (int): The numeric status code from the print job.

        Returns:
            str: A human-readable status string.
        """
        status_map = {
            0x00000000: "Ready",
            0x00000001: "Paused",
            0x00000002: "Error",
            0x00000004: "Deleting",
            0x00000008: "Spooling",
            0x00000010: "Printing",
            0x00000020: "Offline",
            0x00000040: "Out of Paper",
            0x00000080: "Printed",
            0x00000100: "Deleted",
            0x00000200: "Blocked",
            0x00000400: "User Intervention Required",
            0x00000800: "Restarting",
            0x00001000: "Completed",
            0x00002000: "Retained",
        }

        # Check for each status flag (jobs can have multiple status flags)
        statuses = []
        for code, name in status_map.items():
            if status_code & code:
                statuses.append(name)

        return ", ".join(statuses) if statuses else f"Unknown: {status_code}"

    def purge_print_queue(self) -> dict:
        """Purge (delete) all print jobs from the printer queue.

        This operation will cancel and remove all pending print jobs from the queue.
        Use with caution as this cannot be undone.

        Note: This operation requires administrator privileges. If you receive an
        "Access is denied" error, run the application as administrator.

        Returns:
            dict: Result of the operation with status and message
                - success (bool): True if operation succeeded
                - message (str): Description of the result
                - jobs_purged (int): Number of jobs that were in the queue
        """
        try:
            # Get current queue to count jobs
            queue_before = self.get_print_queue()
            job_count = len(queue_before)

            # Try opening printer with explicit PRINTER_ACCESS_ADMINISTER rights
            # PRINTER_ACCESS_ADMINISTER = 0x00000004
            # Define printer defaults with access rights
            pDefaults = {
                "pDatatype": None,
                "pDevMode": None,
                "DesiredAccess": 0x000F000C,  # PRINTER_ALL_ACCESS (STANDARD_RIGHTS_REQUIRED | PRINTER_ACCESS_ADMINISTER | PRINTER_ACCESS_USE)
            }

            try:
                printer_handle = win32print.OpenPrinter(self.printer_name, pDefaults)
            except Exception as open_error:
                # If that fails, try without explicit access rights
                printer_handle = win32print.OpenPrinter(self.printer_name)

            try:
                # Use PRINTER_CONTROL_PURGE to delete all jobs
                # Command value: 3 = PRINTER_CONTROL_PURGE
                win32print.SetPrinter(
                    printer_handle,
                    0,  # Level
                    None,  # pPrinter
                    3,  # PRINTER_CONTROL_PURGE
                )

                return {
                    "success": True,
                    "message": f"Successfully purged {job_count} job(s) from queue",
                    "jobs_purged": job_count,
                }
            finally:
                # Always close the printer handle
                win32print.ClosePrinter(printer_handle)

        except Exception as e:
            error_message = str(e)

            # Check if this is an access denied error
            if "Access is denied" in error_message or "(5," in error_message:
                # Try the alternative method of deleting jobs individually
                alt_result = self.delete_all_jobs()
                if alt_result["success"]:
                    return alt_result

                return {
                    "success": False,
                    "message": f"Access denied using SetPrinter. Tried deleting jobs individually: {alt_result['message']}. The printer may have specific security settings preventing purge operations.",
                    "jobs_purged": 0,
                    "jobs_deleted": alt_result.get("jobs_deleted", 0),
                    "error_code": 5,
                }

            return {
                "success": False,
                "message": f"Failed to purge print queue: {error_message}",
                "jobs_purged": 0,
            }

    def delete_print_job(self, job_id: int) -> dict:
        """Delete a specific print job from the queue.

        This may work without administrator privileges if you own the job,
        but requires admin rights to delete jobs owned by other users.

        Args:
            job_id (int): The job ID to delete

        Returns:
            dict: Result of the operation with status and message
                - success (bool): True if operation succeeded
                - message (str): Description of the result
        """
        try:
            printer_handle = win32print.OpenPrinter(self.printer_name)

            try:
                # JOB_CONTROL_DELETE = 5
                win32print.SetJob(
                    printer_handle,
                    job_id,
                    0,  # Level
                    None,  # pJob
                    5,  # JOB_CONTROL_DELETE
                )

                return {
                    "success": True,
                    "message": f"Successfully deleted job {job_id}",
                    "job_id": job_id,
                }
            finally:
                win32print.ClosePrinter(printer_handle)

        except Exception as e:
            error_message = str(e)

            # Check if this is an access denied error
            if "Access is denied" in error_message or "(5," in error_message:
                return {
                    "success": False,
                    "message": f"Access denied. You may need administrator privileges to delete job {job_id} (owned by another user).",
                    "job_id": job_id,
                    "error_code": 5,
                }

            return {
                "success": False,
                "message": f"Failed to delete job {job_id}: {error_message}",
                "job_id": job_id,
            }

    def delete_all_jobs(self) -> dict:
        """Delete all print jobs from the queue by deleting them individually.

        This is an alternative to purge_print_queue() that may work better
        in some permission scenarios. It attempts to delete each job individually.

        Returns:
            dict: Result of the operation with status and message
                - success (bool): True if all jobs were deleted
                - message (str): Description of the result
                - jobs_deleted (int): Number of jobs successfully deleted
                - jobs_failed (int): Number of jobs that failed to delete
        """
        try:
            # Get current queue
            queue = self.get_print_queue()

            if not queue:
                return {
                    "success": True,
                    "message": "No jobs in queue to delete",
                    "jobs_deleted": 0,
                    "jobs_failed": 0,
                }

            deleted_count = 0
            failed_count = 0
            failed_jobs = []

            # Try to delete each job individually
            for job in queue:
                result = self.delete_print_job(job["job_id"])
                if result["success"]:
                    deleted_count += 1
                else:
                    failed_count += 1
                    failed_jobs.append(job["job_id"])

            if failed_count == 0:
                return {
                    "success": True,
                    "message": f"Successfully deleted all {deleted_count} job(s)",
                    "jobs_deleted": deleted_count,
                    "jobs_failed": 0,
                }
            elif deleted_count > 0:
                return {
                    "success": False,
                    "message": f"Deleted {deleted_count} job(s), failed to delete {failed_count} job(s). Failed job IDs: {failed_jobs}",
                    "jobs_deleted": deleted_count,
                    "jobs_failed": failed_count,
                    "failed_job_ids": failed_jobs,
                }
            else:
                return {
                    "success": False,
                    "message": f"Failed to delete any jobs. You may need administrator privileges.",
                    "jobs_deleted": 0,
                    "jobs_failed": failed_count,
                    "failed_job_ids": failed_jobs,
                }

        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to delete jobs: {str(e)}",
                "jobs_deleted": 0,
                "jobs_failed": 0,
            }

    def check_printer_permissions(self) -> dict:
        """Check what permissions we have on the printer.

        Returns:
            dict: Information about printer access rights
        """
        try:
            import win32security
            import ntsecuritycon

            # Try to get printer security descriptor
            printer_handle = win32print.OpenPrinter(self.printer_name)

            try:
                # Get printer information including security descriptor
                printer_info = win32print.GetPrinter(printer_handle, 2)

                permissions = {
                    "printer_name": self.printer_name,
                    "server_name": printer_info.get("pServerName", "Local"),
                    "driver_name": printer_info.get("pDriverName", "Unknown"),
                    "status": printer_info.get("Status", 0),
                    "attributes": printer_info.get("Attributes", 0),
                }

                # Try different access levels
                access_tests = {
                    "PRINTER_ACCESS_USE": 0x00000008,
                    "PRINTER_ACCESS_ADMINISTER": 0x00000004,
                    "PRINTER_ALL_ACCESS": 0x000F000C,
                }

                permissions["access_levels"] = {}
                for name, access_code in access_tests.items():
                    try:
                        test_defaults = {
                            "pDatatype": None,
                            "pDevMode": None,
                            "DesiredAccess": access_code,
                        }
                        test_handle = win32print.OpenPrinter(
                            self.printer_name, test_defaults
                        )
                        win32print.ClosePrinter(test_handle)
                        permissions["access_levels"][name] = "✓ Granted"
                    except Exception as e:
                        permissions["access_levels"][name] = f"✗ Denied: {str(e)}"

                return {
                    "success": True,
                    "permissions": permissions,
                }

            finally:
                win32print.ClosePrinter(printer_handle)

        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to check permissions: {str(e)}",
            }

    def flush_printer(self) -> dict:
        """Flush the printer buffer and clear any pending data.

        This uses the FlushPrinter function to clear the printer's internal buffer.
        This is different from purging the queue - it clears data that has already
        been sent to the printer but not yet processed.

        Returns:
            dict: Result of the operation with status and message
                - success (bool): True if operation succeeded
                - message (str): Description of the result
        """
        try:
            # Open the printer
            printer_handle = win32print.OpenPrinter(self.printer_name)

            try:
                # Flush the printer buffer
                # FlushPrinter takes: handle, buffer, buffer_size
                # To just flush without reading data, pass empty bytes buffer
                win32print.FlushPrinter(
                    printer_handle, b"", 0  # Empty bytes buffer  # Buffer size
                )

                return {
                    "success": True,
                    "message": "Successfully flushed printer buffer",
                }
            finally:
                # Always close the printer handle
                win32print.ClosePrinter(printer_handle)

        except Exception as e:
            return {"success": False, "message": f"Failed to flush printer: {str(e)}"}

    def restart_print_spooler(self) -> dict:
        """Restart the Windows Print Spooler service.

        This stops and then starts the Print Spooler service (spoolsv.exe).
        This can help resolve issues with stuck print jobs or printer communication problems.

        Note: This operation requires administrator privileges.

        Returns:
            dict: Result of the operation with status and message
                - success (bool): True if operation succeeded
                - message (str): Description of the result
                - service_status (str): Final status of the service
        """
        try:
            import win32service
            import win32serviceutil
            import time

            service_name = "Spooler"

            try:
                # Stop the Print Spooler service
                win32serviceutil.StopService(service_name)

                # Wait for service to stop (max 30 seconds)
                timeout = 30
                start_time = time.time()
                while time.time() - start_time < timeout:
                    status = win32serviceutil.QueryServiceStatus(service_name)[1]
                    # SERVICE_STOPPED = 1
                    if status == 1:
                        break
                    time.sleep(0.5)
                else:
                    return {
                        "success": False,
                        "message": "Timeout waiting for Print Spooler service to stop",
                        "service_status": "stopping",
                    }

                # Small delay to ensure service is fully stopped
                time.sleep(1)

                # Start the Print Spooler service
                win32serviceutil.StartService(service_name)

                # Wait for service to start (max 30 seconds)
                start_time = time.time()
                while time.time() - start_time < timeout:
                    status = win32serviceutil.QueryServiceStatus(service_name)[1]
                    # SERVICE_RUNNING = 4
                    if status == 4:
                        return {
                            "success": True,
                            "message": "Print Spooler service restarted successfully",
                            "service_status": "running",
                        }
                    time.sleep(0.5)

                return {
                    "success": False,
                    "message": "Timeout waiting for Print Spooler service to start",
                    "service_status": "starting",
                }

            except Exception as service_error:
                error_msg = str(service_error)

                # Check for specific error codes
                if "Access is denied" in error_msg or "(5," in error_msg:
                    return {
                        "success": False,
                        "message": "Access denied. Administrator privileges required to restart Print Spooler service.",
                        "service_status": "unknown",
                        "error_code": 5,
                    }

                return {
                    "success": False,
                    "message": f"Failed to restart Print Spooler service: {error_msg}",
                    "service_status": "unknown",
                }

        except ImportError:
            return {
                "success": False,
                "message": "Required module 'pywin32' not available for service control",
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Unexpected error restarting Print Spooler: {str(e)}",
            }

    def pause_printer(self) -> dict:
        """Pause the printer (stop processing all jobs).

        Returns:
            dict: Result of the operation with status and message
        """
        try:
            printer_handle = win32print.OpenPrinter(self.printer_name)
            try:
                # PRINTER_CONTROL_PAUSE = 1
                win32print.SetPrinter(printer_handle, 0, None, 1)
                return {"success": True, "message": "Printer paused successfully"}
            finally:
                win32print.ClosePrinter(printer_handle)
        except Exception as e:
            return {"success": False, "message": f"Failed to pause printer: {str(e)}"}

    def resume_printer(self) -> dict:
        """Resume the printer (continue processing jobs).

        Returns:
            dict: Result of the operation with status and message
        """
        try:
            printer_handle = win32print.OpenPrinter(self.printer_name)
            try:
                # PRINTER_CONTROL_RESUME = 2
                win32print.SetPrinter(printer_handle, 0, None, 2)
                return {"success": True, "message": "Printer resumed successfully"}
            finally:
                win32print.ClosePrinter(printer_handle)
        except Exception as e:
            return {"success": False, "message": f"Failed to resume printer: {str(e)}"}

    def print_from_url(self, url: str, doc_name: str = None) -> dict:
        """Download a file from a URL and print it.

        This method downloads a file from the given URL, determines if it's a PDF or image,
        and routes it to the appropriate printing method.

        Args:
            url (str): The URL of the file to download and print
            doc_name (str, optional): Custom document name. If not provided, will be extracted from URL

        Returns:
            dict: Result of the operation with status and message
                - success (bool): True if operation succeeded
                - message (str): Description of the result
                - file_type (str): The detected file type (pdf, image, or unknown)
                - doc_name (str): The document name used for printing
        """
        temp_file_path = None

        try:
            # Download the file
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            # Get content type from headers
            content_type = response.headers.get("content-type", "").lower()

            # Extract filename from URL if doc_name not provided
            if not doc_name:
                # Try to get filename from URL
                doc_name = url.split("/")[-1].split("?")[0]
                if not doc_name:
                    doc_name = "Downloaded Document"

            # Get file extension from URL or content type
            file_extension = None
            if "." in doc_name:
                file_extension = doc_name.split(".")[-1].lower()

            # Determine file type
            is_pdf = False
            is_image = False

            # Check content type
            if "pdf" in content_type:
                is_pdf = True
            elif any(
                img_type in content_type
                for img_type in [
                    "image/jpeg",
                    "image/jpg",
                    "image/png",
                    "image/gif",
                    "image/bmp",
                    "image/tiff",
                ]
            ):
                is_image = True

            # Check file extension if content type didn't help
            if not is_pdf and not is_image and file_extension:
                if file_extension == "pdf":
                    is_pdf = True
                elif file_extension in [
                    "jpg",
                    "jpeg",
                    "png",
                    "gif",
                    "bmp",
                    "tiff",
                    "tif",
                ]:
                    is_image = True

            # If still uncertain, try to detect from file content
            if not is_pdf and not is_image:
                file_content = response.content
                # Check PDF magic bytes
                if file_content.startswith(b"%PDF"):
                    is_pdf = True
                # Check common image magic bytes
                elif file_content.startswith(b"\xff\xd8\xff"):  # JPEG
                    is_image = True
                elif file_content.startswith(b"\x89PNG"):  # PNG
                    is_image = True
                elif file_content.startswith(b"GIF8"):  # GIF
                    is_image = True
                elif file_content.startswith(b"BM"):  # BMP
                    is_image = True

            # Route to appropriate printing method
            if is_pdf:
                # Print PDF from bytes
                self.print_pdf_io(
                    pdf_file_io=response.content,
                    page_width=self.page_width,
                    page_height=self.page_height,
                    raster_dpi=self.raster_dpi,
                    doc_name=doc_name,
                )

                return {
                    "success": True,
                    "message": f"Successfully printed PDF document: {doc_name}",
                    "file_type": "pdf",
                    "doc_name": doc_name,
                }

            elif is_image:
                # Load image from bytes and print
                image = Image.open(BytesIO(response.content))
                self.print_images(
                    images=[image],
                    page_width=self.page_width,
                    page_height=self.page_height,
                    doc_name=doc_name,
                )

                return {
                    "success": True,
                    "message": f"Successfully printed image document: {doc_name}",
                    "file_type": "image",
                    "doc_name": doc_name,
                }

            else:
                return {
                    "success": False,
                    "message": f"Could not determine file type for: {doc_name}. Content-Type: {content_type}",
                    "file_type": "unknown",
                    "doc_name": doc_name,
                }

        except requests.RequestException as e:
            return {
                "success": False,
                "message": f"Failed to download file from URL: {str(e)}",
                "url": url,
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to print from URL: {str(e)}",
                "url": url,
            }

        finally:
            # Clean up temp file if it was created
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except:
                    pass  # Ignore cleanup errors


class M479fdw:
    """Handler for HP LaserJet Pro M479fdw printer-specific operations.

    Attributes:
        printer_ip (str): The IP address of the printer.
        session_id (str): The session ID (sid) cookie value for authentication.
    """

    def __init__(
        self, printer_ip: str, session_id: str = None, auto_get_session: bool = True
    ):
        """Initialize the M479fdw printer handler.

        Args:
            printer_ip (str): The IP address of the printer.
            session_id (str, optional): Pre-existing session ID. If not provided and
                auto_get_session is True, will automatically obtain one from the printer.
            auto_get_session (bool): If True and no session_id is provided, automatically
                obtains a session ID from the printer. Default is True.
        """
        self.printer_ip = printer_ip
        self.session_id = session_id

        # Disable SSL warnings since printer uses self-signed certificate
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # Automatically obtain session ID if not provided
        if not self.session_id and auto_get_session:
            result = self.get_session_id()
            if not result["success"]:
                print(
                    f"Warning: Failed to automatically obtain session ID: {result['message']}"
                )

    def get_session_id(self) -> dict:
        """Obtain a session ID from the printer by accessing its web interface.

        The HP printer automatically generates a session ID cookie when you access
        its web interface. This method captures that cookie for use in subsequent requests.

        Returns:
            dict: Result of the operation
                - success (bool): True if session ID was obtained
                - message (str): Description of the result
                - session_id (str): The session ID value (if successful)
        """
        try:
            # Create a new session to capture cookies
            session = requests.Session()

            # Access the printer's main web interface
            url = f"https://{self.printer_ip}/"

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:147.0) Gecko/20100101 Firefox/147.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Sec-GPC": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Pragma": "no-cache",
                "Cache-Control": "no-cache",
            }

            response = session.get(
                url,
                headers=headers,
                verify=False,  # Ignore SSL certificate verification
                timeout=10,
            )

            # Check if we received a session ID cookie
            if "sid" in session.cookies:
                sid = session.cookies["sid"]
                self.session_id = sid  # Store it in the instance

                return {
                    "success": True,
                    "message": "Successfully obtained session ID from printer",
                    "session_id": sid,
                }
            else:
                # Check if there are any other cookies that might be the session
                cookie_names = list(session.cookies.keys())

                if cookie_names:
                    return {
                        "success": False,
                        "message": f"No 'sid' cookie found. Available cookies: {cookie_names}",
                        "cookies": dict(session.cookies),
                    }
                else:
                    return {
                        "success": False,
                        "message": "No session cookies received from printer",
                    }

        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "message": f"Failed to connect to printer: {str(e)}",
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Unexpected error obtaining session ID: {str(e)}",
            }

    def powercycle(
        self, session_id: str = None, timeout: int = 300, poll_interval: int = 5
    ) -> dict:
        """Power cycle the printer and wait for it to come back online.

        This method sends a power cycle command to the printer via its web interface,
        then polls the printer until it responds successfully, indicating it's back online.

        Args:
            session_id (str, optional): Session ID for authentication. If not provided,
                uses the session_id from initialization.
            timeout (int): Maximum time in seconds to wait for printer to come back online.
                Default is 300 seconds (5 minutes).
            poll_interval (int): Time in seconds between polling attempts. Default is 5 seconds.

        Returns:
            dict: Result of the operation with status and timing information
                - success (bool): True if operation succeeded
                - message (str): Description of the result
                - power_cycle_sent (bool): Whether the power cycle command was sent successfully
                - came_back_online (bool): Whether the printer came back online
                - offline_duration (float): How long the printer was offline in seconds
                - total_duration (float): Total operation duration in seconds
        """
        start_time = time.time()

        # Use provided session_id or fall back to instance session_id
        sid = session_id or self.session_id

        if not sid:
            return {
                "success": False,
                "message": "No session ID provided. Cannot authenticate with printer.",
                "power_cycle_sent": False,
                "came_back_online": False,
            }

        # Prepare session with cookie
        session = requests.Session()
        session.cookies.set("sid", sid, domain=self.printer_ip, path="/")

        # Common headers
        base_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:147.0) Gecko/20100101 Firefox/147.0",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Sec-GPC": "1",
            "Referer": f"https://{self.printer_ip}/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
        }

        try:
            # Step 1: Send power cycle command
            power_cycle_url = f"https://{self.printer_ip}/ProductActions/PowerCycle"
            power_cycle_headers = base_headers.copy()
            power_cycle_headers.update(
                {
                    "Accept": "text/plain, */*",
                    "Origin": f"https://{self.printer_ip}",
                    "Priority": "u=0",
                }
            )

            try:
                print("Sending power cycle command to printer...")
                power_cycle_response = session.put(
                    power_cycle_url,
                    headers=power_cycle_headers,
                    verify=False,  # Ignore SSL certificate verification
                    timeout=10,
                )

                print(power_cycle_response)
                print(f"Status code: {power_cycle_response.status_code}")
                print("\n\n")

                if power_cycle_response.status_code not in [200, 202, 204]:
                    return {
                        "success": False,
                        "message": f"Power cycle command failed with status code: {power_cycle_response.status_code}",
                        "power_cycle_sent": False,
                        "came_back_online": False,
                        "status_code": power_cycle_response.status_code,
                    }

                power_cycle_sent_time = time.time()

            except requests.exceptions.RequestException as e:
                return {
                    "success": False,
                    "message": f"Failed to send power cycle command: {str(e)}",
                    "power_cycle_sent": False,
                    "came_back_online": False,
                }

            # Step 2: Wait a bit for printer to start shutting down
            time.sleep(10)

            # Step 3: Poll until printer comes back online
            check_url = f"https://{self.printer_ip}/DevMgmt/DiscoveryTree.xml"
            check_headers = base_headers.copy()
            check_headers["Accept"] = "application/xml, text/xml, */*"

            poll_start_time = time.time()
            attempts = 0

            print("Polling for printer to come back online...")
            while (time.time() - poll_start_time) < timeout:
                attempts += 1
                print(f"Poll attempt {attempts}...")
                try:
                    check_response = session.get(
                        check_url, headers=check_headers, verify=False, timeout=5
                    )

                    print(check_response.text)
                    print(
                        f"Poll attempt {attempts}: Status code {check_response.status_code}"
                    )
                    if check_response.status_code == 200:
                        # Printer is back online!
                        online_time = time.time()
                        offline_duration = online_time - power_cycle_sent_time
                        total_duration = online_time - start_time

                        return {
                            "success": True,
                            "message": f"Printer successfully power cycled and came back online after {offline_duration:.1f} seconds",
                            "power_cycle_sent": True,
                            "came_back_online": True,
                            "offline_duration": offline_duration,
                            "total_duration": total_duration,
                            "poll_attempts": attempts,
                        }

                except requests.exceptions.RequestException:
                    # Printer is still offline or starting up, this is expected
                    pass

                # Wait before next poll
                time.sleep(poll_interval)

            # Timeout reached
            total_duration = time.time() - start_time
            return {
                "success": False,
                "message": f"Printer did not come back online within {timeout} seconds",
                "power_cycle_sent": True,
                "came_back_online": False,
                "total_duration": total_duration,
                "poll_attempts": attempts,
                "timeout": timeout,
            }

        except Exception as e:
            total_duration = time.time() - start_time
            return {
                "success": False,
                "message": f"Unexpected error during power cycle: {str(e)}",
                "power_cycle_sent": False,
                "came_back_online": False,
                "total_duration": total_duration,
            }


if __name__ == "__main__":
    # Test printerHandler
    print("=" * 80)
    print("Testing printerHandler...")
    print("=" * 80)

    printer = printerHandler(printer_name="PTS_Desktop_Printer")
    printer.get_device_properties()
    printer_queue = printer.get_print_queue()
    if not printer_queue:
        print("No jobs in the print queue.")
    else:
        for job in printer_queue:
            print(job)

    print("\n" + "=" * 80)
    print("Testing M479fdw - Automatic Session ID in __init__...")
    print("=" * 80)

    # Test 0: Automatically obtain session ID during initialization (default behavior)
    print("\nTest 0: Creating M479fdw instance (auto_get_session=True by default)")
    print("-" * 80)

    print(f"Creating printer instance for 172.16.2.175...")
    m479_printer_auto = M479fdw(printer_ip="172.16.2.175")

    if m479_printer_auto.session_id:
        print(f"\n✓ SUCCESS: Session ID automatically obtained during initialization")
        print(f"Session ID: {m479_printer_auto.session_id}")
    else:
        print(f"\n✗ FAILED: No session ID obtained")

    # Test 0b: Manually call get_session_id if needed
    print("\n" + "=" * 80)
    print("Test 0b: Manually refreshing session ID")
    print("-" * 80)

    if m479_printer_auto.session_id:
        old_sid = m479_printer_auto.session_id
        print(f"Old session ID: {old_sid}")

        session_result = m479_printer_auto.get_session_id()

        if session_result["success"]:
            print(f"New session ID: {session_result['session_id']}")
            print(f"Session IDs match: {old_sid == session_result['session_id']}")
        else:
            print(f"Failed to refresh: {session_result['message']}")

    # Test 1: Using the automatically obtained session ID for power cycle
    if m479_printer_auto.session_id:
        print("\n" + "=" * 80)
        print("Test 1: Power cycle using automatically obtained session ID")
        print("-" * 80)

        print(f"Using session ID: {m479_printer_auto.session_id}")
        print(
            f"Initiating power cycle for printer at {m479_printer_auto.printer_ip}..."
        )
        result = m479_printer_auto.powercycle(timeout=300, poll_interval=5)

        print(f"\nResult: {json.dumps(result, indent=2)}")

        if result["success"]:
            print(
                f"\n✓ SUCCESS: Printer came back online after {result['offline_duration']:.1f} seconds"
            )
        else:
            print(f"\n✗ FAILED: {result['message']}")

    # Test 2: Using a manually provided session ID (bypasses auto-get)
    print("\n" + "=" * 80)
    print("Test 2: Using manually provided session ID (auto-get skipped)")
    print("-" * 80)
    m479_printer_manual = M479fdw(
        printer_ip="172.16.2.175",
        session_id="s4bab98b4-b7c1d286917ed47669f38fdf6f0c7ced",
    )

    print(f"Using manually provided session ID: {m479_printer_manual.session_id}")
    print("(Auto session retrieval was skipped because session_id was provided)")

    # Test 3: Creating instance with auto_get_session=False
    print("\n" + "=" * 80)
    print("Test 3: Creating instance with auto_get_session=False")
    print("-" * 80)

    m479_printer_no_auto = M479fdw(printer_ip="172.16.2.175", auto_get_session=False)

    if m479_printer_no_auto.session_id:
        print(f"Session ID: {m479_printer_no_auto.session_id}")
    else:
        print("✓ No session ID obtained (as expected with auto_get_session=False)")
        print("You can manually provide one or call get_session_id() later")

    # Test 4: Using a random/invalid session ID (should fail authentication)
    print("\n" + "=" * 80)
    print("Test 4: Using random/invalid session ID (expected to fail)")
    print("-" * 80)

    import random
    import string

    random_sid = "s" + "".join(
        random.choices(string.ascii_lowercase + string.digits, k=44)
    )

    m479_printer_invalid = M479fdw(printer_ip="172.16.2.175", session_id=random_sid)

    print(f"Testing with random session ID: {random_sid}")
    print(f"Initiating power cycle for printer at {m479_printer_invalid.printer_ip}...")
    result_invalid = m479_printer_invalid.powercycle(timeout=30, poll_interval=3)

    print(f"\nResult: {json.dumps(result_invalid, indent=2)}")

    if result_invalid["success"]:
        print(f"\n✓ SUCCESS (unexpected): Printer came back online")
    else:
        print(f"\n✗ FAILED (as expected): {result_invalid['message']}")
