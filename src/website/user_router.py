
from flask import current_app, request
from flask_login import current_user, login_required

def set_routes(blueprint):
    
    @blueprint.route("/reset-password", methods=["GET", "POST"])
    @login_required
    def reset_password():
        current_app.logger.debug(f"Rendering reset password page for {current_user.username}")
        from website.dashboards.settings import UserSettings
        user_settings = UserSettings(current_user, current_app)
        if request.method == "POST":
            current_app.logger.info("Processing reset password form submission")
            return user_settings.reset_user_password()
        return user_settings.render_reset_password_form()
    
    
    @blueprint.route("/update-email", methods=["GET", "POST"])
    @login_required
    def update_email():
        current_app.logger.debug(f"Rendering update email page for {current_user.username}")
        from website.dashboards.settings import UserSettings
        user_settings = UserSettings(current_user, current_app)
        if request.method == "POST":
            current_app.logger.info("Processing update email form submission")
            return user_settings.update_user_email()
        return user_settings.render_update_email_form()
    
    
    @blueprint.route("/reset-token", methods=["GET", "POST"])
    @login_required
    def reset_token():
        current_app.logger.debug(f"Rendering reset token page for {current_user.username}")
        from website.dashboards.settings import UserSettings
        user_settings = UserSettings(current_user, current_app)
        if request.method == "POST":
            current_app.logger.info("Processing reset token form submission")
            return user_settings.reset_user_token()
        return user_settings.render_reset_token_form()
    
    
    @blueprint.route("/forgot-password", methods=["GET", "POST"])
    def forgot_password():
        current_app.logger.debug(f"Rendering forgot password page")
        from website.forms.forgot_password import ForgotPassword
        forgot_password = ForgotPassword(current_app, current_app.logger)
        if request.method == "POST":
            current_app.logger.info("Processing forgot password form submission")
            return forgot_password.reset_forgotten_password()
        return forgot_password.render_forgot_password_form()


    @blueprint.route("/user-settings", methods=["GET"])
    @login_required
    def user_settings():
        current_app.logger.debug(f"Rendering user settings for {current_user.username}")
        from website.dashboards.settings import UserSettings
        user_settings = UserSettings(current_user, current_app)
        return user_settings.render_user_settings()