from flask import (
    render_template,
    request,
    jsonify,
    current_app,
    Blueprint,
    redirect,
    url_for,
)

from flask_login import current_user

osrs_route = Blueprint("osrs", __name__, url_prefix="/osrs")


@osrs_route.route("/", methods=["GET"])
def index():
    page_html = render_template("osrs/index.html")
    return jsonify({"status": "success", "html": page_html})


@osrs_route.route("/calc", methods=["GET"])
def calc():
    from src.osrs.osrs_calcs import OSRSCalcsHandler

    calc_handler = OSRSCalcsHandler(current_app)
    page_html = calc_handler.render_index()
    return jsonify({"status": "success", "html": page_html})


@osrs_route.route("/super-combats", methods=["GET"])
def super_combats():
    from src.osrs.calcs.super_combats import SuperCombats

    sc = SuperCombats()
    page_html = sc.display()
    return jsonify({"status": "success", "html": page_html})


@osrs_route.route("/goading-regens", methods=["GET"])
def goading_regens():
    from src.osrs.calcs.goading_regens import GoadingRegens

    gr = GoadingRegens()
    page_html = gr.display()
    return jsonify({"status": "success", "html": page_html})
