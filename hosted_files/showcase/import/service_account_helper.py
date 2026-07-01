#!/usr/bin/env python3
"""
11-06-2025

Service Account Authentication Helper

This module provides helper functions to authenticate Google service accounts
with optional domain-wide delegation (user impersonation) support.

Dependencies:
- google-auth
- google-auth-oauthlib
- google-auth-httplib2
- google-api-python-client

Example Usage:
    # Basic authentication without impersonation
    creds = authenticate_service_account(
        service_account_file='cred/my_sa.json',
        scopes=['https://www.googleapis.com/auth/gmail.send']
    )

    # With user impersonation (requires domain-wide delegation)
    creds = authenticate_service_account(
        service_account_file='cred/my_sa.json',
        scopes=['https://www.googleapis.com/auth/gmail.send'],
        subject='user@example.com'
    )

    # Using with Gmail API
    from googleapiclient.discovery import build
    service = build('gmail', 'v1', credentials=creds)
"""

from google.oauth2 import service_account
from pathlib import Path
import os
import json

FILE_PATH = Path(__file__).resolve()
ROOT_PATH = FILE_PATH.parent.parent.parent
CRED_DIR = ROOT_PATH / "cred"
DEFAULT_SA = CRED_DIR / "service_account.json"

def authenticate_service_account(
    service_account_file: str = str(DEFAULT_SA),
    scopes: list = [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/devstorage.full_control",
        "https://mail.google.com/",  # Full Gmail access
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/gmail.compose",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.settings.basic",
        "https://www.googleapis.com/auth/gmail.settings.sharing",
        "https://www.googleapis.com/auth/admin.directory.user",  # For UserAlias management
        "https://www.googleapis.com/auth/admin.directory.user.alias",  # For UserAlias management
        "https://www.googleapis.com/auth/admin.directory.group",  # For Group management
        "https://www.googleapis.com/auth/admin.directory.domain",  # For Domain management
    ],
    subject: str = None,
    root_path: str = None,
):
    """
    Authenticate a Google service account and return the credentials object.

    This function loads a service account from a JSON file and creates credentials
    with the specified scopes. Optionally, it can impersonate a user in your
    workspace using domain-wide delegation.

    Args:
        service_account_file (str, optional): Path to the service account JSON file.
            Can be an absolute path or relative to root_path. Defaults to DEFAULT_SA.
        scopes (list, optional): List of OAuth2 scopes to request.
            Defaults to:
            [
                'https://www.googleapis.com/auth/gmail.send',
                'https://www.googleapis.com/auth/drive',
                'https://mail.google.com/',
                'https://www.googleapis.com/auth/devstorage.full_control',
            ]
        subject (str, optional): Email address of the user to impersonate.
            Requires domain-wide delegation to be enabled for the service account.
            If None, no impersonation is performed. Defaults to None.
        root_path (str, optional): Root path for resolving relative paths.
            If None, uses the parent directory of the current file. Defaults to None.

    Returns:
        google.oauth2.service_account.Credentials: Authenticated credentials object
            that can be used with Google API client libraries.

    Raises:
        FileNotFoundError: If the service account file is not found.
        ValueError: If the service account file is not valid JSON or missing required fields.
        Exception: If authentication fails for any other reason.

    Example:
        # Basic usage
        creds = authenticate_service_account(
            service_account_file='cred/service_account.json',
            scopes=['https://www.googleapis.com/auth/gmail.send']
        )

        # With impersonation
        creds = authenticate_service_account(
            service_account_file='cred/service_account.json',
            scopes=['https://www.googleapis.com/auth/gmail.send'],
            subject='admin@example.com'
        )

        # Use with API
        from googleapiclient.discovery import build
        gmail_service = build('gmail', 'v1', credentials=creds)

    Notes:
        - For user impersonation, the service account must have domain-wide
          delegation enabled in Google Workspace Admin Console.
        - The service account must be granted the necessary scopes in the
          Admin Console for impersonation to work.
        - If impersonation fails, check that:
          1. Domain-wide delegation is enabled for the service account
          2. The required scopes are authorized in Admin Console
          3. The subject email exists in your workspace
    """
    # Determine the root path
    if root_path is None:
        root_path = ROOT_PATH
    else:
        root_path = Path(root_path).resolve()

    # Resolve the service account file path
    sa_path = Path(service_account_file)
    if not sa_path.is_absolute():
        sa_path = root_path / service_account_file

    # Check if the file exists
    if not sa_path.exists():
        raise FileNotFoundError(
            f"Service account file not found: {sa_path}\n"
            f"Please ensure the file exists at the specified path."
        )

    # Load and validate the service account file
    try:
        with open(sa_path, "r") as f:
            sa_data = json.load(f)

        # Validate required fields
        required_fields = [
            "type",
            "project_id",
            "private_key_id",
            "private_key",
            "client_email",
        ]
        missing_fields = [field for field in required_fields if field not in sa_data]

        if missing_fields:
            raise ValueError(
                f"Service account file is missing required fields: {', '.join(missing_fields)}"
            )

        if sa_data.get("type") != "service_account":
            raise ValueError(
                f"Invalid service account file. Expected type 'service_account', "
                f"got '{sa_data.get('type')}'"
            )
    except json.JSONDecodeError as e:
        raise ValueError(f"Service account file is not valid JSON: {e}")

    # Create credentials from service account file
    try:
        credentials = service_account.Credentials.from_service_account_file(
            filename=str(sa_path), scopes=scopes
        )
    except Exception as e:
        raise Exception(f"Failed to create credentials from service account file: {e}")

    # Apply user impersonation if subject is provided
    if subject:
        try:
            credentials = credentials.with_subject(subject)
        except Exception as e:
            raise Exception(
                f"Failed to impersonate user '{subject}'. "
                f"Ensure domain-wide delegation is enabled and the user exists. "
                f"Error: {e}"
            )

    return credentials


