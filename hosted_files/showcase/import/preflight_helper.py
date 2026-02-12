#!/usr/bin/env python3

import logging, os, shutil, time

logger = logging.getLogger(__name__)

class PreflightHelper:
    def __init__(self):
        self.log_tracker = []

    def verify_tuple(func):
        def wrapper(*args, **kwards):
            if not isinstance(args[1], tuple) or len(args[1]) != 2:
                logger.error("Target size must be a tuple of (width, height).")
                raise ValueError("Target size must be a tuple of (width, height).")
            return func(*args, **kwards)

        return wrapper

    def verify_float(func):
        def wrapper(*args, **kwards):
            if not isinstance(args[1], float):
                logger.error("Scale factor must be a float.")
                raise ValueError("Scale factor must be a float.")
            return func(*args, **kwards)

        return wrapper

    def verify_path(func):
        def wrapper(*args, **kwards):
            path = args[1]
            logger.debug(f"Verifying path: {path}")
            
            if not isinstance(path, str):
                logger.error("Path must be a string.")
                raise ValueError("Path must be a string.")

            if not os.path.exists(args[1]):
                logger.error(f"Path does not exist: {args[1]}")
                raise FileNotFoundError(f"Path does not exist: {args[1]}")
            return func(*args, **kwards)

        return wrapper

    def remove_file(self, file_path) -> bool:
        """
        Removes the specified file if it exists.
        #### Args:
            - file_path (str): The path to the file to be removed.
        #### Logs:
            - Info: When the file removal process starts and completes.
            - Debug: If the file does not exist.
        """
        logger.info(f"Removing file: {file_path}")

        try:
            os.remove(file_path)
            logger.info(f"File {file_path} has been removed.")
            return True
        except FileNotFoundError:
            logger.warning(f"File {file_path} does not exist.")
            return True
        except OSError as e:
            logger.error(f"Error removing file {file_path}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error removing file {file_path}: {e}")
            raise

    @verify_path
    def move_file(self, current_path: str, target_path: str) -> bool:
        """
        Move the image from the current path to the target path.
        If the target path already exists, it will be overwritten.
        Args:
            current_path (str): The current file path of the image.
            target_path (str): The target file path where the image should be moved.
        Returns:
            bool: True if the image was moved successfully, False otherwise.
        """
        logger.info(f"Moving image from {current_path} to {target_path}")
        if os.path.exists(target_path):
            self.remove_file(target_path)

        try:
            os.rename(current_path, target_path)
            logger.info(f"Image moved from {current_path} to {target_path}")
            return True
        except OSError as e:
            logger.error(
                f"Error moving image from {current_path} to {target_path} - {e}"
            )
            return False
        except Exception as e:
            raise Exception(
                f"Unexpected error moving image from {current_path} to {target_path} - {e}"
            )

    @verify_path
    def copy_file(self, current_path: str, target_path: str) -> bool:
        """
        Copy the image from the current path to the target path.
        If the target path already exists, it will be overwritten.
        Args:
            current_path (str): The current file path of the image.
            target_path (str): The target file path where the image should be copied.
        Returns:
            bool: True if the image was copied successfully, False otherwise.
        Raises:
            ValueError: If the current path is not a string or does not exist.
            FileNotFoundError: If the current path does not exist.
        """
        if os.path.exists(target_path):
            self.remove_file(target_path)

        try:
            shutil.copy2(current_path, target_path)
            logger.info(f"Image copied from {current_path} to {target_path}")
            return True
        except OSError as e:
            logger.error(
                f"Error copying image from {current_path} to {target_path} - {e}"
            )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error copying image from {current_path} to {target_path} - {e}"
            )
            raise

    def check_done_transfer(self, path: str, count=0) -> bool | str:
        """
        Check if the file is a temporary file or if it exists.
        Determinse if the file is a temporary file by checking if it contains ".~#~".
        If the file is a temporary file, wait and check again.
        If the file does not exist after 5 attempts, return False.
        Args:
            path (str): The path to the file.
            count (int): The number of attempts to check the file.
        Returns:
            bool: False if the file hasn't finished transferring after 5 attempts.
            str: The path to the file if it exists.

        """
        if ".~#~" in path:
            logger.debug(f"File {path} is a temporary file. Waiting.")
            file_path = path.replace(".~#~", "")
            time.sleep(1)
            return self.check_done_transfer(file_path, count)
        elif os.path.exists(path):
            logger.debug(f"File {path} exists.")
            return path
        else:
            if count < 5:
                time.sleep(1)
                count += 1
                return self.check_done_transfer(path, count)
            else:
                logger.debug(f"File {path} does not exist after 5 attempts.")
                return False

    def get_ar(self, xpix: int, ypix: int) -> float:
        """
        Calculate the aspect ratio of the image.

        Args:
            image (PIL.Image): The image object.

        Returns:
            float: The aspect ratio of the image.
        """
        if not xpix or not ypix:
            logger.error("Width or height is zero, cannot calculate aspect ratio.")
            return 0.0

        return xpix / ypix

    def check_rotation_by_ar(
        self,
        xpix: int,
        ypix: int,
        targ_xpix: int,
        targ_ypix: int,
    ) -> tuple:
        """
        Compare the given dimensions to the target aspect ratio, returns the dimensions
        that are closest to the target aspect ratio.
        Args:
            xpix (int): The width of the image.
            ypix (int): The height of the image.
            target_ar (float): The target aspect ratio.
            targ_xpix (int): The target width.
            targ_ypix (int): The target height.
        Returns:
            tuple: A tuple containing the dimensions that are closest to the target aspect ratio
            and the aspect ratio of the original dimensions.
        """

        if targ_xpix is None or targ_ypix is None:
            logger.error("No target dimensions provided.")
            raise ValueError("No target dimensions provided.")

        if xpix == 0 or ypix == 0:
            logger.error("Width or height is zero, cannot calculate aspect ratio.")
            raise ValueError("Width or height is zero, cannot calculate aspect ratio.")

        cur_ar = self.get_ar(xpix, ypix)
        
        target_ar = self.get_ar(targ_xpix, targ_ypix)
        rotated_targ_ar = self.get_ar(targ_ypix, targ_xpix)

        original_dif = abs(cur_ar - target_ar)
        rotated_dif = abs(cur_ar - rotated_targ_ar)

        logger.info(f"Original image size: ({xpix}, {ypix})")
        logger.info(f"Target size: ({targ_xpix}, {targ_ypix})")

        if original_dif <= rotated_dif:
            logger.debug(f"Original dimensions are closer, keep target aspect ratio.")
            return (targ_xpix, targ_ypix), target_ar
        else:
            logger.debug(f"Rotated dimensions are closer, rotate target aspect ratio.")
            logger.info(f"Rotating target dimensions to: ({targ_ypix}, {targ_xpix})")
            return (targ_ypix, targ_xpix), rotated_targ_ar

    def calc_scale_factor(image_size: tuple, target_size: tuple):
        """
        Calculate the scale factor to resize the image to the target size.

        Args:
            image_size (tuple): The current size of the image as (width, height).
            target_size (tuple): The target size as (width, height).

        Returns:
            float: The scale factor to resize the image.
        """
        for each in [image_size, target_size]:
            if not isinstance(each, tuple) or len(each) != 2:
                return None

        scale_factor = min(
            target_size[0] / image_size[0], target_size[1] / image_size[1]
        )
        return scale_factor

    def validate_image_size(self, image, target_size: tuple, allowed_var: int) -> bool:
        """
        Validate the size of the image against the target size.

        Args:
            image (PIL.Image): The image object.
            target_size (tuple): The target size as a tuple (width, height).
            allowed_var (int): The allowed variation in pixels.

        Returns:
            bool: True if the image size matches the target size, False otherwise.
        """
        if not isinstance(target_size, tuple) or len(target_size) != 2:
            self.log_tracker.append("Target size must be a tuple of (width, height).")
            logger.debug(self.log_tracker[-1])
            return False

        if allowed_var < 0:
            self.log_tracker.append("Allowed variation must be a non-negative integer.")
            logger.debug(self.log_tracker[-1])
            return False

        # Get the closest aspect ratio to target size
        target_size, target_ar = self.check_rotation_by_ar(
            image.width, image.height, *target_size
        )
        
        image_size = (image.width, image.height)

        # Calc max and min size
        max_size = (int(target_size[0]) + allowed_var, int(target_size[1]) + allowed_var)
        min_size = (int(target_size[0]) - allowed_var, int(target_size[1]) - allowed_var)

        logger.debug(
            f"Validating image size: {image_size} against target size: {target_size} "
            f"with allowed variation: {allowed_var}."
        )

        # Check if the image size is within the allowed variation
        if (
            image_size[0] <= max_size[0]
            and image_size[1] <= max_size[1]
            and image_size[0] >= min_size[0]
            and image_size[1] >= min_size[1]
        ):
            logger.debug(f"Image size {image_size} matches target size {target_size}.")
            return True

        # Image size is not within the allowed variation
        self.log_tracker.append(
            f"Image size {image_size} does not match target size {target_size}."
        )
        logger.debug(self.log_tracker[-1])
        return False

    def validate_image_ar(self, image, target_ar: float, allowed_var: float) -> bool:
        """
        Validate the aspect ratio of the image against the target aspect ratio.

        Args:
            image (PIL.Image): The image object.
            target_ar (float): The target aspect ratio.
            allowed_var (float): The allowed variation in aspect ratio.

        Returns:
            bool: True if the image aspect ratio matches the target aspect ratio, False otherwise.
        """
        if target_ar is None:
            self.log_tracker.append("Target aspect ratio is None.")
            logger.debug(self.log_tracker[-1])
            return False

        image_ar = self.get_ar(image.width, image.height)

        logger.debug(
            f"Validating image aspect ratio: {image_ar} against target aspect ratio: {target_ar}."
        )

        # Check if the image aspect ratio is within the allowed variation
        if abs(image_ar - target_ar) < allowed_var:
            logger.debug(
                f"Image aspect ratio {image_ar} matches target aspect ratio {target_ar}."
            )
            return True

        # Image aspect ratio is not within the allowed variation
        self.log_tracker.append(
            f"Image aspect ratio {image_ar} does not match target aspect ratio {target_ar}."
        )
        logger.debug(self.log_tracker[-1])
        return False
