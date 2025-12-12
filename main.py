"""Scrapefruit - Desktop scraping platform entry point."""

import sys
import threading
import time
import webview

from api import create_app
from database.connection import init_db
import config


def start_flask(app):
    """Start Flask server in background thread."""
    # Simple Flask server without SocketIO for initial testing
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=False,
        use_reloader=False,
        threaded=True
    )


def main():
    """Main entry point for Scrapefruit."""
    print("Initializing Scrapefruit...")

    # Initialize database
    init_db()
    print("Database initialized")

    # Create Flask app
    app = create_app()
    print("Flask app created")

    # Start Flask in background thread
    flask_thread = threading.Thread(target=start_flask, args=(app,), daemon=True)
    flask_thread.start()
    print(f"Flask server starting on http://{config.FLASK_HOST}:{config.FLASK_PORT}")

    # Give Flask a moment to start
    time.sleep(1)

    # Create PyWebView window pointing to Flask server
    api_url = f"http://{config.FLASK_HOST}:{config.FLASK_PORT}"

    window = webview.create_window(
        title=config.WINDOW_TITLE,
        url=api_url,
        width=config.WINDOW_WIDTH,
        height=config.WINDOW_HEIGHT,
        min_size=(config.WINDOW_MIN_WIDTH, config.WINDOW_MIN_HEIGHT),
        resizable=True,
        frameless=False,
        easy_drag=False,
        text_select=True,
    )

    print("Starting PyWebView window...")
    # Start webview (blocks until window is closed)
    webview.start(debug=config.FLASK_DEBUG)


if __name__ == "__main__":
    main()
