#!/usr/bin/env python3
# Aria Corona Sept 19th, 2024

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
import os
import json
import smtplib
import base64


class AutomatedEmails:
    def __init__(self, client_secret_path: str = None):
        # Initializes the AutomatedEmails class and sets up the credentials for sending emails.
        root_path = Path(os.path.dirname(os.path.abspath(__file__))).parent.resolve()
        secret_path = os.path.join(
            root_path,
            "cred",
            "client_secret.json",
        )
        cred_path = (
            os.path.join(root_path, "cred", "gmail_token.json")
            if not client_secret_path
            else client_secret_path
        )
        creds = Credentials.from_authorized_user_file(
            cred_path, scopes=["https://mail.google.com/"]
        )
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(cred_path, "w") as token:
                    token.write(creds.to_json())
            except Exception as e:
                flow = InstalledAppFlow.from_client_secrets_file(
                    secret_path, scopes=["https://mail.google.com/"]
                )
                creds = flow.run_local_server(port=0)
                with open(cred_path, "w") as token:
                    token.write(creds.to_json())

        auth_string = base64.urlsafe_b64encode(
            f"user=no-reply@menoenterprises.com\1auth=Bearer {creds.token}\1\1".encode()
        ).decode()

        self.creds = creds
        self.root_path = root_path
        self.auth_string = auth_string

    # string, string = "", string = "", list of strings = None
    def send_email(
        self, email_config_path, subject="", body="", file_attachment_paths=[]
    ):
        """
        Sends an email with the specified subject, body, and file attachments using the configuration provided in a JSON file.
        Args:
            email_config_path (str): Path to the JSON file containing email configuration.
            subject (str, optional): Subject of the email. Defaults to an empty string.
            body (str, optional): Body of the email. Defaults to an empty string.
            file_attachment_paths (list, optional): List of file paths to attach to the email. Defaults to an empty list.
        Returns:
            None
        Raises:
            FileNotFoundError: If the email configuration file or any attachment file is not found.
            Exception: If there is an error in sending the email or attaching files.
        The email configuration JSON file should contain the following keys:
            - smtp_server (str): SMTP server address.
            - smtp_port (int): SMTP server port.
            - smtp_username (str): SMTP server username.
            - smtp_password (str): SMTP server password.
            - from_name (str): Name of the sender.
            - from_email (str): Email address of the sender.
            - to_email (list): List of recipient email addresses.
            - cc_email (list): List of CC email addresses.
            - bcc_email (list): List of BCC email addresses.

        Example configuration file (email_config.json):
        {
            "smtp_server": "smtp.example.com",
            "smtp_port": 587,
            "smtp_username": "username@user.com",
            "smtp_password": "password123",
            "from_name": "Sender Name",
            "from_email": "sender@example.com",
            "to_email": ["recipient@example.com"],
            "cc_email": ["cc_recipient1@example.com", "cc_recipient2@example.com"],
            "bcc_email": []
        }
        """

        def load_email_config(email_config_file_name):
            print(f"Loading email configuration from {email_config_file_name}...")
            try:
                with open(email_config_file_name, "r") as file:
                    email_config = json.load(file)
                return email_config
            except FileNotFoundError:
                print(f"Email configuration file '{email_config_file_name}' not found.")
                return None

        # Load email configuration from JSON file
        email_config = load_email_config(email_config_path)
        if email_config is None:
            return

        # Set email configuration variables
        print("Setting email configuration variables...")
        from_name = email_config["from_name"]  # string
        from_email = email_config["from_email"]  # string
        to_email = email_config["to_email"]  # list of strings
        cc_email = email_config["cc_email"]  # list of strings
        bcc_email = email_config["bcc_email"]  # list of strings

        smtp_server = smtplib.SMTP("smtp.gmail.com", 587)
        smtp_server.starttls()
        smtp_server.docmd("AUTH", "XOAUTH2" + " " + self.auth_string)

        # Create the email
        print("Generating email...")
        msg = MIMEMultipart()
        if from_email:
            msg["From"] = f"{from_name} <{from_email}>"
        else:
            print(f"No sender address in {email_config_path}.")
            return
        if to_email:
            msg["To"] = ", ".join(to_email)
        else:
            print(f"No recipient address in {email_config_path}.")
            return
        if cc_email:
            msg["Cc"] = ", ".join(cc_email)
        if bcc_email:
            msg["Bcc"] = ", ".join(bcc_email)
        msg["Subject"] = subject if subject else ""

        # Attach the body with the msg instance
        body = body if body else ""
        msg.attach(MIMEText(body, "plain"))

        # Attach files if any
        if file_attachment_paths:
            for file_path in file_attachment_paths:
                try:
                    print(f"Attaching file '{file_path}'...")
                    with open(file_path, "rb") as attachment:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(attachment.read())
                        encoders.encode_base64(part)
                        part.add_header(
                            "Content-Disposition",
                            f"attachment; filename={os.path.basename(file_path)}",
                        )
                        msg.attach(part)
                except FileNotFoundError:
                    print(f"File '{file_path}' not found. Aborting email.")
                    return
                except Exception as e:
                    print(f"Failed to attach file '{file_path}': {e}")
                    return

        # Combine all recipients
        all_recipients = to_email
        if cc_email:
            all_recipients += cc_email
        if bcc_email:
            all_recipients += bcc_email

        # Send the email
        try:
            print("Sending email...")
            text = msg.as_string()
            smtp_server.sendmail(from_email, all_recipients, text)
            smtp_server.quit()
            print("Email sent successfully.")
        except Exception as e:
            print(f"Failed to send email: {e}")

    def email_from_memory(
        self,
        from_name: str,
        from_email: str,
        to_email: list | str,
        cc_email: list | str = None,
        bcc_email: list | str = None,
        subject="",
        body="",
        file_attachment_ios: list = [],
        file_names: list = [],
        disable_header: bool = True,  # Switch to false once time to deploy
        disable_footer: bool = True,  # Switch to false once time to deploy
        is_html: bool = False,  # Set to True to send HTML emails
    ):
        """
        Sends an email with the specified subject, body, and file attachments using the provided parameters.
        This method is intended to be used when the email configuration is not stored in a JSON file, and the file attachments are provided as in-memory byte strings.
        It uses the Google OAuth2 credentials for authentication.
        Args:
            from_name (str): Name of the sender.
            from_email (str): Email address of the sender.
            to_email (list): Recipient email address.
            cc_email (list, optional): CC email address. Defaults to None.
            bcc_email (list, optional): BCC email address. Defaults to None.
            subject (str, optional): Subject of the email. Defaults to an empty string.
            body (str, optional): Body of the email. Defaults to an empty string.
            file_attachment_ios (list, optional): List of tuples containing file name and file content. Defaults to an empty list.
            disable_header (bool, optional): Whether to disable the header in the email. Defaults to True.
            disable_footer (bool, optional): Whether to disable the footer in the email. Defaults to True.
            is_html (bool, optional): Whether the body content is HTML. Defaults to False (plain text).
        Returns:
            None
        Raises:
            Exception: If there is an error in sending the email or attaching files.
        """
        smtp_server = smtplib.SMTP("smtp.gmail.com", 587)
        smtp_server.starttls()
        smtp_server.docmd("AUTH", "XOAUTH2" + " " + self.auth_string)

        if isinstance(to_email, str):
            to_email = [to_email]
        if isinstance(cc_email, str):
            cc_email = [cc_email]
        if isinstance(bcc_email, str):
            bcc_email = [bcc_email]

        # Create the email
        print("Generating email...")
        msg = MIMEMultipart()
        msg["From"] = f"{from_name} <{from_email}>"
        msg["To"] = ", ".join(to_email)
        if cc_email:
            msg["Cc"] = ", ".join(cc_email)
        if bcc_email:
            msg["Bcc"] = ", ".join(bcc_email)
        msg["Subject"] = subject if subject else ""

        # Attach the body with the msg instance
        body = body if body else ""
        # Use 'html' if is_html is True, otherwise use 'plain'
        content_type = "html" if is_html else "plain"
        msg.attach(MIMEText(body, content_type))

        # Attach files if any
        if file_attachment_ios:
            for file_io in file_attachment_ios:
                try:
                    try:
                        print("Grabbing file name...")
                        file_name = file_io.name
                    except Exception as e:
                        print(
                            "File name not stored in file_io, using magic to determine file name..."
                        )
                        import magic
                        import mimetypes
                        from io import BytesIO

                        mime = magic.Magic(mime=True)
                        mime_type = mime.from_buffer(file_io.getvalue())
                        file_extension = (
                            mimetypes.guess_extension(mime_type) if mime_type else ""
                        )
                        file_name = (
                            f"attachment{file_extension}"
                            if file_extension
                            else "attachment"
                        )

                    file_content = file_io.getvalue()
                    print(f"Attaching file '{file_name}'...")
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(file_content)
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition", f"attachment; filename={file_name}"
                    )
                    msg.attach(part)

                except Exception as e:
                    print(f"Failed to attach file: {e}")
                    return

        # Combine all recipients
        all_recipients = to_email
        if cc_email:
            all_recipients += cc_email
        if bcc_email:
            all_recipients += bcc_email

        # Send the email
        try:
            print("Sending email...")
            text = msg.as_string()
            smtp_server.sendmail(from_email, all_recipients, text)
            smtp_server.quit()
            print("Email sent successfully.")
        except Exception as e:
            print(f"Failed to send email: {e}")
            raise e


if __name__ == "__main__":
    automated_emails = AutomatedEmails()
    from extras.helpers import get_html_email_str

    subject = "Test Email"
    html_email_body = get_html_email_str(
        content_path="emails/organization_activation.html",
        support_email="mod-customer-service@menoenterprises.com",
        content_context={"organization_id": "TEST12345"},
        sender_name="The Meno On-Demand Team",
    )

    automated_emails.email_from_memory(
        from_name="Meno No-Reply",
        from_email="no-reply@menoenterprises.com",
        to_email="acorona@menoenterprises.com",
        subject=subject,
        body=html_email_body,
        is_html=True,
    )
