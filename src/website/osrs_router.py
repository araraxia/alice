
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

osrs_route = Blueprint('osrs', __name__, url_prefix='/osrs')

@osrs_route.route('/', methods=['GET'])
def index():
    return render_template('osrs/index.html')

@osrs_route.route('/calc', methods=['GET'])
def calc():
    from src.osrs.osrs_calcs import OSRSCalcsHandler
    calc_handler = OSRSCalcsHandler(current_app)
    return calc_handler.render_index()

@osrs_route.route('/super-combats', methods=['GET'])
def super_combats():
    try:
        from src.osrs.calcs.super_combats import SuperCombats
        sc = SuperCombats()
        data = sc.find_cheapest_ingredients()

        if not data:
            return render_template('osrs/super_combats.html', error="No data available")

        return render_template('osrs/super_combats.html', data=data)
    except Exception as e:
        current_app.logger.error(f"Error in super_combats route: {e}")
        return render_template('osrs/super_combats.html', error=str(e))