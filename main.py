"""Scrapefruit - Desktop scraping platform entry point."""

import atexit
import signal
import sys
import threading
import time
import webview

from api import create_app
from database.connection import init_db
import config

# Global flag for shutdown coordination
_shutdown_requested = False
_cleanup_done = False
_cleanup_lock = threading.Lock()


def cleanup_resources():
    """
    Clean up all resources before shutdown.

    Stops running jobs, closes browser instances, and releases locks.
    Safe to call multiple times.
    """
    global _cleanup_done

    with _cleanup_lock:
        if _cleanup_done:
            return
        _cleanup_done = True

    print("\nCleaning up resources...")

    try:
        # Stop all running jobs
        from core.jobs.orchestrator import JobOrchestrator
        orchestrator = JobOrchestrator()
        running_jobs = orchestrator.get_running_jobs()
        if running_jobs:
            print(f"Stopping {len(running_jobs)} running job(s)...")
            orchestrator.stop_all_jobs()
    except Exception as e:
        print(f"Warning: Error stopping jobs: {e}")

    try:
        # Clean up Playwright browser instances
        from core.scraping.fetchers.playwright_fetcher import PlaywrightFetcher
        fetcher = PlaywrightFetcher()
        fetcher.cleanup()
    except Exception as e:
        print(f"Warning: Error closing Playwright: {e}")

    try:
        # Clean up Puppeteer browser instances
        from core.scraping.fetchers.puppeteer_fetcher import HAS_PYPPETEER
        if HAS_PYPPETEER:
            from core.scraping.fetchers.puppeteer_fetcher import PuppeteerFetcher
            try:
                fetcher = PuppeteerFetcher()
                if fetcher.browser:
                    import asyncio
                    loop = asyncio.new_event_loop()
                    loop.run_until_complete(fetcher.close())
                    loop.close()
            except ImportError:
                pass
    except Exception as e:
        print(f"Warning: Error closing Puppeteer: {e}")

    print("Cleanup complete.")


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    global _shutdown_requested
    _shutdown_requested = True
    print(f"\nReceived signal {signum}, shutting down...")
    cleanup_resources()
    sys.exit(0)


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

    # Register cleanup handlers
    atexit.register(cleanup_resources)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)
    # Windows-specific signal
    if hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, signal_handler)

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
    try:
        # Start webview (blocks until window is closed)
        webview.start(debug=config.FLASK_DEBUG)
    finally:
        # Ensure cleanup runs when window closes
        cleanup_resources()


if __name__ == "__main__":
    main()
