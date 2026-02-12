#!/usr/bin/env python3

"""
2025-11-02
"""


from google.oauth2 import service_account
from googleapiclient.discovery import build
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
import json
import base64
import os
from dotenv import load_dotenv
from logging import Logger
from typing import Optional
import random

# Load environment variables from .env file
load_dotenv()

FILE_PATH = Path(__file__).resolve()
ROOT_PATH = FILE_PATH.parent.parent.parent
CRED_DIR = ROOT_PATH / "cred"
DEFAULT_SA = CRED_DIR / "service_account.json"


class Thread:
    """
    Represents a Gmail conversation thread containing one or more messages.

    A thread is a collection of messages that belong to the same conversation.
    This class acts as a parent to Message objects and manages the relationship
    between messages in a thread.

    Attributes:
        id (str): Gmail thread ID
        history_id (str): History ID for the thread
        messages (list[Message]): List of Message objects in this thread (ordered by date)
        snippet (str): Preview text from the most recent message
        _raw (dict): Raw thread data from Gmail API
        _manager (ServiceAccountEmailManager or None): Reference to email manager for lazy loading

    Properties (Read-only):
        message_count (int): Number of messages in the thread
        first_message (Message or None): First (oldest) message in the thread
        last_message (Message or None): Last (newest) message in the thread
        subject (str): Subject line from the first message
        participants (set): Set of all email addresses involved in the thread
        has_unread (bool): True if any message in the thread is unread
        has_starred (bool): True if any message in the thread is starred
        all_labels (set): Set of all unique labels across all messages

    Methods:
        add_message: Add a message to the thread
        remove_message: Remove a message from thread (auto-deletes thread if last message)
        delete: Permanently delete the thread from Gmail
        modify_labels: Add or remove labels from all messages in the thread
        get_messages_by_sender: Filter messages by sender email
        get_unread_messages: Get all unread messages in the thread
        to_dict: Convert thread to dictionary representation
    """

    def __init__(self, raw_thread: dict = None, thread_id: str = None, manager=None):
        """
        Initialize a Thread from Gmail API response or thread ID.

        Args:
            raw_thread (dict, optional): Raw thread dictionary from Gmail API.
                Should contain 'id', 'historyId', 'messages', etc.
            thread_id (str, optional): Gmail thread ID for lazy initialization.
                If provided without raw_thread, messages will be loaded when accessed.
            manager (ServiceAccountEmailManager, optional): Reference to the email
                manager for lazy loading messages. Required if using thread_id only.

        Raises:
            ValueError: If neither raw_thread nor thread_id is provided, or if
                        thread_id is empty
        """
        if raw_thread is None and thread_id is None:
            raise ValueError("Either raw_thread or thread_id must be provided")

        # Validate thread_id if provided
        if thread_id is not None and (not thread_id or not str(thread_id).strip()):
            raise ValueError("thread_id cannot be empty or whitespace")

        self._raw = raw_thread or {}
        self._manager = manager
        self._messages_loaded = False

        # Set thread ID
        self.id = raw_thread.get("id") if raw_thread else thread_id

        # Validate extracted ID
        if not self.id or not str(self.id).strip():
            raise ValueError("Thread ID cannot be empty")

        self.history_id = raw_thread.get("historyId") if raw_thread else None

        # Initialize messages list
        self.messages = []

        # If raw_thread provided with messages, initialize them
        if raw_thread and "messages" in raw_thread:
            self._initialize_messages(raw_messages=raw_thread["messages"])
            self._messages_loaded = True

        # Set snippet from last message or raw data
        self.snippet = raw_thread.get("snippet", "") if raw_thread else ""

    def _initialize_messages(self, raw_messages: list):
        """
        Initialize Message objects from raw message data.

        Args:
            raw_messages (list): List of raw message dictionaries from Gmail API
        """
        self.messages = []
        existing_ids = set()
        for raw_msg in raw_messages:
            msg_id = raw_msg.get("id")
            # Prevent duplicate messages by checking ID
            if msg_id and msg_id not in existing_ids:
                # Create Message with thread reference
                message = Message(raw_msg, thread=self)
                self.messages.append(message)
                existing_ids.add(msg_id)

        # Sort messages by internal_date (oldest to newest)
        self.messages.sort(key=lambda m: int(m.internal_date) if m.internal_date else 0)

    def _ensure_messages_loaded(self):
        """
        Ensure messages are loaded (lazy loading support).

        If the thread was initialized with only thread_id, this will fetch
        the full thread data including messages from the API.
        """
        if not self._messages_loaded and self._manager:
            # Mark as loaded BEFORE fetching to prevent infinite recursion
            self._messages_loaded = True
            try:
                # Fetch full thread data from Gmail API
                thread_data = self._manager.get_thread_by_id(self.id, format="full")
                if isinstance(thread_data, Thread):
                    # If manager returns Thread object, copy its data
                    self.messages = thread_data.messages
                    self.history_id = thread_data.history_id
                    self.snippet = thread_data.snippet
                    self._raw = thread_data._raw
                else:
                    # If manager returns dict, initialize from it
                    self._raw = thread_data
                    self.history_id = thread_data.get("historyId")
                    self.snippet = thread_data.get("snippet", "")
                    if "messages" in thread_data:
                        self._initialize_messages(thread_data["messages"])
            except Exception as e:
                # Reset flag on failure so retry is possible
                self._messages_loaded = False
                raise Exception(f"Failed to load messages for thread '{self.id}': {e}")

    def add_message(self, message):
        """
        Add a message to this thread.

        Args:
            message (Message): Message object to add to the thread

        Note:
            This method also sets the message's thread reference to this thread.
            Messages are automatically sorted by date after addition.
        """
        if message not in self.messages:
            message.thread = self
            self.messages.append(message)
            # Re-sort messages by date
            self.messages.sort(
                key=lambda m: int(m.internal_date) if m.internal_date else 0
            )

    def remove_message(self, message):
        """
        Remove a message from this thread and delete it from Gmail.

        If this is the last message in the thread, the thread will be automatically
        deleted from Gmail instead of raising an error. The message is permanently
        deleted via message.delete().

        Args:
            message (Message): Message object to remove from the thread

        Returns:
            bool: True if thread was deleted (last message removed), False otherwise

        Note:
            When the last message is removed, this method calls delete() which
            permanently deletes the thread and all remaining messages from Gmail.
            For non-last messages, the individual message is deleted via message.delete().
        """
        if len(self.messages) <= 1:
            # Last message - delete just this message to avoid double deletion
            if message in self.messages:
                self.messages.remove(message)

            # Set manager if not already set
            if not message._manager:
                message._manager = self._manager

            # Delete the single message
            try:
                message.delete()
            except Exception as e:
                print(f"Warning: Failed to delete last message {message.id}: {e}")

            # Clear thread's messages list since thread is now empty
            self.messages = []
            return True

        if message in self.messages:
            # Remove from thread's message list
            self.messages.remove(message)

            # Set manager if not already set
            if not message._manager:
                message._manager = self._manager

            # Delete the individual message from Gmail
            try:
                message.delete()
            except Exception as e:
                print(f"Warning: Failed to delete message {message.id}: {e}")

        return False

    def delete(self):
        """
        Permanently delete this thread from Gmail.

        This deletes the entire thread including all messages from the Gmail mailbox.
        Each message in the thread is individually deleted via message.delete().
        After deletion, all message objects in this thread will have their thread
        reference cleared, and the thread's messages list will be emptied.

        Raises:
            Exception: If the thread cannot be deleted (no manager, API error, etc.)

        Warning:
            AFAIK This operation is permanent and cannot be undone. The thread and all
            its messages will be permanently deleted from Gmail (not moved to trash).

        Note:
            Requires a manager reference (_manager) to perform the deletion.
            If the thread was created without a manager, this will raise an exception.
            Each message in the thread is deleted individually using message.delete().
        """
        if not self._manager:
            raise Exception(
                "Cannot delete thread: No manager reference. "
                "Thread must be created with a manager to support deletion."
            )

        try:
            # Delete each message individually
            # Make a copy of the list since we'll be modifying it during iteration
            messages_to_delete = list(self.messages)

            for message in messages_to_delete:
                try:
                    # Set manager if not already set (for lazy-loaded messages)
                    if not message._manager:
                        message._manager = self._manager

                    # Delete the individual message
                    message.delete()
                except Exception as e:
                    # Log but continue deleting other messages
                    print(f"Warning: Failed to delete message {message.id}: {e}")

            # Clear the messages list
            self.messages = []

        except Exception as e:
            raise Exception(f"Failed to delete thread '{self.id}': {e}")

    def modify_labels(
        self, add_label_ids: list[str] = None, remove_label_ids: list[str] = None
    ):
        """
        Modify labels for all messages in this thread.

        This applies label changes to every message in the thread by calling
        message.modify() on each message. Labels can be added, removed, or both
        in a single operation.

        Args:
            add_label_ids (list[str], optional): List of label IDs to add to all messages.
                Each ID should be a Gmail label ID (e.g., 'Label_123', 'INBOX', 'STARRED').
            remove_label_ids (list[str], optional): List of label IDs to remove from all messages.
                Each ID should be a Gmail label ID.

        Raises:
            Exception: If no manager reference exists, or if label modification fails

        Note:
            - Requires a manager reference (_manager) to perform the modification
            - Changes are applied to ALL messages in the thread
            - If a message doesn't have a label being removed, no error occurs
            - If a message already has a label being added, it remains unchanged
            - Uses batch operations internally for efficiency
        """
        if not self._manager:
            raise Exception(
                "Cannot modify thread labels: No manager reference. "
                "Thread must be created with a manager to support label modification."
            )

        if not add_label_ids and not remove_label_ids:
            # Nothing to do
            return

        # Ensure messages are loaded
        self._ensure_messages_loaded()

        if not self.messages:
            # No messages to modify
            return

        try:
            # Apply label changes to each message
            success_count = 0
            error_count = 0

            for message in self.messages:
                try:
                    # Set manager if not already set (for lazy-loaded messages)
                    if not message._manager:
                        message._manager = self._manager

                    # Prepare label modifications
                    if add_label_ids and remove_label_ids:
                        # Both add and remove
                        message.modify(label_ids=add_label_ids, action="add")
                        message.modify(label_ids=remove_label_ids, action="remove")
                    elif add_label_ids:
                        # Only add
                        message.modify(label_ids=add_label_ids, action="add")
                    elif remove_label_ids:
                        # Only remove
                        message.modify(label_ids=remove_label_ids, action="remove")

                    success_count += 1

                except Exception as e:
                    # Log but continue modifying other messages
                    print(
                        f"Warning: Failed to modify labels for message {message.id}: {e}"
                    )
                    error_count += 1

            if error_count > 0:
                print(
                    f"Modified {success_count}/{len(self.messages)} messages "
                    f"({error_count} failed)"
                )

        except Exception as e:
            raise Exception(f"Failed to modify thread '{self.id}' labels: {e}")

    # Properties
    @property
    def message_count(self) -> int:
        """
        Get the number of messages in this thread.

        Returns:
            int: Count of messages in the thread
        """
        self._ensure_messages_loaded()
        return len(self.messages)

    @property
    def first_message(self):
        """
        Get the first (oldest) message in the thread.

        Returns:
            (Message or None): First message, or None if thread is empty
        """
        self._ensure_messages_loaded()
        return self.messages[0] if self.messages else None

    @property
    def last_message(self):
        """
        Get the last (newest) message in the thread.

        Returns:
            (Message or None): Last message, or None if thread is empty
        """
        self._ensure_messages_loaded()
        return self.messages[-1] if self.messages else None

    @property
    def subject(self) -> str:
        """
        Get the subject line from the first message in the thread.

        Returns:
            str: Email subject, or empty string if no messages
        """
        self._ensure_messages_loaded()
        return self.first_message.subject if self.first_message else ""

    @property
    def participants(self) -> set:
        """
        Get all unique email addresses involved in the thread.

        Returns:
            set: Set of email addresses (from From, To, Cc fields)
        """
        self._ensure_messages_loaded()
        participants = set()
        for message in self.messages:
            # Add from address
            if message.from_email:
                participants.add(message.from_email)
            # Add to addresses (may be comma-separated)
            if message.to_email:
                for addr in message.to_email.split(","):
                    participants.add(addr.strip())
            # Add cc addresses
            if message.cc_email:
                for addr in message.cc_email.split(","):
                    participants.add(addr.strip())
        return participants

    @property
    def has_unread(self) -> bool:
        """
        Check if any message in the thread is unread.

        Returns:
            bool: True if at least one message is unread
        """
        self._ensure_messages_loaded()
        return any(message.is_unread() for message in self.messages)

    @property
    def has_starred(self) -> bool:
        """
        Check if any message in the thread is starred.

        Returns:
            bool: True if at least one message is starred
        """
        self._ensure_messages_loaded()
        return any(message.is_starred() for message in self.messages)

    @property
    def all_labels(self) -> set:
        """
        Get all unique labels across all messages in the thread.

        Returns:
            set: Set of all label IDs used in the thread
        """
        self._ensure_messages_loaded()
        labels = set()
        for message in self.messages:
            labels.update(message.label_ids)
        return labels

    def get_messages_by_sender(self, email: str) -> list:
        """
        Get all messages from a specific sender.

        Args:
            email (str): Email address to filter by

        Returns:
            list[Message]: List of messages from the specified sender
        """
        self._ensure_messages_loaded()
        return [msg for msg in self.messages if email.lower() in msg.from_email.lower()]

    def get_unread_messages(self) -> list:
        """
        Get all unread messages in the thread.

        Returns:
            list[Message]: List of unread messages
        """
        self._ensure_messages_loaded()
        return [msg for msg in self.messages if msg.is_unread()]

    def to_dict(self) -> dict:
        """
        Convert Thread to dictionary representation.

        This method is useful for JSON serialization or when you need to pass
        thread data to systems that expect dictionary format.

        Returns:
            dict: Dictionary containing all thread data with keys:
                - id: Thread ID
                - history_id: History ID
                - message_count: Number of messages
                - snippet: Thread preview
                - subject: Subject line
                - participants: List of participant email addresses
                - has_unread: Boolean indicating if thread has unread messages
                - has_starred: Boolean indicating if thread has starred messages
                - labels: List of all unique labels
                - messages: List of Messages as dictionaries (each message converted via message.to_dict())
        """
        self._ensure_messages_loaded()
        return {
            "id": self.id,
            "history_id": self.history_id,
            "message_count": self.message_count,
            "snippet": self.snippet,
            "subject": self.subject,
            "participants": list(self.participants),
            "has_unread": self.has_unread,
            "has_starred": self.has_starred,
            "labels": list(self.all_labels),
            "messages": [msg.to_dict() for msg in self.messages],
        }

    def __repr__(self) -> str:
        """
        Technical string representation of the Thread.

        Returns:
            str: String in format "Thread(id='...', messages=N, subject='...')"
        """
        return (
            f"Thread(id='{self.id}', "
            f"messages={self.message_count}, "
            f"subject='{self.subject[:50]}...')"
        )

    def __str__(self) -> str:
        """
        Human-readable string representation of the Thread.

        Returns:
            str: Formatted string with thread details and message list
        """
        self._ensure_messages_loaded()
        msg_list = "\n".join(
            f"  [{i+1}] {msg.from_email}: {msg.snippet[:50]}..."
            for i, msg in enumerate(self.messages)
        )
        return (
            f"Thread ID: {self.id}\n"
            f"Subject: {self.subject}\n"
            f"Messages: {self.message_count}\n"
            f"Participants: {', '.join(list(self.participants)[:3])}\n"
            f"Messages:\n{msg_list}"
        )

    def __len__(self) -> int:
        """
        Get number of messages (allows len(thread)).

        Returns:
            int: Number of messages in the thread
        """
        return self.message_count

    def __iter__(self):
        """
        Iterate over messages in the thread.

        Yields:
            Message: Each message in the thread (oldest to newest)
        """
        self._ensure_messages_loaded()
        return iter(self.messages)

    def __getitem__(self, index):
        """
        Get message by index (allows thread[0], thread[-1], etc.).

        Args:
            index (int): Message index (0 = oldest, -1 = newest)

        Returns:
            Message: Message at the specified index

        Raises:
            IndexError: If index is out of range
        """
        self._ensure_messages_loaded()
        return self.messages[index]

    def __eq__(self, other):
        """
        Check equality based on thread ID.

        Args:
            other: Another object to compare

        Returns:
            bool: True if both are Thread objects with the same ID
        """
        if not isinstance(other, Thread):
            return False
        return self.id == other.id

    def __hash__(self):
        """
        Hash based on thread ID for use in sets and dicts.

        Returns:
            int: Hash of the thread ID
        """
        return hash(self.id) if self.id else 0


