#!/usr/bin/env python3

import sys, os, json, re, requests, logging, mimetypes
from flask import redirect, url_for, current_app
from flask_login import current_user
from colorama import Fore
from functools import wraps
from urllib.parse import urlparse
from pathlib import Path
from dotenv import load_dotenv

ROOT_PATH = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT_PATH / ".env")
MIN_USERNAME_LENGTH = int(os.getenv("MIN_USERNAME_LENGTH", 3))
MAX_USERNAME_LENGTH = int(os.getenv("MAX_USERNAME_LENGTH", 30))
MAX_NAME_LENGTH = int(os.getenv("MAX_NAME_LENGTH", 50))
MIN_PASSWORD_LENGTH = int(os.getenv("MIN_PASSWORD_LENGTH", 8))
MAX_PASSWORD_LENGTH = int(os.getenv("MAX_PASSWORD_LENGTH", 100))
DISC_GLOBAL_WARN_URL = os.getenv("DISC_GLOBAL_WARN_URL", "")


_logger = logging.getLogger(__name__)
_logger.setLevel(logging.DEBUG)
if not _logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    _logger.addHandler(handler)
    _logger.propagate = False
    _logger.info("Logging initialized for helpers.py")


def generate_token():
    """
    Generates a random API key using secrets.
    """
    import secrets

    return secrets.token_urlsafe(32)

def generate_password(length=16):
    """
    Generates a random password of the specified length using secrets.
    Args:
        length (int): The length of the password to generate. Default is 16.
    Returns:
        str: A randomly generated password.
    """
    import secrets
    import string

    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for i in range(length))

def hash_string(input_string: str, hash_type: str = "sha256") -> str:
    """
    Hashes a string using the specified hash type.
    Args:
        input_string (str): The string to hash.
        hash_type (str): The type of hash to use. Default is "sha256".
    Returns:
        str: The hashed string in hexadecimal format.
    Raises:
        ValueError: If an unsupported hash type is provided.
    """
    import hashlib

    if hash_type == "sha256":
        return hashlib.sha256(input_string.encode()).hexdigest()
    elif hash_type == "md5":
        return hashlib.md5(input_string.encode()).hexdigest()
    else:
        raise ValueError(f"Unsupported hash type: {hash_type}")

def create_disc_command_options():
    # https://discord.com/developers/docs/interactions/application-commands#application-command-object-application-command-option-structure

    inputs = [
        {
            "name": "Enter Option Name: ",
            "error": "Option Name cannot be empty",
            "check": lambda x: x != "",
            "type": str,
        },
        {
            "name": "Enter Option Description: ",
            "error": "Option Description cannot be empty",
            "check": lambda x: x != "",
            "type": str,
        },
        {
            "name": "Enter Option Type (1-11): ",
            "error": "Option Type must be between 1-9",
            "check": lambda x: x in [str(i) for i in range(1, 11)],
            "type": int,
        },
        {
            "name": "Is Option Required (Y/n): ",
            "error": "Option Required must be 'y' or 'n'",
            "check": lambda x: x.lower() in ["y", "n"],
            "type": bool,
        },
    ]

    flag = True

    option_list = []

    option_template = {
        "name": "option_name",
        "description": "option_description",
        "type": 3,
        "required": False,
    }

    choices_template = {"name": "choice_name", "value": "choice_value"}

    while flag:
        option_instance = option_template.copy()
        option_attributes = get_inputs(inputs)

        for i, attribute in enumerate(option_instance.keys()):
            option_instance[attribute] = option_attributes[i]

        flag2 = True
        while flag2:
            choice = input("Do you want to add a choice? (Y/n): ")
            if choice.lower() == "y":
                choice_instance = choices_template.copy()
                choice_instance["name"] = input("Enter Choice Name: ")
                choice_instance["value"] = input("Enter Choice Value: ")
                if "choices" not in option_instance:
                    option_instance["choices"] = []
                option_instance["choices"].append(choice_instance)
            else:
                print(Fore.GREEN + "Option Created Successfully\n" + Fore.RESET)
                option_list.append(option_instance)
                flag2 = False

        choice = input("Do you want to add another option? (Y/n): ")
        if choice.lower() != "y":
            flag = False

