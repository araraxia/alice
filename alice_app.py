from email.policy import default
import sys
from flask import Flask, render_template, request, jsonify, send_file, current_app
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from waitress import serve
from werkzeug.middleware.proxy_fix import ProxyFix
from pathlib import Path

from src.user_auth import UserAuth
from src.logger import setup_logger
from src.limiter import limiter
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from src.website.site_router import fort_route
from src.website.wiki_router import wiki_route
from src.discord.discord_router import discord_route
ROUTE_LIST = [
    fort_route,
    wiki_route,
    discord_route,
]

from datetime import timedelta
import os, pickle

BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
DEFAULT_SECRET_FILE = BASE_DIR / "conf" / "cred" / "secret_key.pkl"

class Alice:
    def __init__(self):
        self.app = Flask(
__name__,
            template_folder=TEMPLATE_DIR,
            static_folder=STATIC_DIR,
            )

        self.init_attributes()
        self.init_limiter()
        CSRFProtect(self.app)
        self.init_login_manager()

        # Blueprint registration
        for route in ROUTE_LIST:
            self.app.register_blueprint(route)

        self.set_routes()
        self.app.logger.info("Alice initialized")

    
    def init_attributes(self):
        self.app.wsgi_app = ProxyFix(self.app.wsgi_app, x_for=1, x_proto=1,)
        self.app.secret_key = self.get_secret()
        self.app = setup_logger(self.app)
        self.app.config['VERSION'] = '0.1.0'
        self.app.config['CURRENT_YEAR'] = 2025
        self.app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024  # 64 MB
        self.app.permanent_session_lifetime = timedelta(minutes=90)
        
        self.static_dir = STATIC_DIR
        self.template_dir = TEMPLATE_DIR
        self.favicon_path = os.path.join(STATIC_DIR, "favicon.png")
        
    
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
    
    def init_limiter(self):
        try:
            limiter.init_app(self.app)
            self.app.logger.info("Limiter initialized with Memcached storage")
        except Exception as e:
            self.app.logger.error(f"Error initializing limiter: {e}")
            self.app.logger.error("Attempting failover limiter setup")
            failover_limiter = Limiter(
                key_func=get_remote_address,
                default_limits=["50000 per day", "1000 per hour"],
                storage_uri="memory://",
            )
            failover_limiter.init_app(self.app)
            self.app.logger.info("Failover limiter initialized with in-memory storage")
    def get_secret(self):
        if os.path.exists(DEFAULT_SECRET_FILE):
            with open(DEFAULT_SECRET_FILE, "rb") as f:
                secret = pickle.load(f)
            return secret
        else:
            import secrets
            secret = secrets.token_hex(32)
            os.makedirs(os.path.dirname(DEFAULT_SECRET_FILE), exist_ok=True)
            with open(DEFAULT_SECRET_FILE, "wb") as f:
                pickle.dump(secret, f)
            return secret

    def set_routes(self):
        @self.app.before_request
        def before_request():
            client_ip = (
                request.headers.get("X-Forwarded-For") or
                request.remote_addr
            )
            self.app.logger.debug(f"Request from {client_ip} to {request.path}")
        
        @self.app.route("/", methods=["GET"])
        def index():
            from src.website.index import IndexPage
            index_page = IndexPage(current_app)
            return index_page.display()

        @self.app.route("/health", methods=["GET"])
        def health_check():
            return jsonify({"status": "ok"}), 200
        
        @self.app.route("/debug", methods=["GET"])
        def debug_info():
            info = {
                "remote_addr": request.remote_addr,
                "x_forwarded_for": request.headers.get("X-Forwarded-For"),
                "all_headers": dict(request.headers),
            }
            return jsonify(info), 200
        
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
        
alice = Alice()
app = alice.app
    
if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=6969, threads=4, expose_tracebacks=True)