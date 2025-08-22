from PIL import Image
from io import BytesIO
from urllib.request import urlopen
import sys, os


class ImageManip:
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
            self.image_width = int(input(f"Width ({sug_width}): ").strip())
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

    def run(self):
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
    img = ImageManip()
    img.run()