class Message:
    """
    Represents a Gmail message with parsed data and utility methods.

    This class encapsulates email message data retrieved from the Gmail API and provides
    convenient access to commonly used fields like headers, body, and attachments. It
    automatically parses headers and decodes the message body from base64 encoding.

    Messages can be initialized either with full raw message data or just a message ID
    for lazy loading. When initialized with only a message ID, the full data is loaded
    automatically when any property is accessed.

    Messages belong to a Thread (conversation) and maintain a bidirectional relationship
    with their parent thread. A message can auto-create its parent thread if initialized
    without one.

    Attributes:
        id (str): Gmail message ID
        thread_id (str): Gmail thread ID that this message belongs to
        thread (Thread or None): Parent Thread object this message belongs to
        label_ids (list[str]): List of label IDs applied to this message (e.g., ['INBOX', 'UNREAD'])
        snippet (str): Short preview text of the message body
        history_id (str): Gmail history ID for syncing purposes
        internal_date (str): Internal timestamp from Gmail
        size_estimate (int): Estimated size of the message in bytes
        payload (dict): Raw payload data from Gmail API
        headers (dict): Parsed email headers as key-value pairs
        body (str): Decoded message body text (plain text or HTML)
        accessed_as_user (str or None): Email address of the user whose mailbox was accessed
            (set when using get_message_by_message_id_for_user)
        _data_loaded (bool): Whether full message data has been loaded
        _manager: Reference to ServiceAccountEmailManager for lazy loading

    Properties (Read-only):
        from_email (str): Sender's email address from 'From' header
        to_email (str): Recipient's email address from 'To' header
        subject (str): Email subject line from 'Subject' header
        date (str): Email date/time from 'Date' header
        cc_email (str): CC recipients from 'Cc' header
        bcc_email (str): BCC recipients from 'Bcc' header
        message_id (str): Message-ID header value
        reply_to (str): Reply-To address from 'Reply-To' header

    Methods:
        delete: Permanently delete the message from Gmail
        trash: Move the message to trash (recoverable for 30 days)
        untrash: Restore the message from trash
        modify: Add or remove labels from the message
        is_unread: Check if message is unread
        is_starred: Check if message is starred
        is_trash: Check if message is in trash
        is_first_in_thread: Check if this is the first (oldest) message in its thread
        has_attachments: Check if message has attachments
        get_attachments: Get list of attachment information
        to_dict: Convert message to dictionary representation
    """

    def __init__(
        self,
        raw_message: dict = None,
        message_id: str = None,
        thread=None,
        manager=None,
    ):
        """
        Initialize a Message from Gmail API response or message ID.

        Args:
            raw_message (dict, optional): Raw message dictionary from Gmail API.
                Should contain 'id', 'threadId', 'payload', etc.
            message_id (str, optional): Gmail message ID for lazy initialization.
                If provided without raw_message, full message data will be loaded when accessed.
            thread (Thread, optional): Parent Thread object this message belongs to.
                If None and the message has a threadId, a new Thread will be created.
            manager (ServiceAccountEmailManager, optional): Reference to email manager
                for lazy loading message/thread data. Required if using message_id only.

        Raises:
            ValueError: If neither raw_message nor message_id is provided, or if
                        message_id is empty
        """
        
        if raw_message is None and message_id is None:
            raise ValueError("Either raw_message or message_id must be provided")

        # Validate message_id if provided
        if message_id is not None and (not message_id or not str(message_id).strip()):
            raise ValueError("message_id cannot be empty or whitespace")

        self._raw = raw_message or {}
        self._manager = manager
        self._data_loaded = raw_message is not None

        # Set message ID
        self.id = raw_message.get("id") if raw_message else message_id

        # Validate extracted ID
        if not self.id or not str(self.id).strip():
            raise ValueError("Message ID cannot be empty")

        # Initialize with raw data if provided, otherwise set defaults for lazy loading
        if raw_message:
            self.thread_id = raw_message.get("threadId")
            self.label_ids = raw_message.get("labelIds", [])
            self.snippet = raw_message.get("snippet", "")
            self.history_id = raw_message.get("historyId")
            self.internal_date = raw_message.get("internalDate")
            self.size_estimate = raw_message.get("sizeEstimate")
            self.payload = raw_message.get("payload", {})
            self.accessed_as_user = raw_message.get("accessed_as_user")

            # Parse headers and decode body
            self.headers = self._parse_headers()
            self.body = self._decode_body()
        else:
            # Lazy loading - set defaults
            self.thread_id = None
            self.label_ids = []
            self.snippet = ""
            self.history_id = None
            self.internal_date = None
            self.size_estimate = None
            self.payload = {}
            self.accessed_as_user = None
            self.headers = {}
            self.body = ""

        # Handle thread relationship
        self.thread = None
        if thread is not None:
            # Attach to provided thread
            self.thread = thread
            # Only add to thread if not already present (prevents duplicates)
            if self not in thread.messages:
                thread.messages.append(self)
        elif self._data_loaded and self.thread_id and manager:
            # Auto-create thread with lazy loading (only if data is loaded)
            # Create thread without triggering message load to prevent circular creation
            self.thread = Thread(thread_id=self.thread_id, manager=manager)
            # Add this message to the thread without triggering _ensure_messages_loaded
            if self not in self.thread.messages:
                self.thread.messages.append(self)

    def _ensure_data_loaded(self):
        """
        Ensure message data is loaded (lazy loading support).

        If the message was initialized with only message_id, this will fetch
        the full message data from the API.
        """
        if not self._data_loaded and self._manager:
            try:
                # Fetch full message data
                raw_message = (
                    self._manager.service.users()
                    .messages()
                    .get(userId="me", id=self.id, format="full")
                    .execute()
                )

                # Update all properties
                self._raw = raw_message
                self.thread_id = raw_message.get("threadId")
                self.label_ids = raw_message.get("labelIds", [])
                self.snippet = raw_message.get("snippet", "")
                self.history_id = raw_message.get("historyId")
                self.internal_date = raw_message.get("internalDate")
                self.size_estimate = raw_message.get("sizeEstimate")
                self.payload = raw_message.get("payload", {})
                self.accessed_as_user = raw_message.get("accessed_as_user")

                # Parse headers and decode body
                self.headers = self._parse_headers()
                self.body = self._decode_body()

                # Mark as loaded
                self._data_loaded = True

                # Auto-create thread if needed
                if self.thread is None and self.thread_id and self._manager:
                    self.thread = Thread(
                        thread_id=self.thread_id, manager=self._manager
                    )
                    self.thread.add_message(self)

            except Exception as e:
                raise Exception(f"Failed to load message data for '{self.id}': {e}")

    def _parse_headers(self) -> dict:
        """
        Parse email headers from payload into a dictionary.

        Converts the Gmail API header format (list of name-value pairs) into a
        more accessible dictionary format for easy header lookup.

        Returns:
            dict: Dictionary mapping header names to their values
                (e.g., {'From': 'sender@example.com', 'Subject': 'Hello'})
        """
        headers_dict = {}
        if "headers" in self.payload:
            for header in self.payload["headers"]:
                headers_dict[header["name"]] = header["value"]
        return headers_dict

    def _decode_body(self) -> str:
        """
        Decode the email body from base64 encoding.

        Handles both simple message bodies and multipart messages. For multipart
        messages, concatenates text/plain and text/html parts.

        Returns:
            str: Decoded email body text. Returns empty string if body cannot be decoded.
        """
        body_text = ""

        if "body" in self.payload and "data" in self.payload["body"]:
            # Simple body
            try:
                body_text = base64.urlsafe_b64decode(
                    self.payload["body"]["data"]
                ).decode("utf-8", errors="ignore")
            except Exception as e:
                # Log decoding error for debugging
                print(f"Warning: Failed to decode message body for {self.id}: {e}")
        elif "parts" in self.payload:
            # Multipart message
            for part in self.payload["parts"]:
                if part.get("mimeType") in ["text/plain", "text/html"]:
                    if "data" in part.get("body", {}):
                        try:
                            body_text += base64.urlsafe_b64decode(
                                part["body"]["data"]
                            ).decode("utf-8", errors="ignore")
                        except Exception as e:
                            # Log decoding error for debugging
                            print(
                                f"Warning: Failed to decode message part for {self.id}: {e}"
                            )

        return body_text

    # Header convenience properties
    @property
    def from_email(self) -> str:
        """
        Get the From email address.

        Returns:
            str: Sender's email address from the 'From' header, or empty string if not present
        """
        self._ensure_data_loaded()
        return self.headers.get("From", "")

    @property
    def to_email(self) -> str:
        """
        Get the To email address.

        Returns:
            str: Recipient's email address from the 'To' header, or empty string if not present
        """
        self._ensure_data_loaded()
        return self.headers.get("To", "")

    @property
    def to_email_list(self) -> list:
        """
        Get the To email addresses as a list.

        Returns:
            list: List of recipient email addresses from the 'To' header
        """
        self._ensure_data_loaded()
        to_header = self.headers.get("To", "")
        return [addr.strip() for addr in to_header.split(",")] if to_header else []

    @property
    def subject(self) -> str:
        """
        Get the email subject.

        Returns:
            str: Email subject line from the 'Subject' header, or empty string if not present
        """
        self._ensure_data_loaded()
        return self.headers.get("Subject", "")

    @property
    def date(self) -> str:
        """
        Get the email date.

        Returns:
            str: Email date/time from the 'Date' header, or empty string if not present
        """
        self._ensure_data_loaded()
        return self.headers.get("Date", "")

    @property
    def cc_email(self) -> str:
        """
        Get the CC email addresses.

        Returns:
            str: CC recipients from the 'Cc' header, or empty string if not present
        """
        self._ensure_data_loaded()
        return self.headers.get("Cc", "")

    @property
    def cc_email_list(self) -> list:
        """
        Get the CC email addresses as a list.

        Returns:
            list: List of CC email addresses from the 'Cc' header
        """
        self._ensure_data_loaded()
        cc_header = self.headers.get("Cc", "")
        return [addr.strip() for addr in cc_header.split(",")] if cc_header else []

    @property
    def bcc_email(self) -> str:
        """
        Get the BCC email addresses.

        Returns:
            str: BCC recipients from the 'Bcc' header, or empty string if not present
        """
        self._ensure_data_loaded()
        return self.headers.get("Bcc", "")

    @property
    def bcc_email_list(self) -> list:
        """
        Get the BCC email addresses as a list.

        Returns:
            list: List of BCC email addresses from the 'Bcc' header
        """
        self._ensure_data_loaded()
        bcc_header = self.headers.get("Bcc", "")
        return [addr.strip() for addr in bcc_header.split(",")] if bcc_header else []

    @property
    def message_id(self) -> str:
        """
        Get the Message-ID header.

        Returns:
            str: Unique message identifier from the 'Message-ID' header, or empty string if not present
        """
        self._ensure_data_loaded()
        return self.headers.get("Message-ID", "")

    @property
    def reply_to(self) -> str:
        """
        Get the Reply-To address.

        Returns:
            str: Reply-To email address from the 'Reply-To' header, or empty string if not present
        """
        self._ensure_data_loaded()
        return self.headers.get("Reply-To", "")

    # Utility methods
    def is_unread(self) -> bool:
        """
        Check if the message is unread.

        Returns:
            bool: True if the message has the 'UNREAD' label, False otherwise
        """
        return "UNREAD" in self.label_ids

    def is_starred(self) -> bool:
        """
        Check if the message is starred.

        Returns:
            bool: True if the message has the 'STARRED' label, False otherwise
        """
        return "STARRED" in self.label_ids

    def is_important(self) -> bool:
        """
        Check if the message is marked as important.

        Returns:
            bool: True if the message has the 'IMPORTANT' label, False otherwise
        """
        return "IMPORTANT" in self.label_ids

    def is_in_inbox(self) -> bool:
        """
        Check if the message is in the inbox.

        Returns:
            bool: True if the message has the 'INBOX' label, False otherwise
        """
        return "INBOX" in self.label_ids

    def is_sent(self) -> bool:
        """
        Check if the message is in sent folder.

        Returns:
            bool: True if the message has the 'SENT' label, False otherwise
        """
        return "SENT" in self.label_ids

    def is_draft(self) -> bool:
        """
        Check if the message is a draft.

        Returns:
            bool: True if the message has the 'DRAFT' label, False otherwise
        """
        return "DRAFT" in self.label_ids

    def is_spam(self) -> bool:
        """
        Check if the message is marked as spam.

        Returns:
            bool: True if the message has the 'SPAM' label, False otherwise
        """
        return "SPAM" in self.label_ids

    def is_trash(self) -> bool:
        """
        Check if the message is in trash.

        Returns:
            bool: True if the message has the 'TRASH' label, False otherwise
        """
        return "TRASH" in self.label_ids

    def is_first_in_thread(self) -> bool:
        """
        Check if this message is the first (oldest) message in its thread.

        This method compares the message's ID with the first message in the thread.
        Requires that the thread has been loaded and contains messages.

        Returns:
            bool: True if this is the first message in the thread, False otherwise.
                Returns False if the thread is not set or has no messages.

        Note:
            - Returns False if self.thread is None
            - Returns False if the thread has no messages
            - Ensures thread messages are loaded before comparison
            - A thread's first message is typically the original email that started
                the conversation
        """
        if self.thread is None:
            return False

        # Ensure thread messages are loaded
        self.thread._ensure_messages_loaded()

        # Check if thread has messages
        if not self.thread.messages:
            return False

        # Compare with first message in thread
        first_message = self.thread.first_message
        return first_message is not None and self.id == first_message.id

    def has_attachments(self) -> bool:
        """
        Check if the message has attachments.

        Returns:
            bool: True if the message contains any file attachments, False otherwise
        """
        if "parts" in self.payload:
            for part in self.payload["parts"]:
                if part.get("filename"):
                    return True
        return False

    def get_attachments(self) -> list:
        """
        Get list of attachment information.

        Returns:
            list: List of dictionaries containing attachment metadata. Each dict contains:
                - filename (str): Name of the attached file
                - mimeType (str): MIME type of the attachment (e.g., 'application/pdf')
                - size (int): Size of the attachment in bytes
                - attachmentId (str): Gmail attachment ID for downloading the file
        """
        attachments = []
        if "parts" in self.payload:
            for part in self.payload["parts"]:
                if part.get("filename"):
                    attachments.append(
                        {
                            "filename": part["filename"],
                            "mimeType": part.get("mimeType"),
                            "size": part.get("body", {}).get("size", 0),
                            "attachmentId": part.get("body", {}).get("attachmentId"),
                        }
                    )
        return attachments

    def to_dict(self) -> dict:
        """
        Convert Message to dictionary representation.

        This method is useful for JSON serialization or when you need to pass
        message data to systems that expect dictionary format.

        Returns:
            dict: Dictionary containing all message data with keys:
                - id: Message ID
                - thread_id: Thread ID
                - label_ids: List of label IDs
                - snippet: Message preview
                - history_id: History ID
                - internal_date: Internal timestamp
                - size_estimate: Size in bytes
                - headers: Full headers dictionary
                - body: Decoded body text
                - from: Sender email address
                - to: Recipient email address
                - subject: Email subject
                - date: Email date
                - accessed_as_user: User whose mailbox was accessed
                - has_attachments: Boolean indicating if attachments exist
                - attachments: List of attachment info dicts
        """
        return {
            "id": self.id,
            "thread_id": self.thread_id,
            "label_ids": self.label_ids,
            "snippet": self.snippet,
            "history_id": self.history_id,
            "internal_date": self.internal_date,
            "size_estimate": self.size_estimate,
            "headers": self.headers,
            "body": self.body,
            "from": self.from_email,
            "to": self.to_email,
            "subject": self.subject,
            "date": self.date,
            "accessed_as_user": self.accessed_as_user,
            "has_attachments": self.has_attachments(),
            "attachments": self.get_attachments(),
        }

    def delete(self):
        """
        Permanently delete this message from Gmail.

        This deletes the message permanently (not to trash). The message is removed
        from its thread and all message references are cleared.

        Raises:
            Exception: If the message cannot be deleted (no manager, API error, etc.)

        Warning:
            AFAIK this operation is permanent and cannot be undone. The message will be
            permanently deleted from Gmail (not moved to trash).

        Note:
            Requires a manager reference (_manager) to perform the deletion.
            If the message was created without a manager, this will raise an exception.
            After deletion, the message's thread reference is cleared.
            If this was the last message in the thread, the thread becomes empty.
        """
        if not self._manager:
            raise Exception(
                "Cannot delete message: No manager reference. "
                "Message must be created with a manager to support deletion."
            )

        try:
            # Delete the message via Gmail API
            self._manager.service.users().messages().delete(
                userId="me", id=self.id
            ).execute()

            # Remove from thread if attached
            if self.thread and self in self.thread.messages:
                self.thread.messages.remove(self)
                # If thread is now empty, mark it as effectively dead
                if len(self.thread.messages) == 0:
                    # Thread is empty but we don't delete the Thread object
                    # since the user may still have a reference to it
                    pass

            # Clear thread reference
            self.thread = None

        except Exception as e:
            raise Exception(f"Failed to delete message '{self.id}': {e}")

    def trash(self):
        """
        Move this message to trash.

        This moves the message to the trash folder, where it can be restored
        using untrash() or will be permanently deleted after 30 days.

        Raises:
            Exception: If the message cannot be trashed (no manager, API error, etc.)
        
        Note:
            Requires a manager reference (_manager) to perform the operation.
            Messages in trash are automatically deleted after 30 days.
            The message's label_ids will be updated to include 'TRASH'.
        """
        if not self._manager:
            raise Exception(
                "Cannot trash message: No manager reference. "
                "Message must be created with a manager to support trash operation."
            )

        try:
            # Trash the message via Gmail API
            result = (
                self._manager.service.users()
                .messages()
                .trash(userId="me", id=self.id)
                .execute()
            )

            # Update label_ids to reflect trash status
            self.label_ids = result.get("labelIds", [])

        except Exception as e:
            raise Exception(f"Failed to trash message '{self.id}': {e}")

    def untrash(self):
        """
        Restore this message from trash.

        This removes the message from the trash folder and restores it to its
        previous labels (inbox, etc.).

        Raises:
            Exception: If the message cannot be untrashed (no manager, API error, etc.)

        Note:
            Requires a manager reference (_manager) to perform the operation.
            The message's label_ids will be updated to remove 'TRASH'.
            Only works on messages currently in trash.
        """
        if not self._manager:
            raise Exception(
                "Cannot untrash message: No manager reference. "
                "Message must be created with a manager to support untrash operation."
            )

        try:
            # Untrash the message via Gmail API
            result = (
                self._manager.service.users()
                .messages()
                .untrash(userId="me", id=self.id)
                .execute()
            )

            # Update label_ids to reflect restored status
            self.label_ids = result.get("labelIds", [])

        except Exception as e:
            raise Exception(f"Failed to untrash message '{self.id}': {e}")

    def modify_labels(self, label_ids: list, action: str = "add"):
        """
        Add or remove labels from this message.

        This method modifies the labels applied to the message by either adding
        new labels or removing existing ones. The message's label_ids attribute
        is automatically updated to reflect the changes.

        Args:
            label_ids (list): List of label IDs to add or remove.
                Can be system labels (e.g., 'INBOX', 'UNREAD', 'STARRED') or
                user-created label IDs (e.g., 'Label_123').
            action (str, optional): Action to perform. Must be either:
                - "add": Add the specified labels to the message (default)
                - "remove": Remove the specified labels from the message

        Raises:
            ValueError: If action is not "add" or "remove", or if label_ids is empty
            Exception: If the manager reference is not set or API call fails

        Returns:
            Message: Self (for method chaining)

        Note:
            - Requires a manager reference (_manager) to perform the operation
            - The label_ids attribute is automatically updated after modification
            - System labels: INBOX, SPAM, TRASH, UNREAD, STARRED, IMPORTANT, SENT, DRAFT
            - User labels: Create with Label class or use existing label IDs
            - Some system labels cannot be modified (e.g., CHAT, CATEGORY_*)

        See Also:
            - trash(): Move message to trash (adds TRASH label)
            - untrash(): Restore from trash (removes TRASH label)
            - Label class: Create and manage custom labels
        """
        # Validate action
        if action not in ["add", "remove"]:
            raise ValueError(f"Invalid action '{action}'. Must be 'add' or 'remove'.")

        # Validate label_ids
        if not label_ids:
            raise ValueError("label_ids cannot be empty.")

        if not isinstance(label_ids, list):
            raise ValueError("label_ids must be a list of label ID strings.")

        if not self._manager:
            raise Exception(
                "Cannot modify message labels: No manager reference. "
                "Message must be created with a manager to support label modification."
            )

        try:
            # Build the request body based on action
            body = {}
            if action == "add":
                body["addLabelIds"] = label_ids
            else:  # action == "remove"
                body["removeLabelIds"] = label_ids

            # Modify the message via Gmail API
            result = (
                self._manager.service.users()
                .messages()
                .modify(userId="me", id=self.id, body=body)
                .execute()
            )

            # Update label_ids to reflect changes
            self.label_ids = result.get("labelIds", [])

            return self

        except Exception as e:
            raise Exception(
                f"Failed to {action} labels {label_ids} for message '{self.id}': {e}"
            )

    def __repr__(self) -> str:
        """
        Technical string representation of the Message.

        Returns:
            str: String in format "Message(id='...', from='...', subject='...')"
        """
        return (
            f"Message(id='{self.id}', "
            f"from='{self.from_email}', "
            f"subject='{self.subject[:50]}...')"
        )

    def __str__(self) -> str:
        """
        Human-readable string representation of the Message.

        Returns:
            str: Formatted string with From, To, Subject, Date, and body preview
        """
        return (
            f"From: {self.from_email}\n"
            f"To: {self.to_email}\n"
            f"Subject: {self.subject}\n"
            f"Date: {self.date}\n"
            f"Body: {self.body[:100]}..."
        )

    def __eq__(self, other):
        """
        Check equality based on message ID.

        Args:
            other: Another object to compare

        Returns:
            bool: True if both are Message objects with the same ID
        """
        if not isinstance(other, Message):
            return False
        return self.id == other.id

    def __hash__(self):
        """
        Hash based on message ID for use in sets and dicts.

        Returns:
            int: Hash of the message ID
        """
        return hash(self.id) if self.id else 0


