# Flask User Authorization

## Overview

The Flask User Authorization system provides a robust, secure user authentication and management framework built on top of Flask-Login. This implementation handles the complete user lifecycle from registration through authentication, password management, and user settings, while maintaining security best practices through password hashing and token-based API access. The system integrates seamlessly with PostgreSQL for persistent user data storage and provides a clean interface for both web-based login flows and programmatic API access.

## What is Flask User Authorization?

The user authorization system consists of a custom `UserAuth` class that extends Flask-Login's `UserMixin`, providing a complete authentication solution with the following capabilities:

**User Authentication**: Validates user credentials through secure password hashing (SHA256) and maintains session state through Flask-Login's session management. The system distinguishes between registered, active, and authenticated users to enforce proper access controls.

**User Management**: Handles the complete user lifecycle including registration with email verification, account activation, password resets, and user settings management. All operations integrate with PostgreSQL for reliable data persistence.

**API Token Management**: In addition to password-based authentication, the system supports token-based authentication for API access, allowing programmatic interaction with protected endpoints through secure token hashing and validation.

**Session Integration**: Works seamlessly with Flask's session management and Flask-Login's authentication framework to provide "remember me" functionality, login_required decorators, and automatic user object loading from session data.

## Core Authentication Features

### UserAuth Class Architecture

The `UserAuth` class serves as the central authentication entity, initialized with minimal required information:

```python
user = UserAuth(
    log=logger,
    username="example_user",
    password="user_password",
)
```

Upon initialization, the class automatically loads the complete user profile from the database if the user exists, populating attributes including email, password hash, token hash, creation timestamp, role, and active status. This lazy-loading approach keeps authentication checks efficient while ensuring all user data is available when needed.

### Database-Backed User Loading

The `init_user()` method implements intelligent user loading that accepts either username or user_id as the lookup key:

**Username Lookup**: Used during login flows where users provide their username and password. The system queries the database for the username and loads the complete user profile.

**User ID Lookup**: Used when Flask-Login reloads the user object from session data (via the user_loader callback). The user_id serves as the primary key for efficient session-based lookups.

If the user doesn't exist in the database, the method returns None, allowing the calling code to distinguish between existing and non-existent users for appropriate handling.

### Password Security

Password security follows industry best practices through SHA256 hashing:

**Hash Storage**: Raw passwords are never stored. During registration or password reset, the system generates a SHA256 hash of the password and stores only this hash in the database.

**Comparison Validation**: When a user attempts to log in, the provided password is hashed using the same algorithm and compared against the stored hash. This ensures that even database compromise doesn't expose actual passwords.

**Hash Generation**: The password hash is generated on initialization if a password is provided:

```python
self.password_hash = (
    "" 
    if not self.password 
    else hashlib.sha256(self.password.encode()).hexdigest()
)
```

This approach keeps hashing logic centralized and ensures consistent hash generation across all password operations.

### Active User Enforcement

The system distinguishes between registered users and active users through the `is_active` flag:

**Registration State**: Newly registered users exist in the database but have `is_active=False`, preventing login until they complete email verification.

**Activation Process**: After email verification, the `activate_user()` method sets `is_active=True`, enabling login. This two-phase registration prevents automated bot registrations and confirms email ownership.

**Login Validation**: The `check_password()` method validates both password correctness AND active status, raising `UserNotActiveError` if the account hasn't been activated:

```python
if not is_active:
    raise UserNotActiveError(username=self.username, message="Account not activated")
```

This enforcement ensures inactive accounts cannot authenticate even with valid credentials.

## User Management Methods

### User Registration

The `register_user()` method handles new user creation with comprehensive validation and default generation:

**Pre-Registration Validation**: Checks if the user is already active (preventing duplicate registrations) and validates that all required fields are present or can be generated.

**Automatic Generation**: If not provided, the system automatically generates:
- User ID (UUID-based unique identifier)
- API Token (for programmatic access)
- Password (if registering via admin interface)
- Activation Code (for email verification)

**Dual Table Population**: Registration populates both the `auth.users` table (authentication credentials) and the `settings.user_settings` table (user preferences and profile data), ensuring complete user setup in a single operation.

The method returns `self`, allowing method chaining for workflows that need to perform additional operations immediately after registration.

### Account Activation

The `activate_user()` method transitions a registered user to active status:

**Existence Validation**: Verifies the user exists before attempting activation, preventing activation of non-existent accounts.

**Flag Update**: Sets `is_active=True` in the database using `update_existing_record()`, enabling login for the user.

