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


@osrs_route.route("/item-graph-data", methods=["POST"])
def item_graph_data():
    """
    Return raw price/volume records for a given item and date range.

    Request JSON: { item_id, start_date, end_date (opt), table_type }
    Response:     { status, item_name, table_type, records: [{timestamp, high, low, highVol, lowVol}] }
    """
    from src.osrs.item_properties import osrsItemProperties

    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400

    item_id    = data.get("item_id")
    start_date = data.get("start_date")
    end_date   = data.get("end_date")
    table_type = data.get("table_type", "5min")

    if not item_id:
        return jsonify({"status": "error", "message": "item_id is required"}), 400
    if not start_date:
        return jsonify({"status": "error", "message": "start_date is required"}), 400
    if table_type not in ["latest", "5min", "1h"]:
        return jsonify({"status": "error", "message": "Invalid table_type"}), 400

    try:
        item = osrsItemProperties(item_id=int(item_id), load_data=True)

        records = item.get_prices_between_dates(
            start_date=start_date,
            end_date=end_date,
            table_type=table_type,
            sort_desc=False,
        )

        if not records:
            return jsonify({"status": "error", "message": "No data available for the specified range"}), 404

        def fmt(rec):
            ts = rec.get("timestamp")
            ts_iso = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
            if table_type == "latest":
                return {"timestamp": ts_iso, "high": rec.get("high"), "low": rec.get("low"),
                        "highVol": None, "lowVol": None}
            return {"timestamp": ts_iso, "high": rec.get("avgHighPrice"), "low": rec.get("avgLowPrice"),
                    "highVol": rec.get("highPriceVolume"), "lowVol": rec.get("lowPriceVolume")}

        return jsonify({
            "status":    "success",
            "item_name": item.name or f"Item {item_id}",
            "table_type": table_type,
            "records":   [fmt(r) for r in records],
        })

    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error in item-graph-data: {e}")
        return jsonify({"status": "error", "message": "An error occurred"}), 500


@osrs_route.route("/item-price-graph", methods=["POST"])
def item_price_graph():
    data = request.get_json()

    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400

    item_id   = data.get("item_id")
    item_name = data.get("item_name")

    if not item_id:
        return jsonify({"status": "error", "message": "item_id is required"}), 400

    try:
        item_id = int(item_id)
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "item_id must be an integer"}), 400

    if not item_name:
        item_name = f"Item {item_id}"

    modal_html = render_template(
        "osrs/price_graph_modal.html",
        item_id=item_id,
        item_name=item_name,
    )
    return jsonify({"status": "success", "html": modal_html})
