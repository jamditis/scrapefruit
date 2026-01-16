"""Centralized error handling middleware for the Flask API.

This module provides consistent error responses across all API endpoints.
It catches exceptions and converts them to structured JSON responses.

Error response format:
{
    "error": {
        "code": "ERROR_CODE",
        "message": "Human-readable error message",
        "details": {...}  # Optional additional details
    }
}

Usage:
    from api.middleware.error_handler import register_error_handlers

    app = Flask(__name__)
    register_error_handlers(app)
"""

import logging
import traceback
from typing import Any, Dict, Tuple

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

# Import exception classes from the Flask-independent module
from api.middleware.exceptions import (
    APIError,
    ValidationError,
    NotFoundError,
    ConflictError,
    ServiceUnavailableError,
    RateLimitError,
    format_error_response,
)

# Re-export for convenience
__all__ = [
    "APIError",
    "ValidationError",
    "NotFoundError",
    "ConflictError",
    "ServiceUnavailableError",
    "RateLimitError",
    "format_error_response",
    "register_error_handlers",
    "register_request_logging",
]

# Configure logging
logger = logging.getLogger(__name__)


def log_error(error: Exception, include_traceback: bool = True) -> None:
    """Log an error with request context."""
    request_info = {
        "method": request.method,
        "path": request.path,
        "remote_addr": request.remote_addr,
    }

    if include_traceback:
        logger.error(
            f"Error handling request: {request_info}",
            exc_info=error,
        )
    else:
        logger.warning(
            f"Handled error for request {request_info}: {error}",
        )


# =============================================================================
# Error Handlers
# =============================================================================


def handle_api_error(error: APIError) -> Tuple[Dict[str, Any], int]:
    """Handle custom API errors."""
    # Don't log 4xx errors with full traceback (they're expected)
    if error.status_code >= 500:
        log_error(error, include_traceback=True)
    else:
        log_error(error, include_traceback=False)

    return (
        format_error_response(
            code=error.code,
            message=error.message,
            details=error.details if error.details else None,
        ),
        error.status_code,
    )


def handle_http_exception(error: HTTPException) -> Tuple[Dict[str, Any], int]:
    """Handle Werkzeug HTTP exceptions."""
    # Map common HTTP status codes to error codes
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        413: "PAYLOAD_TOO_LARGE",
        415: "UNSUPPORTED_MEDIA_TYPE",
        422: "UNPROCESSABLE_ENTITY",
        429: "TOO_MANY_REQUESTS",
        500: "INTERNAL_SERVER_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
        504: "GATEWAY_TIMEOUT",
    }

    code = code_map.get(error.code, f"HTTP_{error.code}")
    message = error.description or str(error)

    if error.code >= 500:
        log_error(error, include_traceback=True)

    return (
        format_error_response(code=code, message=message),
        error.code,
    )


def handle_generic_exception(error: Exception) -> Tuple[Dict[str, Any], int]:
    """Handle unexpected exceptions."""
    log_error(error, include_traceback=True)

    # In debug mode, include traceback
    from flask import current_app
    if current_app.debug:
        return (
            format_error_response(
                code="INTERNAL_ERROR",
                message=str(error),
                details={"traceback": traceback.format_exc()},
            ),
            500,
        )

    # In production, hide internal details
    return (
        format_error_response(
            code="INTERNAL_ERROR",
            message="An unexpected error occurred. Please try again later.",
        ),
        500,
    )


# =============================================================================
# Registration Function
# =============================================================================


def register_error_handlers(app: Flask) -> None:
    """
    Register all error handlers with the Flask app.

    This should be called during app initialization to enable
    consistent error handling across all endpoints.

    Args:
        app: The Flask application instance
    """

    @app.errorhandler(APIError)
    def api_error_handler(error):
        response, status_code = handle_api_error(error)
        return jsonify(response), status_code

    @app.errorhandler(HTTPException)
    def http_exception_handler(error):
        response, status_code = handle_http_exception(error)
        return jsonify(response), status_code

    @app.errorhandler(Exception)
    def generic_exception_handler(error):
        response, status_code = handle_generic_exception(error)
        return jsonify(response), status_code

    # Also register specific HTTP error codes to ensure they're caught
    # even if raised directly (e.g., abort(404))
    for status_code in [400, 401, 403, 404, 405, 413, 415, 422, 429, 500, 502, 503, 504]:
        @app.errorhandler(status_code)
        def http_status_handler(error, code=status_code):
            if isinstance(error, HTTPException):
                response, _ = handle_http_exception(error)
            else:
                response = format_error_response(
                    code=f"HTTP_{code}",
                    message=str(error),
                )
            return jsonify(response), code


# =============================================================================
# Request/Response Logging Middleware
# =============================================================================


def register_request_logging(app: Flask, log_level: int = logging.INFO) -> None:
    """
    Register request/response logging middleware.

    Logs:
    - Request method, path, and client IP
    - Response status code and time taken
    - Any errors that occurred

    Args:
        app: The Flask application instance
        log_level: Logging level for successful requests
    """
    import time

    @app.before_request
    def log_request_start():
        request._start_time = time.time()

    @app.after_request
    def log_request_end(response):
        duration_ms = 0
        if hasattr(request, "_start_time"):
            duration_ms = int((time.time() - request._start_time) * 1000)

        # Skip logging for static files
        if request.path.startswith("/static"):
            return response

        log_msg = (
            f"{request.method} {request.path} "
            f"- {response.status_code} "
            f"({duration_ms}ms)"
        )

        if response.status_code >= 400:
            logger.warning(log_msg)
        else:
            logger.log(log_level, log_msg)

        return response