def get_inputs(inputs):
    """
    Prompts the user for a series of inputs, validates them, and returns the processed values.
    Args:
        inputs (list of dict): A list of dictionaries where each dictionary represents an input prompt.
            Each dictionary should have the following keys:
                - 'name' (str): The prompt message to display to the user.
                - 'check' (function): A function that takes the user input as an argument and returns True if the input is valid, False otherwise.
                - 'error' (str): The error message to display if the input is invalid.
                - 'type' (function): A function to convert the input to the desired type.
    Returns:
        list: A list of processed input values, converted to their respective types.
    """
    input_list = []
    for i in inputs:
        value = input(i["name"])
        while not i["check"](value):
            print(Fore.RED + i["error"] + "\n" + Fore.RESET)
            value = i(i["name"])
        input_list.append(i["type"](value))

    return input_list

def create_disc_command():
    # https://discord.com/developers/docs/interactions/application-commands#application-commandsc
    def _command_type_help():
        print(
            """
              1: CHAT_INPUT: Slash commands; a text-based command that shows up when a user types /
              2: USER: A UI-based command that shows up when you right-click or tap on a user
              3: MESSAGE: A UI-based command that shows up when you right-click or tap on a message
              4: PRIMARY_ENTRY_POINT: A UI-based command that shows up when you click on the application
              0: Exit
              """
        )
        type = int(input("Enter Command Type (0-4): "))
        if type <= 0 or type > 4:
            return _command_type_help()
        elif type == 0:
            sys.exit()
        else:
            return type

    name = input("Enter Command Name: ").lower()
    description = input("Enter Command Description: ")

    type = _command_type_help()

    choice = input("Do you want to add options? (Y/n): ")
    if choice.lower() == "n":
        options = None
    else:
        options = create_disc_command_options()

    command_json = {
        "name": name,
        "description": description,
        "type": type,
        "options": options,
    }

    choice = input(
        "Set the integration type. 0 for guild, 1 for user, 10 for both or 2 for application default: "
    )
    if choice == "0":
        command_json["integration_types"] = [0]
    elif choice == "1":
        command_json["integration_types"] = [1]
    elif choice == "10":
        command_json["integration_types"] = [0, 1]
    else:
        print("Setting to application default")

    choice = input("Is this a globally scoped command? (Y/n): ")
    if choice.lower() == "y":
        choice = input(
            "Set the interaction context by entering all that apply:\n0: GUILD\n1: BOT_DM\n2: PRIVATE_CHANNEL\n\nEnter selection: "
        )
        for option in range(3):
            if str(option) in choice:
                if "context" not in command_json:
                    command_json["context"] = []
                command_json["interaction_context"].append(option)
    else:
        choice = input("Enter the guild ID: ")
        command_json["guild_id"] = int(choice)

    choice = input("Name your file: disc_com_")
    output_path = os.path.join("output", "disc_commands", f"disc_com_{choice}.json")
    flag = True
    i = 0
    while flag:
        i += 1
        if os.path.exists(output_path):
            output_path = os.path.join(
                "output", "disc_commands", f"disc_com_{choice}_{str(i)}.json"
            )
        else:
            flag = False

    print(json.dumps(command_json, indent=4))

    with open(output_path, "w") as f:
        json.dump(command_json, f)

    print("\n")
    print(Fore.GREEN + "Options saved to " + output_path + "\n" + Fore.RESET)
    return output_path

def validate_input(input_value, expected_type: str = "USERNAME"):
    """
    Validate the input value against the expected type.
    Args:
        input_value (str): The input value to validate.
        expected_type (str): The expected type of the input value. Can be "USERNAME" or "PASSWORD".
    Returns:
        str: The validated input value.
    Raises:
        ValueError: If the input value does not match the expected type.
    """
    if expected_type == "USERNAME":
        input_value = input_value.strip()
        if not isinstance(input_value, str):
            raise ValueError("Username must be a string.")
        if len(input_value) < MIN_USERNAME_LENGTH or len(input_value) > MAX_USERNAME_LENGTH:
            raise ValueError(f"Username must be between {MIN_USERNAME_LENGTH} and {MAX_USERNAME_LENGTH} characters long.")
        if not re.match(r"^[a-zA-Z0-9_]+$", input_value):
            raise ValueError(
                "Username can only contain letters, numbers, and underscores."
            )
    elif expected_type == "PASSWORD":
        if not isinstance(input_value, str):
            raise ValueError("Password must be a string.")
        if len(input_value) < MIN_PASSWORD_LENGTH or len(input_value) > MAX_PASSWORD_LENGTH:
            raise ValueError(f"Password must be between {MIN_PASSWORD_LENGTH} and {MAX_PASSWORD_LENGTH} characters long.")
        if not re.match(r"^[a-zA-Z0-9!@#$%^&*()_\-+=]+$", input_value):
            raise ValueError(
                "Password can only contain letters, numbers, and special characters."
            )

    return input_value

