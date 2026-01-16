"""API middleware components.

Exception classes can be imported directly from this module or from
api.middleware.exceptions (which has no Flask dependency).

Flask integration functions require Flask to be installed.
"""

# Import Flask-independent exception classes
from api.middleware.exceptions import (
    APIError,
    ValidationError,
    NotFoundError,
    ConflictError,
    ServiceUnavailableError,
    RateLimitError,
    format_error_response,
)

# Defer Flask-dependent imports to avoid requiring Flask for exception-only usage
def register_error_handlers(app):
    """Register error handlers with Flask app (requires Flask)."""
    from api.middleware.error_handler import register_error_handlers as _register
    return _register(app)


def register_request_logging(app, log_level=None):
    """Register request logging with Flask app (requires Flask)."""
    from api.middleware.error_handler import register_request_logging as _register
    import logging
    return _register(app, log_level or logging.INFO)


__all__ = [
    # Exception classes (Flask-independent)
    "APIError",
    "ValidationError",
    "NotFoundError",
    "ConflictError",
    "ServiceUnavailableError",
    "RateLimitError",
    "format_error_response",
    # Flask integration functions
    "register_error_handlers",
    "register_request_logging",
]
