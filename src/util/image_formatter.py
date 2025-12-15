from PIL import Image
from io import BytesIO
from urllib.request import urlopen
from pathlib import Path
import sys, os, requests

if __name__ != "__main__":
    ROOT_PATH = Path(__file__).resolve().parent.parent.parent
    sys.path.append(str(ROOT_PATH))
    from src.util.independant_logger import Logger

    log = Logger(
        log_name="image_formatter",
        log_file="image_formatter.log",
        log_dir="logs",
        log_level=20,
        file_level=20,
        console_level=10,
    ).get_logger()


class ImageManip:
    def __init__(
        self,
        image_path: str = None,
        image_url: str = None,
        image_io: BytesIO = None,
        file_name: str = None,
        file_format: str = None,
        file_mimetype: str = None,
    ):
        if not image_path and not image_url and not image_io:
            raise ValueError(
                "Either image_path, image_url or image_io must be provided."
            )

        self.save_dir = "static/images"
        self.tmp_dir = "tmp"
        self.image_path = image_path
        self.image_url = image_url
        self.image_io = image_io
        self.image_pil = None
        self.img_width = None
        self.img_height = None
        self.file_size = None
        self.file_name = file_name
        self.file_format = file_format
        self.file_mimetype = file_mimetype
        log.debug(f"ImageManip initialized.")

    def load_image(self):
        """
        Loads an image from the provided path, URL, or BytesIO object.
        Returns:
            PIL.Image: object
        """
        if self.image_path:
            log.info(f"Loading image from path: {self.image_path}")
            try:
                self.image_pil = Image.open(self.image_path)
                self.image_pil.load()
                log.debug(f"Image loaded from path: {self.image_path}")
                return self.image_pil
            except Exception as e:
                log.error(
                    f"Error loading image from path {self.image_path}: {e}",
                    exc_info=True,
                )

        elif self.image_url:
            log.info(f"Loading image from URL: {self.image_url}")
            try:
                self._check_file_size(image_url=self.image_url)
                self._download_image(image_url=self.image_url)
                self._load_image_from_io(image_io=self.image_io)
                log.debug(f"Image loaded from URL: {self.image_url}")
                return self.image_pil
            except Exception as e:
                log.error(
                    f"Error loading image from URL {self.image_url}: {e}", exc_info=True
                )

        elif self.image_io:
            log.info(f"Loading image from BytesIO object.")
            try:
                self.image_pil = Image.open(self.image_io)
                self.image_pil.load()
                log.debug(f"Image loaded from BytesIO object.")
                return self.image_pil
            except Exception as e:
                log.error(f"Error loading image from BytesIO: {e}", exc_info=True)

        log.error(f"Failed to load image from all sources.")
        raise ValueError("No valid image source provided or failed to load image.")

    def close_image(self):
        if self.image_pil:
            self.image_pil.close()
            log.debug("Image closed.")
        else:
            log.debug("No image to close.")

    def _check_file_size(self, max_size_mb=20, image_url: str = None):
        if not image_url or max_size_mb <= 0:
            raise ValueError(
                "image_url must be provided and max_size_mb must be greater than 0."
            )
        max_size = max_size_mb * 1024 * 1024  # Convert MB to bytes
        file_size = None

        try:
            response = requests.head(image_url, allow_redirects=True)
            content_length = response.headers.get("content-length")
            file_size = int(content_length)
            self.file_size = file_size
            if content_length and file_size > max_size:
                raise ValueError(
                    f"Image size {content_length} bytes exceeds the maximum allowed size of {str(max_size)} bytes."
                )
        except Exception as e:
            log.error(f"Error checking image size for {image_url}: {e}", exc_info=True)
            raise

        return file_size

    def _download_image(self, image_url: str = None):
        if not image_url:
            raise ValueError("image_url must be provided.")
        try:
            response = urlopen(image_url)
            image_data = response.read()
            self._convert_data_to_io(data=image_data)
            log.debug(f"Image downloaded from URL: {image_url}")
            return self.image_io
        except Exception as e:
            log.error(f"Error downloading image from URL {image_url}: {e}", exc_info=True)
            raise
    
    def _convert_data_to_io(self, data: bytes = None):
        if not data:
            raise ValueError("data must be provided.")
        try:
            self.image_io = BytesIO(data)
            log.debug("BytesIO object created from data.")
            return self.image_io
        except Exception as e:
            log.error(f"Error creating BytesIO from data: {e}", exc_info=True)
            raise
    
    def _load_image_from_io(self, image_io: BytesIO = None):
        if not image_io:
            raise ValueError("image_io must be provided.")
        try:
            self.image_pil = Image.open(image_io)
            self.image_pil.load()
            log.debug("Image opened from BytesIO object.")
            return self.image_pil
        except Exception as e:
            log.error(f"Error opening image from BytesIO: {e}", exc_info=True)
            raise
    

