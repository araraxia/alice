from flask import render_template, jsonify, current_app, Blueprint

from src.website.forms.minecraft_register import MinecraftRegistration

minecraft_route = Blueprint("minecraft", __name__, url_prefix="/minecraft")


@minecraft_route.route("/", methods=["GET"])
def index():
    page_html = render_template("minecraft/index.html")
    return jsonify({"status": "success", "html": page_html})


@minecraft_route.route("/register", methods=["GET"])
def register_modal():
    registration = MinecraftRegistration(current_app.logger)
    return jsonify({"status": "success", "html": registration.render_form()})


@minecraft_route.route("/register", methods=["POST"])
def register_submit():
    registration = MinecraftRegistration(current_app.logger)
    return registration.process_registration()
