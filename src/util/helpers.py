#!/usr/bin/env python3

import sys, os, json, re, requests, logging
from colorama import Fore

DISC_GLOBAL_WARN_URL = ""

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

    alphabet = string.ascii_letters + string.digits + string.punctuation
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
    if expected_type == "USERNAME":
        input_value = input_value.strip()
        if not isinstance(input_value, str):
            raise ValueError("Username must be a string.")
        if len(input_value) < 3 or len(input_value) > 50:
            raise ValueError("Username must be between 3 and 50 characters long.")
        if not re.match(r"^[a-zA-Z0-9_]+$", input_value):
            raise ValueError(
                "Username can only contain letters, numbers, and underscores."
            )
    elif expected_type == "PASSWORD":
        if not isinstance(input_value, str):
            raise ValueError("Password must be a string.")
        if len(input_value) < 8 or len(input_value) > 50:
            raise ValueError("Password must be between 8 and 50 characters long.")
        if not re.match(r"^[a-zA-Z0-9!@#$%^&*()_+=]+$", input_value):
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
        if len(input_value) < 2 or len(input_value) > 32:
            raise ValueError("Username must be between 2 and 32 characters long.")
        if not re.match(r"^[a-zA-Z0-9_]+$", input_value):
            raise ValueError(
                "Username can only contain letters, numbers, and underscores."
            )
    elif expected_type == "PASSWORD":
        if not isinstance(input_value, str):
            raise ValueError("Password must be a string.")
        if len(input_value) < 12 or len(input_value) > 50:
            raise ValueError("Password must be between 12 and 50 characters long.")
        if not re.match(r"^[a-zA-Z0-9!@#$%^&*_\-]+$", input_value):
            raise ValueError(
                "Password can only contain letters, numbers, and special characters."
            )

    return input_value