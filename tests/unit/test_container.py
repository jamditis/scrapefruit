"""Unit tests for the dependency injection container."""

import threading
import pytest

from core.container import (
    Container,
    Lifecycle,
    get_container,
    reset_container,
)


class TestContainer:
    """Tests for Container functionality."""

    @pytest.fixture
    def container(self):
        """Fresh container for each test."""
        return Container()

    # ========================================================================
    # Registration Tests
    # ========================================================================

    def test_register_instance(self, container):
        """Instance registration stores the exact object."""
        obj = {"key": "value"}
        container.register_instance("config", obj)

        resolved = container.resolve("config")
        assert resolved is obj

    def test_register_singleton(self, container):
        """Singleton returns same instance on each resolve."""
        call_count = 0

        def factory(c):
            nonlocal call_count
            call_count += 1
            return {"count": call_count}

        container.register_singleton("service", factory)

        first = container.resolve("service")
        second = container.resolve("service")
        third = container.resolve("service")

        assert first is second is third
        assert call_count == 1  # Factory called only once

    def test_register_factory(self, container):
        """Factory creates new instance on each resolve."""
        call_count = 0

        def factory(c):
            nonlocal call_count
            call_count += 1
            return {"count": call_count}

        container.register_factory("service", factory)

        first = container.resolve("service")
        second = container.resolve("service")

        assert first is not second
        assert first["count"] == 1
        assert second["count"] == 2
        assert call_count == 2

    def test_register_scoped(self, container):
        """Scoped returns same instance within scope, new between scopes."""
        call_count = 0

        def factory(c):
            nonlocal call_count
            call_count += 1
            return {"count": call_count}

        container.register_scoped("service", factory)

        # First scope
        container.begin_scope()
        first_a = container.resolve("service")
        first_b = container.resolve("service")
        assert first_a is first_b
        container.end_scope()

        # Second scope
        container.begin_scope()
        second = container.resolve("service")
        assert second is not first_a
        assert call_count == 2
        container.end_scope()

    # ========================================================================
    # Resolution Tests
    # ========================================================================

    def test_resolve_unregistered_raises(self, container):
        """Resolving unregistered service raises KeyError."""
        with pytest.raises(KeyError, match="not registered"):
            container.resolve("unknown")

    def test_resolve_optional_returns_none(self, container):
        """resolve_optional returns None for unregistered services."""
        result = container.resolve_optional("unknown")
        assert result is None

    def test_resolve_optional_returns_service(self, container):
        """resolve_optional returns service when registered."""
        container.register_instance("config", {"key": "value"})
        result = container.resolve_optional("config")
        assert result == {"key": "value"}

    def test_is_registered(self, container):
        """is_registered checks registration status."""
        assert not container.is_registered("service")
        container.register_instance("service", {})
        assert container.is_registered("service")

    # ========================================================================
    # Dependency Injection Tests
    # ========================================================================

    def test_factory_receives_container(self, container):
        """Factory function receives container for resolving dependencies."""
        container.register_instance("config", {"url": "http://localhost"})

        def service_factory(c):
            config = c.resolve("config")
            return {"config_url": config["url"]}

        container.register_factory("service", service_factory)

        service = container.resolve("service")
        assert service["config_url"] == "http://localhost"

    def test_nested_dependencies(self, container):
        """Services can depend on other services."""
        container.register_singleton("db", lambda c: {"type": "sqlite"})
        container.register_singleton(
            "repo",
            lambda c: {"db": c.resolve("db")}
        )
        container.register_factory(
            "service",
            lambda c: {"repo": c.resolve("repo")}
        )

        service = container.resolve("service")
        assert service["repo"]["db"]["type"] == "sqlite"

    # ========================================================================
    # Chaining Tests
    # ========================================================================

    def test_registration_chaining(self, container):
        """Registration methods return container for chaining."""
        result = (
            container
            .register_instance("a", 1)
            .register_singleton("b", lambda c: 2)
            .register_factory("c", lambda c: 3)
        )

        assert result is container
        assert container.resolve("a") == 1
        assert container.resolve("b") == 2
        assert container.resolve("c") == 3

    # ========================================================================
    # Reset Tests
    # ========================================================================

    def test_reset_clears_everything(self, container):
        """Reset clears registrations and instances."""
        container.register_singleton("service", lambda c: {})
        container.resolve("service")  # Create singleton

        container.reset()

        assert not container.is_registered("service")
        with pytest.raises(KeyError):
            container.resolve("service")

    # ========================================================================
    # Thread Safety Tests
    # ========================================================================

    def test_concurrent_singleton_creation(self, container):
        """Singleton is only created once even with concurrent access."""
        call_count = 0
        lock = threading.Lock()

        def slow_factory(c):
            nonlocal call_count
            with lock:
                call_count += 1
            # Simulate slow initialization
            import time
            time.sleep(0.01)
            return {"id": call_count}

        container.register_singleton("service", slow_factory)

        results = []
        errors = []

        def worker():
            try:
                result = container.resolve("service")
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert call_count == 1  # Factory called only once
        # All threads got the same instance
        assert all(r is results[0] for r in results)

    def test_scoped_is_thread_local(self, container):
        """Scoped services are isolated per thread."""
        container.register_scoped("service", lambda c: threading.current_thread().name)

        results = {}

        def worker(name):
            container.begin_scope()
            results[name] = container.resolve("service")
            container.end_scope()

        threads = [
            threading.Thread(target=worker, args=(f"thread-{i}",), name=f"thread-{i}")
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Each thread got its own value
        assert len(set(results.values())) == 5

    # ========================================================================
    # Service Listing Tests
    # ========================================================================

    def test_get_registered_services(self, container):
        """get_registered_services returns all registrations."""
        container.register_instance("a", 1)
        container.register_singleton("b", lambda c: 2)
        container.register_factory("c", lambda c: 3)
        container.register_scoped("d", lambda c: 4)

        services = container.get_registered_services()

        assert services == {
            "a": Lifecycle.INSTANCE,
            "b": Lifecycle.SINGLETON,
            "c": Lifecycle.FACTORY,
            "d": Lifecycle.SCOPED,
        }


class TestGlobalContainer:
    """Tests for global container functions."""

    def setup_method(self):
        """Reset global container before each test."""
        reset_container()

    def teardown_method(self):
        """Clean up after each test."""
        reset_container()

    def test_get_container_returns_singleton(self):
        """get_container returns the same instance."""
        c1 = get_container()
        c2 = get_container()
        assert c1 is c2

    def test_reset_container_creates_new_instance(self):
        """reset_container allows creating a new container."""
        c1 = get_container()
        c1.register_instance("test", "value")

        reset_container()
        c2 = get_container()

        assert not c2.is_registered("test")
