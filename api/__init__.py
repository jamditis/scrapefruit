"""Flask application factory for Scrapefruit API.

Note: This module defers Flask imports to the create_app function to allow
importing api.middleware.exceptions without requiring Flask to be installed.
"""


def create_app():
    """Create and configure the Flask application."""
    # Import Flask dependencies inside the function to allow importing
    # api.middleware.exceptions without requiring Flask
    from flask import Flask, request, Response
    from flask_cors import CORS

    import config
    from database.connection import remove_session
    from api.middleware import register_error_handlers, register_request_logging
    from core.container import get_container, configure_default_services

    # Initialize DI container with default services
    container = get_container()
    configure_default_services(container)

    def check_auth(username, password):
        """Verify username and password against config."""
        return username == config.AUTH_USERNAME and password == config.AUTH_PASSWORD

    def authenticate():
        """Send 401 response to trigger browser's basic auth prompt."""
        return Response(
            "Authentication required. Please provide valid credentials.",
            401,
            {"WWW-Authenticate": 'Basic realm="Scrapefruit"'},
        )

    app = Flask(
        __name__,
        static_folder="../static",
        static_url_path="/static",
    )

    # Configuration
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.config["DEBUG"] = config.FLASK_DEBUG
    app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB max upload size

    # Enable CORS for all routes
    CORS(app)

    # Register error handling middleware
    register_error_handlers(app)
    register_request_logging(app)

    # Basic auth middleware (only when AUTH_ENABLED=true)
    if config.AUTH_ENABLED:
        @app.before_request
        def require_auth():
            # Skip auth for health check endpoint
            if request.path == "/api/health":
                return None

            auth = request.authorization
            if not auth or not check_auth(auth.username, auth.password):
                return authenticate()

    # Clean up database sessions after each request
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        remove_session()

    # Register blueprints
    from api.routes.jobs import jobs_bp
    from api.routes.scraping import scraping_bp
    from api.routes.export import export_bp
    from api.routes.settings import settings_bp
    from api.routes.database import database_bp

    app.register_blueprint(jobs_bp, url_prefix="/api/jobs")
    app.register_blueprint(scraping_bp, url_prefix="/api/scraping")
    app.register_blueprint(export_bp, url_prefix="/api/export")
    app.register_blueprint(settings_bp, url_prefix="/api/settings")
    app.register_blueprint(database_bp, url_prefix="/api/database")

    # Root route serves the frontend
    @app.route("/")
    def index():
        return app.send_static_file("index.html")

    # Health check
    @app.route("/api/health")
    def health():
        return {"status": "ok", "app": "scrapefruit"}

    return app
