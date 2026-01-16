"""Run Scrapefruit in development mode (browser-based, no desktop window)."""

from api import create_app
from database.connection import init_db
import config

if __name__ == "__main__":
    print("Initializing Scrapefruit (dev mode)...")
    init_db()
    print("Database initialized")

    app = create_app()
    print("Flask app created")

    print(f"\n{'='*50}")
    print(f"  Scrapefruit running at: http://127.0.0.1:{config.FLASK_PORT}")
    print(f"  Open this URL in your browser")
    print(f"{'='*50}\n")

    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=True,
        use_reloader=True,
        threaded=True
    )
