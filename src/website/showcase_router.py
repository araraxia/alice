from flask import (
    render_template,
    request,
    jsonify,
    current_app,
    Blueprint,
    send_from_directory,
)
import os
import json
import markdown

showcase_route = Blueprint("showcase", __name__, url_prefix="/showcase")

# Define the showcase content directory
SHOWCASE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "showcase_content"
)


@showcase_route.route("/showcase-window", methods=["GET"])
def showcase_modal():
    """Main showcase window endpoint"""
    page_html = render_template("showcase/index.html")
    return jsonify({"status": "success", "html": page_html})


@showcase_route.route("/navigation", methods=["GET"])
def get_navigation():
    """Get the navigation structure for the sidebar"""
    try:
        nav_file = os.path.join(SHOWCASE_DIR, "navigation.json")

        if not os.path.exists(nav_file):
            current_app.logger.error(f"Navigation file not found: {nav_file}")
            # Return default navigation if file doesn't exist
            return jsonify(
                {
                    "categories": [
                        {
                            "name": "Getting Started",
                            "items": [{"id": "welcome", "title": "Welcome"}],
                        }
                    ]
                }
            )

        with open(nav_file, "r", encoding="utf-8") as f:
            navigation = json.load(f)

        return jsonify(navigation)

    except Exception as e:
        current_app.logger.error(f"Error loading navigation: {e}")
        return jsonify({"error": str(e)}), 500


@showcase_route.route("/topic/<topic_id>", methods=["GET"])
def get_topic(topic_id):
    """Load a specific topic's markdown content"""
    try:
        # Sanitize topic_id to prevent directory traversal
        safe_topic_id = topic_id.replace("..", "").replace("/", "").replace("\\", "")

        # Try to find the markdown file
        md_file = os.path.join(SHOWCASE_DIR, "topics", f"{safe_topic_id}.md")

        if not os.path.exists(md_file):
            return (
                jsonify(
                    {"status": "error", "message": f"Topic '{topic_id}' not found"}
                ),
                404,
            )

        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()

        html = markdown.markdown(
            content,
            extensions=[
                "fenced_code",
                "codehilite",
                "tables",
                "toc",
                "def_list",
                "markdown_checklist.extension",
            ]
        )
        
        return jsonify({"status": "success", "content": html, "topic_id": topic_id})

    except Exception as e:
        current_app.logger.error(f"Error loading topic {topic_id}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
