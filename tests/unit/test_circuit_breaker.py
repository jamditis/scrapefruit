"""Unit tests for the circuit breaker pattern."""

import time
import pytest
import threading

from core.patterns.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitOpenError,
    get_circuit_breaker,
)


class TestCircuitBreaker:
    """Tests for CircuitBreaker functionality."""

    # ========================================================================
    # Basic State Tests
    # ========================================================================

    def test_initial_state_is_closed(self):
        """Circuit starts in closed state."""
        breaker = CircuitBreaker()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_closed
        assert not breaker.is_open

    def test_can_execute_when_closed(self):
        """Calls are allowed when circuit is closed."""
        breaker = CircuitBreaker()
        assert breaker.can_execute() is True

    def test_success_keeps_circuit_closed(self):
        """Successful calls keep circuit closed."""
        breaker = CircuitBreaker(failure_threshold=3)
        for _ in range(10):
            breaker.record_success()
        assert breaker.state == CircuitState.CLOSED

    # ========================================================================
    # Failure Threshold Tests
    # ========================================================================

    def test_circuit_opens_after_threshold_failures(self):
        """Circuit opens after reaching failure threshold."""
        breaker = CircuitBreaker(failure_threshold=3)

        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED

        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED

        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        assert breaker.is_open

    def test_cannot_execute_when_open(self):
        """Calls are rejected when circuit is open."""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=60)
        breaker.record_failure()

        assert breaker.can_execute() is False

    def test_success_resets_failure_count(self):
        """Success resets the failure counter."""
        breaker = CircuitBreaker(failure_threshold=3)

        breaker.record_failure()
        breaker.record_failure()
        breaker.record_success()  # Reset
        breaker.record_failure()
        breaker.record_failure()

        # Should still be closed - counter was reset
        assert breaker.state == CircuitState.CLOSED

    # ========================================================================
    # Recovery Tests
    # ========================================================================

    def test_circuit_transitions_to_half_open(self):
        """Circuit transitions to half-open after recovery timeout."""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        time.sleep(0.15)  # Wait for recovery timeout
        assert breaker.state == CircuitState.HALF_OPEN

    def test_half_open_allows_limited_calls(self):
        """Half-open state allows limited test calls."""
        breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0.1,
            half_open_max_calls=2,
        )
        breaker.record_failure()
        time.sleep(0.15)

        # Should allow exactly 2 calls
        assert breaker.can_execute() is True
        assert breaker.can_execute() is True
        assert breaker.can_execute() is False

    def test_success_in_half_open_closes_circuit(self):
        """Successful calls in half-open state close the circuit."""
        breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0.1,
            half_open_max_calls=2,
        )
        breaker.record_failure()
        time.sleep(0.15)

        assert breaker.state == CircuitState.HALF_OPEN
        breaker.can_execute()
        breaker.record_success()
        breaker.can_execute()
        breaker.record_success()

        assert breaker.state == CircuitState.CLOSED

    def test_failure_in_half_open_reopens_circuit(self):
        """Failure in half-open state reopens the circuit."""
        breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=0.1,
            half_open_max_calls=3,
        )
        breaker.record_failure()
        time.sleep(0.15)

        assert breaker.state == CircuitState.HALF_OPEN
        breaker.can_execute()
        breaker.record_failure()

        assert breaker.state == CircuitState.OPEN

    # ========================================================================
    # Statistics Tests
    # ========================================================================

    def test_stats_tracking(self):
        """Statistics are tracked correctly."""
        breaker = CircuitBreaker(failure_threshold=5)

        breaker.can_execute()
        breaker.record_success()
        breaker.can_execute()
        breaker.record_failure()
        breaker.can_execute()
        breaker.record_success()

        stats = breaker.get_stats()
        assert stats.total_calls == 3
        assert stats.total_failures == 1
        # Note: success_count is 2, but failure_count is 0 because
        # the last success reset the consecutive failure counter
        assert stats.success_count == 2
        # failure_count tracks consecutive failures, which resets on success
        assert stats.failure_count == 0  # Reset by last success

    def test_rejection_tracking(self):
        """Rejected calls are tracked."""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=60)
        breaker.record_failure()  # Open circuit

        breaker.can_execute()  # Rejected
        breaker.can_execute()  # Rejected

        stats = breaker.get_stats()
        assert stats.total_rejections == 2

    # ========================================================================
    # Reset Tests
    # ========================================================================

    def test_reset_closes_circuit(self):
        """Reset closes the circuit and clears counters."""
        breaker = CircuitBreaker(failure_threshold=1)
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        breaker.reset()
        assert breaker.state == CircuitState.CLOSED

        stats = breaker.get_stats()
        assert stats.total_calls == 0
        assert stats.total_failures == 0

    # ========================================================================
    # Decorator Tests
    # ========================================================================

    def test_protect_decorator_success(self):
        """Protect decorator allows successful calls."""
        breaker = CircuitBreaker()

        @breaker.protect()
        def successful_call():
            return "success"

        result = successful_call()
        assert result == "success"
        assert breaker.is_closed

    def test_protect_decorator_failure(self):
        """Protect decorator records failures."""
        breaker = CircuitBreaker(failure_threshold=2)

        @breaker.protect()
        def failing_call():
            raise ValueError("failed")

        with pytest.raises(ValueError):
            failing_call()

        with pytest.raises(ValueError):
            failing_call()

        assert breaker.is_open

    def test_protect_decorator_with_fallback(self):
        """Protect decorator uses fallback when circuit is open."""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=60)

        @breaker.protect(fallback=lambda: "fallback")
        def call_service():
            raise ValueError("failed")

        # First call fails and opens circuit
        with pytest.raises(ValueError):
            call_service()

        # Second call uses fallback
        result = call_service()
        assert result == "fallback"

    def test_protect_decorator_raises_without_fallback(self):
        """Protect decorator raises CircuitOpenError when open with no fallback."""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=60)
        breaker.record_failure()

        @breaker.protect()
        def call_service():
            return "success"

        with pytest.raises(CircuitOpenError):
            call_service()

    # ========================================================================
    # Thread Safety Tests
    # ========================================================================

    def test_thread_safety(self):
        """Circuit breaker is thread-safe."""
        breaker = CircuitBreaker(failure_threshold=100)
        errors = []

        def worker():
            try:
                for _ in range(50):
                    if breaker.can_execute():
                        breaker.record_success()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert breaker.state == CircuitState.CLOSED


class TestGetCircuitBreaker:
    """Tests for the circuit breaker factory function."""

    def test_returns_same_instance_for_same_name(self):
        """Factory returns same instance for same name."""
        breaker1 = get_circuit_breaker("test_service")
        breaker2 = get_circuit_breaker("test_service")
        assert breaker1 is breaker2

    def test_returns_different_instances_for_different_names(self):
        """Factory returns different instances for different names."""
        breaker1 = get_circuit_breaker("service_a")
        breaker2 = get_circuit_breaker("service_b")
        assert breaker1 is not breaker2

    def test_uses_provided_config_for_new_breakers(self):
        """Factory uses provided config when creating new breakers."""
        breaker = get_circuit_breaker(
            "configured_service",
            failure_threshold=10,
            recovery_timeout=120,
        )
        assert breaker.failure_threshold == 10
        assert breaker.recovery_timeout == 120
