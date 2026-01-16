"""LLM Service - Local-first language model integration.

This service provides text processing capabilities using local LLMs (Ollama)
with fallback to cloud providers (OpenAI, Anthropic) when available.

Designed for DigitalOcean droplet deployment with minimal resources:
- Default: Ollama with small models (Gemma 3:4B, Phi-3 Mini, etc.)
- Fallback: Cloud APIs when local inference isn't available

Features:
- Automatic provider detection and fallback
- Circuit breaker protection per provider for resilience
- Thread-safe singleton access

Usage:
    from core.llm.service import LLMService, get_llm_service

    llm = get_llm_service()
    if llm.is_available():
        result = llm.summarize(text)
        entities = llm.extract_entities(text)
"""

import os
import json
import threading
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from core.patterns.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    get_circuit_breaker,
)


@dataclass
class LLMResult:
    """Result from an LLM operation."""
    success: bool
    content: str = ""
    error: Optional[str] = None
    model: str = ""
    provider: str = ""
    tokens_used: int = 0
    response_time_ms: int = 0


class LLMService:
    """
    Local-first LLM service with cloud fallback.

    Provider priority:
    1. Ollama (local, free) - requires ollama server running
    2. OpenAI (cloud) - requires OPENAI_API_KEY
    3. Anthropic (cloud) - requires ANTHROPIC_API_KEY

    Recommended Ollama models for low-memory systems:
    - gemma3:4b - 1.7GB, good balance of speed/quality
    - phi3:mini - 2.3GB, strong reasoning
    - qwen2.5:1.5b - 1GB, fast inference
    - bitnet:2b - 0.4GB, extreme memory efficiency
    """

    # Default models per provider (optimized for low memory)
    DEFAULT_MODELS = {
        "ollama": "gemma3:4b",
        "openai": "gpt-4o-mini",
        "anthropic": "claude-3-haiku-20240307",
    }

    # Circuit breaker settings per provider
    CIRCUIT_BREAKER_CONFIG = {
        "ollama": {"failure_threshold": 3, "recovery_timeout": 10.0},  # Local, quick recovery
        "openai": {"failure_threshold": 5, "recovery_timeout": 30.0},  # Cloud, moderate recovery
        "anthropic": {"failure_threshold": 5, "recovery_timeout": 30.0},  # Cloud, moderate recovery
    }

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        ollama_base_url: str = "http://localhost:11434",
        use_circuit_breaker: bool = True,
    ):
        """
        Initialize the LLM service.

        Args:
            provider: Force a specific provider ("ollama", "openai", "anthropic")
                     If None, auto-detects based on availability.
            model: Model name to use. If None, uses provider default.
            ollama_base_url: Base URL for Ollama server.
            use_circuit_breaker: Whether to use circuit breakers for resilience.
        """
        self.forced_provider = provider
        self.forced_model = model
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", ollama_base_url)
        self.use_circuit_breaker = use_circuit_breaker
        self._provider: Optional[str] = None
        self._model: Optional[str] = None
        self._client: Any = None

        # Circuit breakers per provider
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        if use_circuit_breaker:
            for prov, config in self.CIRCUIT_BREAKER_CONFIG.items():
                self._circuit_breakers[prov] = get_circuit_breaker(
                    f"llm_{prov}",
                    failure_threshold=config["failure_threshold"],
                    recovery_timeout=config["recovery_timeout"],
                )

    @property
    def provider(self) -> Optional[str]:
        """Get the active provider name."""
        if self._provider is None:
            self._detect_provider()
        return self._provider

    @property
    def model(self) -> str:
        """Get the active model name."""
        if self._model is None:
            self._detect_provider()
        return self._model or ""

    def is_available(self) -> bool:
        """Check if any LLM provider is available."""
        return self.provider is not None

    def _detect_provider(self):
        """Auto-detect the best available provider."""
        if self.forced_provider:
            self._provider = self.forced_provider
            self._model = self.forced_model or self.DEFAULT_MODELS.get(self.forced_provider, "")
            return

        # Priority 1: Ollama (local, free)
        if self._check_ollama():
            self._provider = "ollama"
            self._model = self.forced_model or os.getenv("OLLAMA_MODEL", self.DEFAULT_MODELS["ollama"])
            return

        # Priority 2: OpenAI
        if os.getenv("OPENAI_API_KEY"):
            self._provider = "openai"
            self._model = self.forced_model or self.DEFAULT_MODELS["openai"]
            return

        # Priority 3: Anthropic
        if os.getenv("ANTHROPIC_API_KEY"):
            self._provider = "anthropic"
            self._model = self.forced_model or self.DEFAULT_MODELS["anthropic"]
            return

        self._provider = None
        self._model = None

    def _get_circuit_breaker(self, provider: str) -> Optional[CircuitBreaker]:
        """Get the circuit breaker for a provider, if enabled."""
        if not self.use_circuit_breaker:
            return None
        return self._circuit_breakers.get(provider)

    def _is_circuit_open(self, provider: str) -> bool:
        """Check if the circuit breaker for a provider is open."""
        breaker = self._get_circuit_breaker(provider)
        return breaker is not None and breaker.is_open

    def _record_success(self, provider: str) -> None:
        """Record a successful call to the circuit breaker."""
        breaker = self._get_circuit_breaker(provider)
        if breaker:
            breaker.record_success()

    def _record_failure(self, provider: str) -> None:
        """Record a failed call to the circuit breaker."""
        breaker = self._get_circuit_breaker(provider)
        if breaker:
            breaker.record_failure()

    def _check_ollama(self) -> bool:
        """Check if Ollama server is running."""
        try:
            import urllib.request
            req = urllib.request.Request(f"{self.ollama_base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status == 200
        except Exception:
            return False

    def _get_ollama_models(self) -> List[str]:
        """Get list of available Ollama models."""
        try:
            import urllib.request
            req = urllib.request.Request(f"{self.ollama_base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    def _call_ollama(self, prompt: str, system: str = "") -> LLMResult:
        """Call Ollama API directly (no LangChain dependency)."""
        import urllib.request
        start_time = time.time()
        provider = "ollama"

        # Check circuit breaker before calling
        breaker = self._get_circuit_breaker(provider)
        if breaker and not breaker.can_execute():
            return LLMResult(
                success=False,
                error="Circuit breaker open: Ollama service temporarily unavailable",
                model=self._model or "",
                provider=provider,
                response_time_ms=0,
            )

        try:
            payload = {
                "model": self._model,
                "prompt": prompt,
                "stream": False,
            }
            if system:
                payload["system"] = system

            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{self.ollama_base_url}/api/generate",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode())
                self._record_success(provider)
                return LLMResult(
                    success=True,
                    content=result.get("response", ""),
                    model=self._model,
                    provider=provider,
                    tokens_used=result.get("eval_count", 0),
                    response_time_ms=int((time.time() - start_time) * 1000),
                )
        except Exception as e:
            self._record_failure(provider)
            return LLMResult(
                success=False,
                error=str(e),
                model=self._model,
                provider=provider,
                response_time_ms=int((time.time() - start_time) * 1000),
            )

    def _call_openai(self, prompt: str, system: str = "") -> LLMResult:
        """Call OpenAI API."""
        start_time = time.time()
        provider = "openai"

        # Check circuit breaker before calling
        breaker = self._get_circuit_breaker(provider)
        if breaker and not breaker.can_execute():
            return LLMResult(
                success=False,
                error="Circuit breaker open: OpenAI service temporarily unavailable",
                model=self._model or "",
                provider=provider,
                response_time_ms=0,
            )

        try:
            from openai import OpenAI
            client = OpenAI()

            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            response = client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=0,
            )

            self._record_success(provider)
            return LLMResult(
                success=True,
                content=response.choices[0].message.content or "",
                model=self._model,
                provider=provider,
                tokens_used=response.usage.total_tokens if response.usage else 0,
                response_time_ms=int((time.time() - start_time) * 1000),
            )
        except Exception as e:
            self._record_failure(provider)
            return LLMResult(
                success=False,
                error=str(e),
                model=self._model,
                provider=provider,
                response_time_ms=int((time.time() - start_time) * 1000),
            )

    def _call_anthropic(self, prompt: str, system: str = "") -> LLMResult:
        """Call Anthropic API."""
        start_time = time.time()
        provider = "anthropic"

        # Check circuit breaker before calling
        breaker = self._get_circuit_breaker(provider)
        if breaker and not breaker.can_execute():
            return LLMResult(
                success=False,
                error="Circuit breaker open: Anthropic service temporarily unavailable",
                model=self._model or "",
                provider=provider,
                response_time_ms=0,
            )

        try:
            from anthropic import Anthropic
            client = Anthropic()

            kwargs = {
                "model": self._model,
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system:
                kwargs["system"] = system

            response = client.messages.create(**kwargs)

            content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    content += block.text

            self._record_success(provider)
            return LLMResult(
                success=True,
                content=content,
                model=self._model,
                provider=provider,
                tokens_used=response.usage.input_tokens + response.usage.output_tokens,
                response_time_ms=int((time.time() - start_time) * 1000),
            )
        except Exception as e:
            self._record_failure(provider)
            return LLMResult(
                success=False,
                error=str(e),
                model=self._model,
                provider=provider,
                response_time_ms=int((time.time() - start_time) * 1000),
            )

    def complete(self, prompt: str, system: str = "") -> LLMResult:
        """
        Send a prompt to the LLM and get a completion.

        Args:
            prompt: The user prompt
            system: Optional system prompt for context

        Returns:
            LLMResult with the completion or error
        """
        if not self.is_available():
            return LLMResult(
                success=False,
                error="No LLM provider available. Install Ollama or set API keys.",
            )

        if self.provider == "ollama":
            return self._call_ollama(prompt, system)
        elif self.provider == "openai":
            return self._call_openai(prompt, system)
        elif self.provider == "anthropic":
            return self._call_anthropic(prompt, system)
        else:
            return LLMResult(success=False, error=f"Unknown provider: {self.provider}")

    def summarize(self, text: str, max_words: int = 100) -> LLMResult:
        """
        Summarize text content.

        Args:
            text: Text to summarize
            max_words: Target summary length

        Returns:
            LLMResult with summary
        """
        system = "You are a concise summarizer. Output only the summary, no preamble."
        prompt = f"Summarize the following text in approximately {max_words} words:\n\n{text[:8000]}"
        return self.complete(prompt, system)

    def extract_entities(self, text: str, entity_types: Optional[List[str]] = None) -> LLMResult:
        """
        Extract named entities from text.

        Args:
            text: Text to analyze
            entity_types: Types of entities to extract (e.g., ["person", "organization", "date"])
                         If None, extracts all common types.

        Returns:
            LLMResult with JSON-formatted entities
        """
        if entity_types is None:
            entity_types = ["person", "organization", "location", "date", "event"]

        types_str = ", ".join(entity_types)
        system = "You are an entity extraction system. Output valid JSON only."
        prompt = f"""Extract the following entity types from the text: {types_str}

Output format (valid JSON):
{{
  "entities": [
    {{"type": "person", "text": "John Smith", "context": "..."}},
    ...
  ]
}}

Text:
{text[:6000]}"""

        return self.complete(prompt, system)

    def classify(self, text: str, categories: List[str]) -> LLMResult:
        """
        Classify text into one of the given categories.

        Args:
            text: Text to classify
            categories: List of category options

        Returns:
            LLMResult with the selected category and confidence
        """
        cats_str = ", ".join(f'"{c}"' for c in categories)
        system = "You are a text classifier. Output valid JSON only."
        prompt = f"""Classify the following text into one of these categories: {cats_str}

Output format (valid JSON):
{{
  "category": "selected_category",
  "confidence": 0.85,
  "reasoning": "brief explanation"
}}

Text:
{text[:4000]}"""

        return self.complete(prompt, system)

    def answer_question(self, context: str, question: str) -> LLMResult:
        """
        Answer a question based on provided context.

        Args:
            context: The context/document to reference
            question: The question to answer

        Returns:
            LLMResult with the answer
        """
        system = "Answer questions based only on the provided context. If the answer isn't in the context, say so."
        prompt = f"""Context:
{context[:6000]}

Question: {question}

Answer:"""

        return self.complete(prompt, system)

    def get_status(self) -> Dict[str, Any]:
        """Get current LLM service status including circuit breaker states."""
        status = {
            "available": self.is_available(),
            "provider": self.provider,
            "model": self.model,
            "ollama_running": self._check_ollama(),
            "ollama_models": self._get_ollama_models() if self._check_ollama() else [],
            "has_openai_key": bool(os.getenv("OPENAI_API_KEY")),
            "has_anthropic_key": bool(os.getenv("ANTHROPIC_API_KEY")),
            "circuit_breakers": {},
        }

        # Add circuit breaker status for each provider
        if self.use_circuit_breaker:
            for prov, breaker in self._circuit_breakers.items():
                stats = breaker.get_stats()
                status["circuit_breakers"][prov] = {
                    "state": stats.state.value,
                    "failure_count": stats.failure_count,
                    "total_calls": stats.total_calls,
                    "total_failures": stats.total_failures,
                    "total_rejections": stats.total_rejections,
                }

        return status

    def get_circuit_breaker_stats(self, provider: str) -> Optional[Dict[str, Any]]:
        """Get circuit breaker stats for a specific provider."""
        breaker = self._get_circuit_breaker(provider)
        if not breaker:
            return None
        stats = breaker.get_stats()
        return {
            "state": stats.state.value,
            "failure_count": stats.failure_count,
            "success_count": stats.success_count,
            "total_calls": stats.total_calls,
            "total_failures": stats.total_failures,
            "total_rejections": stats.total_rejections,
            "last_failure_time": stats.last_failure_time,
            "last_success_time": stats.last_success_time,
        }

    def reset_circuit_breaker(self, provider: str) -> bool:
        """Manually reset a circuit breaker to closed state."""
        breaker = self._get_circuit_breaker(provider)
        if breaker:
            breaker.reset()
            return True
        return False


# Singleton instance with thread-safe initialization
_llm_service: Optional[LLMService] = None
_llm_lock = threading.Lock()


def get_llm_service() -> LLMService:
    """Get the singleton LLM service instance (thread-safe)."""
    global _llm_service
    if _llm_service is None:
        with _llm_lock:
            # Double-check after acquiring lock
            if _llm_service is None:
                _llm_service = LLMService()
    return _llm_service