def send_discord_warning(
    message: str,
    webhook_url: str = DISC_GLOBAL_WARN_URL,
    username: str = "Meno API",
    flags: int = 0,
):
    """
    Sends a warning message to a Discord channel using a webhook.
    Args:
        message (str): The warning message to send.
        webhook_url (str): The Discord webhook URL. Defaults to a global warning URL.
        flags (int): Flags for the message. Defaults to 0. Accepts the int number of the flag, function converts to binary.
        username (str): The username to display for the webhook message. Defaults to "Meno API".
    """
    data = {"content": message, "username": username}
    if flags:
        data["flags"] = bin(flags)[2:]

    response = requests.post(webhook_url, json=data)

    if response.status_code != 204:
        print(
            Fore.RED
            + f"Failed to send warning: {response.status_code} - {response.text}"
            + Fore.RESET
        )

def get_file(url: str):
    """
    Downloads a file from a given URL and returns its content as bytes.
    Args:
        url (str): The URL of the file to download.
    Returns:
        BytesIO: The content of the downloaded file as a BytesIO object.
    Raises:
        requests.RequestException: If there is an error during the HTTP request.
    """
    from io import BytesIO

    try:
        response = requests.get(url)
        response.raise_for_status()
        file = BytesIO(response.content)
        content_disposition = response.headers.get("Content-Disposition")
        if content_disposition:
            filename = re.findall('filename="(.+)"', content_disposition)
            if filename:
                filename = filename[0]
                _logger.info(f"Downloaded file: {filename}")
        else:
            _logger.info("Downloaded file with no filename in headers")
            import mimetypes

            content_type = response.headers.get("Content-Type")
            file.content_type = content_type
            extension = mimetypes.guess_extension(content_type)
            filename = f"downloaded_file{extension}" if extension else "downloaded_file"
            _logger.info("Generated_filename: " + filename)

        file.name = filename
        return file
    except requests.RequestException as e:
        _logger.error(f"Error downloading file from {url}: {e}")
        raise

def save_file(file_data, directory, file_name=None):
    """
    Saves a file to the specified directory.
    Args:
        file_data (BytesIO): The file data to save.
        directory (str): The directory where the file should be saved.
        file_name (str, optional): The name of the file. If not provided, uses the original filename from the BytesIO object.
    Returns:
        str: The path to the saved file.
    """
    if not os.path.exists(directory):
        os.makedirs(directory)

    if not file_name:
        file_name = getattr(file_data, "name", "downloaded_file")

    file_path = os.path.join(directory, file_name)
    with open(file_path, "wb") as f:
        f.write(file_data.getbuffer())

    _logger.info(f"File saved to {file_path}")
    return file_path

def string_to_tt(date_string: str):
    """
    Converts a date string in the format 'YYYY-MM-DD' to a time tuple.
    Args:
        date_string (str): The date string to convert.
    Returns:
        time.struct_time: The corresponding time tuple.
    Raises:
        ValueError: If the date string is not in the correct format.
    """
    import time
    formats = [
        "%Y-%m-%dT%H:%M:%S.%f%z",      # 2025-02-11T13:00:00.000+00:00
        "%Y-%m-%dT%H:%M:%S.%f",        # 2025-02-11T13:00:00.000
        "%Y-%m-%dT%H:%M:%S%z",         # 2025-02-11T13:00:00+00:00
        "%Y-%m-%dT%H:%M:%S",           # 2025-02-11T13:00:00
        "%Y-%m-%d %H:%M:%S.%f",        # 2025-02-11 13:00:00.000
        "%Y-%m-%d %H:%M:%S",           # 2025-02-11 13:00:00
        "%Y-%m-%d",                    # 2025-02-11
    ]

    for fmt in formats:
        try:
            return time.strptime(date_string, fmt)
        except ValueError:
            continue
        
def format_timestamp(timestamp: str | object, output_format: str="%Y-%m-%d"):
    from datetime import datetime
    import dateutil.parser
    
    if not timestamp:
        return ""
    
    if isinstance(timestamp, datetime):
        return timestamp.strftime(output_format)
    
    try:
        parsed_date = dateutil.parser.parse(timestamp)
        return parsed_date.strftime(output_format)
    except ValueError as e:
        return timestamp  # Return original string if parsing fails
    
def format_currency(value: str | float | int, currency_symbol: str="$") -> str:
    """
    Formats a numeric value as a currency string.
    Args:
        value (str | float | int): The numeric value to format.
        currency_symbol (str): The currency symbol to prepend. Default is "$".
    Returns:
        str: The formatted currency string.
    """
    default = f"{currency_symbol}0.00"
    try:
        if isinstance(value, str):
            cleaned = value.replace(",", "").replace("$", "").strip()
            if cleaned.lower() in ["", "n/a", "na"]:
                return default
            value = float(cleaned)
        elif not isinstance(value, (float, int)):
            return default
    except (ValueError, TypeError):
        return default

    return f"{currency_symbol}{value:,.2f}"