class Label:
    """
    Represents a Gmail label with properties and methods.

    This class provides a complete interface for managing Gmail labels including
    creation, retrieval, updating, and deletion of labels.

    Attributes:
        id (str): The immutable ID of the label
        name (str): The display name of the label
        color (dict): Color settings with textColor and backgroundColor
        labelListVisibility (str): Visibility in label list (labelShow, labelHide, labelShowIfUnread)
        messageListVisibility (str): Visibility in message list (show, hide)
        type (str): Type of label (system or user)
        messagesTotal (int): Total number of messages with this label
        messagesUnread (int): Number of unread messages with this label
        threadsTotal (int): Total number of threads with this label
        threadsUnread (int): Number of unread threads with this label
        _manager: Reference to ServiceAccountEmailManager for API calls

    Methods:
        create_label: Create a new label in Gmail
        get: Retrieve label details from Gmail
        list: List all labels (static method)
        update: Update label properties
        patch: Partially update label properties
        delete: Delete the label from Gmail
    """

    def __init__(
        self,
        label_id: str = None,
        name: str = None,
        text_color: str = None,
        background_color: str = None,
        labelListVisibility: str = "labelShow",
        messageListVisibility: str = "show",
        manager=None,
        create_if_missing: bool = False,
    ):
        valid_colors = [
            "#000000",
            "#434343",
            "#666666",
            "#999999",
            "#cccccc",
            "#efefef",
            "#f3f3f3",
            "#ffffff",
            "#fb4c2f",
            "#ffad47",
            "#fad165",
            "#16a766",
            "#43d692",
            "#4a86e8",
            "#a479e2",
            "#f691b3",
            "#f6c5be",
            "#ffe6c7",
            "#fef1d1",
            "#b9e4d0",
            "#c6f3de",
            "#c9daf8",
            "#e4d7f5",
            "#fcdee8",
            "#efa093",
            "#ffd6a2",
            "#fce8b3",
            "#89d3b2",
            "#a0eac9",
            "#a4c2f4",
            "#d0bcf1",
            "#fbc8d9",
            "#e66550",
            "#ffbc6b",
            "#fcda83",
            "#44b984",
            "#68dfa9",
            "#6d9eeb",
            "#b694e8",
            "#f7a7c0",
            "#cc3a21",
            "#eaa041",
            "#f2c960",
            "#149e60",
            "#3dc789",
            "#3c78d8",
            "#8e63ce",
            "#e07798",
            "#ac2b16",
            "#cf8933",
            "#d5ae49",
            "#0b804b",
            "#2a9c68",
            "#285bac",
            "#653e9b",
            "#b65775",
            "#822111",
            "#a46a21",
            "#aa8831",
            "#076239",
            "#1a764d",
            "#1c4587",
            "#41236d",
            "#83334c",
            "#464646",
            "#e7e7e7",
            "#0d3472",
            "#b6cff5",
            "#0d3b44",
            "#98d7e4",
            "#3d188e",
            "#e3d7ff",
            "#711a36",
            "#fbd3e0",
            "#8a1c0a",
            "#f2b2a8",
            "#7a2e0b",
            "#ffc8af",
            "#7a4706",
            "#ffdeb5",
            "#594c05",
            "#fbe983",
            "#684e07",
            "#fdedc1",
            "#0b4f30",
            "#b3efd3",
            "#04502e",
            "#a2dcc1",
            "#c2c2c2",
            "#4986e7",
            "#2da2bb",
            "#b99aff",
            "#994a64",
            "#f691b2",
            "#ff7537",
            "#ffad46",
            "#662e37",
            "#ebdbde",
            "#cca6ac",
            "#094228",
            "#42d692",
            "#16a765",
        ]
        self.id = label_id
        self.name = name
        self.labelListVisibility = labelListVisibility
        self.messageListVisibility = messageListVisibility
        self._manager = manager
        self.type = None
        self.messagesTotal = None
        self.messagesUnread = None
        self.threadsTotal = None
        self.threadsUnread = None

        # Handle color generation - only generate if creating a new label
        if label_id is None and create_if_missing:
            # Generate colors if not provided
            if text_color is None or background_color is None:
                # Generate random background color
                generated_bg = random.choice(valid_colors)

                # Calculate appropriate text color based on background luminance
                hex_code = int(generated_bg.lstrip("#"), 16)
                r = (hex_code >> 16) & 0xFF
                g = (hex_code >> 8) & 0xFF
                b = hex_code & 0xFF

                # Calculate luminance using standard formula
                luminance = 0.299 * r + 0.587 * g + 0.114 * b

                # Choose contrasting text color based on luminance
                generated_text = "#000000" if luminance > 128 else "#ffffff"

                # Use generated colors only if not provided
                if background_color is None:
                    background_color = generated_bg
                if text_color is None:
                    text_color = generated_text

        # Set color dictionary
        self.color = {
            "textColor": text_color,
            "backgroundColor": background_color,
        }

        # Auto-create label if this is a new label and manager is provided
        if label_id is None and self._manager and create_if_missing:
            self.create_label()

    def create_label(self):
        """
        Create a new label in Gmail.

        Creates the label using the Gmail API with the current label properties.
        Updates the label's ID and other properties from the API response.

        Returns:
            Label: Self (for method chaining)

        Raises:
            ValueError: If label name is not provided
            Exception: If the manager reference is not set or API call fails
        """
        if not self.name:
            raise ValueError("Label name must be provided to create a new label.")

        if not self._manager:
            raise Exception(
                "Cannot create label: No manager reference. "
                "Label must be created with a manager to support API operations."
            )

        try:
            label_object = {
                "name": self.name,
                "color": self.color,
                "labelListVisibility": self.labelListVisibility,
                "messageListVisibility": self.messageListVisibility,
            }

            # Create the label via Gmail API
            response = (
                self._manager.service.users()
                .labels()
                .create(userId="me", body=label_object)
                .execute()
            )

            # Update label properties from response
            self.id = response.get("id")
            self.name = response.get("name")
            self.type = response.get("type")
            self.messagesTotal = response.get("messagesTotal", 0)
            self.messagesUnread = response.get("messagesUnread", 0)
            self.threadsTotal = response.get("threadsTotal", 0)
            self.threadsUnread = response.get("threadsUnread", 0)

            if "color" in response:
                self.color = response["color"]

            if "labelListVisibility" in response:
                self.labelListVisibility = response["labelListVisibility"]

            if "messageListVisibility" in response:
                self.messageListVisibility = response["messageListVisibility"]

            return self

        except Exception as e:
            raise Exception(f"Failed to create label '{self.name}': {e}")

    def get(self):
        """
        Retrieve label details from Gmail and update this object.

        Fetches the latest label information from Gmail API and updates
        all properties of this Label object.

        Returns:
            Label: Self (for method chaining)

        Raises:
            Exception: If the manager reference is not set, label ID is missing, or API call fails
        """
        if not self._manager:
            raise Exception(
                "Cannot get label: No manager reference. "
                "Label must have a manager to support API operations."
            )

        if not self.id:
            raise Exception("Cannot get label: Label ID is required.")

        try:
            # Get label details via Gmail API
            response = (
                self._manager.service.users()
                .labels()
                .get(userId="me", id=self.id)
                .execute()
            )

            # Update all properties from response
            self.id = response.get("id")
            self.name = response.get("name")
            self.type = response.get("type")
            self.messagesTotal = response.get("messagesTotal", 0)
            self.messagesUnread = response.get("messagesUnread", 0)
            self.threadsTotal = response.get("threadsTotal", 0)
            self.threadsUnread = response.get("threadsUnread", 0)

            if "color" in response:
                self.color = response["color"]

            if "labelListVisibility" in response:
                self.labelListVisibility = response["labelListVisibility"]

            if "messageListVisibility" in response:
                self.messageListVisibility = response["messageListVisibility"]

            return self

        except Exception as e:
            raise Exception(f"Failed to get label '{self.id}': {e}")

    @staticmethod
    def list(manager):
        """
        List all labels for the authenticated user.

        Retrieves all labels (both user-created and system labels) from Gmail.

        Args:
            manager: ServiceAccountEmailManager instance for API access

        Returns:
            list[Label]: List of Label objects

        Raises:
            Exception: If manager is not provided or API call fails
        """
        if not manager:
            raise Exception("Manager reference is required to list labels.")

        try:
            # List all labels via Gmail API
            response = manager.service.users().labels().list(userId="me").execute()

            labels = []
            if "labels" in response:
                for label_data in response["labels"]:
                    label = Label(
                        label_id=label_data.get("id"),
                        name=label_data.get("name"),
                        manager=manager,
                    )

                    # Update properties from response
                    label.type = label_data.get("type")
                    label.messagesTotal = label_data.get("messagesTotal", 0)
                    label.messagesUnread = label_data.get("messagesUnread", 0)
                    label.threadsTotal = label_data.get("threadsTotal", 0)
                    label.threadsUnread = label_data.get("threadsUnread", 0)

                    if "color" in label_data:
                        label.color = label_data["color"]

                    if "labelListVisibility" in label_data:
                        label.labelListVisibility = label_data["labelListVisibility"]

                    if "messageListVisibility" in label_data:
                        label.messageListVisibility = label_data[
                            "messageListVisibility"
                        ]

                    labels.append(label)

            return labels

        except Exception as e:
            raise Exception(f"Failed to list labels: {e}")

    def update(self):
        """
        Update all properties of the label in Gmail.

        Performs a full update (PUT) of the label, replacing all modifiable properties.
        Use patch() for partial updates.

        Returns:
            Label: Self (for method chaining)

        Raises:
            Exception: If the manager reference is not set, label ID is missing, or API call fails
        """
        if not self._manager:
            raise Exception(
                "Cannot update label: No manager reference. "
                "Label must have a manager to support API operations."
            )

        if not self.id:
            raise Exception("Cannot update label: Label ID is required.")

        try:
            label_object = {
                "id": self.id,
                "name": self.name,
                "color": self.color,
                "labelListVisibility": self.labelListVisibility,
                "messageListVisibility": self.messageListVisibility,
            }

            # Update the label via Gmail API
            response = (
                self._manager.service.users()
                .labels()
                .update(userId="me", id=self.id, body=label_object)
                .execute()
            )

            # Update properties from response
            self.id = response.get("id")
            self.name = response.get("name")
            self.type = response.get("type")
            self.messagesTotal = response.get("messagesTotal", 0)
            self.messagesUnread = response.get("messagesUnread", 0)
            self.threadsTotal = response.get("threadsTotal", 0)
            self.threadsUnread = response.get("threadsUnread", 0)

            if "color" in response:
                self.color = response["color"]

            if "labelListVisibility" in response:
                self.labelListVisibility = response["labelListVisibility"]

            if "messageListVisibility" in response:
                self.messageListVisibility = response["messageListVisibility"]

            return self

        except Exception as e:
            raise Exception(f"Failed to update label '{self.id}': {e}")

    def patch(self, **kwargs):
        """
        Partially update label properties in Gmail.

        Performs a partial update (PATCH) of the label, updating only specified properties.
        Use update() for full updates.

        Args:
            **kwargs: Label properties to update. Supported keys:
                - name (str): New label name
                - text_color (str): New text color hex code
                - background_color (str): New background color hex code
                - labelListVisibility (str): Label list visibility
                - messageListVisibility (str): Message list visibility
                - color (dict): Full color object with textColor and backgroundColor

        Returns:
            Label: Self (for method chaining)

        Raises:
            Exception: If the manager reference is not set, label ID is missing, or API call fails
        """
        if not self._manager:
            raise Exception(
                "Cannot patch label: No manager reference. "
                "Label must have a manager to support API operations."
            )

        if not self.id:
            raise Exception("Cannot patch label: Label ID is required.")

        try:
            label_object = {"id": self.id}

            # Build patch object from kwargs
            if "name" in kwargs:
                label_object["name"] = kwargs["name"]
                self.name = kwargs["name"]

            if "color" in kwargs:
                label_object["color"] = kwargs["color"]
                self.color = kwargs["color"]
            elif "text_color" in kwargs or "background_color" in kwargs:
                color_obj = {}
                if "text_color" in kwargs:
                    color_obj["textColor"] = kwargs["text_color"]
                    self.color["textColor"] = kwargs["text_color"]
                if "background_color" in kwargs:
                    color_obj["backgroundColor"] = kwargs["background_color"]
                    self.color["backgroundColor"] = kwargs["background_color"]
                label_object["color"] = color_obj

            if "labelListVisibility" in kwargs:
                label_object["labelListVisibility"] = kwargs["labelListVisibility"]
                self.labelListVisibility = kwargs["labelListVisibility"]

            if "messageListVisibility" in kwargs:
                label_object["messageListVisibility"] = kwargs["messageListVisibility"]
                self.messageListVisibility = kwargs["messageListVisibility"]

            # Patch the label via Gmail API
            response = (
                self._manager.service.users()
                .labels()
                .patch(userId="me", id=self.id, body=label_object)
                .execute()
            )

            # Update properties from response
            self.id = response.get("id")
            self.name = response.get("name")
            self.type = response.get("type")
            self.messagesTotal = response.get("messagesTotal", 0)
            self.messagesUnread = response.get("messagesUnread", 0)
            self.threadsTotal = response.get("threadsTotal", 0)
            self.threadsUnread = response.get("threadsUnread", 0)

            if "color" in response:
                self.color = response["color"]

            if "labelListVisibility" in response:
                self.labelListVisibility = response["labelListVisibility"]

            if "messageListVisibility" in response:
                self.messageListVisibility = response["messageListVisibility"]

            return self

        except Exception as e:
            raise Exception(f"Failed to patch label '{self.id}': {e}")

    def delete(self):
        """
        Permanently delete this label from Gmail.

        Deletes the label from Gmail. Messages with this label will not be deleted,
        but the label will be removed from all messages.

        Raises:
            Exception: If the manager reference is not set, label ID is missing, or API call fails

        Warning:
            System labels (INBOX, SENT, TRASH, etc.) cannot be deleted.
            Only user-created labels can be deleted.
        """
        if not self._manager:
            raise Exception(
                "Cannot delete label: No manager reference. "
                "Label must have a manager to support API operations."
            )

        if not self.id:
            raise Exception("Cannot delete label: Label ID is required.")

        try:
            # Delete the label via Gmail API
            self._manager.service.users().labels().delete(
                userId="me", id=self.id
            ).execute()

        except Exception as e:
            raise Exception(f"Failed to delete label '{self.id}': {e}")

    def to_dict(self) -> dict:
        """
        Convert Label to dictionary representation.

        Returns:
            dict: Dictionary containing all label properties
        """
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "color": self.color,
            "labelListVisibility": self.labelListVisibility,
            "messageListVisibility": self.messageListVisibility,
            "messagesTotal": self.messagesTotal,
            "messagesUnread": self.messagesUnread,
            "threadsTotal": self.threadsTotal,
            "threadsUnread": self.threadsUnread,
        }

    def __repr__(self) -> str:
        """String representation of the Label."""
        return f"Label(id='{self.id}', name='{self.name}', type='{self.type}')"

    def __str__(self) -> str:
        """Human-readable string representation of the Label."""
        return (
            f"Label: {self.name} (ID: {self.id})\n"
            f"Type: {self.type}\n"
            f"Messages: {self.messagesTotal} total, {self.messagesUnread} unread\n"
            f"Threads: {self.threadsTotal} total, {self.threadsUnread} unread"
        )


