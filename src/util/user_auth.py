#!/usr/bin/env python3

import psycopg2, hashlib, os, sys
from flask_login import UserMixin

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from extras.helpers import (
    generate_token,
    generate_password,
)
from extras.sql_helper import init_psql_con_cursor, get_record

password = "ytb*kpk6enf2AZA2eca"


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
        self.db_name = "meno_accounts"
        self.schema = "auth"
        self.table = "users"
        self.secret_key = None

        # User attributes
        self.username = username
        self.password = password
        self.password_hash = hashlib.sha256(password.encode()).hexdigest()
        self.user_id = user_id
        self.email = email
        self.token_hash = None
        self.given_token = (
            hashlib.sha256(api_token.encode()).hexdigest() if api_token else None
        )
        self.created_at = None
        self.role = role
        self.init_user()
        log.debug(
            f"UserAuth initialized with username: {self.username}, user_id: {self.user_id}, email: {self.email}"
        )

    def init_user(self: object, database: str = "meno_accounts"):
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

        self.username = (
            psql_user.get("username", self.username)
            if not self.username
            else self.username
        )

        self.user_id = (
            psql_user.get("user_id", self.user_id) if not self.user_id else self.user_id
        )

        self.email = (
            psql_user.get("email", self.email) if not self.email else self.email
        )

        self.password_hash = (
            psql_user.get("password_hash", self.password_hash)
            if not self.password_hash
            else self.password_hash
        )

        self.token_hash = (
            psql_user.get("token_hash", self.given_token)
            if not self.given_token
            else self.token_hash
        )

        self.created_at = (
            psql_user.get("created", None)
            if self.created_at is None
            else self.created_at
        )

        self.role = psql_user.get("role", self.role) if not self.role else self.role

        return self

    # UserMixin Overrides

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
        database: str = "meno_accounts",
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

    def user_exists(self, cursor, connection):
        """
        Checks if a user exists in the database.
        #### Args:
            - cursor: psycopg2 cursor object
            - connection: psycopg2 connection object
        #### Returns:
            - bool: True if user exists, False otherwise
        """
        query = f"""
        SELECT EXISTS (
            SELECT 1 FROM {self.schema}.{self.table}
            WHERE username = %s OR email = %s
        )
        """
        values = (self.username, self.email)

        try:
            cursor.execute(query, values)
            exists = cursor.fetchone()[0]
            return exists
        except KeyError:
            return False
        except psycopg2.Error as e:
            self.log.error(f"Error checking if user {self.username} exists: {e}")
            raise e

    @init_psql_con_cursor
    def check_password(
        cursor,
        connection,
        self,
        database: str = "meno_accounts",
    ):
        if not self.password:
            raise ValueError("Password is required to check password.")

        self.password_hash = hashlib.sha256(self.password.encode()).hexdigest()
        self.log.debug(F"Password hash for {self.username}: {self.password_hash}")
        password_query = f"""
        SELECT password_hash FROM {self.schema}.{self.table}
        WHERE username = %s
        """
        values = (self.username,)
        try:
            cursor.execute(password_query, values)
            result = cursor.fetchone()
            if result:
                stored_password_hash = result.get("password_hash", None)
                self.log.debug(f"Database password hash for {self.username}: {stored_password_hash}")
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
        self,
        database: str = "meno_accounts",
        new_password: str = None,
    ):
        """
        Resets the password for a customer in the database.
        #### Args:
            - database: str: name of the database to connect to
        #### Kwargs:
            - cursor: psycopg2 cursor object
            - connection: psycopg2 connection object
        #### Returns:
            - new_password: str: the new password for the customer
        #### Raises:
            - psycopg2.Error: if there is an error executing the SQL query
        """

        if not new_password:
            new_password = generate_password()

        password_hash = hashlib.sha256(new_password.encode()).hexdigest()
        self.password_hash = password_hash

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


if __name__ == "__main__":
    import os, json, logging

    logger = logging.getLogger("UserAuth")
    username = "meno_api"
    user_id = "user_001"
    email = "acorona@menoenterprises.com"

    user = UserAuth(
        username=username,
        log=logger,
        user_id=user_id,
        password=password,
        email=email,
    )

    """
    new_password = user.reset_user_password(database="meno_accounts",
        new_password=password)
    print(f"New password: {new_password}")
    """

    user.add_user_to_sql(database="meno_accounts")
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
