from flask import jsonify, render_template, redirect, url_for
from flask_wtf import FlaskForm
from wtforms import StringField, EmailField, SubmitField, PasswordField
from wtforms.validators import DataRequired, Email, Length, EqualTo
from flask_limiter.util import get_remote_address
from flask_limiter import RateLimitExceeded
from src.util.sql_helper import get_record
from src.user_auth import UserAuth
from src.util.helpers import validate_input
from src.util.form_helper import clear_form_errors
from src.automated_emails import AutomatedEmails
from src.limiter import limiter


class RegisterUserForm(FlaskForm):
    first_name = StringField(
        "First Name",
        validators=[DataRequired(), Length(max=50)],
        render_kw={"placeholder": "Enter your first name"},
    )
    last_name = StringField(
        "Last Name",
        validators=[DataRequired(), Length(max=50)],
        render_kw={"placeholder": "Enter your last name"},
    )
    username = StringField(
        "Username",
        validators=[DataRequired(), Length(min=2, max=32)],
        render_kw={"placeholder": "Choose a username"},
    )
    password1 = PasswordField(
        "Password",
        validators=[DataRequired(), Length(min=12, max=50)],
        render_kw={"placeholder": "Enter a secure password (min 12 characters)"},
    )
    password2 = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(),
            Length(min=12),
            EqualTo("password1", message="Passwords must match."),
        ],
        render_kw={"placeholder": "Re-enter your password"},
    )
    email = EmailField(
        "Email",
        validators=[DataRequired(), Email()],
        render_kw={"placeholder": "Enter your email address"},
    )
    submit = SubmitField("Register User")


class ValidateRegistration(FlaskForm):
    secret_code = StringField(
        "Secret Code", validators=[DataRequired(), Length(min=6, max=6)]
    )
    submit = SubmitField("Validate Registration")


