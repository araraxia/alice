
from pathlib import Path
import sys

FILE_PATH = Path(__file__).resolve()
ROOT_PATH = FILE_PATH.parent.parent.parent
SRC_PATH = ROOT_PATH / "src"

if SRC_PATH not in sys.path:
    sys.path.append(str(SRC_PATH))
    
from website.site_router import fort_route
from website.wiki_router import wiki_route
from website.osrs_router import osrs_route
from website.showcase_router import showcase_route
from discord.discord_router import discord_route

ROUTE_LIST = [
    fort_route,
    wiki_route,
    osrs_route,
    showcase_route,
    discord_route,
]

def register_blueprints(app):
    for route in ROUTE_LIST:
        app.register_blueprint(route)