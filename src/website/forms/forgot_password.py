from flask import render_template, redirect, url_for, flash
from flask_wtf import FlaskForm
from wtforms import StringField, EmailField, SubmitField
from wtforms.validators import DataRequired, Email
from util.sql_helper import init_psql_connection
from util.user_auth import UserAuth
from src.automated_emails import AutomatedEmails
from time import sleep


class ForgotPasswordForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    email = EmailField("Email", validators=[DataRequired(), Email()])
    submit = SubmitField("Reset Password")


class ForgotPassword:
    """
    Class representing the forgot password functionality.
    """

    def __init__(self, app, log):
        self.app = app
        self.log = log

    def render_forgot_password_form(self, form=None):
        """
        Render the forgot password form.
        """
        self.log.debug("Rendering forgot password form")
        if not form:
            form = ForgotPasswordForm()
        return render_template(
            "forms/forgot-password-form.html",
            form=form,
        )

    def reset_forgotten_password(self):
        """
        Process the forgot password form submission.
        """
        self.log.debug("Processing forgot password form submission")
        form = ForgotPasswordForm()

        if form.validate_on_submit():
            self.log.info(f"Resetting password for user {form.username.data}")
            username = form.username.data
            email = form.email.data

            # Create a UserAuth instance to handle user operations
            self.log.debug(f"Creating UserAuth instance for user {username}")
            user = UserAuth(
                log=self.log,
                username=username,
                email=email,
            )

            # Check if the user exists and email matches
            self.log.debug(f"Checking if user exists and email matches")
            conn = init_psql_connection(db="accounts")
            cursor = conn.cursor()
            try:
                if user.user_exists(cursor, conn) and email == user.email:

                    # Reset the user's password
                    new_password = user.reset_user_password(database="accounts")

                    # If the password was reset successfully, send an email notification
                    if new_password:
                        self.log.info(f"Password reset successful for user {username}")
                        subject = "Araxia.xyz Password Reset"
                        body = f"""
Your password has been reset successfully.
Your new password is: {new_password}
Please log in and change your password immediately.
                        """
                        automated_emails = AutomatedEmails()
                        automated_emails.send_email(
                            from_name="Alice No-Reply",
                            to_email=[email],
                            subject=subject,
                            body=body,
                        )
                        self.log.info(f"Password reset email sent to {email}")
                        flash(
                            "Password reset successful. Please check your email for the new password.",
                            "success",
                        )
                        sleep(5)  # Pause to allow user to read the message
                        return redirect(url_for("fort.login"))

                # If the user does not exist or email does not match, display an error
                else:
                    self.log.warning(f"User {username} does not exist")
                    form.username.errors.append(
                        "User does not exist with these credentials. Please check your username and email and try again."
                    )
                    return self.render_forgot_password_form(form)
            finally:
                cursor.close()
                conn.close()

            return redirect(url_for("fort.login"))
        return self.render_forgot_password_form()
