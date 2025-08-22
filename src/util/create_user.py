
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from extras.sql_helper import update_record
from extras.helpers import (
    generate_token,
    generate_password,
    hash_string,
)

def create_user(username,
                email,
                password: str=None,
                token: str=None,
                role: str="user-role",
                is_active: bool=True,
                ) -> dict:
    """
    Create a new user in the system. Adds to meno_accounts.auth.users
    
    Args:
        username (str) : The username for the new user.
        email (str) : The email address for the new user.
        password (str: optional) : The password for the new user. Generates a random password if not provided.
        role (str: optional) : The role of the new user. Default is "user-role".
        is_active (bool: optional) : Whether the user account is active. Default is True.
    
    Returns:
        dict: A dictionary containing the status and message of the operation.
    """
    if not password or len(password) < 8:
        password = generate_password(length=12)
    password_hash = hash_string(password)
    if not token:
        token = generate_token()
    token_hash = hash_string(token)
    user_id = username.lower()
    
    columns = [
        "user_id",
        "username",
        "email",
        "password_hash",
        "token_hash",
        "role",
        "is_active",
        ]
    values = [
        user_id,
        username,
        email,
        password_hash,
        token_hash,
        role,
        is_active,
    ]
    
    try:
        # Add or update the user record in the database
        update_record(
            database="meno_accounts",
            schema="auth",
            table="users",
            columns=columns,
            values=values,
            on_conflict=["username"],
        )
        return {
            "user_id": user_id,
            "username": username,
            "email": email,
            "password": password,
            "token": token,
            "role": role,
            "is_active": is_active,
            "status": "success",
        }
    
    except Exception as e:
        print(e)
        return {
            "username": username,
            "email": email,
            "status": "error",
            "message": str(e)
            }
    
if __name__ == "__main__":
    # Example usage
    print(create_user(
        username="web-bot",
        password="!1|b;tB=v32G",
        email="no-reply@menoenterprises.com",
        token="7BVFQLmBnf3wMo9fq0t6G6rHjil9EjDVXhsvBy4HhbQ"
    ))