class TerminalImageManip:
    def __init__(self, image_path: str = None, image_url: str = None):
        self.save_dir = "static/images"
        self.image_name = None
        self.image = None
        self.image_path = image_path
        self.image_url = image_url

    def load_image(self):
        if self.image_path:
            try:
                self.image = Image.open(self.image_path)
                self.image.load()
                print(f"Image loaded from path: {self.image_path}")
                return self.image
            except Exception as e:
                print(f"Error loading image from path {self.image_path}: {e}")

        if self.image_url:
            try:
                from urllib.request import urlopen

                response = urlopen(self.image_url)
                image_data = response.read()
                self.image = Image.open(BytesIO(image_data))
                self.image.load()
                print(f"Image loaded from URL: {self.image_url}")
                return self.image
            except Exception as e:
                print(f"Error loading image from URL {self.image_url}: {e}")

        if not self.image:
            message = """
No image loaded. Please provide a valid image path or URL.

Input: """
            url_path = input(message).strip()
            self.image_path = url_path
            self.image_url = url_path
            return self.load_image()

    def resize_image(self):
        if not self.image:
            print("No image loaded to resize. Please load an image first.")
            return self.load_image()

        cur_img_size = self.image.size
        message = """
Please input a new size for the image (pixel format). Input 'height' to set height first:

Width: """
        value = input(message).strip().lower()
        if value == "height":
            self.img_height = int(input("Height: ").strip())
            sug_width = int(cur_img_size[0] * (self.img_height / cur_img_size[1]))
            self.img_width = int(input(f"Width ({sug_width}): ").strip())
        else:
            self.img_width = int(value)
            sug_height = int(cur_img_size[1] * (self.img_width / cur_img_size[0]))
            message = f"Height ({sug_height}): "
            self.img_height = int(input(message).strip())

        resample_map = {
            "nearest": Image.NEAREST,
            "box": Image.BOX,
            "bilinear": Image.BILINEAR,
            "hamming": Image.HAMMING,
            "bicubic": Image.BICUBIC,
            "lanczos": Image.LANCZOS,
        }

        message = """
Please select a resampling filter (default is 'lanczos'):
nearest - Fastest, lowest quality
box - Fast, low quality
bilinear - Balanced speed and quality
hamming - Similar to bilinear, better for edges
bicubic - Slow, high quality
lanczos - Slower, very high quality

Input: """
        input_filter = input(message).strip().lower()
        resample_filter = resample_map.get(input_filter, Image.LANCZOS)

        # Resize the image
        self.image = self.image.resize(
            (self.img_width, self.img_height), resample_filter
        )
        print(f"Image resized to {self.img_width}x{self.img_height} pixels.")
        return self.image

    def save_image(self):
        def sel_format():
            message = """
Please select a file format to save the image:
png - Portable Network Graphics
jpg - JPEG Image
webp - WebP Image
bmp - Bitmap Image
gif - Graphics Interchange Format

Input: """
            file_format = input(message).strip().lower()
            if file_format not in ["png", "jpg", "webp", "bmp", "gif"]:
                print("Invalid format selected.")
                file_format = sel_format()
            return file_format

        if hasattr(self, "image"):
            message = """
Please input the name for the image, or `cd` to change the directory:

Input: """
            image_name = input(message).strip()

            if image_name == "cd":
                new_dir = input("Enter the new directory path: ").strip()
                if not os.path.isdir(new_dir):
                    print(f"Directory {new_dir} does not exist. Creating it.")
                    os.makedirs(new_dir)

                self.save_dir = new_dir
                print(f"Changed directory to {new_dir}")
                return self.save_image()
            elif not image_name:
                print("No name provided.")
                return self.save_image()
            else:
                self.image_name = image_name

            if not os.path.exists(self.save_dir):
                print(f"Directory {self.save_dir} does not exist. Creating it.")
                os.makedirs(self.save_dir)

            self.file_format = sel_format()
            self.save_path = os.path.join(
                self.save_dir, f"{self.image_name}.{self.file_format}"
            )

            try:
                print(f"Saving image to {self.save_path}...")
                self.image.save(self.save_path, self.file_format.upper())
                print(f"Image saved to {self.save_path}")
            except OSError as e:
                print(f"Error saving image: {e}. Converting to RGB and retrying...")
                try:
                    rgb_image = self.image.convert("RGB")
                    rgb_image.save(self.save_path, self.file_format.upper())
                    print(f"Image saved to {self.save_path} after conversion to RGB.")
                except Exception as e:
                    print(f"Failed to save image after conversion: {e}", exc_info=True)
            except Exception as e:
                print(f"Error saving image to {self.save_path}: {e}", exc_info=True)
        else:
            print("No image loaded to save. Please load an image first.")
            return self.load_image()

    def _sel_map(self, value):
        map = {
            "load": self.load_image,
            "resize": self.resize_image,
            "save": self.save_image,
            "close": (
                self.image.close if self.image else lambda: print("No image to close.")
            ),
            "exit": sys.exit,
        }
        return map.get(value, lambda: print("Invalid command. Please try again."))()

    def run_terminal(self):
        while True:
            message = """
========== Image Manipulation Menu ==========
Please select an option:
load - Load image from path or URL
resize - Resize an image to a specific size
save - Save the image to a file
close - Close the current image
exit - Exit the program

Input: """
            value = input(message).lower().strip()
            self._sel_map(value)


if __name__ == "__main__":
    # Example usage
    img = TerminalImageManip()
    img.run_terminal()
