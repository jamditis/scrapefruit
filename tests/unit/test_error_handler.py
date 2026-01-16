"""Unit tests for error handling middleware exception classes."""

import pytest

# Import from the Flask-independent exceptions module
from api.middleware.exceptions import (
    APIError,
    ValidationError,
    NotFoundError,
    ConflictError,
    ServiceUnavailableError,
    RateLimitError,
    format_error_response,
)


class TestAPIError:
    """Tests for the base APIError class."""

    def test_default_values(self):
        """Default values are set correctly."""
        error = APIError("Something went wrong")

        assert error.message == "Something went wrong"
        assert error.code == "API_ERROR"
        assert error.status_code == 500
        assert error.details == {}

    def test_custom_values(self):
        """Custom values are set correctly."""
        error = APIError(
            message="Custom error",
            code="CUSTOM_CODE",
            status_code=418,
            details={"foo": "bar"},
        )

        assert error.message == "Custom error"
        assert error.code == "CUSTOM_CODE"
        assert error.status_code == 418
        assert error.details == {"foo": "bar"}

    def test_str_representation(self):
        """str() returns the message."""
        error = APIError("Test message")
        assert str(error) == "Test message"

    def test_is_exception(self):
        """APIError is a proper Exception subclass."""
        assert issubclass(APIError, Exception)

        with pytest.raises(APIError):
            raise APIError("Test error")


class TestValidationError:
    """Tests for ValidationError."""

    def test_defaults(self):
        """ValidationError has correct defaults."""
        error = ValidationError("Invalid input")

        assert error.message == "Invalid input"
        assert error.code == "VALIDATION_ERROR"
        assert error.status_code == 400
        assert error.details == {}

    def test_with_details(self):
        """ValidationError accepts details."""
        error = ValidationError(
            "Email is invalid",
            details={"field": "email", "value": "not-an-email"},
        )

        assert error.details == {"field": "email", "value": "not-an-email"}

    def test_is_api_error_subclass(self):
        """ValidationError is an APIError subclass."""
        assert issubclass(ValidationError, APIError)


class TestNotFoundError:
    """Tests for NotFoundError."""

    def test_without_identifier(self):
        """NotFoundError message without identifier."""
        error = NotFoundError("Job")

        assert error.message == "Job not found"
        assert error.code == "NOT_FOUND"
        assert error.status_code == 404
        assert error.details == {"resource": "Job", "identifier": None}

    def test_with_identifier(self):
        """NotFoundError message with identifier."""
        error = NotFoundError("Job", 123)

        assert error.message == "Job with id '123' not found"
        assert error.details == {"resource": "Job", "identifier": 123}

    def test_with_string_identifier(self):
        """NotFoundError with string identifier."""
        error = NotFoundError("User", "john@example.com")

        assert error.message == "User with id 'john@example.com' not found"


class TestConflictError:
    """Tests for ConflictError."""

    def test_defaults(self):
        """ConflictError has correct defaults."""
        error = ConflictError("Resource already exists")

        assert error.message == "Resource already exists"
        assert error.code == "CONFLICT"
        assert error.status_code == 409

    def test_with_details(self):
        """ConflictError accepts details."""
        error = ConflictError(
            "Duplicate entry",
            details={"field": "email", "existing_id": 42},
        )

        assert error.details == {"field": "email", "existing_id": 42}


class TestServiceUnavailableError:
    """Tests for ServiceUnavailableError."""

    def test_default_message(self):
        """ServiceUnavailableError generates default message."""
        error = ServiceUnavailableError("Ollama")

        assert error.message == "Ollama service is temporarily unavailable"
        assert error.code == "SERVICE_UNAVAILABLE"
        assert error.status_code == 503
        assert error.details == {"service": "Ollama"}

    def test_custom_message(self):
        """ServiceUnavailableError accepts custom message."""
        error = ServiceUnavailableError("OpenAI", "Rate limit exceeded")

        assert error.message == "Rate limit exceeded"
        assert error.details == {"service": "OpenAI"}


class TestRateLimitError:
    """Tests for RateLimitError."""

    def test_without_retry_after(self):
        """RateLimitError without retry_after."""
        error = RateLimitError()

        assert error.message == "Rate limit exceeded. Please try again later."
        assert error.code == "RATE_LIMIT_EXCEEDED"
        assert error.status_code == 429
        assert error.details == {}

    def test_with_retry_after(self):
        """RateLimitError with retry_after."""
        error = RateLimitError(retry_after=60)

        assert error.details == {"retry_after_seconds": 60}


class TestFormatErrorResponse:
    """Tests for format_error_response function."""

    def test_basic_response(self):
        """Basic error response format."""
        response = format_error_response(
            code="TEST_ERROR",
            message="Test message",
        )

        assert response == {
            "error": {
                "code": "TEST_ERROR",
                "message": "Test message",
            }
        }

    def test_with_details(self):
        """Error response with details."""
        response = format_error_response(
            code="VALIDATION_ERROR",
            message="Invalid input",
            details={"field": "email", "reason": "must be valid email"},
        )

        assert response == {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid input",
                "details": {"field": "email", "reason": "must be valid email"},
            }
        }

    def test_details_none_omitted(self):
        """None details are not included."""
        response = format_error_response(
            code="ERROR",
            message="Message",
            details=None,
        )

        assert "details" not in response["error"]

    def test_empty_details_omitted(self):
        """Empty details dict is included (different from None)."""
        response = format_error_response(
            code="ERROR",
            message="Message",
            details={},
        )

        # Empty dict is falsy, so it should be omitted
        assert "details" not in response["error"]


class TestExceptionHierarchy:
    """Tests for exception class hierarchy."""

    def test_all_errors_inherit_from_api_error(self):
        """All custom errors inherit from APIError."""
        error_classes = [
            ValidationError,
            NotFoundError,
            ConflictError,
            ServiceUnavailableError,
            RateLimitError,
        ]

        for cls in error_classes:
            assert issubclass(cls, APIError), f"{cls.__name__} should inherit from APIError"

    def test_all_errors_inherit_from_exception(self):
        """All custom errors inherit from Exception."""
        error_classes = [
            APIError,
            ValidationError,
            NotFoundError,
            ConflictError,
            ServiceUnavailableError,
            RateLimitError,
        ]

        for cls in error_classes:
            assert issubclass(cls, Exception), f"{cls.__name__} should inherit from Exception"

    def test_can_catch_all_with_api_error(self):
        """Can catch all custom errors with APIError."""
        errors = [
            ValidationError("test"),
            NotFoundError("test"),
            ConflictError("test"),
            ServiceUnavailableError("test"),
            RateLimitError(),
        ]

        for error in errors:
            try:
                raise error
            except APIError as e:
                # Should catch all of them
                assert e.message is not None
            except Exception:
                pytest.fail(f"{type(error).__name__} was not caught by APIError handler")
