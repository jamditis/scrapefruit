"""Simple dependency injection container.

A lightweight DI container for managing component lifecycles and dependencies.
No external dependencies required.

Usage:
    from core.container import Container, get_container

    # Register services
    container = get_container()
    container.register_singleton("db", lambda: Database())
    container.register_factory("fetcher", lambda c: HTTPFetcher())
    container.register_instance("config", my_config)

    # Resolve dependencies
    db = container.resolve("db")
    fetcher = container.resolve("fetcher")

    # Use with Flask
    @app.before_request
    def inject_dependencies():
        g.job_repo = container.resolve("job_repository")

Lifecycle types:
- singleton: Created once, reused for all requests
- factory: Created fresh for each resolve() call
- instance: Pre-created object, used as-is
- scoped: Created once per scope (e.g., per request)
"""

import threading
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar, Generic

T = TypeVar("T")


class Lifecycle(Enum):
    """Service lifecycle types."""

    SINGLETON = "singleton"  # Created once, reused forever
    FACTORY = "factory"  # Created fresh each time
    INSTANCE = "instance"  # Pre-existing instance
    SCOPED = "scoped"  # Created once per scope


@dataclass
class ServiceRegistration:
    """Registration info for a service."""

    name: str
    lifecycle: Lifecycle
    factory: Optional[Callable[["Container"], Any]] = None
    instance: Optional[Any] = None


class Container:
    """
    Simple dependency injection container.

    Thread-safe container for managing service lifecycles and dependencies.
    Supports singleton, factory, instance, and scoped lifecycles.

    Example:
        container = Container()

        # Register a singleton (created once)
        container.register_singleton("db", lambda c: Database())

        # Register a factory (created each time)
        container.register_factory("fetcher", lambda c: HTTPFetcher())

        # Register an existing instance
        container.register_instance("config", app_config)

        # Resolve dependencies
        db = container.resolve("db")  # Same instance every time
        fetcher = container.resolve("fetcher")  # New instance each time
    """

    def __init__(self):
        self._registrations: Dict[str, ServiceRegistration] = {}
        self._singletons: Dict[str, Any] = {}
        # Use RLock to allow recursive resolution (factories calling resolve())
        self._lock = threading.RLock()
        self._scoped_instances: threading.local = threading.local()

    def register_singleton(
        self,
        name: str,
        factory: Callable[["Container"], T],
    ) -> "Container":
        """
        Register a singleton service.

        The factory is called once on first resolve, then cached.

        Args:
            name: Service identifier
            factory: Function that creates the service (receives container)

        Returns:
            self for chaining
        """
        with self._lock:
            self._registrations[name] = ServiceRegistration(
                name=name,
                lifecycle=Lifecycle.SINGLETON,
                factory=factory,
            )
        return self

    def register_factory(
        self,
        name: str,
        factory: Callable[["Container"], T],
    ) -> "Container":
        """
        Register a factory service.

        The factory is called on every resolve.

        Args:
            name: Service identifier
            factory: Function that creates the service (receives container)

        Returns:
            self for chaining
        """
        with self._lock:
            self._registrations[name] = ServiceRegistration(
                name=name,
                lifecycle=Lifecycle.FACTORY,
                factory=factory,
            )
        return self

    def register_instance(self, name: str, instance: T) -> "Container":
        """
        Register an existing instance.

        The same instance is returned on every resolve.

        Args:
            name: Service identifier
            instance: The pre-created service instance

        Returns:
            self for chaining
        """
        with self._lock:
            self._registrations[name] = ServiceRegistration(
                name=name,
                lifecycle=Lifecycle.INSTANCE,
                instance=instance,
            )
        return self

    def register_scoped(
        self,
        name: str,
        factory: Callable[["Container"], T],
    ) -> "Container":
        """
        Register a scoped service.

        The factory is called once per scope (e.g., per request).
        Use begin_scope() and end_scope() to manage scope lifecycle.

        Args:
            name: Service identifier
            factory: Function that creates the service (receives container)

        Returns:
            self for chaining
        """
        with self._lock:
            self._registrations[name] = ServiceRegistration(
                name=name,
                lifecycle=Lifecycle.SCOPED,
                factory=factory,
            )
        return self

    def resolve(self, name: str) -> Any:
        """
        Resolve a service by name.

        Args:
            name: Service identifier

        Returns:
            The service instance

        Raises:
            KeyError: If service is not registered
        """
        with self._lock:
            if name not in self._registrations:
                raise KeyError(f"Service '{name}' is not registered")

            registration = self._registrations[name]

            if registration.lifecycle == Lifecycle.INSTANCE:
                return registration.instance

            if registration.lifecycle == Lifecycle.SINGLETON:
                if name not in self._singletons:
                    self._singletons[name] = registration.factory(self)
                return self._singletons[name]

            if registration.lifecycle == Lifecycle.SCOPED:
                scoped = getattr(self._scoped_instances, "instances", {})
                if name not in scoped:
                    scoped[name] = registration.factory(self)
                    self._scoped_instances.instances = scoped
                return scoped[name]

            # Factory - create new each time
            return registration.factory(self)

    def resolve_optional(self, name: str) -> Optional[Any]:
        """
        Resolve a service, returning None if not registered.

        Args:
            name: Service identifier

        Returns:
            The service instance or None
        """
        try:
            return self.resolve(name)
        except KeyError:
            return None

    def is_registered(self, name: str) -> bool:
        """Check if a service is registered."""
        with self._lock:
            return name in self._registrations

    def begin_scope(self) -> None:
        """
        Begin a new scope for scoped services.

        Call this at the start of a request or operation.
        """
        self._scoped_instances.instances = {}

    def end_scope(self) -> None:
        """
        End the current scope, clearing scoped instances.

        Call this at the end of a request or operation.
        """
        if hasattr(self._scoped_instances, "instances"):
            self._scoped_instances.instances = {}

    def reset(self) -> None:
        """
        Reset the container, clearing all registrations and instances.

        Useful for testing.
        """
        with self._lock:
            self._registrations.clear()
            self._singletons.clear()
            self.end_scope()

    def get_registered_services(self) -> Dict[str, Lifecycle]:
        """Get all registered services and their lifecycles."""
        with self._lock:
            return {
                name: reg.lifecycle
                for name, reg in self._registrations.items()
            }


