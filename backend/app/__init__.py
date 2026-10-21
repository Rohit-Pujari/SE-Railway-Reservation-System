"""Flask application factory and static frontend serving."""

from pathlib import Path

from flask import Flask, send_from_directory

from .config import Config
from .routes import api

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


def create_app() -> Flask:
    app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
    app.config.from_object(Config)
    app.register_blueprint(api)

    @app.get("/")
    def index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    return app