**Status Synchronization**: Updates the instance's `is_active_var` to reflect the new state, ensuring subsequent method calls see the updated status without requiring a database reload.

This separation of registration and activation supports email verification workflows where users must confirm their email before gaining access.

### Password Management

Two methods handle password operations:

**check_password()**: Validates user credentials during login by hashing the provided password and comparing against the stored hash. The method also enforces active status, raising `UserNotActiveError` for inactive accounts even when passwords match.

**reset_user_password()**: Changes a user's password, either to a provided value or a randomly generated strong password. The method:
1. Validates user existence
2. Hashes the new password
3. Updates the database
4. Returns the new password (for admin-initiated resets where users need to receive their new password)

Password resets maintain security by immediately hashing new passwords and never storing plaintext values.

### Token Management

API token operations parallel password operations:

**Token Generation**: The `reset_user_token()` method generates a new random token using `generate_token()`, hashes it with SHA256, and stores the hash in the database.

**Return Value**: Returns the plaintext token to the caller, as this is the only time the unhashed token is available. Users must store this token for API authentication since it cannot be retrieved later (only its hash exists in the database).

Token rotation through password-style hashing ensures API access remains secure even if the database is compromised.

### User Settings Management

Two methods handle user settings:

**get_user_settings()**: Loads user preferences from the `settings.user_settings` table and populates instance attributes like `first_name` and `last_name`. The method returns the complete settings dictionary for workflows that need to access multiple settings simultaneously.

**update_user_setting()**: Updates individual settings by key-value pair, immediately persisting changes to the database and reloading settings to ensure instance synchronization.

This separation allows granular settings updates without requiring full profile edits.

## Security Implementation

### Multi-Layer Validation

The authentication system implements validation at multiple levels:

**Input Validation**: The `entrance` route in [site_router.py](c:/Users/dev/.code/alice/src/website/site_router.py) uses `validate_input()` to sanitize username and password inputs before processing, preventing injection attacks and malformed data.

**Rate Limiting**: Authentication endpoints use Flask-Limiter to enforce "10 per 15 minutes" rate limiting, preventing brute force password attacks. Exceeded limits return graceful error messages without leaking information about valid usernames.

**Existence Checks**: All update operations (password reset, token reset, email update) validate user existence before proceeding, preventing information leakage through error messages that distinguish between invalid credentials and non-existent users.

### Exception Handling

The custom `UserNotActiveError` exception provides detailed context:

```python
class UserNotActiveError(Exception):
    def __init__(self, username=None, user_id=None, message=None):
        if message is None:
            if username:
                message = f"User {username} is not active"
            elif user_id:
                message = f"User with ID {user_id} is not active"
        self.username = username
        self.user_id = user_id
        super().__init__(message)
```

This exception carries both username and user_id context, allowing calling code to log detailed information while returning generic error messages to users.

### Session Security

The system integrates with Flask's session security:

**Permanent Sessions**: The login route sets `session.permanent = True` to respect session lifetime configuration, allowing administrators to control session duration.

**Remember Me**: Supports Flask-Login's "remember me" functionality through `login_user(user, remember=form_remember)`, storing a secure cookie for extended authentication.

**Clean Logout**: The logout route properly calls `logout_user()` to clear session state and invalidate the authentication cookie.

## Database Integration

### Multi-Database Architecture

The authentication system spans multiple database schemas:

**accounts.auth.users**: Stores authentication credentials including password_hash, token_hash, user_id, username, email, role, is_active, and created_at. This table contains security-critical data.

**accounts.settings.user_settings**: Stores user preferences and profile information like first_name, last_name, and other customizable settings. This separation keeps security data isolated from mutable user preferences.

### SQL Helper Integration

All database operations use the `sql_helper` module's methods:

**get_record()**: Retrieves single user records by username or user_id, returning dictionaries of column-value pairs or None if no match exists.

**add_update_record()**: Inserts new users during registration or updates existing records, providing upsert-like functionality.

**update_existing_record()**: Updates specific columns for existing users, used for activation, password resets, token resets, and settings updates.

This abstraction layer centralizes SQL query construction and error handling, keeping the UserAuth class focused on business logic rather than database mechanics.

## Flask-Login Integration

### UserMixin Override Methods

The `UserAuth` class overrides Flask-Login's `UserMixin` methods to customize authentication behavior:

**is_active()**: Returns the `is_active_var` instance variable, allowing Flask-Login to enforce activation status checks on protected routes.

**is_authenticated()**: Returns `True` if password validation succeeds, ensuring only users with correct credentials can access protected resources.