class SendAsAlias:
    """
    Represents a Gmail send-as alias (custom "From" address).

    A send-as alias allows sending emails from a different email address while using
    Gmail. This is useful for managing multiple email identities or sending from
    custom domains through Gmail.

    Attributes:
        send_as_email (str): The email address that appears in the "From" header
        display_name (str): The name that appears with the email address
        reply_to_address (str): The email address for replies
        signature (str): HTML signature to append to outgoing messages
        is_primary (bool): Whether this is the primary send-as address
        is_default (bool): Whether this is the default send-as address
        treat_as_alias (bool): Whether Gmail should treat this as an alias
        smtp_msa (dict): SMTP relay configuration (host, port, username, password, security mode)
        verification_status (str): Verification status ("accepted", "pending", "verificationStatusUnspecified")
        _manager (ServiceAccountEmailManager or None): Reference to email manager for API operations

    Properties (Read-only):
        is_verified (bool): True if the alias is verified (status is "accepted")

    Methods:
        create: Create a new send-as alias in Gmail
        get: Refresh alias data from Gmail
        update: Update all modifiable alias properties
        patch: Update specific alias properties
        delete: Remove the send-as alias
        verify: Send verification email for the alias
        to_dict: Convert alias to dictionary representation
    """

    def __init__(
        self,
        send_as_email: str = None,
        display_name: str = None,
        reply_to_address: str = None,
        signature: str = "",
        is_primary: bool = False,
        is_default: bool = False,
        treat_as_alias: bool = True,
        smtp_msa: dict = None,
        verification_status: str = None,
        manager=None,
        raw_alias: dict = None,
    ):
        """
        Initialize a SendAsAlias instance.

        Args:
            send_as_email (str, optional): The email address for the send-as alias
            display_name (str, optional): Display name for the alias
            reply_to_address (str, optional): Reply-to email address
            signature (str, optional): HTML signature (default: "")
            is_primary (bool, optional): Whether this is primary address (default: False)
            is_default (bool, optional): Whether this is default address (default: False)
            treat_as_alias (bool, optional): Treat as alias (default: True)
            smtp_msa (dict, optional): SMTP configuration with keys: host, port, username,
                password, securityMode
            verification_status (str, optional): Verification status
            manager (ServiceAccountEmailManager, optional): Email manager reference
            raw_alias (dict, optional): Raw alias data from Gmail API

        Note:
            If raw_alias is provided, it takes precedence and populates all attributes
            from the API response data.
        """
        self._manager = manager

        if raw_alias:
            # Initialize from raw API data
            self.send_as_email = raw_alias.get("sendAsEmail")
            self.display_name = raw_alias.get("displayName", "")
            self.reply_to_address = raw_alias.get("replyToAddress", "")
            self.signature = raw_alias.get("signature", "")
            self.is_primary = raw_alias.get("isPrimary", False)
            self.is_default = raw_alias.get("isDefault", False)
            self.treat_as_alias = raw_alias.get("treatAsAlias", True)
            self.smtp_msa = raw_alias.get("smtpMsa")
            self.verification_status = raw_alias.get("verificationStatus")
        else:
            # Initialize from provided parameters
            self.send_as_email = send_as_email
            self.display_name = display_name or ""
            self.reply_to_address = reply_to_address or ""
            self.signature = signature or ""
            self.is_primary = is_primary
            self.is_default = is_default
            self.treat_as_alias = treat_as_alias
            self.smtp_msa = smtp_msa
            self.verification_status = verification_status

    @property
    def is_verified(self) -> bool:
        """Check if the send-as alias is verified."""
        return self.verification_status == "accepted"

    def create(self):
        """
        Create a new send-as alias in Gmail.

        Creates the alias using the Gmail API. After creation, a verification email
        will be sent to the send-as address unless it's the primary address or
        already verified.

        Returns:
            SendAsAlias: Self for method chaining

        Raises:
            Exception: If manager reference is missing, send_as_email is not set,
                or API call fails
        """
        if not self._manager:
            raise Exception(
                "Cannot create alias: No manager reference. "
                "Alias must have a manager to support API operations."
            )

        if not self.send_as_email:
            raise Exception("Cannot create alias: send_as_email is required.")

        try:
            # Build request body
            body = {
                "sendAsEmail": self.send_as_email,
                "displayName": self.display_name,
                "replyToAddress": self.reply_to_address or self.send_as_email,
                "signature": self.signature,
                "treatAsAlias": self.treat_as_alias,
            }

            # Add SMTP configuration if provided
            if self.smtp_msa:
                body["smtpMsa"] = self.smtp_msa

            # Create the send-as alias
            result = (
                self._manager.service.users()
                .settings()
                .sendAs()
                .create(userId="me", body=body)
                .execute()
            )

            # Update properties from response
            self.send_as_email = result.get("sendAsEmail")
            self.display_name = result.get("displayName", "")
            self.reply_to_address = result.get("replyToAddress", "")
            self.signature = result.get("signature", "")
            self.is_primary = result.get("isPrimary", False)
            self.is_default = result.get("isDefault", False)
            self.treat_as_alias = result.get("treatAsAlias", True)
            self.smtp_msa = result.get("smtpMsa")
            self.verification_status = result.get("verificationStatus")

            return self

        except Exception as e:
            raise Exception(
                f"Failed to create send-as alias '{self.send_as_email}': {e}"
            )

    def get(self):
        """
        Refresh alias data from Gmail.

        Fetches the latest alias information from Gmail and updates all properties.

        Returns:
            SendAsAlias: Self for method chaining

        Raises:
            Exception: If manager reference is missing, send_as_email is not set,
                or API call fails
        """
        if not self._manager:
            raise Exception(
                "Cannot get alias: No manager reference. "
                "Alias must have a manager to support API operations."
            )

        if not self.send_as_email:
            raise Exception("Cannot get alias: send_as_email is required.")

        try:
            # Get the send-as alias
            result = (
                self._manager.service.users()
                .settings()
                .sendAs()
                .get(userId="me", sendAsEmail=self.send_as_email)
                .execute()
            )

            # Update properties from response
            self.send_as_email = result.get("sendAsEmail")
            self.display_name = result.get("displayName", "")
            self.reply_to_address = result.get("replyToAddress", "")
            self.signature = result.get("signature", "")
            self.is_primary = result.get("isPrimary", False)
            self.is_default = result.get("isDefault", False)
            self.treat_as_alias = result.get("treatAsAlias", True)
            self.smtp_msa = result.get("smtpMsa")
            self.verification_status = result.get("verificationStatus")

            return self

        except Exception as e:
            raise Exception(f"Failed to get send-as alias '{self.send_as_email}': {e}")

    def update(self):
        """
        Update all modifiable properties of the send-as alias.

        Performs a full update (PUT) of the alias, replacing all modifiable fields
        with the current property values. Use patch() for partial updates.

        Returns:
            SendAsAlias: Self for method chaining

        Raises:
            Exception: If manager reference is missing, send_as_email is not set,
                or API call fails

        Note:
            Cannot modify is_primary, is_default, or verification_status directly.
            These are managed by Gmail based on verification and user settings.
        """
        if not self._manager:
            raise Exception(
                "Cannot update alias: No manager reference. "
                "Alias must have a manager to support API operations."
            )

        if not self.send_as_email:
            raise Exception("Cannot update alias: send_as_email is required.")

        try:
            # Build request body with all modifiable fields
            body = {
                "sendAsEmail": self.send_as_email,
                "displayName": self.display_name,
                "replyToAddress": self.reply_to_address or self.send_as_email,
                "signature": self.signature,
                "treatAsAlias": self.treat_as_alias,
            }

            # Add SMTP configuration if provided
            if self.smtp_msa:
                body["smtpMsa"] = self.smtp_msa

            # Update the send-as alias
            result = (
                self._manager.service.users()
                .settings()
                .sendAs()
                .update(userId="me", sendAsEmail=self.send_as_email, body=body)
                .execute()
            )

            # Update properties from response
            self.display_name = result.get("displayName", "")
            self.reply_to_address = result.get("replyToAddress", "")
            self.signature = result.get("signature", "")
            self.treat_as_alias = result.get("treatAsAlias", True)
            self.smtp_msa = result.get("smtpMsa")
            self.verification_status = result.get("verificationStatus")
            self.is_primary = result.get("isPrimary", False)
            self.is_default = result.get("isDefault", False)

            return self

        except Exception as e:
            raise Exception(
                f"Failed to update send-as alias '{self.send_as_email}': {e}"
            )

    def patch(self, **kwargs):
        """
        Update specific properties of the send-as alias (partial update).

        Performs a partial update (PATCH) of the alias, only modifying the fields
        provided as keyword arguments. Other fields remain unchanged.

        Args:
            **kwargs: Keyword arguments for fields to update:
                - display_name (str): Display name
                - reply_to_address (str): Reply-to email
                - signature (str): HTML signature
                - treat_as_alias (bool): Treat as alias flag
                - smtp_msa (dict): SMTP configuration

        Returns:
            SendAsAlias: Self for method chaining

        Raises:
            Exception: If manager reference is missing, send_as_email is not set,
                or API call fails
        """
        if not self._manager:
            raise Exception(
                "Cannot patch alias: No manager reference. "
                "Alias must have a manager to support API operations."
            )

        if not self.send_as_email:
            raise Exception("Cannot patch alias: send_as_email is required.")

        try:
            # Build request body with only provided fields
            body = {}

            if "display_name" in kwargs:
                body["displayName"] = kwargs["display_name"]
                self.display_name = kwargs["display_name"]

            if "reply_to_address" in kwargs:
                body["replyToAddress"] = kwargs["reply_to_address"]
                self.reply_to_address = kwargs["reply_to_address"]

            if "signature" in kwargs:
                body["signature"] = kwargs["signature"]
                self.signature = kwargs["signature"]

            if "treat_as_alias" in kwargs:
                body["treatAsAlias"] = kwargs["treat_as_alias"]
                self.treat_as_alias = kwargs["treat_as_alias"]

            if "smtp_msa" in kwargs:
                body["smtpMsa"] = kwargs["smtp_msa"]
                self.smtp_msa = kwargs["smtp_msa"]

            if not body:
                raise ValueError("No fields provided to update")

            # Patch the send-as alias
            result = (
                self._manager.service.users()
                .settings()
                .sendAs()
                .patch(userId="me", sendAsEmail=self.send_as_email, body=body)
                .execute()
            )

            # Update all properties from response
            self.display_name = result.get("displayName", "")
            self.reply_to_address = result.get("replyToAddress", "")
            self.signature = result.get("signature", "")
            self.treat_as_alias = result.get("treatAsAlias", True)
            self.smtp_msa = result.get("smtpMsa")
            self.verification_status = result.get("verificationStatus")
            self.is_primary = result.get("isPrimary", False)
            self.is_default = result.get("isDefault", False)

            return self

        except Exception as e:
            raise Exception(
                f"Failed to patch send-as alias '{self.send_as_email}': {e}"
            )

    def delete(self):
        """
        Delete the send-as alias from Gmail.

        Permanently removes the send-as alias. The primary send-as address (usually
        the main account email) cannot be deleted.

        Raises:
            Exception: If manager reference is missing, send_as_email is not set,
                attempting to delete primary address, or API call fails

        Warning:
            The primary send-as address cannot be deleted. Only additional aliases
            can be removed.
        """
        if not self._manager:
            raise Exception(
                "Cannot delete alias: No manager reference. "
                "Alias must have a manager to support API operations."
            )

        if not self.send_as_email:
            raise Exception("Cannot delete alias: send_as_email is required.")

        if self.is_primary:
            raise Exception(
                f"Cannot delete primary send-as address '{self.send_as_email}'. "
                "Only additional aliases can be deleted."
            )

        try:
            # Delete the send-as alias
            self._manager.service.users().settings().sendAs().delete(
                userId="me", sendAsEmail=self.send_as_email
            ).execute()

        except Exception as e:
            raise Exception(
                f"Failed to delete send-as alias '{self.send_as_email}': {e}"
            )

    def verify(self):
        """
        Send verification email for the send-as alias.

        Triggers Gmail to send a verification email to the send-as address.
        The recipient must click the verification link to complete the process.
        Can be called on already-verified aliases to resend verification email.

        Returns:
            SendAsAlias: Self for method chaining

        Raises:
            Exception: If manager reference is missing, send_as_email is not set,
                or API call fails

        Note:
            - Verification is not needed for the primary address
            - Can be called on already-verified aliases to resend verification
            - The verification link expires after a certain period
        """
        if not self._manager:
            raise Exception(
                "Cannot verify alias: No manager reference. "
                "Alias must have a manager to support API operations."
            )

        if not self.send_as_email:
            raise Exception("Cannot verify alias: send_as_email is required.")

        # Allow resending verification even if already verified
        if self.is_verified:
            print(
                f"Note: Alias '{self.send_as_email}' is already verified. "
                "Resending verification email anyway."
            )

        try:
            # Send verification email
            self._manager.service.users().settings().sendAs().verify(
                userId="me", sendAsEmail=self.send_as_email
            ).execute()

            return self

        except Exception as e:
            raise Exception(
                f"Failed to verify send-as alias '{self.send_as_email}': {e}"
            )

    def to_dict(self) -> dict:
        """
        Convert SendAsAlias to dictionary representation.

        Returns:
            dict: Dictionary containing all alias properties
        """
        return {
            "sendAsEmail": self.send_as_email,
            "displayName": self.display_name,
            "replyToAddress": self.reply_to_address,
            "signature": self.signature,
            "isPrimary": self.is_primary,
            "isDefault": self.is_default,
            "treatAsAlias": self.treat_as_alias,
            "smtpMsa": self.smtp_msa,
            "verificationStatus": self.verification_status,
        }

    def __repr__(self) -> str:
        """String representation of the SendAsAlias."""
        verified = "✓" if self.is_verified else "✗"
        return (
            f"SendAsAlias(sendAsEmail='{self.send_as_email}', "
            f"displayName='{self.display_name}', verified={verified})"
        )

    def __str__(self) -> str:
        """Human-readable string representation of the SendAsAlias."""
        status_parts = []
        if self.is_primary:
            status_parts.append("Primary")
        if self.is_default:
            status_parts.append("Default")
        if self.is_verified:
            status_parts.append("Verified")
        else:
            status_parts.append("Unverified")

        status = ", ".join(status_parts)

        return (
            f"Send-As Alias: {self.display_name} <{self.send_as_email}>\n"
            f"Status: {status}\n"
            f"Reply-To: {self.reply_to_address}\n"
            f"Verification: {self.verification_status}"
        )


