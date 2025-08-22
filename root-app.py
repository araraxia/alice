from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from flask_login import LoginManager
from waitress import serve
from werkzeug.middleware.proxy_fix import ProxyFix

from src.user_auth import UserAuth
from src.logger import setup_logger
from src.limiter import limiter

from src.website.site_router import fort_route
from src.website.wiki_router import wiki_route
route_list = [
    fort_route,
    wiki_route,
]

from datetime import timedelta
import os, pickle

template_dir = os.path.join(os.path.dirname(__file__), "templates")
static_dir = os.path.join(os.path.dirname(__file__), "static")

class Alice:
    def __init__(self):
        self.app = Flask(
__name__,
            template_folder=template_dir,
            static_folder=static_dir,
            )

        self.init_attributes()
        limiter.init_app(self.app)
        self.init_login_manager()

        # Blueprint registration
        for route in route_list:
            self.app.register_blueprint(route)

        self.set_routes()
        self.app.logger.info("Alice initialized")

    
    def init_attributes(self):
        self.app.wsgi_app = ProxyFix(self.app.wsgi_app, x_for=1, x_proto=1,)
        self.app.secret_key = self.get_secret()
        self.app = setup_logger(self.app)
        self.app.config['VERSION'] = '0.1.0'
        self.app.config['CURRENT_YEAR'] = 2025
        self.app.permanent_session_lifetime = timedelta(minutes=90)
        
        self.static_dir = static_dir
        self.template_dir = template_dir
        self.favicon_path = os.path.join(static_dir, "favicon.ico")
        
    
    def init_login_manager(self):
        login_manager = LoginManager()
        login_manager.init_app(self.app)
        login_manager.login_view = "fort.login"
        login_manager.session_protection = "strong"
        login_manager.remember_cookie_duration = timedelta(days=7)
        self.login_manager = login_manager
        
        @self.login_manager.user_loader
        def load_user(user_id):
            return UserAuth(log=self.app.logger, user_id=user_id)
    
    def get_secret(self):
        secret_file = "cred/secret_key.pkl"
        if os.path.exists(secret_file):
            with open(secret_file, "rb") as f:
                secret = pickle.load(f)
            return secret

    def set_routes(self):
        @self.app.before_request
        def before_request():
            client_ip = (
                request.headers.get("X-Forwarded-For") or
                request.remote_addr
            )
            self.app.logger.debug(f"Request from {client_ip}")
        
        @self.app.route("/", methods=["GET"])
        def index():
            return redirect(url_for("fort.homepage"))

        @self.app.route("/health", methods=["GET"])
        def health_check():
            return jsonify({"status": "ok"}), 200
        
        @self.app.errorhandler(404)
        def not_found_error(e):
            return render_template("404.html"), 404
        
        @self.app.errorhandler(500)
        def internal_error(e):
            self.app.logger.error(f"Internal server error: {e}")
            return render_template("500.html"), 500
        
        @self.app.route("/favicon.ico")
        def favicon():
            return send_file(self.favicon_path, mimetype="image/webp")
        
if __name__ == "__main__":
    alice = Alice()
    serve(alice.app, host="0.0.0.0", port=6969, threads=4, expose_tracebacks=True)