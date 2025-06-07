from flask import Flask, request, jsonify
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from waitress import serve
from werkzeug.middleware.proxy_fix import ProxyFix

from src.user_auth import UserAuth
from src.logger import setup_logger
from src.limiter import limiter

from datetime import timedelta
import os, pickle

template_dir = os.path.join(os.path.dirname(__file__), "templates")
static_dir = os.path.join(os.path.dirname(__file__), "static")

class Alice:
    def __init__(self):
        self.app = Flask(__name__,
                        template_folder=template_dir,
                        static_folder=static_dir,)

        self.app.wsgi_app = ProxyFix(self.app.wsgi_app, x_for=1, x_proto=1,)
        self.app.secret_key = self.get_secret()
        self.app = setup_logger(self.app)
        
        limiter.init_app(self.app)

        self.set_routes()
        self.app.logger.info("Alice initialized")

    def get_secret(self):
        secret_file = "cred/secret_key.pkl"
        if os.path.exists(secret_file):
            with open(secret_file, "rb") as f:
                secret = pickle.load(f)
            return secret

    def set_routes(self):
        @self.app.route("/", methods=["GET"])
        def index():
                return "Welcome to Alice!"
        
        @self.app.route("/health", methods=["GET"])
        def health_check():
            return jsonify({"status": "ok"}), 200
        