class UserAlias:
    """
    Represents a Google Workspace User Alias.

    User aliases are additional email addresses that deliver to the same mailbox as
    the primary email address. Unlike send-as aliases, these are actual email addresses
    configured at the Google Workspace user account level and can receive email.

    User aliases are managed through the Google Admin SDK Directory API, not the Gmail API.
    They allow a user to have multiple email addresses (e.g., john.doe@company.com and
    jdoe@company.com) that all deliver to the same mailbox.

    Key Differences from SendAsAlias:
        - UserAlias: Actual email addresses that can RECEIVE mail (Directory API)
        - SendAsAlias: Custom "From" addresses for SENDING mail (Gmail API)

    Attributes:
        alias (str): The alias email address (e.g., 'support@company.com')
        primary_email (str): The primary email address this alias belongs to
        _manager (ServiceAccountEmailManager or None): Reference to email manager for API operations

    Methods:
        create: Add a new alias to a user account
        get: Check if an alias exists for a user
        list: List all aliases for a user (static method)
        delete: Remove an alias from a user account
        to_dict: Convert alias to dictionary representation

    Requirements:
        - Service account with domain-wide delegation
        - Admin SDK API enabled in Google Cloud Project
        - Required OAuth scope: https://www.googleapis.com/auth/admin.directory.user.alias
        - Service account must have User Management admin privileges

    Note:
        User aliases must be in a domain owned by your organization. You cannot
        create aliases in external domains.
    """

    def __init__(
        self,
        alias: str = None,
        primary_email: str = None,
        manager=None,
        raw_alias: dict = None,
    ):
        """
        Initialize a UserAlias instance.

        Args:
            alias (str, optional): The alias email address to create/manage
            primary_email (str, optional): The primary user email that owns this alias
            manager (ServiceAccountEmailManager, optional): Email manager for API calls
            raw_alias (dict, optional): Raw alias data from Directory API response
        """
        self._manager = manager

        if raw_alias:
            self.alias = raw_alias.get("alias")
            self.primary_email = raw_alias.get("primaryEmail")
        else:
            self.alias = alias
            self.primary_email = primary_email

    def create(self):
        """
        Create a new alias for a user account.

        Adds this alias email address to the user's account, allowing them to
        receive email at the alias address.

        Returns:
            UserAlias: Self, with updated data from API response

        Raises:
            ValueError: If manager, alias, or primary_email is not set
            Exception: If the API call fails

        Note:
            The alias domain must be a verified domain in your Google Workspace.
        """
        if not self._manager:
            raise ValueError("Manager is required to create a user alias")

        if not self.alias:
            raise ValueError("Alias email address is required")

        if not self.primary_email:
            raise ValueError("Primary email is required")

        try:
            # Build Admin SDK Directory service
            admin_service = build(
                "admin",
                "directory_v1",
                credentials=self._manager.credentials,
            )

            # Create alias body
            alias_body = {"alias": self.alias}

            # Insert alias
            result = (
                admin_service.users()
                .aliases()
                .insert(userKey=self.primary_email, body=alias_body)
                .execute()
            )

            # Update from response
            self.alias = result.get("alias")
            self.primary_email = result.get("primaryEmail")

            return self

        except Exception as e:
            raise Exception(f"Failed to create user alias: {e}")

    def get(self) -> bool:
        """
        Check if this alias exists for the user.

        Returns:
            bool: True if the alias exists, False otherwise

        Raises:
            ValueError: If manager, alias, or primary_email is not set
            Exception: If the API call fails (other than 404 not found)

        """
        if not self._manager:
            raise ValueError("Manager is required to get user alias")

        if not self.alias:
            raise ValueError("Alias email address is required")

        if not self.primary_email:
            raise ValueError("Primary email is required")

        try:
            # Build Admin SDK Directory service
            admin_service = build(
                "admin",
                "directory_v1",
                credentials=self._manager.credentials,
            )

            # Get all aliases for user
            result = (
                admin_service.users()
                .aliases()
                .list(userKey=self.primary_email)
                .execute()
            )

            aliases = result.get("aliases", [])

            # Check if our alias exists
            for alias_data in aliases:
                if alias_data.get("alias", "").lower() == self.alias.lower():
                    return True

            return False

        except Exception as e:
            # If user has no aliases, API returns 404
            if "404" in str(e):
                return False
            raise Exception(f"Failed to get user alias: {e}")

    @staticmethod
    def list(manager, primary_email: str) -> list:
        """
        List all aliases for a user.

        Args:
            manager (ServiceAccountEmailManager): Email manager for API calls
            primary_email (str): The primary email of the user

        Returns:
            list[UserAlias]: List of UserAlias objects for the user

        Raises:
            ValueError: If manager or primary_email is not provided
            Exception: If the API call fails
        """
        if not manager:
            raise ValueError("Manager is required to list user aliases")

        if not primary_email:
            raise ValueError("Primary email is required")

        try:
            # Build Admin SDK Directory service
            admin_service = build(
                "admin",
                "directory_v1",
                credentials=manager.credentials,
            )

            # List aliases
            result = (
                admin_service.users().aliases().list(userKey=primary_email).execute()
            )

            aliases_data = result.get("aliases", [])

            # Convert to UserAlias objects
            aliases = []
            for alias_data in aliases_data:
                alias = UserAlias(
                    raw_alias=alias_data,
                    manager=manager,
                )
                aliases.append(alias)

            return aliases

        except Exception as e:
            # If user has no aliases, API returns 404
            if "404" in str(e):
                return []
            raise Exception(f"Failed to list user aliases: {e}")

    def delete(self):
        """
        Delete this alias from the user account.

        Removes the alias email address from the user's account. Email sent to
        this address will no longer be delivered.

        Raises:
            ValueError: If manager, alias, or primary_email is not set
            Exception: If the API call fails

        Warning:
            This operation cannot be undone. The alias will be immediately removed
            and email sent to it will bounce.
        """
        if not self._manager:
            raise ValueError("Manager is required to delete user alias")

        if not self.alias:
            raise ValueError("Alias email address is required")

        if not self.primary_email:
            raise ValueError("Primary email is required")

        try:
            # Build Admin SDK Directory service
            admin_service = build(
                "admin",
                "directory_v1",
                credentials=self._manager.credentials,
            )

            # Delete alias
            admin_service.users().aliases().delete(
                userKey=self.primary_email,
                alias=self.alias,
            ).execute()

        except Exception as e:
            raise Exception(f"Failed to delete user alias: {e}")

    def to_dict(self) -> dict:
        """
        Convert UserAlias to dictionary representation.

        Returns:
            dict: Dictionary containing alias data
        """
        return {
            "alias": self.alias,
            "primary_email": self.primary_email,
        }

    def __repr__(self) -> str:
        """
        Technical string representation.

        Returns:
            str: String in format "UserAlias(alias='...', primary_email='...')"
        """
        return f"UserAlias(alias='{self.alias}', primary_email='{self.primary_email}')"

    def __str__(self) -> str:
        """
        Human-readable string representation.

        Returns:
            str: Formatted string with alias details
        """
        return f"{self.alias} -> {self.primary_email}"


