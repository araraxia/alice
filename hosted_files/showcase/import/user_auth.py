#!/usr/bin/env python3

import psycopg2, hashlib, os, sys
from flask_login import UserMixin
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT_DIR / "src"
if SRC_DIR not in sys.path:
    sys.path.append(str(SRC_DIR))

from extras.helpers import (
    generate_token,
    generate_password,
    hash_string,
    get_html_email_str
)
from extras.sql_helper import (
    init_psql_con_cursor,
    get_record,
    update_existing_record,
    add_update_record,
    delete_record,
)
from AutomatedEmails import AutomatedEmails


class UserAuth(UserMixin):
    def __init__(
        self,
        log,
        username: str = "",
        password: str = "",
        email: str = "",
        user_id: str = None,
        api_token: str = None,
        role: str = "",
        company_uuid: str = None,
        company_code: str = None,
    ):
        self.set_utility_attributes(log)
        self.init_user(
            username=username,
            password=password,
            email=email,
            user_id=user_id,
            api_token=api_token,
            role=role,
            company_uuid=company_uuid,
            company_code=company_code,
        )
        self.log.debug(
            f"UserAuth initialized with username: {self.username}, user_id: {self.user_id}, email: {self.email}"
        )
        self.log.debug(f"Company UUID: {self.company_uuid} ")

    def set_utility_attributes(self, log):
        self.log = log
        self.db_name = "accounts"
        self.schema = "auth"
        self.table = "users"

    def init_user(
        self,
        username: str = "",
        password: str = "",
        email: str = "",
        user_id: str = None,
        api_token: str = None,
        role: str = "",
        company_uuid: str = None,
        company_code: str = None,
    ) -> object:
        """
        Initializes the user by setting attributes and loading existing user data from the database.
        This method checks if the user exists in the database and updates the user attributes accordingly.
        Will not overwrite provided attributes if they already exist.
        """
        # Set initial attributes

        self.username = username
        self.user_id = user_id
        self.email = email
        self.role = role
        self.company_uuid = company_uuid
        self.company_code = company_code
        self.created_at = None
        self.active_status = False
        self.activation_code = None
        self.first_name = None
        self.last_name = None
        self.user_settings = {}

        if password:
            self.password = password
            self.password_hash = hash_string(password)
        else:
            self.password = None
            self.password_hash = None

        if api_token:
            self.given_token = hash_string(api_token)
        else:
            self.given_token = None
        self.token_hash = None  # Will be loaded from DB if user exists

        psql_user = self.get_user_auth_record()
        # If user does not exist in the database, return
        if not psql_user:
            self.log.warning(f"User does not exist in the database.")
            return None

        if not self.username:
            self.username = psql_user.get("username", None)
        if not self.user_id:
            self.user_id = psql_user.get("user_id", None)
        if not self.email:
            self.email = psql_user.get("email", None)
        if not self.role:
            self.role = psql_user.get("role", None)
        if not self.company_uuid:
            self.company_uuid = psql_user.get("company_uuid", None)
        if not self.password_hash:
            self.password_hash = psql_user.get("password_hash", None)
        if not self.token_hash:
            self.token_hash = psql_user.get("token_hash", None)

        self.created_at = psql_user.get("created", None)
        self.active_status = psql_user.get("is_active", False)

        if not self.company_uuid and self.role == "customer-role":
            self.set_company_uuid()

        self.get_user_settings(database="accounts")

        for attribute in [
            "username",
            "user_id",
            "email",
            "role",
            "company_uuid",
            "company_code",
            "password_hash",
            "token_hash",
            "created_at",
        ]:
            value = getattr(self, attribute, None)
            if not value:
                self.log.warning(
                    f"Attribute {attribute} is not set for user {self.username}"
                )
        return self

    def get_user_auth_record(self):
        # Load existing user data from the database if user exists
        self.log.debug(
            f"Fetching user auth record for username: {self.username or 'null'}, user_id:{self.user_id or 'null'}"
        )
        psql_user = None
        if self.user_id:
            psql_user = get_record(
                schema=self.schema,
                table=self.table,
                column="user_id",
                value=self.user_id,
                database=self.db_name,
            )
        elif self.username:
            psql_user = get_record(
                schema=self.schema,
                table=self.table,
                column="username",
                value=self.username,
                database=self.db_name,
            )
        else:
            self.log.warning("No user_id or username provided to initialize UserAuth.")
            return None
        self.log.debug(f"Fetched user auth record: {psql_user}")
        return psql_user

    def set_company_uuid(self):
        try:
            if self.role == "customer-role" and not self.company_uuid:
                self.user_settings = self.get_user_settings(database="accounts")
                customer_record = get_record(
                    database="db",
                    schema="Accounts",
                    table="Customers",
                    column="Customer ID",
                    value=self.company_code,
                )
                self.company_uuid = customer_record.get("primary_key_id", None)
                self.log.info(f"Adding company_uuid to user auth for {self.username}")
                update_existing_record(
                    database="accounts",
                    schema="auth",
                    table="users",
                    update_columns=["company_uuid"],
                    update_values=[self.company_uuid],
                    where_column="username",
                    where_value=self.username,
                )
        except Exception as e:
            self.log.error(f"Error setting company_uuid for {self.username}: {e}")
            self.company_uuid = None

    def get_user_settings(self, database: str) -> dict:
        """
        Retrieves the user settings from the database.
        This method checks if the user settings are already loaded, and if not, it fetches them from the database.
        #### Args:
            - database: str: name of the database to connect to
        #### Returns:
            - dict: user settings for the specified user
        """
        self.log.info(f"Loading user settings for {self.username}")
        self.user_settings = get_record(
            schema="accounts",
            table="settings",
            column="user_id",
            value=self.user_id,
            database=database,
        )
        if self.user_settings:
            self.company_code = self.user_settings.get("company_code", "")
            self.first_name = self.user_settings.get("first_name", "")
            self.last_name = self.user_settings.get("last_name", "")
        else:
            self.company_code = ""
            self.first_name = ""
            self.last_name = ""

        return self.user_settings

    def reload_user_settings(self, database: str) -> dict:
        """
        Reloads the user settings from the database.
        This is useful if the user settings have been changed and you want to refresh them.
        """
        self.user_settings = get_record(
            schema="accounts",
            table="settings",
            column="user_id",
            value=self.user_id,
            database=database,
        )
        self.company_code = self.user_settings.get("company_code", "")
        self.log.info(f"User {self.username} settings reloaded.")
        return self.user_settings

    #############################################
    ############ UserMixin Overrides ############
    #############################################

    @init_psql_con_cursor
    def is_active(cursor, connection, self):
        is_active_query = f"""
        SELECT is_active FROM {self.schema}.{self.table}
        WHERE username = %s
        """
        if self.user_exists(cursor, connection):
            try:
                cursor.execute(is_active_query, (self.username,))
                result = cursor.fetchone()
                if result:
                    return result.get("is_active", False)
                else:
                    self.log.warning(f"User {self.username} does not exist.")
                    return False
            except psycopg2.Error as e:
                self.log.error(f"Error checking user activity for {self.username}: {e}")
                return False
        else:
            self.log.warning(f"User {self.username} does not exist.")
            return False

    def is_authenticated(self):
        return self.check_password() if self.password else False

    def is_anonymous(self):
        """
        Returns False, as this class does not support anonymous users.
        """
        return False

    def get_id(self):
        """
        Returns the user ID for the UserMixin interface.
        This is used by Flask-Login to identify the user.
        """
        return self.user_id

    def get_user(self):
        return self

    def __repr__(self):
        return f"UserAuth(customer_id={self.user_id}, username={self.username}, email={self.email})"

    # User Management Methods
    @init_psql_con_cursor
    def add_user_to_sql(
        cursor,
        connection,
        self,
        database: str = "accounts",
        role: str = "customer-role",
    ) -> object:
        """
        Adds a new customer to the database. If the customer already exists, it updates the existing record.
        #### Args:
            - database: str: name of the database to connect to
            - role: str: the role to assign to the user (default is "customer-role")
        #### Kwargs:
            - cursor: psycopg2 cursor object
            - connection: psycopg2 connection object
        #### Returns:
            - self: UserAuth object
        #### Raises:
            - psycopg2.Error: if there is an error executing the SQL query
        """
        if self.user_exists():
            raise ValueError(f"User {self.username} already exists in the database.")
        
        if not self.token_hash:
            if not self.given_token:
                self.given_token = generate_token()
            self.token_hash = hash_string(self.given_token)

        if not self.password:
            self.password = generate_password()
        self.password_hash = hashlib.sha256(self.password.encode()).hexdigest()

        columns = (
            "user_id",
            "username",
            "email",
            "password_hash",
            "token_hash",
            "is_active",
            "role",
            "company_uuid",
            "activation_code",
        )
        values = (
            self.user_id,
            self.username,
            self.email,
            self.password_hash,
            self.token_hash,
            False,
            role,
            self.company_uuid,
            self.activation_code
        )

        try:
            add_update_record(
                cursor=cursor,
                connection=connection,
                database=database,
                schema=self.schema,
                table=self.table,
                columns=columns,
                values=values,
                conflict_target=["username"],
                on_conflict="DO NOTHING",
            )
            self.log.info(f"Customer {self.username} added to database.")
        except psycopg2.Error as e:
            self.log.error(f"Error adding customer {self.username} to database: {e}")
            raise e

        columns = (
            "user_id",
            "first_name",
            "last_name",
            "company_code",
        )
        values = (
            self.user_id,
            self.first_name,
            self.last_name,
            self.company_code,
        )
        try:
            add_update_record(
                cursor=cursor,
                connection=connection,
                database=database,
                schema="accounts",
                table="settings",
                columns=columns,
                values=values,
                conflict_target=["user_id"],
                on_conflict="DO NOTHING",
            )
            self.log.info(f"User settings for {self.username} added to database.")
        except psycopg2.Error as e:
            self.log.error(f"Error adding user settings for {self.username}: {e}")
            raise e

        return self

    def user_exists(self, cursor=None, connection=None) -> dict:
        """
        Checks if a user exists in the database.
        #### Args:
            - cursor: psycopg2 cursor object
            - connection: psycopg2 connection object
        #### Returns:
            - dict: user record if exists, None otherwise
        """
        return get_record(
            cursor=cursor,
            connection=connection,
            database=self.db_name,
            schema=self.schema,
            table=self.table,
            column="username",
            value=self.username,
        )

    @init_psql_con_cursor
    def check_password(
        cursor,
        connection,
        self: object,
        database: str = "accounts",
    ):
        """
        Checks if the provided password matches the stored password hash for the user.
        #### Args:
            - database: str: name of the database to connect to
        #### Returns:
            - bool: True if the password matches, False otherwise
        #### Raises:
            - psycopg2.Error: if there is an error executing the SQL query
            - ValueError: if the password is not provided
        """
        self.log.info(f"Checking password for user {self.username}")
        if not self.password:
            raise ValueError("Password is required to check password.")

        # Hash the password to compare with the stored hash
        self.password_hash = hashlib.sha256(self.password.encode()).hexdigest()
        self.log.debug(f"Password hash for {self.username}: {self.password_hash}")

        # Build the SQL query to check the password
        password_query = f"""
        SELECT password_hash FROM {self.schema}.{self.table}
        WHERE username = %s
        """
        values = (self.username,)

        # Execute the query and check the result
        try:
            cursor.execute(password_query, values)
            result = cursor.fetchone()
            if result:
                stored_password_hash = result.get("password_hash", None)
                self.log.debug(
                    f"Database password hash for {self.username}: {stored_password_hash}"
                )
                if stored_password_hash == self.password_hash:
                    self.log.info(f"Password for user {self.username} is correct.")
                    return True
                else:
                    self.log.warning(f"Incorrect password for user {self.username}.")
                    return False
            else:
                self.log.warning(f"User {self.username} does not exist.")
                return False
        except psycopg2.Error as e:
            self.log.error(f"Error checking password for user {self.username}: {e}")
            raise e
        except Exception as e:
            self.log.error(
                f"Unexpected error checking password for user {self.username}: {e}"
            )
            raise e

    @init_psql_con_cursor
    def reset_user_password(
        cursor,
        connection,
        self: object,
        database: str = "accounts",
        new_password: str = None,
    ):
        """
        Resets the password for a customer in the database.
        #### Args:
            - database: str: name of the database to connect to
            - new_password: str: the new password to set for the user. If not provided, a new password will be generated.
        #### Kwargs:
            - cursor: psycopg2 cursor object
            - connection: psycopg2 connection object
        #### Returns:
            - new_password: str: the new password for the customer
        #### Raises:
            - psycopg2.Error: if there is an error executing the SQL query
        """
        self.log.info(f"Resetting password for user {self.username}")
        # Generate a new password if not provided
        if not new_password:
            new_password = generate_password()

        # Hash the new password
        password_hash = hashlib.sha256(new_password.encode()).hexdigest()
        self.password_hash = password_hash

        # Check if the user exists in the database
        if not self.user_exists(cursor, connection):
            self.log.warning(
                f"User {self.username} does not exist. Cannot reset password."
            )
            raise ValueError(f"User {self.username} does not exist.")

        update_query = f"""
        UPDATE {self.schema}.{self.table}
        SET password_hash = %s
        WHERE username = %s and email = %s
        """
        values = (self.password_hash, self.username, self.email)

        try:
            cursor.execute(update_query, values)
            connection.commit()
            self.log.info(f"Password for customer {self.username} updated.")
            return new_password
        except psycopg2.Error as e:
            self.log.error(
                f"Error resetting password for customer {self.username}: {e}"
            )
            connection.rollback()
            raise e

    @init_psql_con_cursor
    def reset_user_token(
        cursor,
        connection,
        self: object,
        database: str = "accounts",
    ):
        """
        Resets the token for a user in the database.
        #### Args:
            - database: str: name of the database to connect to
        #### Returns:
            - new_token: str: the new token for the user
        #### Raises:
            - psycopg2.Error: if there is an error executing the SQL query
        """
        self.log.info(f"Resetting token for user {self.username}")
        new_token = generate_token()
        self.token_hash = hashlib.sha256(new_token.encode()).hexdigest()

        # Check if the user exists before updating the token
        if not self.user_exists(cursor, connection):
            self.log.warning(
                f"User {self.username} does not exist. Cannot reset token."
            )
            raise ValueError(f"User {self.username} does not exist.")

        self.log.debug(f"Updating token for user {self.username}")
        update_query = f"""
        UPDATE {self.schema}.{self.table}
        SET token_hash = %s
        WHERE username = %s
        """
        values = (self.token_hash, self.username)

        try:
            cursor.execute(update_query, values)
            connection.commit()
            self.log.info(f"Token for customer {self.username} updated.")
            return new_token
        except psycopg2.Error as e:
            self.log.error(f"Error resetting token for customer {self.username}: {e}")
            connection.rollback()
            raise e

    @init_psql_con_cursor
    def update_user_email(
        cursor,
        connection,
        self,
        database: str = "accounts",
        new_email: str = None,
    ):
        """
        Updates the email for a user in the database.
        #### Args:
            - database: str: name of the database to connect to
            - new_email: str: the new email to set for the user
        #### Returns:
            - bool: True if the email was updated successfully, False otherwise
        """
        if not new_email:
            raise ValueError("New email is required to update the user email.")
        self.log.info(f"Updating email for user {self.username} to {new_email}")

        if not self.user_exists(cursor, connection):
            self.log.warning(
                f"User {self.username} does not exist. Cannot update email."
            )
            raise ValueError(f"User {self.username} does not exist.")

        self.log.debug(f"Updating email for user {self.username}")
        update_query = f"""
        UPDATE {self.schema}.{self.table}
        SET email = %s
        WHERE username = %s
        """
        values = (new_email, self.username)

        try:
            cursor.execute(update_query, values)
            connection.commit()
            self.log.info(f"Email for user {self.username} updated.")
            return True
        except psycopg2.Error as e:
            self.log.error(f"Error updating email for user {self.username}: {e}")
            connection.rollback()
            return False

    @init_psql_con_cursor
    def update_user_setting(cursor, connection, self, database, request):
        """
        Updates the user settings based on the request data.
        #### Args:
            - request: Flask request object containing the new user settings
        #### Returns:
            - bool: True if the settings were updated successfully, False otherwise
        """
        setting_key = request.json.get("setting_key", "")
        setting_value = request.json.get("setting_value", "")
        user_id = request.json.get("user_id", self.user_id)
        self.log.info(
            f"Updating user setting {setting_key} to {setting_value} for user_id {user_id}"
        )

        # Serialize setting_value to JSON if it's a dict or list
        from psycopg2.extras import Json

        original_setting_value = setting_value
        if isinstance(setting_value, (dict, list)):
            self.log.info(
                f"Using psycopg2.Json for complex data type: {type(setting_value)}"
            )
            self.log.debug(f"Original data: {setting_value}")
            setting_value = Json(setting_value)
            self.log.debug(f"Using Json wrapper for PostgreSQL")
        else:
            self.log.debug(f"Using plain value: {setting_value}")

        if not setting_key or original_setting_value is None or not user_id:
            raise ValueError("Both setting_key and setting_value are required.")
        self.log.info(f"Updating settings for user {self.username}")

        if not self.user_exists(cursor, connection):
            self.log.warning(
                f"User {self.username} does not exist. Cannot update settings."
            )
            raise ValueError(f"User {self.username} does not exist.")

        update_existing_record(
            cursor=cursor,
            connection=connection,
            database=database,
            schema="accounts",
            table="settings",
            update_columns=[setting_key],
            update_values=[setting_value],
            where_column="user_id",
            where_value=user_id,
        )

    def get_user_setting(self, setting_key: str):
        """
        Retrieves a specific user setting.
        #### Args:
            - setting_key: str: the key of the setting to retrieve
        #### Returns:
            - setting_value: the value of the specified setting, or None if not found
        """
        if not self.user_settings:
            self.get_user_settings(database="accounts")

        setting_value = self.user_settings.get(setting_key, None)

        # Try to deserialize JSON strings back to Python objects
        if isinstance(setting_value, str):
            try:
                import json

                # Try to parse as JSON - if it fails, return the original string
                return json.loads(setting_value)
            except (json.JSONDecodeError, ValueError):
                # If it's not valid JSON, return the original string
                return setting_value

        return setting_value

    def delete_user(self):
        self.log.info(f"Deleting user {self.username}")
        try:
            delete_record(
                database="accounts",
                log=self.log,
                schema_name="auth",
                table_name="users",
                columns="user_id",
                values=self.user_id,
            )
            delete_record(
                database="accounts",
                log=self.log,
                schema_name="accounts",
                table_name="settings",
                columns="user_id",
                values=self.user_id,
            )
            self.log.info(f"User {self.username} deleted.")
        except Exception as e:
            self.log.error(f"Error deleting user {self.username}: {e}")
            raise e

    def activate_user(self,):
        from flask import url_for
        try:
            update_existing_record(
                database="accounts",
                schema="auth",
                table="users",
                update_columns=["is_active", "activation_code"],
                update_values=[True, None],
                where_column="username",
                where_value=self.username,
            )
            self.active_status = True
            self.activation_code = None
            update_existing_record(
                database="accounts",
                schema="accounts",
                table="settings",
                update_columns=["company_code"],
                update_values=[self.company_code],
                where_column="user_id",
                where_value=self.user_id,
            )
            self.log.info(f"User {self.username} activated successfully.")
        except Exception as e:
            self.log.error(f"Error activating user: {e}", exc_info=True)
            raise e
        
        if self.first_name:
            first_name = self.first_name.capitalize()
        else:
            first_name = self.username.capitalize()
        
        login_url = url_for('internal_portal.login', _external=True)
        subject = "Your Account is Now Active"
        body = get_html_email_str(
            content_path="emails/new-user-activated.html",
            support_email="customer-service@email.com",
            content_context={
                "first_name": first_name,
                "login_url": login_url,
            },
        )
        automated_emails = AutomatedEmails()
        automated_emails.email_from_memory(
            from_name="No-Reply",
            from_email="no-reply@email.com",
            to_email=[self.email],
            subject=subject,
            body=body,
            is_html=True,
        )
        self.log.info(f"Activation email sent to {self.email}")


if __name__ == "__main__":
    import os, json, logging

    logger = logging.getLogger("UserAuth")
    username = "username"
    user_id = "userid"
    email = "user@email.com"

    user = UserAuth(
        username=username,
        log=logger,
        user_id=user_id,
        email=email,
    )

    """
    new_password = user.reset_user_password(database="accounts",
        new_password=password)
    print(f"New password: {new_password}")
    """

    new_token = user.reset_user_token(database="accounts")
    print(f"New token: {new_token}")

    sys.exit(0)

    user.add_user_to_sql(database="accounts")
    secret = user.secret_key
    username = user.username
    package = {
        "user_id": user.user_id,
        "username": user.username,
        "email": user.email,
        "secret_key": user.secret_key,
        "password": password,
    }

    dir = os.path.join("user_cred.json")
    with open(dir, "w") as f:
        json.dump(package, f, indent=4)