# Global container singleton
_container: Optional[Container] = None
_container_lock = threading.Lock()


def get_container() -> Container:
    """
    Get the global container instance.

    Thread-safe singleton accessor.

    Returns:
        The global Container instance
    """
    global _container
    if _container is None:
        with _container_lock:
            if _container is None:
                _container = Container()
    return _container


def reset_container() -> None:
    """
    Reset the global container.

    Useful for testing to get a fresh container.
    """
    global _container
    with _container_lock:
        if _container is not None:
            _container.reset()
        _container = None


def configure_default_services(container: Container) -> Container:
    """
    Configure the container with default application services.

    This sets up all the standard services used by the application.
    Call this once at application startup.

    Args:
        container: The container to configure

    Returns:
        The configured container
    """
    # Import here to avoid circular imports
    from database.repositories.job_repository import JobRepository
    from database.repositories.url_repository import UrlRepository
    from database.repositories.result_repository import ResultRepository
    from database.repositories.rule_repository import RuleRepository
    from database.repositories.settings_repository import SettingsRepository

    # Repositories - singletons (stateless, safe to share)
    container.register_singleton("job_repository", lambda c: JobRepository())
    container.register_singleton("url_repository", lambda c: UrlRepository())
    container.register_singleton("result_repository", lambda c: ResultRepository())
    container.register_singleton("rule_repository", lambda c: RuleRepository())
    container.register_singleton("settings_repository", lambda c: SettingsRepository())

    # Fetchers - factories (may have state)
    from core.scraping.fetchers.http_fetcher import HTTPFetcher

    container.register_factory("http_fetcher", lambda c: HTTPFetcher())

    # Optional fetchers
    try:
        from core.scraping.fetchers.playwright_fetcher import PlaywrightFetcher
        container.register_factory("playwright_fetcher", lambda c: PlaywrightFetcher())
    except ImportError:
        pass

    # Scraping engine - singleton (manages fetcher pool)
    from core.scraping.engine import ScrapingEngine
    container.register_singleton("scraping_engine", lambda c: ScrapingEngine())

    # Job orchestrator - singleton (manages running jobs)
    from core.jobs.orchestrator import JobOrchestrator
    container.register_singleton("job_orchestrator", lambda c: JobOrchestrator())

    # LLM service - singleton with lazy init
    from core.llm.service import get_llm_service
    container.register_singleton("llm_service", lambda c: get_llm_service())

    return container