class ServiceAccountEmailManager:
    """
    Email manager using Google service account authentication with Gmail API.

    This class provides comprehensive email functionality using service account credentials
    with optional user impersonation for domain-wide delegation. It allows sending emails,
    reading messages, and processing Gmail Pub/Sub notifications.

    The service account approach is preferred over OAuth2 user credentials for:
    - Automated systems that don't require user interaction
    - Sending emails from shared accounts (e.g., user@example.com)
    - Production environments where token refresh might fail
    - Accessing multiple users' mailboxes in a workspace

    Attributes:
        root_path (Path): Root directory of the project
        impersonated_user (str or None): Email address of the user being impersonated
        credentials (service_account.Credentials): Google service account credentials
        service (Resource): Gmail API service instance

    Methods:
        send_email: Send emails with attachments and HTML/plain text support
        get_message_by_message_id: Retrieve a specific email by Gmail message ID
        get_message_by_message_id_for_user: Retrieve email from any workspace user's mailbox
        get_message_from_pubsub: Process Gmail Pub/Sub notifications and fetch new messages
        get_thread_by_id: Retrieve email thread by thread ID (supports any user via user_email parameter)
        list_threads: List email threads with filtering and pagination
        batch_delete: Efficiently delete multiple messages in a single API call
        list_aliases: List all send-as aliases for the authenticated user
        watch: Set up Gmail push notifications via Cloud Pub/Sub
        get_account_info: Get information about the authenticated account

    Requirements:
        - Service account with domain-wide delegation enabled
        - Gmail API scopes authorized in Google Workspace Admin Console
        - Service account JSON key file
        - For impersonation: Domain-wide delegation configured with appropriate scopes

    Gmail API Scopes Required:
        - https://www.googleapis.com/auth/gmail.send - For sending emails
        - https://www.googleapis.com/auth/gmail.readonly - For reading emails

    See Also:
        - Thread: Email conversation thread class
        - Message: Email message representation class
        - service_account_helper.py: Generic service account authentication helper
        - Documentation: docs_unlisted/service-account-*.md files
    """

    def __init__(
        self,
        service_account_file: str = str(DEFAULT_SA),
        impersonate_user: str = None,
        scopes: list = None,
        log: Optional[Logger] = None,
    ):
        """
        Initialize the ServiceAccountEmailManager.

        Sets up authentication with Google service account credentials and optionally
        impersonates a user for domain-wide delegation. Creates a Gmail API service
        instance for making API calls.

        Args:
            service_account_file (str, optional): Path to the service account JSON key file.
                Can be absolute or relative to the project root. If relative, it will be
                resolved from the project root directory.
                Defaults to 'cred/service_account.json'.

            impersonate_user (str, optional): Email address of the user to impersonate.
                Requires domain-wide delegation to be configured in Google Workspace Admin
                Console. If None, uses service account directly (limited functionality).
                Defaults to None.

            scopes (list, optional): List of Gmail API scopes to request. If not provided,
                defaults to all Gmail scopes:
                - 'https://mail.google.com/' (full Gmail access)
                - 'https://www.googleapis.com/auth/gmail.modify' (modify emails)
                - 'https://www.googleapis.com/auth/gmail.compose' (compose/send)
                - 'https://www.googleapis.com/auth/gmail.send' (send emails)
                - 'https://www.googleapis.com/auth/gmail.readonly' (read emails)
                - 'https://www.googleapis.com/auth/gmail.metadata' (metadata access)
                - 'https://www.googleapis.com/auth/gmail.settings.basic' (basic settings)
                - 'https://www.googleapis.com/auth/gmail.settings.sharing' (sharing settings)
                - 'https://www.googleapis.com/auth/admin.directory.user' (user alias management)
                - 'https://www.googleapis.com/auth/admin.directory.user.alias' (user alias management)
                - 'https://www.googleapis.com/auth/admin.directory.group' (group management)
                - 'https://www.googleapis.com/auth/admin.directory.domain' (domain management)
                Defaults to None.

            log (Logger, optional): Logger instance for logging. If None, logging
                will be done via print statements. Defaults to None.

        Raises:
            FileNotFoundError: If the service account file doesn't exist at the specified path
            google.auth.exceptions.DefaultCredentialsError: If credentials are invalid
            Exception: If authentication or service building fails

        Note:
            For user impersonation to work, you must:
            1. Enable domain-wide delegation for the service account
            2. Authorize the OAuth scopes in Google Workspace Admin Console
            3. Ensure the service account has the Client ID registered
        """
        # Initialize logger
        self.log = log

        # Set default scopes if not provided
        if scopes is None:
            scopes = [
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
            ]

        # Determine root path
        self.root_path = ROOT_PATH

        # Resolve service account file path
        sa_path = Path(service_account_file)
        if not sa_path.is_absolute():
            sa_path = self.root_path / service_account_file

        # Check if file exists
        if not sa_path.exists():
            raise FileNotFoundError(f"Service account file not found: {sa_path}")

        # Create credentials from service account
        try:
            self.credentials = service_account.Credentials.from_service_account_file(
                filename=str(sa_path), scopes=scopes
            )
        except Exception as e:
            self._log(f"Error loading service account credentials: {e}", level="error")
            raise Exception(f"Failed to load service account credentials: {e}")

        # Apply user impersonation if specified
        if impersonate_user:
            try:
                self.credentials = self.credentials.with_subject(impersonate_user)
                self.impersonated_user = impersonate_user
            except Exception as e:
                self._log(
                    f"Error impersonating user '{impersonate_user}': {e}", level="error"
                )
                raise Exception(
                    f"Failed to impersonate user '{impersonate_user}'. "
                    f"Ensure domain-wide delegation is enabled. Error: {e}"
                )
        else:
            self.impersonated_user = None

        # Build Gmail API service
        try:
            self.service = build("gmail", "v1", credentials=self.credentials)
        except Exception as e:
            raise Exception(f"Failed to build Gmail API service: {e}")

    def _log(self, message: str, level: str = "info", exc_info: bool = False):
        """
        Internal logging method that uses logger if available, otherwise prints.

        Args:
            message (str): Message to log
            level (str): Log level ('info', 'error', 'warning', 'debug')
        """
        if self.log:
            log_func = getattr(self.log, level, self.log.info)
            log_func(message, exc_info=exc_info)
        else:
            print(message)

    def send_email(
        self,
        email_config_path: str = None,
        subject: str = "",
        body: str = "",
        file_attachment_paths: list = None,
        from_name: str = None,
        from_email: str = None,
        to_email: list = None,
        cc_email: list = None,
        bcc_email: list = None,
    ):
        """
        Send an email using the Gmail API.

        Args:
            email_config_path (str, optional): Path to JSON config file with email settings.
                If provided, settings from config file are used unless overridden by parameters.
            subject (str, optional): Email subject. Defaults to "".
            body (str, optional): Email body (plain text or HTML). Defaults to "".
            file_attachment_paths (list, optional): List of file paths to attach. Defaults to None.
            from_name (str, optional): Sender's display name. Defaults to None.
            from_email (str, optional): Sender's email address. Defaults to impersonated user.
            to_email (list, optional): List of recipient email addresses. Defaults to None.
            cc_email (list, optional): List of CC email addresses. Defaults to None.
            bcc_email (list, optional): List of BCC email addresses. Defaults to None.

        Returns:
            dict: Gmail API response containing the sent message details.

        Raises:
            ValueError: If required fields are missing.
            Exception: If email sending fails.

        Example:
            # Using config file
            sender.send_email(
                email_config_path='conf/email_config.json',
                subject='Test Email',
                body='Hello World'
            )

            # Using parameters directly
            sender.send_email(
                from_name='Dock Johnson',
                from_email='user@example.com',
                to_email=['recipient@example.com'],
                subject='Test Email',
                body='Hello World',
                file_attachment_paths=['report.pdf']
            )
        """
        # Load config file if provided
        config = {}
        if email_config_path:
            config_path = Path(email_config_path)
            if not config_path.is_absolute():
                config_path = self.root_path / email_config_path

            if config_path.exists():
                with open(config_path, "r") as f:
                    config = json.load(f)

        # Merge config with parameters (parameters take precedence)
        from_name = from_name or config.get("from_name", "Dock Johnson")
        from_email = from_email or config.get("from_email") or self.impersonated_user
        to_email = to_email or config.get("to_email", [])
        cc_email = cc_email or config.get("cc_email", [])
        bcc_email = bcc_email or config.get("bcc_email", [])

        # Validate required fields
        if not from_email:
            raise ValueError(
                "from_email is required. Provide it in config, parameter, or via impersonation."
            )

        if not to_email:
            raise ValueError("to_email is required and cannot be empty.")

        # Ensure lists
        if isinstance(to_email, str):
            to_email = [to_email]
        if isinstance(cc_email, str):
            cc_email = [cc_email]
        if isinstance(bcc_email, str):
            bcc_email = [bcc_email]

        # Create message
        message = MIMEMultipart()
        message["From"] = f"{from_name} <{from_email}>" if from_name else from_email
        message["To"] = ", ".join(to_email)
        message["Subject"] = subject

        if cc_email:
            message["Cc"] = ", ".join(cc_email)

        # Attach body
        # Check if body is HTML
        if body.strip().startswith("<") and body.strip().endswith(">"):
            message.attach(MIMEText(body, "html"))
        else:
            message.attach(MIMEText(body, "plain"))

        # Attach files
        if file_attachment_paths:
            for file_path in file_attachment_paths:
                file_path = Path(file_path)
                if not file_path.is_absolute():
                    file_path = self.root_path / file_path

                if not file_path.exists():
                    print(f"Warning: Attachment not found: {file_path}")
                    continue

                try:
                    with open(file_path, "rb") as f:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(f.read())

                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition", f"attachment; filename= {file_path.name}"
                    )
                    message.attach(part)
                except Exception as e:
                    print(f"Warning: Failed to attach file {file_path}: {e}")

        # Encode message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        # Send via Gmail API
        try:
            # Combine all recipients
            all_recipients = to_email + cc_email + bcc_email

            result = (
                self.service.users()
                .messages()
                .send(userId="me", body={"raw": raw_message})
                .execute()
            )

            print(f"✓ Email sent successfully!")
            print(f"  Message ID: {result['id']}")
            print(f"  From: {from_email}")
            print(f"  To: {', '.join(to_email)}")
            if cc_email:
                print(f"  CC: {', '.join(cc_email)}")
            if bcc_email:
                print(f"  BCC: {', '.join(bcc_email)}")

            return result
        except Exception as e:
            raise Exception(f"Failed to send email: {e}")

    def get_message_by_message_id(self, message_id: str, format: str = "full"):
        """
        Get email details by Gmail message ID.

        Args:
            message_id (str): The Gmail message ID.
            format (str, optional): Format of the message response.
                Options: 'minimal', 'full', 'raw', 'metadata'.
                Defaults to 'full'.

                Note: If format='full' is requested but the service account only has
                gmail.metadata scope authorization, this method will automatically
                fallback to format='metadata'. The metadata format includes headers
                (From, To, Subject, Date, etc.) but not the full message body content.

        Returns:
            Message: Message object with parsed email data.

        Raises:
            Exception: If fetching the email fails.

        Scope Requirements:
            - format='metadata': Requires 'https://www.googleapis.com/auth/gmail.metadata'
            - format='full': Requires 'https://www.googleapis.com/auth/gmail.readonly' or
              'https://mail.google.com/'
        """
        try:
            # Get the message from Gmail API
            raw_message = (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id, format=format)
                .execute()
            )

            # Create and return Message object with manager reference for thread support
            return Message(raw_message, manager=self)

        except Exception as e:
            # If format=full fails due to metadata scope limitation, try with format=metadata
            if format == "full" and "Metadata scope doesn't allow format FULL" in str(
                e
            ):
                self._log(
                    f"Format 'full' not allowed with current scopes, falling back to 'metadata' for message {message_id}",
                    level="warning",
                )
                try:
                    raw_message = (
                        self.service.users()
                        .messages()
                        .get(userId="me", id=message_id, format="metadata")
                        .execute()
                    )
                    return Message(raw_message, manager=self)
                except Exception as metadata_error:
                    raise Exception(
                        f"Failed to get email by message ID '{message_id}' even with metadata format: {metadata_error}"
                    )

            raise Exception(f"Failed to get email by message ID '{message_id}': {e}")

    def get_message_by_message_id_for_user(
        self, user_email: str, message_id: str, format: str = "full"
    ):
        """
        Get email details by Gmail message ID for ANY user in the workspace.

        This function allows you to retrieve emails from any user's mailbox by
        dynamically impersonating that user. Requires domain-wide delegation.

        Args:
            user_email (str): Email address of the user whose email to retrieve.
            message_id (str): The Gmail message ID.
            format (str, optional): Format of the message response.
                Options: 'minimal', 'full', 'raw', 'metadata'.
                Defaults to 'full'.

                Note: If format='full' is requested but the service account only has
                gmail.metadata scope authorization, this method will automatically
                fallback to format='metadata'. The metadata format includes headers
                (From, To, Subject, Date, etc.) but not the full message body content.

        Returns:
            Message: Message object with parsed email data, includes accessed_as_user property.

        Raises:
            Exception: If fetching the email fails or impersonation is not allowed.

        Scope Requirements:
            - format='metadata': Requires 'https://www.googleapis.com/auth/gmail.metadata'
            - format='full': Requires 'https://www.googleapis.com/auth/gmail.readonly' or
              'https://mail.google.com/'
        
        Note:
            This creates a new API service with different impersonation for each call.
            For better performance when accessing many emails from the same user,
            create a dedicated ServiceAccountEmailManager instance for that user.
        """
        try:
            # Create credentials with user impersonation
            temp_credentials = self.credentials.with_subject(user_email)

            # Build temporary Gmail API service for this user
            temp_service = build("gmail", "v1", credentials=temp_credentials)

            # Get the message
            raw_message = (
                temp_service.users()
                .messages()
                .get(userId="me", id=message_id, format=format)
                .execute()
            )

            # Track which user was impersonated
            raw_message["accessed_as_user"] = user_email

            # Create and return Message object with manager reference
            return Message(raw_message, manager=self)

        except Exception as e:
            # If format=full fails due to metadata scope limitation, try with format=metadata
            if format == "full" and "Metadata scope doesn't allow format FULL" in str(
                e
            ):
                self._log(
                    f"Format 'full' not allowed with current scopes, falling back to 'metadata' for message {message_id} (user: {user_email})",
                    level="warning",
                )
                try:
                    raw_message = (
                        temp_service.users()
                        .messages()
                        .get(userId="me", id=message_id, format="metadata")
                        .execute()
                    )
                    raw_message["accessed_as_user"] = user_email
                    return Message(raw_message, manager=self)
                except Exception as metadata_error:
                    raise Exception(
                        f"Failed to get email '{message_id}' for user '{user_email}' even with metadata format: {metadata_error}"
                    )

            raise Exception(
                f"Failed to get email '{message_id}' for user '{user_email}': {e}"
            )

    def get_messages_from_pubsub(self, pubsub_data):
        """
        Extract and return all new Message objects from a Gmail Pub/Sub notification.

        Gmail Pub/Sub notifications are sent when ANY mailbox change occurs (not per-message).
        A single notification can represent multiple new emails, deletions, or label changes.
        This function decodes the Pub/Sub notification and fetches all new messages that were
        added since the historyId checkpoint.

        Important: One Pub/Sub notification can contain MULTIPLE new messages! Always iterate
        through the returned list to process all messages.

        Args:
            pubsub_data (dict or str): Pub/Sub message data. Can be:
                - dict: Pub/Sub message dictionary
                - str: JSON string of Pub/Sub message

        Returns:
            List[Message]: List of all new Message objects from the notification.
                Empty list if no new messages were found.
                        Each Message object has its thread auto-populated.

        Raises:
            ValueError: If pubsub_data format is invalid.
            Exception: If fetching email details fails.

        Example Pub/Sub Message Format:
            {
                "message": {
                    "data": "<base64-encoded-json>",
                    "messageId": "136969346945",  // Pub/Sub notification ID (NOT Gmail message ID)
                    "publishTime": "2021-02-26T19:13:55.749Z"
                },
                "subscription": "projects/myproject/subscriptions/mysubscription"
            }

        Decoded Data Format (from base64 "data" field):
            {
                "emailAddress": "user@example.com",
                "historyId": "12345"  // Mailbox checkpoint - NOT a message ID
            }

        IMPORTANT: The notification does NOT contain Gmail message IDs! This tripped me up at first!
        You must:
            1. Decode the historyId from the notification
            2. Call history.list(startHistoryId=historyId) to get actual changes
            3. Extract Gmail message IDs from the history response
            4. Fetch full message details using those IDs

        Example Usage:
            >>> # Process all new messages from notification
            >>> messages = manager.get_messages_from_pubsub(pubsub_notification)
            >>> print(f"Received {len(messages)} new message(s)")
            >>>
            >>> for message in messages:
            ...     print(f"From: {message.from_email}")
            ...     print(f"Subject: {message.subject}")
            ...     print(f"Body: {message.body[:100]}")
            ...     print(f"Thread has {message.thread.message_count} messages")
            ...     print("---")
            >>>
            >>> # Process only if messages exist
            >>> if messages:
            ...     first_message = messages[0]
            ...     print(f"First message from: {first_message.from_email}")

        Note:
            - One notification can contain multiple messages (e.g., 5 emails arrived at once)
            - history.list() returns ALL mailbox changes since historyId
            - We filter for only "messageAdded" history types
            - Each Message object includes full email content and thread context
            - Returns empty list (not None) if no messages found

        See Also:
            - get_message_by_message_id(): For fetching a single message by ID
            - history.list() API: https://developers.google.com/gmail/api/reference/rest/v1/users.history/list
        """
        try:
            # Parse JSON string if needed
            if isinstance(pubsub_data, str):
                self.log("Parsing pubsub_data from JSON string", level="debug")
                pubsub_data = json.loads(pubsub_data)

            # Validate Pub/Sub message structure
            if not isinstance(pubsub_data, dict):
                self._log(
                    "Invalid pubsub_data format, expected dict or JSON string",
                    level="error",
                )
                raise ValueError("pubsub_data must be a dictionary or JSON string")

            if "message" not in pubsub_data:
                self._log("pubsub_data missing 'message' key", level="error")
                raise ValueError("pubsub_data missing 'message' key")

            message = pubsub_data["message"]

            if "data" not in message:
                self._log("Pub/Sub message missing 'data' key", level="error")
                raise ValueError("Pub/Sub message missing 'data' key")

            # Decode the base64 data
            data_bytes = base64.urlsafe_b64decode(message["data"])
            data_str = data_bytes.decode("utf-8")
            notification_data = json.loads(data_str)

            self._log(
                f"Decoded Pub/Sub notification data: {json.dumps(notification_data, indent=2)}",
                level="debug",
            )

            # Extract email address and history ID
            email_address = notification_data.get("emailAddress")
            history_id = notification_data.get("historyId")

            messages = []

            # Get all new messages since the history ID
            if history_id:
                try:
                    self._log(
                        f"Fetching messages for {email_address} since historyId {history_id}",
                        level="debug",
                    )
                    # List history to get all mailbox changes since historyId
                    # We filter for only "messageAdded" events
                    history_response = (
                        self.service.users()
                        .history()
                        .list(
                            userId="me",
                            startHistoryId=history_id,
                            historyTypes=[
                                "messageAdded",
                                "messageDeleted",
                                "labelAdded",
                                "labelRemoved",
                            ],
                        )
                        .execute()
                    )
                    self._log(
                        f"Full history response: {json.dumps(history_response, indent=2)}",
                        level="debug",
                    )

                    # Process all history items (could be multiple changes)
                    if "history" in history_response:
                        self._log(
                            f"Processing {len(history_response['history'])} history item(s)",
                            level="debug",
                        )
                        for history_item in history_response["history"]:
                            # if "messagesAdded" in history_item:
                            #    self._log(
                            #        f"Found {len(history_item['messagesAdded'])} new message(s) in history",
                            #        level="debug",
                            #    )

                            # Each history item can have multiple messages added
                            for message_added in history_item["messagesAdded"]:
                                msg = message_added["message"]
                                # Get full message details as Message object
                                try:
                                    full_message = self.get_message_by_message_id(
                                        msg["id"]
                                    )
                                    messages.append(full_message)
                                except Exception as e:
                                    self._log(
                                        f"Error fetching full message for ID {msg['id']}: {e}",
                                        level="error",
                                        exc_info=True,
                                    )
                            # else:
                            #    self._log(
                            #        "No 'messagesAdded' in this history item, skipping",
                            #        level="debug",
                            #    )
                    else:
                        self._log(
                            "No 'history' items found in history response",
                            level="warning",
                        )
                        self._log(
                            f"History response: {history_response}", level="debug"
                        )

                except Exception as e:
                    self._log(
                        f"Error fetching messages from history: {e}", level="error"
                    )
                    raise Exception(f"Failed to fetch messages from history: {e}")

            self._log(f"Total new messages fetched: {len(messages)}", level="info")
            return messages

        except json.JSONDecodeError as e:
            self._log(
                "Invalid pubsub_data format, expected dict or JSON string",
                level="error",
            )
            raise ValueError(f"Invalid JSON in pubsub_data: {e}")
        except Exception as e:
            self._log(f"Failed to process Pub/Sub notification: {e}", level="error")
            raise Exception(f"Failed to process Pub/Sub notification: {e}")

    def get_account_info(self):
        """
        Get information about the authenticated Gmail account.

        Retrieves profile information for the currently authenticated user (either the
        service account itself or the impersonated user). Useful for verifying
        authentication and getting mailbox statistics.

        Returns:
            dict: Account information dictionary with the following keys:
                - email (str): The email address of the account
                - messages_total (int): Total number of messages in the mailbox
                - threads_total (int): Total number of email threads
                - history_id (str): Current history ID for the mailbox
                - error (str): Error message if the request failed (only present on error)
        
        Note:
            If an error occurs, the returned dictionary will contain an 'error' key
            instead of the account information keys.
        """
        try:
            profile = self.service.users().getProfile(userId="me").execute()
            return {
                "email": profile.get("emailAddress"),
                "messages_total": profile.get("messagesTotal"),
                "threads_total": profile.get("threadsTotal"),
                "history_id": profile.get("historyId"),
            }
        except Exception as e:
            return {"error": str(e)}

    def get_thread_by_id(
        self, thread_id: str, user_email: str = "me", format: str = "full"
    ):
        """
        Get a complete email thread by Gmail thread ID.

        Retrieves all messages in a thread and returns a Thread object with
        all messages properly linked. Can optionally retrieve threads from
        any user's mailbox via impersonation.

        Args:
            thread_id (str): The Gmail thread ID.
            user_email (str, optional): Email address of the user whose thread to retrieve.
                Use 'me' for the currently impersonated user, or specify any user email
                for domain-wide delegation. Defaults to 'me'.
            format (str, optional): Format of the message responses.
                Options: 'minimal', 'full', 'raw', 'metadata'.
                Defaults to 'full'.

        Returns:
            Thread: Thread object containing all messages in the conversation.
                When user_email is specified (not 'me'), each message includes
                accessed_as_user attribute.

        Raises:
            Exception: If fetching the thread fails or impersonation is not allowed.

        Example:
            >>> # Get thread from current user
            >>> thread = manager.get_thread_by_id('thread_abc123')
            >>> print(f"Thread: {thread.subject}")
            >>> print(f"Messages: {thread.message_count}")
            >>>
            >>> # Get thread from specific user
            >>> thread = manager.get_thread_by_id(
            ...     'thread_xyz789',
            ...     user_email='support@example.com'
            ... )
            >>> print(f"Thread for {thread.messages[0].accessed_as_user}")

        Note:
            This method fetches the complete thread with all messages.
            For large threads, this may take some time. When using user_email
            other than 'me', a temporary API service is created with different
            impersonation for each call.
        """
        try:
            # Use current service if user_email is 'me'
            if user_email == "me":
                # Get the thread from Gmail API
                raw_thread = (
                    self.service.users()
                    .threads()
                    .get(userId="me", id=thread_id, format=format)
                    .execute()
                )
            else:
                # Create credentials with user impersonation
                temp_credentials = self.credentials.with_subject(user_email)

                # Build temporary Gmail API service for this user
                temp_service = build("gmail", "v1", credentials=temp_credentials)

                # Get the thread
                raw_thread = (
                    temp_service.users()
                    .threads()
                    .get(userId="me", id=thread_id, format=format)
                    .execute()
                )

                # Mark each message with accessed_as_user
                if "messages" in raw_thread:
                    for msg in raw_thread["messages"]:
                        msg["accessed_as_user"] = user_email

            # Create Thread object with manager reference
            thread = Thread(raw_thread=raw_thread, manager=self)

            return thread

        except Exception as e:
            if user_email == "me":
                raise Exception(f"Failed to get thread by ID '{thread_id}': {e}")
            else:
                raise Exception(
                    f"Failed to get thread '{thread_id}' for user '{user_email}': {e}"
                )

    def list_threads(
        self,
        max_results: int = 10,
        query: str = None,
        label_ids: list = None,
        page_token: str = None,
        include_spam_trash: bool = False,
    ) -> dict:
        """
        List email threads in the mailbox.

        Args:
            max_results (int, optional): Maximum number of threads to return.
                Defaults to 10.
            query (str, optional): Gmail search query (same as search box).
                Example: 'from:example@gmail.com is:unread'
            label_ids (list, optional): Filter by label IDs (e.g., ['INBOX', 'UNREAD']).
            page_token (str, optional): Token for pagination (from previous response).
            include_spam_trash (bool, optional): Whether to include Spam and Trash folders.
                Defaults to False.
        Returns:
            dict: Contains:
                - threads (list[Thread]): List of Thread objects
                - next_page_token (str or None): Token for next page
                - result_size_estimate (int): Estimated total results

        Raises:
            Exception: If listing threads fails.

        Example:
            >>> # List unread threads
            >>> result = manager.list_threads(
            ...     max_results=20,
            ...     label_ids=['INBOX', 'UNREAD']
            ... )
            >>> for thread in result['threads']:
            ...     print(f"{thread.subject} - {thread.message_count} messages")
            >>>
            >>> # Search threads
            >>> result = manager.list_threads(
            ...     query='from:important@example.com',
            ...     max_results=50
            ... )
        """
        try:
            # Build request parameters
            params = {"userId": "me", "maxResults": max_results}

            if query:
                params["q"] = query
            if label_ids:
                params["labelIds"] = label_ids
            if page_token:
                params["pageToken"] = page_token
            if include_spam_trash:
                params["includeSpamTrash"] = include_spam_trash

            # List threads
            response = self.service.users().threads().list(**params).execute()

            threads = []
            if "threads" in response:
                for thread_data in response["threads"]:
                    # Create Thread with lazy loading (only has ID initially)
                    thread = Thread(thread_id=thread_data["id"], manager=self)
                    # Store snippet if available
                    if "snippet" in thread_data:
                        thread.snippet = thread_data["snippet"]
                    if "historyId" in thread_data:
                        thread.history_id = thread_data["historyId"]

                    threads.append(thread)

            return {
                "threads": threads,
                "next_page_token": response.get("nextPageToken"),
                "result_size_estimate": response.get("resultSizeEstimate", 0),
            }

        except Exception as e:
            raise Exception(f"Failed to list threads: {e}")

    def search_messages_by_subject(
        self,
        subject: str,
        exact_match: bool = False,
        max_results: int = 10,
        label_ids: list = None,
        include_spam_trash: bool = False,
    ) -> list:
        """
        Search for messages by subject line.

        This method searches the authenticated user's mailbox for messages matching
        a specific subject. It uses Gmail's search query syntax to find messages.

        Args:
            subject (str): The subject text to search for. Required.
            exact_match (bool, optional): If True, searches for exact subject match.
                If False (default), searches for messages containing the subject text.
            max_results (int, optional): Maximum number of messages to return.
                Default is 10. Gmail may return fewer results.
            label_ids (list, optional): Only return messages with these label IDs.
                Example: ['INBOX', 'UNREAD']
            include_spam_trash (bool, optional): Include messages from SPAM and TRASH.
                Default is False.

        Returns:
            list[Message]: List of Message objects matching the subject search.
                Returns empty list if no matches found.

        Raises:
            ValueError: If subject is empty or None
            Exception: If the search fails (API error, permission denied, etc.)

        Example:
            >>> # Find all messages with "Invoice" in subject
            >>> messages = manager.search_messages_by_subject("Invoice")
            >>> for msg in messages:
            ...     print(f"{msg.date}: {msg.subject}")
            >>>
            >>> # Find exact subject match
            >>> messages = manager.search_messages_by_subject(
            ...     "Monthly Report - January 2024",
            ...     exact_match=True
            ... )
            >>>
            >>> # Search only in inbox
            >>> messages = manager.search_messages_by_subject(
            ...     "Password Reset",
            ...     label_ids=['INBOX'],
            ...     max_results=5
            ... )
            >>>
            >>> # Search including spam/trash
            >>> all_messages = manager.search_messages_by_subject(
            ...     "Old Newsletter",
            ...     include_spam_trash=True,
            ...     max_results=50
            ... )

        Notes:
            - Search is case-insensitive
            - Partial matches are returned by default unless exact_match=True
            - Results are ordered by most recent first (Gmail default)
            - Each message is fully loaded with headers and body
            - For large result sets, consider using pagination

        See Also:
            - search_threads_by_subject(): Search for threads instead of individual messages
            - list_threads(): List threads with custom query
            - Message: Individual message class with full email data
        """
        # Validate input
        if not subject or not subject.strip():
            raise ValueError("subject cannot be empty")

        # Build search query
        if exact_match:
            query = f'subject:"{subject}"'
        else:
            query = f"subject:{subject}"

        # Add label filter if provided
        if label_ids:
            for label_id in label_ids:
                query += f" label:{label_id}"

        try:
            # Search for messages
            response = (
                self.service.users()
                .messages()
                .list(
                    userId="me",
                    q=query,
                    maxResults=max_results,
                    includeSpamTrash=include_spam_trash,
                )
                .execute()
            )

            messages = []
            if "messages" in response:
                # Get full message data for each result
                for msg_data in response["messages"]:
                    message = self.get_message_by_message_id(msg_data["id"])
                    messages.append(message)

            self._log(
                f"Found {len(messages)} messages matching subject '{subject}'",
                level="info",
            )
            return messages

        except Exception as e:
            raise Exception(f"Failed to search messages by subject: {e}")

    def search_threads_by_subject(
        self,
        subject: str,
        exact_match: bool = False,
        max_results: int = 10,
        label_ids: list = None,
        include_spam_trash: bool = False,
    ) -> list:
        """
        Search for threads (conversations) by subject line.

        This method searches the authenticated user's mailbox for threads containing
        messages that match a specific subject. It uses Gmail's search query syntax
        to find threads. Each thread may contain multiple messages.

        Args:
            subject (str): The subject text to search for. Required.
            exact_match (bool, optional): If True, searches for exact subject match.
                If False (default), searches for threads containing the subject text.
            max_results (int, optional): Maximum number of threads to return.
                Default is 10. Gmail may return fewer results.
            label_ids (list, optional): Only return threads with these label IDs.
                Example: ['INBOX', 'UNREAD']
            include_spam_trash (bool, optional): Include threads from SPAM and TRASH.
                Default is False.

        Returns:
            list[Thread]: List of Thread objects matching the subject search.
                Returns empty list if no matches found. Each Thread contains all
                messages in the conversation.

        Raises:
            ValueError: If subject is empty or None
            Exception: If the search fails (API error, permission denied, etc.)

        Example:
            >>> # Find all threads about "Project Alpha"
            >>> threads = manager.search_threads_by_subject("Project Alpha")
            >>> for thread in threads:
            ...     print(f"Thread: {thread.subject}")
            ...     print(f"  Messages: {thread.message_count}")
            ...     print(f"  Participants: {', '.join(thread.participants)}")
            >>>
            >>> # Find exact subject match
            >>> threads = manager.search_threads_by_subject(
            ...     "Re: Meeting Notes - Q1 Review",
            ...     exact_match=True
            ... )
            >>>
            >>> # Search only unread threads in inbox
            >>> threads = manager.search_threads_by_subject(
            ...     "Weekly Update",
            ...     label_ids=['INBOX', 'UNREAD'],
            ...     max_results=20
            ... )
            >>>
            >>> # Process all messages in matching threads
            >>> threads = manager.search_threads_by_subject("Customer Feedback")
            >>> for thread in threads:
            ...     for message in thread.messages:
            ...         print(f"  {message.from_email}: {message.snippet}")

        Notes:
            - Search is case-insensitive
            - Partial matches are returned by default unless exact_match=True
            - Results are ordered by most recent activity first (Gmail default)
            - Each thread is fully loaded with all messages, headers, and bodies
            - A thread may have multiple messages with different subjects (replies)
            - The search matches any message in the thread, not just the first one

        See Also:
            - search_messages_by_subject(): Search for individual messages instead of threads
            - list_threads(): List threads with custom query
            - Thread: Thread class with full conversation data
            - Message: Individual message class
        """
        # Validate input
        if not subject or not subject.strip():
            raise ValueError("subject cannot be empty")

        # Build search query
        if exact_match:
            query = f'subject:"{subject}"'
        else:
            query = f"subject:{subject}"

        # Add label filter if provided
        if label_ids:
            for label_id in label_ids:
                query += f" label:{label_id}"

        try:
            # Use list_threads method with custom query
            result = self.list_threads(
                max_results=max_results,
                query=query,
                label_ids=None,  # Already included in query
                include_spam_trash=include_spam_trash,
            )

            threads = result.get("threads", [])
            self._log(
                f"Found {len(threads)} threads matching subject '{subject}'",
                level="info",
            )
            return threads

        except Exception as e:
            raise Exception(f"Failed to search threads by subject: {e}")

    def batch_delete(self, message_ids: list) -> dict:
        """
        Permanently delete multiple messages from Gmail using batch deletion.

        This method uses Gmail's batchDelete API to efficiently delete multiple
        messages in a single API call. It's much more efficient than calling
        delete() on individual messages when you need to delete many messages.

        Args:
            message_ids (list): List of Gmail message ID strings to delete.
                Maximum of 1000 message IDs per call (Gmail API limit).

        Returns:
            dict: Result dictionary with keys:
                - success (bool): True if batch deletion succeeded
                - message_count (int): Number of messages deleted
                - error (str, optional): Error message if deletion failed

        Raises:
            ValueError: If message_ids is empty or contains more than 1000 IDs
            Exception: If the batch deletion fails (API error, permission denied, etc.)

        Example:
            >>> # Delete multiple spam messages
            >>> spam_messages = manager.list_messages(label_ids=['SPAM'])
            >>> message_ids = [msg.id for msg in spam_messages]
            >>>
            >>> result = manager.batch_delete(message_ids)
            >>> if result['success']:
            ...     print(f"Deleted {result['message_count']} messages")
            >>> else:
            ...     print(f"Error: {result['error']}")
            >>>
            >>> # Delete messages matching a query
            >>> messages = manager.list_messages(query='older_than:90d')
            >>> ids = [msg.id for msg in messages]
            >>> manager.batch_delete(ids)

        Notes:
            - This operation is permanent and cannot be undone
            - Messages are completely deleted, not moved to trash
            - Maximum 1000 message IDs per call (Gmail API limitation)
            - For larger batches, split into multiple calls
            - All messages must belong to the authenticated user
            - Requires 'https://mail.google.com/' scope or similar

        Warning:
            This permanently deletes messages from Gmail. Unlike trash(),
            there is no way to recover these messages. Use with caution.

        See Also:
            - Message.delete(): Delete a single message
            - Message.trash(): Move message to trash (recoverable)
            - Thread.delete(): Delete an entire thread
        """
        # Validate input
        if not message_ids:
            raise ValueError("message_ids cannot be empty")

        if not isinstance(message_ids, list):
            raise ValueError("message_ids must be a list of message ID strings")

        if len(message_ids) > 1000:
            raise ValueError(
                f"Cannot delete more than 1000 messages at once. "
                f"Got {len(message_ids)} message IDs. "
                f"Split into multiple batch_delete() calls."
            )

        try:
            # Call Gmail API batchDelete
            self.service.users().messages().batchDelete(
                userId="me", body={"ids": message_ids}
            ).execute()

            return {
                "success": True,
                "message_count": len(message_ids),
            }

        except Exception as e:
            error_msg = f"Failed to batch delete {len(message_ids)} messages: {e}"
            return {
                "success": False,
                "message_count": 0,
                "error": error_msg,
            }

    def list_aliases(self) -> list:
        """
        List all send-as aliases for the authenticated user.

        Retrieves all send-as aliases (custom "From" addresses) configured for
        the user's Gmail account. Returns a list of SendAsAlias objects that can
        be used to manage the aliases.

        Returns:
            list[SendAsAlias]: List of SendAsAlias objects, one for each configured alias

        Raises:
            Exception: If the API call fails

        Example:
            >>> manager = ServiceAccountEmailManager(
            ...     service_account_file='cred/sa.json',
            ...     impersonate_user='user@example.com'
            ... )
            >>>
            >>> # List all aliases
            >>> aliases = manager.list_aliases()
            >>> print(f"Found {len(aliases)} send-as aliases:")
            >>> for alias in aliases:
            ...     verified = "✓" if alias.is_verified else "✗"
            ...     primary = " [PRIMARY]" if alias.is_primary else ""
            ...     default = " [DEFAULT]" if alias.is_default else ""
            ...     print(f"  {verified} {alias.display_name} <{alias.send_as_email}>{primary}{default}")
            >>>
            >>> # Filter to verified aliases only
            >>> verified_aliases = [a for a in aliases if a.is_verified]
            >>>
            >>> # Find the primary alias
            >>> primary_alias = next((a for a in aliases if a.is_primary), None)
            >>> if primary_alias:
            ...     print(f"Primary: {primary_alias.send_as_email}")
            >>>
            >>> # Update an alias
            >>> for alias in aliases:
            ...     if alias.send_as_email == 'support@company.com':
            ...         alias.signature = '<p>New signature</p>'
            ...         alias.update()

        Notes:
            - Each SendAsAlias object has a reference to this manager
            - All aliases include both primary and additional send-as addresses
            - Use is_primary property to identify the main account email
            - Use is_verified property to check verification status
            - Requires 'https://www.googleapis.com/auth/gmail.settings.basic' scope

        See Also:
            - SendAsAlias: Class representing a send-as alias
            - SendAsAlias.create(): Create a new alias
            - SendAsAlias.verify(): Send verification email
        """
        try:
            # Call Gmail API to list send-as aliases
            result = (
                self.service.users().settings().sendAs().list(userId="me").execute()
            )

            # Get the list of send-as aliases from response
            send_as_list = result.get("sendAs", [])

            # Convert to SendAsAlias objects
            aliases = []
            for raw_alias in send_as_list:
                alias = SendAsAlias(raw_alias=raw_alias, manager=self)
                aliases.append(alias)

            return aliases

        except Exception as e:
            raise Exception(f"Failed to list send-as aliases: {e}")

    def list_user_aliases(self, primary_email: str = None) -> list:
        """
        List all user aliases (Google Workspace account aliases) for a user.

        User aliases are actual email addresses configured at the Google Workspace
        account level that can receive email (unlike send-as aliases which are only
        for sending).

        Args:
            primary_email (str, optional): Primary email of the user to list aliases for.
                If None, uses the impersonated_user. Defaults to None.

        Returns:
            list[UserAlias]: List of UserAlias objects for the user

        Raises:
            ValueError: If primary_email is not provided and no user is impersonated
            Exception: If the API call fails

        Example:
            >>> # List aliases for impersonated user
            >>> manager = ServiceAccountEmailManager(
            ...     impersonate_user='john.doe@company.com'
            ... )
            >>> aliases = manager.list_user_aliases()
            >>> for alias in aliases:
            ...     print(f"  {alias.alias}")
            >>>
            >>> # List aliases for specific user
            >>> aliases = manager.list_user_aliases('jane.smith@company.com')

        Note:
            Requires the Admin SDK API scope:
            https://www.googleapis.com/auth/admin.directory.user.alias
        """
        # Use impersonated_user if no email provided
        if primary_email is None:
            if self.impersonated_user is None:
                raise ValueError(
                    "primary_email is required when not impersonating a user"
                )
            primary_email = self.impersonated_user

        return UserAlias.list(self, primary_email)

    def watch(
        self,
        topic_name: str = None,
        label_ids: list = None,
        label_filter_behavior: str = "INCLUDE",
    ) -> dict:
        """
        Set up Gmail push notifications via Cloud Pub/Sub.

        Configures Gmail to send push notifications when mailbox changes occur.
        This enables real-time email processing without polling. The watch
        request expires after 7 days and must be renewed.

        Args:
            topic_name (str, optional): Full Pub/Sub topic name in the format
                'projects/{project}/topics/{topic}'. If not provided, uses
                TOPIC_NAME from environment variables.
            label_ids (list[str], optional): List of label IDs to watch.
                If provided, only changes to messages with these labels trigger
                notifications. Examples: ['INBOX'], ['INBOX', 'UNREAD'].
                If None, watches all mailbox changes.
            label_filter_behavior (str, optional): How to apply label_ids filter.
                - "INCLUDE": Watch messages with any of the specified labels (default)
                - "EXCLUDE": Watch messages without any of the specified labels
                Only used when label_ids is provided.

        Returns:
            dict: Watch response containing:
                - historyId (str): Starting history ID for changes
                - expiration (str): Unix timestamp (milliseconds) when watch expires

        Raises:
            ValueError: If topic_name is not provided and TOPIC_NAME env var is not set
            Exception: If the API call fails

        Example:
            >>> manager = ServiceAccountEmailManager(
            ...     service_account_file='cred/sa.json',
            ...     impersonate_user='user@example.com'
            ... )
            >>>
            >>> # Watch all mailbox changes (uses TOPIC_NAME from .env)
            >>> response = manager.watch()
            >>> print(f"Watch expires at: {response['expiration']}")
            >>>
            >>> # Watch with custom topic
            >>> response = manager.watch(
            ...     topic_name='projects/my-project/topics/gmail-notifications'
            ... )
            >>>
            >>> # Watch only INBOX changes
            >>> response = manager.watch(
            ...     label_ids=['INBOX']
            ... )
            >>>
            >>> # Watch everything except SPAM and TRASH
            >>> response = manager.watch(
            ...     label_ids=['SPAM', 'TRASH'],
            ...     label_filter_behavior='EXCLUDE'
            ... )

        Notes:
            - Watch expires after 7 days (maximum allowed by Gmail API)
            - You should renew the watch before expiration to maintain continuous monitoring
            - Requires 'https://www.googleapis.com/auth/gmail.readonly' scope
            - The Pub/Sub topic must grant publish permissions to gmail-api-push@system.gserviceaccount.com
            - Use get_message_from_pubsub() to process incoming notifications

        See Also:
            - get_message_from_pubsub(): Process Pub/Sub notifications
            - Gmail Push Notifications: https://developers.google.com/gmail/api/guides/push
        """
        # Get topic name from parameter or environment variable
        if topic_name is None:
            topic_name = os.getenv("TOPIC_NAME")
            if not topic_name:
                raise ValueError(
                    "topic_name parameter not provided and TOPIC_NAME "
                    "environment variable is not set"
                )

        # Build watch request body
        watch_request = {
            "topicName": topic_name,
        }

        # Add label filter if provided
        if label_ids:
            watch_request["labelIds"] = label_ids
            watch_request["labelFilterBehavior"] = label_filter_behavior

        try:
            # Call Gmail API watch endpoint
            result = (
                self.service.users().watch(userId="me", body=watch_request).execute()
            )

            return result

        except Exception as e:
            raise Exception(f"Failed to set up Gmail watch: {e}")


