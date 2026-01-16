"""Unit tests for the LLM service."""

import pytest
from unittest.mock import patch, MagicMock

from core.llm.service import LLMService, LLMResult
from core.patterns.circuit_breaker import CircuitState


class TestLLMServiceCircuitBreaker:
    """Tests for LLM service circuit breaker integration."""

    def test_circuit_breaker_initialized_by_default(self):
        """Circuit breakers are initialized for each provider by default."""
        llm = LLMService(use_circuit_breaker=True)

        assert len(llm._circuit_breakers) == 3
        assert "ollama" in llm._circuit_breakers
        assert "openai" in llm._circuit_breakers
        assert "anthropic" in llm._circuit_breakers

    def test_circuit_breaker_disabled(self):
        """Circuit breakers can be disabled."""
        llm = LLMService(use_circuit_breaker=False)

        assert len(llm._circuit_breakers) == 0

    def test_get_circuit_breaker_returns_breaker(self):
        """_get_circuit_breaker returns the correct breaker."""
        llm = LLMService(use_circuit_breaker=True)

        breaker = llm._get_circuit_breaker("ollama")
        assert breaker is not None
        assert breaker.name == "llm_ollama"

    def test_get_circuit_breaker_returns_none_when_disabled(self):
        """_get_circuit_breaker returns None when disabled."""
        llm = LLMService(use_circuit_breaker=False)

        breaker = llm._get_circuit_breaker("ollama")
        assert breaker is None

    def test_get_circuit_breaker_stats(self):
        """get_circuit_breaker_stats returns correct stats."""
        llm = LLMService(use_circuit_breaker=True)

        stats = llm.get_circuit_breaker_stats("openai")

        assert stats is not None
        assert "state" in stats
        assert "failure_count" in stats
        assert "total_calls" in stats

    def test_get_circuit_breaker_stats_none_when_disabled(self):
        """get_circuit_breaker_stats returns None when disabled."""
        llm = LLMService(use_circuit_breaker=False)

        stats = llm.get_circuit_breaker_stats("openai")
        assert stats is None

    def test_reset_circuit_breaker(self):
        """reset_circuit_breaker resets the breaker to closed state."""
        llm = LLMService(use_circuit_breaker=True)
        breaker = llm._circuit_breakers["openai"]

        # Manually open the circuit
        for _ in range(5):
            breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Reset it
        result = llm.reset_circuit_breaker("openai")
        assert result is True
        assert breaker.state == CircuitState.CLOSED

    def test_reset_circuit_breaker_returns_false_when_disabled(self):
        """reset_circuit_breaker returns False when disabled."""
        llm = LLMService(use_circuit_breaker=False)

        result = llm.reset_circuit_breaker("openai")
        assert result is False

    def test_status_includes_circuit_breaker_info(self):
        """get_status includes circuit breaker information."""
        llm = LLMService(use_circuit_breaker=True)

        status = llm.get_status()

        assert "circuit_breakers" in status
        assert "ollama" in status["circuit_breakers"]
        assert "state" in status["circuit_breakers"]["ollama"]

    def test_status_empty_circuit_breakers_when_disabled(self):
        """get_status has empty circuit_breakers when disabled."""
        llm = LLMService(use_circuit_breaker=False)

        status = llm.get_status()

        assert status["circuit_breakers"] == {}

    def test_circuit_breaker_config_per_provider(self):
        """Circuit breaker config differs per provider."""
        llm = LLMService(use_circuit_breaker=True)

        # Ollama has lower threshold (local, quick recovery)
        ollama_breaker = llm._circuit_breakers["ollama"]
        openai_breaker = llm._circuit_breakers["openai"]

        assert ollama_breaker.failure_threshold == 3
        assert ollama_breaker.recovery_timeout == 10.0

        assert openai_breaker.failure_threshold == 5
        assert openai_breaker.recovery_timeout == 30.0


class TestLLMServiceCircuitBreakerOnCall:
    """Tests for circuit breaker behavior during API calls."""

    @patch("urllib.request.urlopen")
    def test_ollama_call_records_success(self, mock_urlopen):
        """Successful Ollama call records success on circuit breaker."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"response": "test", "eval_count": 10}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        llm = LLMService(provider="ollama", model="test", use_circuit_breaker=True)
        llm._provider = "ollama"
        llm._model = "test"

        result = llm._call_ollama("test prompt")

        assert result.success is True
        stats = llm.get_circuit_breaker_stats("ollama")
        # Note: can_execute() increments total_calls, record_success doesn't
        assert stats["total_calls"] == 1

    @patch("urllib.request.urlopen")
    def test_ollama_call_records_failure(self, mock_urlopen):
        """Failed Ollama call records failure on circuit breaker."""
        mock_urlopen.side_effect = Exception("Connection refused")

        llm = LLMService(provider="ollama", model="test", use_circuit_breaker=True)
        llm._provider = "ollama"
        llm._model = "test"

        result = llm._call_ollama("test prompt")

        assert result.success is False
        assert "Connection refused" in result.error
        stats = llm.get_circuit_breaker_stats("ollama")
        assert stats["total_failures"] == 1

    @patch("urllib.request.urlopen")
    def test_ollama_call_rejected_when_circuit_open(self, mock_urlopen):
        """Ollama call is rejected immediately when circuit is open."""
        llm = LLMService(provider="ollama", model="test", use_circuit_breaker=True)
        llm._provider = "ollama"
        llm._model = "test"

        # Open the circuit by recording failures
        breaker = llm._circuit_breakers["ollama"]
        for _ in range(3):  # Ollama threshold is 3
            breaker.record_failure()

        assert breaker.state == CircuitState.OPEN

        result = llm._call_ollama("test prompt")

        assert result.success is False
        assert "Circuit breaker open" in result.error
        # urlopen should not have been called
        mock_urlopen.assert_not_called()


class TestLLMResult:
    """Tests for LLMResult dataclass."""

    def test_success_result(self):
        """Test successful result."""
        result = LLMResult(
            success=True,
            content="Hello world",
            model="gpt-4",
            provider="openai",
            tokens_used=100,
            response_time_ms=500,
        )

        assert result.success is True
        assert result.content == "Hello world"
        assert result.error is None

    def test_failure_result(self):
        """Test failure result."""
        result = LLMResult(
            success=False,
            error="API rate limit exceeded",
            model="gpt-4",
            provider="openai",
        )

        assert result.success is False
        assert result.error == "API rate limit exceeded"
        assert result.content == ""

    def test_default_values(self):
        """Test default values."""
        result = LLMResult(success=True)

        assert result.content == ""
        assert result.error is None
        assert result.model == ""
        assert result.provider == ""
        assert result.tokens_used == 0
        assert result.response_time_ms == 0
