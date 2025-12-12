"""Flask application factory for Scrapefruit API."""

from flask import Flask
from flask_cors import CORS

import config
from database.connection import remove_session


def create_app():
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        static_folder="../static",
        static_url_path="/static",
    )

    # Configuration
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.config["DEBUG"] = config.FLASK_DEBUG

    # Enable CORS for all routes
    CORS(app)

    # Clean up database sessions after each request
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        remove_session()

    # Register blueprints
    from api.routes.jobs import jobs_bp
    from api.routes.scraping import scraping_bp
    from api.routes.export import export_bp
    from api.routes.settings import settings_bp

    app.register_blueprint(jobs_bp, url_prefix="/api/jobs")
    app.register_blueprint(scraping_bp, url_prefix="/api/scraping")
    app.register_blueprint(export_bp, url_prefix="/api/export")
    app.register_blueprint(settings_bp, url_prefix="/api/settings")

    # Root route serves the frontend
    @app.route("/")
    def index():
        return app.send_static_file("index.html")

    # Health check
    @app.route("/api/health")
    def health():
        return {"status": "ok", "app": "scrapefruit"}

    return app
