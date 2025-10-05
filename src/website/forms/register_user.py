from flask import render_template, redirect, url_for, flash
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


class RegisterCustomerForm(FlaskForm):
    first_name = StringField("First Name", validators=[DataRequired(), Length(max=50)])
    last_name = StringField("Last Name", validators=[DataRequired(), Length(max=50)])
    username = StringField(
        "Username", validators=[DataRequired(), Length(min=5, max=32)]
    )
    password1 = PasswordField("Password", validators=[DataRequired(), Length(min=12)])
    password2 = PasswordField(
        "Confirm Password",
        validators=[
            DataRequired(),
            Length(min=12),
            EqualTo("password1", message="Passwords must match."),
        ],
    )
    email = EmailField("Email", validators=[DataRequired(), Email()])
    company_code = StringField("Company Code", validators=[DataRequired()])
    submit = SubmitField("Register Customer")


class ValidateCustomerRegistrationForm(FlaskForm):
    secret_code = StringField(
        "Secret Code", validators=[DataRequired(), Length(min=6, max=6)]
    )
    submit = SubmitField("Validate Registration")


class RegisterCustomer:
    def __init__(self, app, log):
        self.app = app
        self.log = log

    def render_register_customer_form(self, form=None):
        """
        Render the register customer form.
        """
        self.log.debug("Rendering register customer form")
        if not form:
            form = RegisterCustomerForm()
        return render_template(
            "internal_portal/forms/register-customer-form.html",
            form=form,
        )

    def process_register_customer(self):
        """
        Process the register customer form submission.
        """
        self.log.debug("Processing register customer form submission")
        form = RegisterCustomerForm()
        if form.validate_on_submit():
            self.log.info(f"Registering new customer {form.username.data}")
            form = clear_form_errors(form)  # Clear any previous errors

            username = form.username.data
            password1 = form.password1.data
            password2 = form.password2.data
            email = form.email.data
            first_name = form.first_name.data
            last_name = form.last_name.data
            company_code = form.company_code.data

            ##### Validate all inputs
            for field in [
                username,
                password1,
                password2,
                email,
                first_name,
                last_name,
                company_code,
            ]:
                if field:
                    continue
                self.log.error(f"{field} is required.")
                form.username.errors.append(f"{field} is required.")
                return self.render_register_customer_form(form)

            # Check if passwords match
            if not password1 == password2:
                self.log.error("Passwords do not match.")
                form.password2.errors.append("Passwords must match.")
                return self.render_register_customer_form(form)

            # Validate input values
            try:
                username = validate_input(username)
                password = validate_input(password1, "PASSWORD")
            except ValueError as e:
                self.log.error(f"Input validation failed: {e}")
                form.username.errors.append(str(e))
                return self.render_register_customer_form(form)

            # Initialize UserAuth instance
            user = UserAuth(
                log=self.log,
                username=username,
                password=password,
                email=email,
                user_id=username,
                role="customer-role",
                company_code=company_code,
            )

            # Check if user already exists
            conn = init_psql_connection(db="meno_accounts")
            cursor = conn.cursor()
            try:
                if user.user_exists(cursor, conn):
                    self.log.error(f"User {username} already exists.")
                    form.username.errors.append("Username already exists.")
                    return self.render_register_customer_form(form)
            finally:
                cursor.close()
                conn.close()

            # Check if company code exists
            customer_records = get_record(
                database="meno_db",
                schema="Meno",
                table="Customers",
                column="Customer ID",
                value=company_code,
            )
            if not customer_records:
                self.log.error(f"Company code {company_code} does not exist.")
                form.company_code.errors.append("Invalid company code.")
                return self.render_register_customer_form(form)

            ##### Create a temp user
            try:
                self.log.debug("Creating new user in the database")
                user.add_user_to_holding()
                columns = [
                    "user_id",
                    "first_name",
                    "last_name",
                    "company_code",
                ]
                values = [
                    user.user_id,
                    first_name,
                    last_name,
                    company_code,
                ]
                add_update_record(
                    database="meno_accounts",
                    schema="accounts",
                    table="settings_holding",
                    columns=columns,
                    values=values,
                    conflict_target=["user_id"],
                )
            except Exception as e:
                self.log.error(f"Error creating user: {e}")
                form.submit.errors.append(
                    "Error creating user. Please try again later. If the problem persists, contact support."
                )
                return self.render_register_customer_form(form)

            # Generate a secret code for verification, store it in the database
            secret_code = generate_password(length=6)
            try:
                add_update_record(
                    database="meno_accounts",
                    schema="auth",
                    table="registration_code",
                    columns=["username", "verification_code"],
                    values=[username, secret_code],
                    conflict_target=["username"],
                )
            except Exception as e:
                self.log.error(f"Error creating verification code: {e}")
                form.submit.errors.append(
                    "Error updating verification code. Please try again later."
                )
                return self.render_register_customer_form(form)

            # Send verification email
            automated_emails = AutomatedEmails()
            subject = "Meno Portal Customer Registration"
            body = f"""
Welcome {first_name},
Thank you for registering as a customer on the Meno Portal.
Your verification code is: {secret_code}
You can validate at the following link:
{url_for('internal_portal.validate_customer_registration', _external=True)}
"""
            automated_emails.email_from_memory(
                from_name="Meno No-Reply",
                from_email="no-reply@menoenterprises.com",
                to_email=[email],
                subject=subject,
                body=body,
            )

            # Log the sending of the verification email
            self.log.info(f"Sent verification email to {email}")
            return redirect(url_for("internal_portal.validate_customer_registration"))
        return self.render_register_customer_form(form)

    def render_validate_registration_form(self, form=None):
        """
        Render the validate registration form.
        """
        self.log.debug("Rendering validate registration form")
        if not form:
            form = ValidateCustomerRegistrationForm()
        return render_template(
            "internal_portal/forms/validate-registration-form.html",
            form=form,
        )

    def process_validate_registration(self):
        validation_form = ValidateCustomerRegistrationForm()
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
                database="meno_accounts",
                schema="auth",
                table="registration_code",
                column="verification_code",
                value=secret_code,
            )

            if not record:
                self.log.warning("Invalid secret code.")
                validation_form.secret_code.errors.append("Invalid secret code.")
                return self.render_validate_registration_form(validation_form)

            username = record.get("username")
            if not username:
                self.log.warning("Username not found for the provided secret code.")
                validation_form.secret_code.errors.append(
                    "Username not found for the provided secret code."
                )
                return self.render_validate_registration_form(validation_form)

            # Retrieve held records
            account_record = get_record(
                database="meno_accounts",
                schema="accounts",
                table="settings_holding",
                column="user_id",
                value=username,
            )
            auth_record = get_record(
                database="meno_accounts",
                schema="auth",
                table="users_holding",
                column="username",
                value=username,
            )

            # Parse records back into lists
            account_columns, account_values = [], []
            for column, value in account_record.items():
                account_columns.append(column)
                account_values.append(value)

            auth_columns, auth_values = [], []
            for column, value in auth_record.items():
                auth_columns.append(column)
                auth_values.append(value)

            # Update records to active tables
            try:
                add_update_record(
                    database="meno_accounts",
                    schema="accounts",
                    table="settings",
                    columns=account_columns,
                    values=account_values,
                    conflict_target=["user_id"],
                )
            except Exception as e:
                self.log.error(f"Error updating account record: {e}")
                validation_form.secret_code.errors.append(
                    "Error updating account record. Please try again later."
                )
                return self.render_validate_registration_form(validation_form)

            # Update auth record
            try:
                add_update_record(
                    database="meno_accounts",
                    schema="auth",
                    table="users",
                    columns=auth_columns,
                    values=auth_values,
                    conflict_target=["user_id"],
                )
            except Exception as e:
                self.log.error(f"Error updating auth record: {e}")
                validation_form.secret_code.errors.append(
                    "Error updating auth record. Please try again later."
                )
                return self.render_validate_registration_form(validation_form)

            # If everything is successful, log the user validation and redirect to login
            self.log.info(f"User {username} validated successfully.")
            flash("Success", "success")
            sleep(5)
            return redirect(url_for("internal_portal.login"))

        self.log.warning("Validation failed.")
        validation_form.secret_code.errors.append("Invalid secret code.")
        return self.render_validate_registration_form(validation_form)