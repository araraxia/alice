# app.py

from flask import render_template, abort, Blueprint, current_app
import markdown
import os

app = current_app
wiki_route = Blueprint("docs", __name__, url_prefix="/docs")

@wiki_route.route("/")
def docs():
    path = os.path.join("docs", "index.md")
    if not os.path.exists(path):
        abort(404)
    with open(path, "r") as f:
        content = f.read()
    html = markdown.markdown(content, extensions=['tables', 'fenced_code', 'codehilite', 'toc'])
    return render_template("wiki.html", content=html)