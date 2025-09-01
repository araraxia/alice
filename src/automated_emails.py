#!/usr/bin/env python3
# Aria Corona Sept 19th, 2024

"""
This is a script that sends automated emails. It is intended to be called by other scripts when needed.
It uses the smtplib library to send emails via an SMTP server. The email configuration is loaded from a JSON file, which should contain the SMTP server details, sender and recipient addresses, and other relevant information.

The send_email method takes the path to the email configuration file, the subject and body of the email, and an optional list of file paths for attachments.
It constructs the email message, attaches any files, and sends the email using the specified SMTP server.

Dependencies:
- None

send_email method parameters:
- email_config_path (str): The path to the email configuration JSON file. Required. If the file is not found or vital details are missing, the method will return without sending an email.
- subject (str): The subject of the email. Optional, defaults to an empty string.
- body (str): The body of the email. Optional, defaults to an empty string.
- file_attachment_paths (list of str): A list of file paths for attachments. Optional, defaults to None.

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
from src.util.independant_logger import Logger
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
import os
import json
import smtplib


class AutomatedEmails:
    def __init__(self, client_secret_path: str = None):
        # Initializes the AutomatedEmails class and sets up the credentials for sending emails.
        root_path = Path(os.path.dirname(os.path.abspath(__file__))).parent.resolve()

        logger = Logger(
            name="AutomatedEmails",
            log_file="automated_emails.log",
        )
        self.log = logger.get_logger()
        
        cred_path = (
            os.path.join(root_path, "conf", "cred", "mail_key.json")
            if not client_secret_path
            else client_secret_path
        )
        with cred_path.open("r") as f:
            self.mail_credentials = json.load(f)
        self.from_email = self.mail_credentials.get("from_email")
        self.password = self.mail_credentials.get("password")
        if not self.from_email or not self.password:
            self.log.error("Missing email credentials.")
            raise ValueError
        self.mail_server = self.mail_credentials.get("mail_server")
        self.mail_port = self.mail_credentials.get("mail_port")
        if not self.mail_server or not self.mail_port:
            self.log.error("Missing email server or port.")
            raise ValueError
        self.log.debug("AutomatedEmails initialized.")

    def send_email(
        self,
        from_name: str,
        to_email: list | str,
        cc_email: list | str = None,
        bcc_email: list | str = None,
        subject: str = "",
        body: str = "",
        file_attachment_ios: list = [],
        file_names: list = [],
        disable_header: bool = True,  # Switch to false once time to deploy
        disable_footer: bool = True,  # Switch to false once time to deploy
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
        Returns:
            None
        Raises:
            Exception: If there is an error in sending the email or attaching files.
        """
        if isinstance(to_email, str):
            to_email = [to_email]
        if isinstance(cc_email, str):
            cc_email = [cc_email]
        if isinstance(bcc_email, str):
            bcc_email = [bcc_email]

        # Create the email
        self.log.debug("Generating email.")
        msg = MIMEMultipart()
        msg["From"] = f"{from_name} <{self.from_email}>"
        msg["To"] = ", ".join(to_email)
        if cc_email:
            msg["Cc"] = ", ".join(cc_email)
        if bcc_email:
            msg["Bcc"] = ", ".join(bcc_email)
        msg["Subject"] = subject if subject else ""

        # Attach the body with the msg instance
        msg.attach(MIMEText(body, "plain"))

        # Attach files if any
        if file_attachment_ios:
            for file_io in file_attachment_ios:
                try:
                    try:
                        self.log.debug("Grabbing file name.")
                        file_name = file_io.name
                    except Exception as e:
                        self.log.warning(
                            "File name not stored in file_io, using magic to determine file name..."
                        )
                        import magic
                        import mimetypes

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
                    self.log.info(f"Attaching file '{file_name}")
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(file_content)
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition", f"attachment; filename={file_name}"
                    )
                    msg.attach(part)

                except Exception as e:
                    self.log.error(f"Failed to attach file: {e}")
                    return

        # Combine all recipients
        all_recipients = to_email
        if cc_email:
            all_recipients += cc_email
        if bcc_email:
            all_recipients += bcc_email

        # Send the email
        try:
            
            with smtplib.SMTP(self.mail_server, self.mail_port) as smtp_server:
                self.log.info(f"Sending email: {msg}")
                text = msg.as_string()
                smtp_server.sendmail(self.from_email, all_recipients, text)
                smtp_server.quit()
                self.log.info("Email sent successfully.")
        except Exception as e:
            self.log.error(f"Failed to send email: {e}")
            raise e
