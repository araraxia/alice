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


@osrs_route.route("/item-search", methods=["GET"])
def item_search():
    from src.osrs.item_search import ItemSearch

    item_search_handler = ItemSearch()
    page_html = item_search_handler.display()
    return jsonify({"status": "success", "html": page_html})


@osrs_route.route("/item-search/search", methods=["POST"])
def item_search_query():
    from src.osrs.item_search import ItemSearch

    item_search_handler = ItemSearch()
    data = request.get_json()

    if not data:
        return jsonify({"status": "error", "message": "No search data provided"}), 400

    search_type = data.get("search_type")
    search_value = data.get("search_value")

    if not search_type or not search_value:
        return jsonify({"status": "error", "message": "Missing search parameters"}), 400

    try:
        if search_type == "id":
            try:
                item_id = int(search_value)
                result = item_search_handler.search_by_id(item_id)
                if result:
                    return jsonify({"status": "success", "items": [dict(result)]})
                else:
                    return jsonify({"status": "success", "items": []})
            except ValueError:
                return jsonify({"status": "error", "message": "Invalid item ID"}), 400
        elif search_type == "name":
            results = item_search_handler.search_by_name(search_value)
            items = [dict(item) for item in results] if results else []
            return jsonify({"status": "success", "items": items})
        else:
            return jsonify({"status": "error", "message": "Invalid search type"}), 400
    except Exception as e:
        current_app.logger.error(f"Error during item search: {e}")
        return (
            jsonify({"status": "error", "message": "An error occurred during search"}),
            500,
        )