# Example usage
if __name__ == "__main__":
    """
    Example usage of the ServiceAccountEmailSender.
    Uncomment and modify to test.
    """

    # Example 1: Send email with impersonation
    # try:
    #     sender = ServiceAccountEmailSender(
    #         service_account_file='cred/noreply_sa.json',
    #         impersonate_user='user@example.com'
    #     )
    #
    #     sender.send_email(
    #         from_name='Dock Johnson',
    #         from_email='user@example.com',
    #         to_email=['test@example.com'],
    #         subject='Test Email via Service Account',
    #         body='This email was sent using service account authentication with user impersonation.',
    #     )
    # except Exception as e:
    #     print(f"Error: {e}")

    # Example 2: Send email using config file
    # try:
    #     sender = ServiceAccountEmailSender(
    #         service_account_file='cred/noreply_sa.json',
    #         impersonate_user='user@example.com'
    #     )
    #
    #     sender.send_email(
    #         email_config_path='conf/email_config.json',
    #         subject='Test Email',
    #         body='Hello World',
    #         file_attachment_paths=['logs/test.log']
    #     )
    # except Exception as e:
    #     print(f"Error: {e}")

    # Example 3: Get account info
    # try:
    #     sender = ServiceAccountEmailManager(
    #         service_account_file='cred/noreply_sa.json',
    #         impersonate_user='user@example.com'
    #     )
    #
    #     info = sender.get_account_info()
    #     print(f"Account Info:")
    #     for key, value in info.items():
    #         print(f"  {key}: {value}")
    # except Exception as e:
    #     print(f"Error: {e}")

    # Example 4: Get email by message ID
    # try:
    #     manager = ServiceAccountEmailManager(
    #         service_account_file='cred/noreply_sa.json',
    #         impersonate_user='user@example.com'
    #     )
    #
    #     message_id = '18c5a1b2f3d4e5f6'  # Replace with actual message ID
    #     email = manager.get_email_by_message_id(message_id)
    #
    #     # Use Message object properties
    #     print(f"Message ID: {email.id}")
    #     print(f"From: {email.from_email}")
    #     print(f"To: {email.to_email}")
    #     print(f"Subject: {email.subject}")
    #     print(f"Date: {email.date}")
    #     print(f"Body: {email.body[:100]}...")  # First 100 chars
    #     print(f"Has attachments: {email.has_attachments()}")
    #     print(f"Is unread: {email.is_unread()}")
    # except Exception as e:
    #     print(f"Error: {e}")

    # Example 5: Process Pub/Sub notification
    # try:
    #     manager = ServiceAccountEmailManager(
    #         service_account_file='cred/noreply_sa.json',
    #         impersonate_user='user@example.com'
    #     )
    #
    #     # Simulated Pub/Sub message
    #     pubsub_message = {
    #         "message": {
    #             "data": "eyJlbWFpbEFkZHJlc3MiOiAibm8tcmVwbHlAbWVub2VudGVycHJpc2VzLmNvbSIsICJoaXN0b3J5SWQiOiAiMTIzNDU2In0=",
    #             "messageId": "136969346945",
    #             "publishTime": "2021-02-26T19:13:55.749Z"
    #         },
    #         "subscription": "projects/myproject/subscriptions/mysubscription"
    #     }
    #
    #     result = manager.get_email_from_pubsub(pubsub_message)
    #     print(f"Email Address: {result['email_address']}")
    #     print(f"History ID: {result['history_id']}")
    #     print(f"New Messages: {len(result['messages'])}")
    #
    #     # Messages are now Message objects
    #     for msg in result['messages']:
    #         print(f"\n  From: {msg.from_email}")
    #         print(f"  Subject: {msg.subject}")
    #         print(f"  Body: {msg.body[:100]}")
    # except Exception as e:
    #     print(f"Error: {e}")

    # Example 6: Get email from ANY user in workspace
    # try:
    #     manager = ServiceAccountEmailManager(
    #         service_account_file='cred/noreply_sa.json',
    #         impersonate_user='user@example.com'  # Default user
    #     )
    #
    #     # Get email from different users
    #     email1 = manager.get_email_by_message_id_for_user(
    #         user_email='user@example.com',
    #         message_id='msg123abc'
    #     )
    #     print(f"Email 1 - From: {email1.from_email}")
    #     print(f"Email 1 - Accessed as: {email1.accessed_as_user}")
    #
    #     email2 = manager.get_email_by_message_id_for_user(
    #         user_email='support@example.com',
    #         message_id='msg456def'
    #     )
    #     print(f"Email 2 - From: {email2.from_email}")
    #     print(f"Email 2 - Accessed as: {email2.accessed_as_user}")
    #
    #     email3 = manager.get_email_by_message_id_for_user(
    #         user_email='admin@example.com',
    #         message_id='msg789ghi'
    #     )
    #     print(f"Email 3 - From: {email3.from_email}")
    #     print(f"Email 3 - Accessed as: {email3.accessed_as_user}")
    # except Exception as e:
    #     print(f"Error: {e}")

    pass
