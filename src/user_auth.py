#!/usr/bin/env python3

import psycopg2, hashlib, os, sys
from flask_login import UserMixin
from src.util.helpers import (
    generate_token,
    generate_password,
)
from src.util.sql_helper import (
    init_psql_con_cursor,
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
        user_id: str = None,
        api_token: str = None,
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
        
        self.init_user()
        self.user_settings = {}
        log.debug(
            f"UserAuth initialized with username: {self.username}, user_id: {self.user_id}, email: {self.email}"
        )

    def init_user(self: object) -> object:
        """
        Initializes the user by loading existing user data from the database.
        This method checks if the user exists in the database and updates the user attributes accordingly.
        Will not overwrite provided attributes if they already exist.
        #### Args:
        #### Returns:
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
            schema="accounts",
            table="settings",
            column="user_id",
            value=self.user_id,
            database=database,
        )

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
    ) -> object:
        """
        Adds a new customer to the database. If the customer already exists, it updates the existing record.
        #### Args:
            - database: str: name of the database to connect to
        #### Kwargs:
            - cursor: psycopg2 cursor object
            - connection: psycopg2 connection object
        #### Returns:
            - self: UserAuth object
        #### Raises:
            - psycopg2.Error: if there is an error executing the SQL query
        """

        insert_query = f"""
        INSERT INTO {self.schema}.{self.table} (user_id, username, email, password_hash, token_hash)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (username) DO UPDATE SET
        user_id = EXCLUDED.user_id,
        email = EXCLUDED.email,
        password_hash = EXCLUDED.password_hash,
        token_hash = EXCLUDED.token_hash
        """

        if not self.token_hash:
            self.secret_key = generate_token()
            self.token_hash = hashlib.sha256(self.secret_key.encode()).hexdigest()

        if not self.password:
            self.password = generate_password()

        if not self.password_hash:
            self.password_hash = hashlib.sha256(self.password.encode()).hexdigest()

        values = (
            self.user_id,
            self.username,
            self.email,
            self.password_hash,
            self.token_hash,
        )

        try:
            cursor.execute(insert_query, values)
            connection.commit()
            self.log.info(f"Customer {self.username} added to database.")
        except psycopg2.Error as e:
            self.log.error(f"Error adding customer {self.username} to database: {e}")
            connection.rollback()
            raise e

        return self

    @init_psql_con_cursor
    def add_user_to_holding(
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
        #### Kwargs:
            - cursor: psycopg2 cursor object
            - connection: psycopg2 connection object
        #### Returns:
            - self: UserAuth object
        #### Raises:
            - psycopg2.Error: if there is an error executing the SQL query
        """

        insert_query = f"""
        INSERT INTO {self.schema}.{self.table}_holding (user_id, username, email, password_hash, token_hash, role)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (username) DO UPDATE SET
        user_id = EXCLUDED.user_id,
        email = EXCLUDED.email,
        password_hash = EXCLUDED.password_hash,
        token_hash = EXCLUDED.token_hash,
        role = EXCLUDED.role
        """

        if not self.token_hash:
            self.secret_key = generate_token()
            self.token_hash = hashlib.sha256(self.secret_key.encode()).hexdigest()

        if not self.password:
            self.password = generate_password()

        if not self.password_hash:
            self.password_hash = hashlib.sha256(self.password.encode()).hexdigest()

        values = (
            self.user_id,
            self.username,
            self.email,
            self.password_hash,
            self.token_hash,
            role,
        )

        try:
            cursor.execute(insert_query, values)
            connection.commit()
            self.log.info(f"Customer {self.username} added to database.")
        except psycopg2.Error as e:
            self.log.error(f"Error adding customer {self.username} to database: {e}")
            connection.rollback()
            raise e

        return self

    def user_exists(self, cursor, connection):
        """
        Checks if a user exists in the database.
        #### Args:
            - cursor: psycopg2 cursor object
            - connection: psycopg2 connection object
        #### Returns:
            - bool: True if user exists, False otherwise
        """
        return get_record(
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
        setting_key = request.json.get("setting_key", {})
        setting_value = request.json.get("setting_value", {})
        user_id = request.json.get("user_id", self.user_id)
        
        if not setting_key or not setting_value or not user_id:
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
            where_value=user_id
        )
        

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