import uuid
from flask import jsonify, render_template, redirect, url_for, flash
from flask_wtf import FlaskForm
from wtforms import StringField, EmailField, SubmitField, PasswordField
from wtforms.validators import DataRequired, Email, Length, EqualTo
from flask_limiter.util import get_remote_address
from flask_limiter import RateLimitExceeded
from src.util.sql_helper import get_record, add_update_record, init_psql_connection
from src.user_auth import UserAuth
from src.util.helpers import generate_password, validate_input
from src.util.form_helper import clear_form_errors
from src.automated_emails import AutomatedEmails
from time import sleep
from limiter import limiter


class RegisterUserForm(FlaskForm):
    first_name = StringField("First Name", validators=[DataRequired(), Length(max=50)])
    last_name = StringField("Last Name", validators=[DataRequired(), Length(max=50)])
    username = StringField(
        "Username", validators=[DataRequired(), Length(min=2, max=32)]
    )
    password1 = PasswordField("Password", validators=[DataRequired(), Length(min=12, max=50)])
    password2 = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(),
            Length(min=12),
            EqualTo("password1", message="Passwords must match."),
        ],
    )
    email = EmailField("Email", validators=[DataRequired(), Email()])
    submit = SubmitField("Register Customer")


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
            title="Register Customer",
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
            user_uuid = str(uuid.uuid4())
            user = UserAuth(
                log=self.log,
                username=username,
                password=password,
                email=email,
                user_id=user_uuid,
                role="user-role",
            )

            # Check if user already exists
            conn = init_psql_connection(db="accounts")
            cursor = conn.cursor()
            try:
                if user.user_exists(cursor, conn):
                    self.log.error(f"User {username} already exists.")
                    return jsonify({"status": "error", "message": "Username already exists."})
            finally:
                cursor.close()
                conn.close()

            user.first_name = first_name
            user.last_name = last_name
            # Generate a secret code for verification, store it in the database
            secret_code = generate_password(length=6)
            user.secret_code = secret_code

            # Add user to sql
            user.add_user_to_sql()

            # Send verification email
            automated_emails = AutomatedEmails()
            subject = "Araxia.xyz Account Registration"
            body = f"""
Welcome {first_name},
Thank you for registering as a user on the Araxia.xyz platform.
Your verification code is: {secret_code}
You can validate at the following link:
{url_for('fort.validate_registration', _external=True)}
"""
            automated_emails.send_email(
                from_name="Alice",
                from_email="alice@araxia.xyz",
                to_email=[email],
                subject=subject,
                body=body,
            )

            # Log the sending of the verification email
            self.log.info(f"Sent verification email to {email}")
            return redirect(url_for("fort.validate_registration"))
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

    def process_validate_registration(self):
        validation_form = ValidateRegistration()
        if validation_form.validate_on_submit():
            validation_form = clear_form_errors(
                validation_form
            )  # Clear any previous errors

            try:
                with limiter.limit("10 per 15 minutes"):
                    self.log.debug("Rate limit check passed, processing login.")
            except RateLimitExceeded:
                self.log.warning(
                    f"Rate limit exceeded for {get_remote_address()}."
                )
                validation_form.secret_code.errors.append(
                    "Too many login attempts. Please try again later."
                )
                return self.render_validate_registration_form(validation_form)

            self.log.info(
                f"Validating registration with code {validation_form.secret_code.data}"
            )
            secret_code = validation_form.secret_code.data

            # Check if the secret code is valid
            record = get_record(
                database="accounts",
                schema="auth",
                table="users",
                column="secret_code",
                value=secret_code,
            )

            if not record:
                self.log.warning("Invalid secret code.")
                validation_form.secret_code.errors.append("Invalid secret code.")
                return self.render_validate_registration_form(validation_form)

            username = record.get("username")
            user_id = record.get("user_id")
            if not username:
                self.log.warning("Username not found for the provided secret code.")
                validation_form.secret_code.errors.append(
                    "Username not found for the provided secret code."
                )
                return self.render_validate_registration_form(validation_form)

            user_settings = get_record(
                database="accounts",
                schema="settings",
                table="user_settings",
                column="user_id",
                value=user_id,
            )

            first_name = user_settings.get("first_name") if user_settings else "User"
            email = record.get("email")
            if not email:
                self.log.warning("Email not found for the provided secret code.")
                validation_form.secret_code.errors.append(
                    "Email not found for the provided secret code."
                )
                return self.render_validate_registration_form(validation_form)
            
            # Send verification email
            automated_emails = AutomatedEmails()
            subject = "Araxia.xyz Registration Confirmation"
            body = f"""
Thank you for validating your account, {first_name},
Your account has been successfully validated. You can now log in and do something.
"""
            automated_emails.send_email(
                from_name="Alice",
                from_email="alice@araxia.xyz",
                to_email=[email],
                subject=subject,
                body=body,
            )

            # If everything is successful, log the user validation and redirect to login
            self.log.info(f"User {username} validated successfully.")
            return redirect(url_for("fort.entrance"))

        self.log.warning("Validation failed.")
        validation_form.secret_code.errors.append("Invalid secret code.")
        return self.render_validate_registration_form(validation_form)