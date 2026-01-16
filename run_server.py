"""Run Scrapefruit server for web deployment (Cloudflare Tunnel compatible)."""

import os
import sys

# Ensure we're in the right directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from api import create_app
from database.connection import init_db
import config

if __name__ == "__main__":
    print("=" * 50)
    print("  SCRAPEFRUIT SERVER")
    print("=" * 50)

    # Initialize database
    print("\n[*] Initializing database...")
    init_db()

    # Create Flask app
    app = create_app()

    # Check auth status
    if config.AUTH_ENABLED:
        print(f"[*] Authentication: ENABLED")
        print(f"    Username: {config.AUTH_USERNAME}")
        print(f"    Password: {'*' * len(config.AUTH_PASSWORD)}")
    else:
        print("[!] Authentication: DISABLED (set AUTH_ENABLED=true in .env)")

    print(f"\n[*] Server starting on http://127.0.0.1:{config.FLASK_PORT}")
    print("[*] Use Cloudflare Tunnel to expose: cloudflared tunnel --url http://127.0.0.1:5150")
    print("\n" + "=" * 50)

    # Run with waitress for production (if available), otherwise Flask dev server
    try:
        from waitress import serve
        print("[*] Running with Waitress (production server)")
        serve(app, host="127.0.0.1", port=config.FLASK_PORT, threads=4)
    except ImportError:
        print("[*] Running with Flask dev server (install waitress for production)")
        app.run(
            host="127.0.0.1",
            port=config.FLASK_PORT,
            debug=False,
            threaded=True,
        )
