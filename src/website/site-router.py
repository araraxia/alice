
from flask import (Flask,
                   request,
                   jsonify,
                   current_app,
                   Blueprint,
                   redirect,
                   url_for,
                   session,
                   )
from flask_login import login_user, logout_user, login_required, current_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from src.user_auth import UserAuth
from src.website.forms.login_form import LoginForm

fort_route = Blueprint('fort', __name__, url_prefix='/fort')
app = current_app
log = app.logger

@fort_route.route('/lounge', methods=['GET'])
@login_required
def lounge():
    return jsonify({"message": "Welcome to the lounge!"})

@fort_route.route('/entrance', methods=['POST'])
def entrance():
    log.debug(f"Entrance route accessed {current_user}")
    
    if current_user.is_authenticated:
        log.debug(f"User {current_user.username} is already logged in.")
        next_url = request.args.get('next', None)
        if next_url:
            return redirect(next_url)
        return redirect(url_for('fort.lounge'))
    
    form = LoginForm()
    
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if username == 'admin' and password == 'secret':
        user = UserAuth(username)
        login_user(user)
        return jsonify({"message": "Logged in successfully!"}), 200
    else:
        return jsonify({"message": "Invalid credentials"}), 401
