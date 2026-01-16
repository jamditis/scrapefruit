"""Circuit breaker pattern for resilient external service calls.

A circuit breaker prevents repeatedly calling a failing service,
allowing it time to recover while providing immediate failure
responses to callers.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Service is failing, requests are rejected immediately
- HALF_OPEN: Testing if service has recovered

Usage:
    from core.patterns.circuit_breaker import CircuitBreaker

    breaker = CircuitBreaker(
        failure_threshold=5,
        recovery_timeout=30,
        half_open_max_calls=3,
    )

    def call_external_service():
        if not breaker.can_execute():
            return fallback_response()

        try:
            result = external_service.call()
            breaker.record_success()
            return result
        except Exception as e:
            breaker.record_failure()
            raise

    # Or use as decorator:
    @breaker.protect
    def call_external_service():
        return external_service.call()
"""

import threading
import time
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Callable, Optional, TypeVar, Any

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Rejecting calls
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitStats:
    """Statistics for circuit breaker monitoring."""

    state: CircuitState
    failure_count: int
    success_count: int
    last_failure_time: Optional[float]
    last_success_time: Optional[float]
    total_calls: int
    total_failures: int
    total_rejections: int


class CircuitBreaker:
    """
    Circuit breaker for protecting against cascading failures.

    When a service fails repeatedly, the circuit "opens" and
    immediately rejects subsequent calls for a cooldown period.
    After the cooldown, a few test calls are allowed through
    (half-open state) to check if the service has recovered.

    Args:
        failure_threshold: Number of consecutive failures to open circuit
        recovery_timeout: Seconds to wait before testing recovery
        half_open_max_calls: Number of test calls in half-open state
        name: Optional name for logging/metrics
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
        name: str = "circuit_breaker",
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.name = name

        # State
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_failure_time: Optional[float] = None
        self._last_success_time: Optional[float] = None
        self._opened_at: Optional[float] = None

        # Metrics
        self._total_calls = 0
        self._total_failures = 0
        self._total_rejections = 0

        # Thread safety
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state (may trigger state transition)."""
        with self._lock:
            self._check_state_transition()
            return self._state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self.state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (rejecting calls)."""
        return self.state == CircuitState.OPEN

    def can_execute(self) -> bool:
        """
        Check if a call should be allowed through.

        Returns:
            True if call should proceed, False if rejected
        """
        with self._lock:
            self._total_calls += 1
            self._check_state_transition()

            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                self._total_rejections += 1
                return False

            # Half-open: allow limited calls
            if self._half_open_calls < self.half_open_max_calls:
                self._half_open_calls += 1
                return True

            self._total_rejections += 1
            return False

    def record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            self._last_success_time = time.time()
            self._success_count += 1

            if self._state == CircuitState.HALF_OPEN:
                # Success in half-open state closes the circuit
                if self._success_count >= self.half_open_max_calls:
                    self._close_circuit()
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call."""
        with self._lock:
            self._last_failure_time = time.time()
            self._failure_count += 1
            self._total_failures += 1

            if self._state == CircuitState.HALF_OPEN:
                # Failure in half-open state re-opens the circuit
                self._open_circuit()
            elif self._state == CircuitState.CLOSED:
                # Check if we should open the circuit
                if self._failure_count >= self.failure_threshold:
                    self._open_circuit()

    def reset(self) -> None:
        """Reset the circuit breaker to closed state."""
        with self._lock:
            self._close_circuit()
            self._total_calls = 0
            self._total_failures = 0
            self._total_rejections = 0

    def get_stats(self) -> CircuitStats:
        """Get current circuit breaker statistics."""
        with self._lock:
            return CircuitStats(
                state=self._state,
                failure_count=self._failure_count,
                success_count=self._success_count,
                last_failure_time=self._last_failure_time,
                last_success_time=self._last_success_time,
                total_calls=self._total_calls,
                total_failures=self._total_failures,
                total_rejections=self._total_rejections,
            )

    def _check_state_transition(self) -> None:
        """Check if state should transition (called with lock held)."""
        if self._state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            if self._opened_at and (time.time() - self._opened_at) >= self.recovery_timeout:
                self._half_open_circuit()

    def _open_circuit(self) -> None:
        """Open the circuit (called with lock held)."""
        self._state = CircuitState.OPEN
        self._opened_at = time.time()

    def _half_open_circuit(self) -> None:
        """Transition to half-open state (called with lock held)."""
        self._state = CircuitState.HALF_OPEN
        self._half_open_calls = 0
        self._success_count = 0
        self._failure_count = 0

    def _close_circuit(self) -> None:
        """Close the circuit (called with lock held)."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._opened_at = None

    def protect(self, fallback: Optional[Callable[[], T]] = None):
        """
        Decorator to protect a function with this circuit breaker.

        Args:
            fallback: Optional function to call when circuit is open

        Usage:
            @breaker.protect(fallback=lambda: "default")
            def call_service():
                return external_service.call()
        """
        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            @wraps(func)
            def wrapper(*args, **kwargs) -> T:
                if not self.can_execute():
                    if fallback:
                        return fallback()
                    raise CircuitOpenError(
                        f"Circuit breaker '{self.name}' is open"
                    )

                try:
                    result = func(*args, **kwargs)
                    self.record_success()
                    return result
                except Exception:
                    self.record_failure()
                    raise

            return wrapper
        return decorator


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open and no fallback provided."""
    pass


# Shared circuit breakers for common services
_circuit_breakers: dict[str, CircuitBreaker] = {}
_breakers_lock = threading.Lock()


def get_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0,
) -> CircuitBreaker:
    """
    Get or create a named circuit breaker.

    Circuit breakers are cached by name, so calling this multiple
    times with the same name returns the same instance.

    Args:
        name: Unique name for this circuit breaker
        failure_threshold: Failures before opening (only for new breakers)
        recovery_timeout: Recovery time in seconds (only for new breakers)

    Returns:
        The circuit breaker instance
    """
    with _breakers_lock:
        if name not in _circuit_breakers:
            _circuit_breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
            )
        return _circuit_breakers[name]
