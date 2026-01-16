"""Custom exception classes for the API.

These exception classes can be imported without Flask, making them
suitable for use anywhere in the application.

Error response format (when converted to JSON):
{
    "error": {
        "code": "ERROR_CODE",
        "message": "Human-readable error message",
        "details": {...}  # Optional additional details
    }
}
"""

from typing import Any, Dict, Optional


class APIError(Exception):
    """Base class for API errors.

    Use this for application-level errors that should return a specific
    HTTP status code and error message.
    """

    def __init__(
        self,
        message: str,
        code: str = "API_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class ValidationError(APIError):
    """Request validation failed."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=400,
            details=details,
        )


class NotFoundError(APIError):
    """Requested resource not found."""

    def __init__(self, resource: str, identifier: Any = None):
        message = f"{resource} not found"
        if identifier:
            message = f"{resource} with id '{identifier}' not found"
        super().__init__(
            message=message,
            code="NOT_FOUND",
            status_code=404,
            details={"resource": resource, "identifier": identifier},
        )


class ConflictError(APIError):
    """Resource conflict (e.g., duplicate entry)."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="CONFLICT",
            status_code=409,
            details=details,
        )


class ServiceUnavailableError(APIError):
    """External service is unavailable."""

    def __init__(self, service: str, message: Optional[str] = None):
        super().__init__(
            message=message or f"{service} service is temporarily unavailable",
            code="SERVICE_UNAVAILABLE",
            status_code=503,
            details={"service": service},
        )


class RateLimitError(APIError):
    """Rate limit exceeded."""

    def __init__(self, retry_after: Optional[int] = None):
        details = {}
        if retry_after:
            details["retry_after_seconds"] = retry_after
        super().__init__(
            message="Rate limit exceeded. Please try again later.",
            code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            details=details,
        )


def format_error_response(
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Format a consistent error response structure."""
    response = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    if details:
        response["error"]["details"] = details
    return response