**is_anonymous()**: Returns `False`, as the system doesn't support anonymous user objects.

**get_id()**: Returns `user_id`, which Flask-Login stores in the session and passes to the user_loader callback for user object reconstruction.

These overrides ensure Flask-Login's authentication framework respects the system's activation and authentication requirements.

### Login Manager Integration

The hosting application configures Flask-Login to use UserAuth:

```python
@login_manager.user_loader
def load_user(user_id):
    return UserAuth(log=logger, user_id=user_id)
```

This callback allows Flask-Login to reconstruct user objects from session data, automatically loading the complete user profile for each request to a protected route.

## Technical Implementation

### Class Initialization Flow

The UserAuth initialization follows a deterministic flow:

1. **Store Parameters**: Save logger, credentials, and identifiers to instance variables
2. **Hash Credentials**: Generate password and token hashes if values are provided
3. **Load Database State**: Call `init_user()` to populate instance from database
4. **Load Settings**: Call `get_user_settings()` to fetch user preferences
5. **Log Initialization**: Record successful initialization with key identifiers

This flow ensures the object is fully populated before returning, providing a ready-to-use authentication object without requiring additional loading calls.

### Method Chaining

Several methods return `self` to enable chaining:

```python
user = UserAuth(log=logger, username="new_user").register_user()
```

This pattern simplifies workflows that perform multiple operations on a single user object without requiring intermediate variable storage.

### Error Handling Strategy

The implementation follows a fail-fast approach:

**Explicit Checks**: Methods explicitly validate prerequisites (user exists, password provided, email format) and raise ValueError for violations rather than attempting to proceed with invalid state.

**Informative Exceptions**: Error messages include context about what validation failed, helping developers diagnose issues during development while keeping production error messages generic.

**Database Errors**: Database operations raise psycopg2 exceptions that bubble up to the caller, allowing route handlers to catch and log database errors appropriately.

### Logging Integration

Comprehensive logging tracks authentication operations:

**Initialization Logging**: Records basic user identification when objects are created
**Operation Logging**: Info-level logs for state changes (activation, password reset, token reset)
**Debug Logging**: Detailed information like password hashes (redacted in production) for development troubleshooting
**Warning Logging**: Invalid operations like attempting to activate non-existent users or login attempts for inactive accounts

This multi-level logging provides both audit trails for security events and diagnostic information for troubleshooting.

## Usage Example

The [site_router.py](c:/Users/dev/.code/alice/src/website/site_router.py) demonstrates typical authentication flows:

### Login Flow

```python
user = UserAuth(
    log=current_app.logger,
    username=form_user,
    password=form_password,
)
if user.check_password():
    login_user(user, remember=form_remember)
    session.permanent = True
```

This pattern validates credentials and establishes the user session in a single flow.

### Registration Flow (via RegisterUser handler)

The registration flow typically involves:
1. Create UserAuth object with username, email, and generated password
2. Call `register_user()` to persist to database
3. Send activation email with activation code
4. User clicks link, system calls `activate_user()`
5. User can now log in

## Source Files

- [user_auth.py](c:/Users/dev/.code/alice/hosted_files/showcase/user_auth.py)
- [site_router.py](c:/Users/dev/.code/alice/src/website/site_router.py)

## Future Enhancements

Several improvements could extend the authentication system's capabilities:

- **Multi-Factor Authentication**: Add TOTP support for time-based one-time passwords as a second authentication factor for sensitive accounts.

- **Password Strength Requirements**: Implement configurable password policies enforcing minimum length, complexity requirements, and common password blacklists.

- **Session Management Dashboard**: Provide users with a view of active sessions across devices with the ability to revoke individual sessions.

- **Account Recovery**: Add security-question-based or phone-number-based account recovery for users who lose access to their email.

- **OAuth Integration**: Support authentication through third-party providers (Google, GitHub, Microsoft) while maintaining the existing password-based flow.

- **Audit Log**: Record all authentication events (successful logins, failed attempts, password changes, token resets) in a separate audit table for security analysis.

- **Token Scoping**: Implement multiple API tokens per user with different permission scopes, allowing users to generate read-only tokens or tokens limited to specific endpoints.

- **Password History**: Prevent password reuse by maintaining a history of previous password hashes and validating that new passwords differ from recent values.

- **Bcrypt Migration**: Upgrade from SHA256 to bcrypt or Argon2 for password hashing, providing stronger cryptographic security and built-in salt generation.

- **Account Lockout**: Implement temporary account lockout after repeated failed login attempts to prevent brute force attacks at the user level rather than just IP level.

