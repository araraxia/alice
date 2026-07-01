
import discord
from flask import (
    request,
    current_app,
    url_for,
    Blueprint,
)

from flask_login import current_user

discord_route = Blueprint('discord', __name__, url_prefix='/discord')

@discord_route.route('/health', methods=['GET'])
def discord_health_check():
    return {"status": "ok"}, 200

@discord_route.route('/interactions', methods=['POST'])
def discord_interactions():
    data = request.json
    current_app.logger.info(f"Received interaction: {data}")
    return {"status": "ok"}, 200