def customer_forbidden(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not hasattr(current_user, "role"):
            current_app.logger.error("Current user does not have a role attribute.")
            return redirect(url_for("internal_portal.login"))
        if current_user.role == "customer-role":
            current_app.logger.warning(
                f"User {current_user.username} attempted to access a forbidden route."
            )
            return redirect(url_for("internal_portal.customer_homepage"))
        elif current_user.role not in ["user-role", "admin-role", "mod-role"]:
            current_app.logger.warning(
                f"User {current_user.username} attempted to access a forbidden route."
            )
            return redirect(url_for("internal_portal.forbidden"))
        else:
            current_app.logger.info(f"User {current_user.username} {current_user.role} accessed a valid route.")
        return func(*args, **kwargs)

    return wrapper

def determine_file_type_from_response(url, response):
    """
    Determine file type when you already have a requests response object

    Args:
        url (str): The original URL
        response (requests.Response): The response object from requests.get()

    Returns:
        tuple: (mime_type, extension) or (None, None) if unable to determine
    """

    # Method 1: Check Content-Type header from response
    try:
        content_type = response.headers.get("content-type", "").split(";")[0].strip()
        if content_type and content_type != "application/octet-stream":
            extension = mimetypes.guess_extension(content_type)
            if extension:
                return content_type, extension
    except:
        pass

    # Method 2: Check URL extension as fallback
    try:
        parsed_url = urlparse(url)
        url_extension = os.path.splitext(parsed_url.path)[1].lower()
        if url_extension:
            mime_type = mimetypes.guess_type(url)[0]
            if mime_type:
                return mime_type, url_extension
    except:
        pass

    # Method 3: Use simple content-based detection (Windows-compatible)
    try:
        content = response.content[:512]  # Read first 512 bytes for detection

        # Simple file signature detection
        if content.startswith(b"\xff\xd8\xff"):
            return "image/jpeg", ".jpg"
        elif content.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png", ".png"
        elif content.startswith(b"GIF87a") or content.startswith(b"GIF89a"):
            return "image/gif", ".gif"
        elif content.startswith(b"%PDF"):
            return "application/pdf", ".pdf"
        elif content.startswith(b"PK"):
            # Could be zip, docx, xlsx, etc.
            return "application/zip", ".zip"
        elif content.startswith(b"\x00\x00\x01\x00"):
            return "image/x-icon", ".ico"
        elif content.startswith(b"RIFF") and b"WEBP" in content[:12]:
            return "image/webp", ".webp"
        else:
            # Fallback to generic binary
            return "application/octet-stream", ".bin"

    except Exception as e:
        print(f"Error detecting file type from content: {e}")

    return None, None

def get_html_email_str(
    content_path: str,
    support_email: str,
    content_context: dict={},
    template_path: str="/internal_portal/partials/email-base.html",
    header_url: str="https://api.menoondemand.com/static/images/meno-logo-200x83.webp",
    header_href: str="https://menoenterprises.com",
    background_color: str="#fff",
    sender_name: str="Meno Enterprises",
):
    """
    Generate an HTML email string from templates and context.
    Args:
        content_path (str): Path to the email content template.
        support_email (str): Support email address to include in the template.
        content_context (dict): Context variables for rendering the content template.
        template_path (str): Path to the base email template. Default is internal_portal partials email_base.html.
        header_url (str): URL for the header image. Default is Meno logo URL.
        header_href (str): Href link for the header image. Default is Meno homepage.
        background_color (str): Background color for the email. Default is #f9f9f9.
        sender_name (str): Name of the sender for footer. Default is Meno Enterprises.
    Returns:
        str: The rendered HTML email body.
    """
    from jinja2 import Environment, FileSystemLoader
    from pathlib import Path
    from datetime import datetime
    
    current_year = datetime.now().year

    template_dir = Path(__file__).parent.parent.parent / "templates"
    print(template_dir)
    env = Environment(loader=FileSystemLoader(str(template_dir)))

    year = str(current_year)
    html_email_content = env.get_template(content_path).render(**content_context)
    html_email_body = env.get_template(template_path).render(
        content=html_email_content,
        year=year,
        support_email=support_email,
        background_color=background_color,
        header_url=header_url,
        header_href=header_href,
        sender_name=sender_name,
    )
    
    return html_email_body