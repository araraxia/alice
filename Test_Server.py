#!/usr/bin/env python3

from flask import Flask, request, jsonify, send_file
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from waitress import serve
from werkzeug.middleware.proxy_fix import ProxyFix

from api_v1.router import v1
from discord.discordRouter import discord_route
from preflight.PreflightRouter import preflight_route
from mod.MOD_Router import mod_route
from wiki.wiki_router import wiki_route
from barcodes.barcode_router import barcode_route
from production.production_router import production_route
from portal.internal_portal_router import portal_route

from loggers.Meno_Webhook_Logger import setup_logger
from limiter import limiter
from extras.user_auth import UserAuth

from datetime import timedelta
import os, pickle

template_dir = os.path.abspath("templates")
static_dir = os.path.abspath("static")

class WebhookMenoHelper:
    def __init__(self):
        self.app = Flask(__name__, 
                         template_folder=template_dir,
                         static_folder=static_dir,)
        self.app.wsgi_app = ProxyFix(self.app.wsgi_app, x_for=1, x_proto=1,)
        self.app.secret_key = self.get_secret()
        self.app.config['VERSION'] = '0.1.1'
        self.app = setup_logger(self.app)
        
        self.init_attributes()

        self.login_manager = LoginManager()
        self.login_manager.init_app(self.app)
        self.init_login_manager()
        self.app.permanent_session_lifetime = timedelta(minutes=90)

        limiter.init_app(self.app)
        
        # Route blueprint registration
        self.app.register_blueprint(v1)
        self.app.register_blueprint(discord_route)
        self.app.register_blueprint(preflight_route)
        self.app.register_blueprint(wiki_route)
        self.app.register_blueprint(mod_route)
        self.app.register_blueprint(barcode_route)
        self.app.register_blueprint(production_route)
        self.app.register_blueprint(portal_route)

        self.set_routes()
        self.app.logger.info("Meno Helper Webhook Server initialized")

    def init_login_manager(self):
        self.login_manager.login_view = "internal_portal.login"
        self.login_manager.session_protection = "strong"
        
        @self.login_manager.user_loader
        def load_user(user_id):
            user = UserAuth(log=self.app.logger, user_id=user_id,)
            return user

    def get_secret(self):
        secret_file = "cred/secret_key.pkl"
        if os.path.exists(secret_file):
            with open(secret_file, "rb") as f:
                secret = pickle.load(f)
            return secret

    def init_attributes(self):
        self.favicon_path = os.path.join(static_dir, "favicon.webp")
        pass

    def set_routes(self):
        @self.app.before_request
        def log_request_info():
            forwarded_for = request.headers.getlist("X-Forwarded-For", None)
            forwarded_for = forwarded_for[0] if forwarded_for else request.remote_addr
            self.app.logger.debug(
                f"{forwarded_for} - {request.method} : {request.full_path}"
            )

        @self.app.route("/")
        def index():
            return "Meno Helper Webhook Server, 200 OK"

        @self.app.route("/version", methods=["GET"])
        def version():
            return jsonify({"version": "1.0.0"}), 200

        @self.app.route("/test", methods=["POST"])
        def test():
            data = request.json  # Get JSON payload
            return jsonify({"status": "success"}), 200  # Respond to sender

        @self.app.route("/favicon.ico")
        def favicon():
            return send_file(self.favicon_path, mimetype="image/webp")
            

if __name__ == "__main__":
    print("Test_Server.py - Starting Meno Helper Webhook Server")
    MenoBot = WebhookMenoHelper()
    serve(MenoBot.app, host="0.0.0.0", port=5570, threads=100)