def get_service_account_info(
    service_account_file: str = str(DEFAULT_SA),
    root_path: str = None
    ):
    """
    Get information about a service account without authenticating.

    Args:
        service_account_file (str): Path to the service account JSON file.
        root_path (str, optional): Root path for resolving relative paths.

    Returns:
        dict: Dictionary containing service account information:
            - client_email (str): Service account email
            - project_id (str): GCP project ID
            - private_key_id (str): Private key ID
            - type (str): Should be 'service_account'

    Raises:
        FileNotFoundError: If the service account file is not found.
        ValueError: If the file is not valid JSON.
    """
    # Determine the root path
    if root_path is None:
        root_path = ROOT_PATH
    else:
        root_path = Path(root_path).resolve()

    # Resolve the service account file path
    sa_path = Path(service_account_file)
    if not sa_path.is_absolute():
        sa_path = root_path / service_account_file

    # Check if the file exists
    if not sa_path.exists():
        raise FileNotFoundError(f"Service account file not found: {sa_path}")

    # Load the service account file
    try:
        with open(sa_path, "r") as f:
            sa_data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Service account file is not valid JSON: {e}")

    # Return relevant information (excluding private key)
    return {
        "client_email": sa_data.get("client_email"),
        "project_id": sa_data.get("project_id"),
        "private_key_id": sa_data.get("private_key_id"),
        "type": sa_data.get("type"),
    }


# Example usage and testing
if __name__ == "__main__":
    """
    Example usage of the service account authentication helper.
    Uncomment and modify the examples below to test.
    """

    # Example 1: Basic authentication without impersonation
    try:
        creds = authenticate_service_account(
            scopes=['https://www.googleapis.com/auth/drive.readonly']
        )
        print(f"✓ Authenticated successfully")
        print(f"  Service Account: {creds.service_account_email}")
    except Exception as e:
        print(f"✗ Authentication failed: {e}")

    # Example 2: Authentication with user impersonation
    try:
        creds = authenticate_service_account(
            scopes=['https://www.googleapis.com/auth/gmail.send'],
            subject='user@email.com'
        )
        print(f"✓ Authenticated successfully with impersonation")
        print(f"  Service Account: {creds.service_account_email}")
        print(f"  Impersonating: user@email.com")
    except Exception as e:
        print(f"✗ Authentication with impersonation failed: {e}")

    # Example 3: Get service account info
    try:
        info = get_service_account_info()
        print(f"✓ Service Account Information:")
        print(f"  Email: {info['client_email']}")
        print(f"  Project: {info['project_id']}")
        print(f"  Type: {info['type']}")
    except Exception as e:
        print(f"✗ Failed to get service account info: {e}")

    pass
