
from flask import (
    render_template,
    request,
    jsonify,
    current_app,
    Blueprint,
    redirect,
    url_for,
    session,
)
from flask_login import login_user, logout_user, login_required, current_user
from flask_limiter import RateLimitExceeded
from flask_limiter.util import get_remote_address

from src.user_auth import UserAuth
from src.limiter import limiter
from src.website.forms.login_page import LoginForm
from src.util.form_helper import clear_form_errors
from src.util.helpers import validate_input

fort_route = Blueprint('fort', __name__, url_prefix='/fort')

def redirect_home(next_page=None):
    """
    Redirect end users to different endpoints depending on their user settings.
    """
    if next_page:
        current_app.logger.debug(f"Redirecting to {next_page} after login")
        return redirect(next_page)
    
    return redirect(url_for('fort.homepage'))

@fort_route.route('/lounge', methods=['GET'])
@login_required
def homepage():
    return jsonify({"message": "Welcome to the lounge!"})

def render_login(form):
    return render_template("login.html", form=form, title="Login")

@fort_route.route('/register', methods=['GET'])
def register():
    return {"status": "success"}, 200
    form = RegistrationForm()
    return render_template("register.html", form=form, title="Register")

@fort_route.route('/login-modal', methods=['GET'])
def login_modal():
    form = LoginForm()
    window_html = render_template("partials/login.html", form=form, title="Login")
    
    # Check if it's an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Return plain HTML for OpenWindow compatibility
        return window_html
    else:
        # Return JSON for other use cases
        return jsonify({"html": window_html})

@fort_route.route('/entrance', methods=['POST'])
def entrance():
    current_app.logger.debug(f"Entrance route accessed {current_user}")
    
    if current_user.is_authenticated:
        return redirect_home(request.args.get("next", None))

    form = LoginForm()
    if form.validate_on_submit():
        try:
            with limiter.limit("10 per 15 minutes"):
                current_app.logger.debug(f"Rate limit check passed.")
        except RateLimitExceeded:
            current_app.logger.warning(
                f"Rate limit exceeded for {get_remote_address()}"
            )
            form.username.errors.append(
                "Rate limit exceeded. Please try again later."
            )
            return render_login(form)

        form = clear_form_errors(form)
        
        try:
            form_user = validate_input(form.username.data)
            form_password = validate_input(form.password.data, expected_type="PASSWORD")
            form_remember = form.remember.data
        except ValueError as e:
            current_app.logger.warning(f"Validation error for {current_user}: {e}")
            form.username.errors.append(
                "Invalid input: " + str(e)
            )
            return render_login(form)
    
        user = UserAuth(
            log=current_app.logger,
            username=form_user,
            password=form_password,
        )
        if user.check_password():
            login_user(user, remember=form_remember)
            session.permanent = True
            next_page = request.args.get("next", None)
            return redirect_home(next_page)

    return render_login(form)

@fort_route.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('fort.login'))