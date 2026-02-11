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


@osrs_route.route("/item-price-graph", methods=["POST"])
def item_price_graph():
    """
    Generate an interactive price graph modal for an OSRS item.

    Expected JSON payload:
    {
        "item_id": int,
        "start_date": str (datetime string, ISO format, or Unix timestamp),
        "end_date": str (optional, datetime string, ISO format, or Unix timestamp),
        "table_type": str (one of: "latest", "5min", "1h")
    }

    Returns:
    {
        "status": "success",
        "html": "<div>...</div>"  # Modal HTML with embedded graph
    }
    """
    from src.osrs.item_properties import osrsItemProperties

    data = request.get_json()

    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400

    item_id = data.get("item_id")
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    table_type = data.get("table_type", "5min")

    # Validate required parameters
    if not item_id:
        return jsonify({"status": "error", "message": "item_id is required"}), 400

    if not start_date:
        return jsonify({"status": "error", "message": "start_date is required"}), 400

    # Validate table_type
    if table_type not in ["latest", "5min", "1h"]:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Invalid table_type. Must be 'latest', '5min', or '1h'",
                }
            ),
            400,
        )

    try:
        # Create item properties instance
        item_props = osrsItemProperties(item_id=int(item_id))

        # Fetch price data
        price_data = item_props.get_prices_between_dates(
            start_date=start_date,
            end_date=end_date,
            table_type=table_type,
            sort_desc=False,
        )

        if not price_data:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "No price data available for the specified date range",
                    }
                ),
                404,
            )

        # Extract and format data for Chart.js
        timestamps = []
        high_prices = []
        low_prices = []

        for record in price_data:
            timestamp = record.get("timestamp")
            if timestamp:
                # Format timestamp as ISO string for JavaScript
                timestamps.append(
                    timestamp.isoformat()
                    if hasattr(timestamp, "isoformat")
                    else str(timestamp)
                )

                # Extract price data based on table type
                if table_type == "latest":
                    high_prices.append(record.get("high"))
                    low_prices.append(record.get("low"))
                else:  # 5min or 1h
                    high_prices.append(record.get("avgHighPrice"))
                    low_prices.append(record.get("avgLowPrice"))

        # Generate modal HTML with dynamic ID based on item_id
        item_name = item_props.name if item_props.name else f"Item {item_id}"
        end_date_display = end_date if end_date else "Now"
        modal_id = f"priceGraphModal_{item_id}"
        canvas_id = f"priceChart_{item_id}"

        # Convert data to JSON strings for embedding
        import json

        timestamps_json = json.dumps(timestamps)
        high_prices_json = json.dumps(high_prices)
        low_prices_json = json.dumps(low_prices)

        # Render the modal template
        modal_html = render_template(
            "osrs/price_graph_modal.html",
            modal_id=modal_id,
            canvas_id=canvas_id,
            item_name=item_name,
            table_type=table_type,
            start_date=start_date,
            end_date_display=end_date_display,
            timestamps_json=timestamps_json,
            high_prices_json=high_prices_json,
            low_prices_json=low_prices_json,
        )

        return jsonify({"status": "success", "html": modal_html})

    except ValueError as e:
        return (
            jsonify({"status": "error", "message": f"Invalid parameter: {str(e)}"}),
            400,
        )
    except Exception as e:
        current_app.logger.error(f"Error generating price graph: {e}")
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "An error occurred while generating the graph",
                }
            ),
            500,
        )