class RegisterUser:
    def __init__(self, app, log):
        self.app = app
        self.log = log

    def render_registration_form(self, form=None):
        """
        Render the registration form.
        """
        self.log.debug("Rendering registration form")
        if not form:
            form = RegisterUserForm()

        reg_window_html = render_template(
            "partials/register_user.html",
            form=form,
            title="Register User",
        )
        return jsonify({"status": "success", "html": reg_window_html})

    def process_registration(self):
        """
        Process the registration form submission.
        """
        self.log.debug("Processing registration form submission")
        form = RegisterUserForm()
        if form.validate_on_submit():
            self.log.info(f"Registering new customer {form.username.data}")
            form = clear_form_errors(form)  # Clear any previous errors

            username = form.username.data
            password1 = form.password1.data
            password2 = form.password2.data
            email = form.email.data
            first_name = form.first_name.data
            last_name = form.last_name.data

            ##### Validate all inputs
            for field in [
                username,
                password1,
                password2,
                email,
                first_name,
                last_name,
            ]:
                if field:
                    continue
                self.log.warning(f"{field} is required.")
                return jsonify({"status": "error", "message": f"{field} is required."})

            # Check if passwords match
            if not password1 == password2:
                self.log.warning("Passwords do not match.")
                return jsonify({"status": "error", "message": "Passwords must match."})

            # Validate input values
            try:
                username = validate_input(username)
                password = validate_input(password1, "PASSWORD")
            except ValueError as e:
                self.log.warning(f"Input validation failed: {e}")
                return jsonify({"status": "error", "message": str(e)})

            # Initialize UserAuth instance
            user = UserAuth(
                log=self.log,
                username=username,
                password=password,
                email=email,
                role="user-role",
            )
            user.first_name = first_name
            user.last_name = last_name

            # Add user to sql
            try:
                user.register_user()
            except ValueError as e:
                self.log.warning(f"User registration failed: {e}")
                return jsonify({"status": "error", "message": str(e)})

            # Send verification email
            automated_emails = AutomatedEmails()
            subject = "Araxia.xyz Account Registration"
            body = f"""
Welcome {first_name},
Thank you for registering as a user on the Araxia.xyz platform.
Your verification code is: {user.activation_code}
You can validate at the following link:
{url_for('fort.validate_user_registration', user_uuid=user.user_id, activation_code=user.activation_code, _external=True)}
"""
            try:
                automated_emails.send_email(
                    from_name="Alice",
                    to_email=[email],
                    bcc_email=["alice@araxia.xyz"],
                    subject=subject,
                    body=body,
                )
                self.log.info(f"Sent verification email to {email}")
            except Exception as e:
                self.log.error(f"Failed to send verification email to {email}: {e}")
                # Don't fail registration if email fails - log the activation link instead
                activation_url = url_for('fort.validate_user_registration', user_uuid=user.user_id, activation_code=user.activation_code, _external=True)
                self.log.warning(f"Email send failed. Activation link for {username}: {activation_url}")

            return jsonify(
                {
                    "status": "success",
                    "message": "Registration successful! Please check your email to validate your account.",
                }
            )
        return self.render_registration_form(form)

    def render_validate_registration_form(self, form=None):
        """
        Render the validate registration form.
        """
        self.log.debug("Rendering validate registration form")
        if not form:
            form = ValidateRegistration()
        return render_template(
            "internal_portal/forms/validate-registration-form.html",
            form=form,
        )

    def process_validate_registration(self, user_uuid, activation_code):
        """
        Validates and activates a user registration.
        Args:
            user_uuid: The user's UUID (user_id)
            activation_code: The activation code sent to the user
        Returns:
            Response with success or error status
        """
        self.log.info(f"Validating registration for user_id: {user_uuid}")

        # Get user record by user_id
        record = get_record(
            database="accounts",
            schema="auth",
            table="users",
            column="user_id",
            value=user_uuid,
        )

        if not record:
            self.log.warning(f"User not found for user_id: {user_uuid}")
            return (
                jsonify({"status": "error", "message": "Invalid activation link."}),
                404,
            )

        # Check if user is already active
        if record.get("is_active", False):
            self.log.warning(f"User {user_uuid} is already activated.")
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "This account has already been activated.",
                    }
                ),
                400,
            )

        # Verify activation code matches
        stored_activation_code = record.get("activation_code") or record.get(
            "secret_code"
        )
        if stored_activation_code != activation_code:
            self.log.warning(f"Invalid activation code for user {user_uuid}")
            return (
                jsonify({"status": "error", "message": "Invalid activation code."}),
                400,
            )

        username = record.get("username")
        email = record.get("email")

        if not username or not email:
            self.log.error(f"Missing username or email for user {user_uuid}")
            return jsonify({"status": "error", "message": "User data incomplete."}), 500

        # Activate the user
        try:
            user = UserAuth(
                log=self.log,
                username=username,
                user_id=user_uuid,
            )
            user.activate_user()
        except Exception as e:
            self.log.error(f"Failed to activate user {user_uuid}: {e}")
            return (
                jsonify({"status": "error", "message": "Failed to activate account."}),
                500,
            )

        # Get user settings for personalized email
        user_settings = get_record(
            database="accounts",
            schema="settings",
            table="user_settings",
            column="user_id",
            value=user_uuid,
        )
        first_name = user_settings.get("first_name") if user_settings else "User"

        # Send confirmation email
        automated_emails = AutomatedEmails()
        subject = "Araxia.xyz Registration Confirmation"
        body = f"""
Thank you for validating your account, {first_name},
Your account has been successfully activated. You can now log in to Araxia.xyz.
"""
        try:
            automated_emails.send_email(
                from_name="Alice",
                from_email="alice@araxia.xyz",
                to_email=[email],
                subject=subject,
                body=body,
            )
        except Exception as e:
            self.log.error(f"Failed to send confirmation email to {email}: {e}")
            # Don't fail the activation if email fails

        self.log.info(f"User {username} (ID: {user_uuid}) activated successfully.")
        return (
            jsonify(
                {
                    "status": "success",
                    "message": f"Account activated successfully! Welcome, {first_name}! You can now log in.",
                }
            ),
            200,
        )
