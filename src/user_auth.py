#!/usr/bin/env python3

import hashlib, os, sys
from flask_login import UserMixin
from src.util.helpers import (
    generate_token,
    generate_password,
)
from src.util.sql_helper import (
    add_update_record,
    get_record,
    update_existing_record,
)

class UserAuth(UserMixin):
    def __init__(
        self,
        log,
        username: str = "",
        password: str = "",
        email: str = "",
        user_id: str = "",
        api_token: str = "",
        role: str = "",
    ):
        # Class util attr
        self.log = log
        self.db_name = "accounts"
        self.schema = "auth"
        self.table = "users"

        # User attributes
        self.username = username
        self.password = password
        self.secret_key = api_token
        self.user_id = user_id
        self.email = email
        self.role = role
        
        self.user_settings = {}
        self.init_user()
        log.debug(
            f"UserAuth initialized with username: {self.username}, user_id: {self.user_id}, email: {self.email}"
        )

    def init_user(self: object) -> object:
        """
        Initializes the user by loading existing user data from the database.
        This method checks if the user exists in the database and updates the user attributes accordingly.
        """
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

        if not psql_user:
            self.log.warning(f"User does not exist in the database.")
            return None

        if not self.username:
            self.username = psql_user.get("username")
        elif not self.user_id:
            self.user_id = psql_user.get("user_id")

        self.email = psql_user.get("email", self.email)
        self.password_hash = psql_user.get("password_hash", self.password_hash)
        self.token_hash = psql_user.get("token_hash", self.token_hash)
        self.created_at = psql_user.get("created_at", None)
        self.role = psql_user.get("role", self.role)
        self.is_active = psql_user.get("is_active", False)
        self.get_user_settings()

        return self

    def get_user_settings(self, database: str = "accounts") -> dict:
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
            schema="settings",
            table="user_settings",
            column="user_id",
            value=self.user_id,
            database=database,
        )
        self.first_name = self.user_settings.get("first_name", "")
        self.last_name = self.user_settings.get("last_name", "")
        return self.user_settings

    #############################################
    ############ UserMixin Overrides ############
    #############################################

    def is_active(self):
        """
        Returns True if the user is active.
        This method is used by Flask-Login to determine if the user account is active.
        """
        return self.is_active

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

    def add_user_to_sql(self,) -> object:
        """
        Adds a new user to the database.
        #### Returns:
            - self: UserAuth object
        #### Raises:
            - psycopg2.Error: if there is an error executing the SQL query
        """
        if self.is_active():
            self.log.warning(f"User {self.username} is already active in the database.")
            raise ValueError(f"User {self.username} already exists.")
        
        if not self.token_hash:
            self.secret_key = generate_token()
            self.token_hash = hashlib.sha256(self.secret_key.encode()).hexdigest()

        if not self.password:
            self.password = generate_password()

        if not self.password_hash:
            self.password_hash = hashlib.sha256(self.password.encode()).hexdigest()

        try:
            add_update_record(
                database=self.db_name,
                schema=self.schema,
                table=self.table,
                columns=["user_id", "username", "email", "password_hash", "token_hash", "is_active", "secret_code"],
                values=[self.user_id, self.username, self.email, self.password_hash, self.token_hash, False, self.secret_code],
                conflict_target="username",
                on_conflict="DO NOTHING",
            )
        except Exception as e:
            self.log.error(f"Error adding user to database: {e}")
            raise e
        
        try:
            self.log.debug("Creating new user in the database")
            columns = [
                "user_id",
                "first_name",
                "last_name",
            ]
            values = [
                self.user_id,
                self.first_name,
                self.last_name,
            ]
            add_update_record(
                database=self.db_name,
                schema="settings",
                table="user_settings",
                columns=columns,
                values=values,
                conflict_target=["user_id"],
            )
        except Exception as e:
            self.log.error(f"Error creating user settings: {e}")

        self.log.info(f"User {self.username} added to database.")

        return self

    def activate_user(self):
        """
        Activates a user in the database by setting the is_active flag to True.
        #### Returns:
            - bool: True if the user was activated successfully, False otherwise
        """
        self.log.info(f"Activating user {self.username}")
        if not self.user_exists():
            self.log.warning(f"User {self.username} does not exist. Cannot activate.")
            return False

        update_existing_record(
            database=self.database,
            schema=self.schema,
            table=self.table,
            update_columns=["is_active"],
            update_values=[True],
            where_column="username",
            where_value=self.username,
        )
        self.log.info(f"User {self.username} has been activated.")
        return True

    def user_exists(self):
        """
        Checks if a user exists in the database.
        #### Returns:
            - bool: True if user exists, False otherwise
        """
        if get_record(
            database=self.db_name,
            schema=self.schema,
            table=self.table,
            column="username",
            value=self.username,
        ):
            return True
        return False

    def check_password(self,):
        """
        Checks if the provided password matches the stored password hash for the user.
        #### Returns:
            - bool: True if the password matches, False otherwise
        #### Raises:
            - ValueError: if the password is not provided
        """
        self.log.info(f"Checking password for user {self.username}")
        if not self.password:
            raise ValueError("Password is required to check password.")

        # Hash the password to compare with the stored hash
        password_hash = hashlib.sha256(self.password.encode()).hexdigest()
        self.log.debug(f"Password hash for {self.username}: {password_hash}")

        # Build the SQL query to check the password
        record = get_record(
            database=self.db_name,
            schema=self.schema,
            table=self.table,
            column="username",
            value=self.username,
        )
        stored_password_hash = record.get("password_hash", None)

        if stored_password_hash == password_hash:
            self.log.info(f"Password for user {self.username} is correct.")
            self.password_hash = password_hash
            return True
        else:
            self.log.warning(f"Incorrect password for user {self.username}.")
            return False


    def reset_user_password(self, new_password: str = None,):
        """
        Resets the password for a customer in the database.
        #### Args:
            - new_password: str: the new password to set for the user. If not provided, a new password will be generated.
        #### Returns:
            - new_password: str: the new password for the customer
        """
        self.log.info(f"Resetting password for user {self.username}")
        # Generate a new password if not provided
        if not new_password:
            new_password = generate_password()

        # Hash the new password
        password_hash = hashlib.sha256(new_password.encode()).hexdigest()
        self.password_hash = password_hash

        # Check if the user exists in the database
        if not self.user_exists():
            self.log.warning(
                f"User {self.username} does not exist. Cannot reset password."
            )
            raise ValueError(f"User {self.username} does not exist.")
        
        update_existing_record(
            database=self.database,
            schema=self.schema,
            table=self.table,
            update_columns=["password_hash"],
            update_values=[self.password_hash],
            where_column="username",
            where_value=self.username,

        )
        self.log.info(f"Password for user {self.username} has been reset.")
        return new_password

    def reset_user_token(self):
        """
        Resets the token for a user in the database.
        #### Returns:
            - new_token: str: the new token for the user
        
        """
        self.log.info(f"Resetting token for user {self.username}")
        new_token = generate_token()
        self.token_hash = hashlib.sha256(new_token.encode()).hexdigest()

        # Check if the user exists before updating the token
        if not self.user_exists():
            self.log.warning(
                f"User {self.username} does not exist. Cannot reset token."
            )
            raise ValueError(f"User {self.username} does not exist.")

        update_existing_record(
            database=self.database,
            schema=self.schema,
            table=self.table,
            update_columns=["token_hash"],
            update_values=[self.token_hash],
            where_column="username",
            where_value=self.username,
        )
        self.log.info(f"Token for user {self.username} has been reset.")
        return new_token
       
    def update_user_email(
        self,
        new_email: str,
    ):
        """
        Updates the email for a user in the database.
        #### Args:
            - new_email: str: the new email to set for the user
        #### Returns:
            - new_email: str: the updated email for the user
        #### Raises:
            - ValueError: if new_email is not provided or user does not exist
        """
        if not self.user_exists():
            self.log.warning(
                f"User {self.username} does not exist. Cannot update email."
            )
            raise ValueError(f"User {self.username} does not exist.")

        update_existing_record(
            database=self.database,
            schema=self.schema,
            table=self.table,
            update_columns=["email"],
            update_values=[new_email],
            where_column="username",
            where_value=self.username,
        )
        self.email = new_email
        self.log.info(f"Email for user {self.username} has been updated to {new_email}")
        return new_email

    def update_user_setting(self, setting_key: str, setting_value: str):
        """
        Updates the user settings based on the request data.
        #### Args:
            - setting_key: str: the key of the setting to update
            - setting_value: str: the new value for the setting
            - user_id: str: the ID of the user whose settings are to be updated
        #### Returns:
            - bool: True if the settings were updated successfully, False otherwise
        """
        self.log.info(f"Updating settings for user {self.username}")
                
        if not self.user_exists():
            self.log.warning(
                f"User {self.username} does not exist. Cannot update settings."
            )
            raise ValueError(f"User {self.username} does not exist.")

        update_existing_record(
            database="accounts",
            schema="settings",
            table="user_settings",
            update_columns=[setting_key],
            update_values=[setting_value],
            where_column="user_id",
            where_value=user_id
        )
        self.get_user_settings()
        self.log.info(f"Settings for user {self.username} have been updated.")
        return True
        

if __name__ == "__main__":
    import os, json, logging

    logger = logging.getLogger("UserAuth")
    username = "web-bot"
    user_id = "web-bot"
    email = "corona.aria.a@gmail.com"

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