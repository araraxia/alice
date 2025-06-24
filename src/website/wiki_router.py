# app.py

from flask import render_template, abort, Blueprint, current_app
import markdown
import os

app = current_app
wiki_route = Blueprint("docs", __name__, url_prefix="/docs")

@wiki_route.route("/")
def wiki_index():
    path = os.path.join("docs", "intro.md")
    if not os.path.exists(path):
        abort(404)
    with open(path, "r") as f:
        content = f.read()
    html = markdown.markdown(content, extensions=['tables', 'fenced_code', 'codehilite', 'toc'])
    return render_template("wiki.html", content=html)

@wiki_route.route("/")
def docs():
    path = os.path.join("docs", "index.md")
    if not os.path.exists(path):
        abort(404)
    with open(path, "r") as f:
        content = f.read()
    html = markdown.markdown(content, extensions=['tables', 'fenced_code', 'codehilite', 'toc'])
    return render_template("wiki.html", content=html)

@wiki_route.route("/preflight/<page>")
def preflight_docs(page):
    page_path = os.path.join("docs", "preflight", f"{page}.md")
    app.logger.info(page_path)
    if not os.path.exists(page_path):
        abort(404)
    with open(page_path, "r") as f:
        content = f.read()
    html = markdown.markdown(content, extensions=['tables', 'fenced_code', 'codehilite', 'toc'])
    return render_template("wiki.html", content=html)

@wiki_route.route("/sql/notion/<page>")
def sql_notion_docs(page):
    page_path = os.path.join("docs", "sql", "notion", f"{page}.md")
    if not os.path.exists(page_path):
        abort(404)
    with open(page_path, "r") as f:
        content = f.read()
    html = markdown.markdown(content, extensions=['tables', 'fenced_code', 'codehilite', 'toc'])
    return render_template("wiki.html", content=html)