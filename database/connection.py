"""SQLite database connection and session management."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import NullPool

import config
from models import Base

# Create engine with NullPool for SQLite
# NullPool creates fresh connections each time, avoiding pool exhaustion
# Safe for concurrent access from Flask requests and background workers
engine = create_engine(
    config.DATABASE_URL,
    echo=config.FLASK_DEBUG,
    connect_args={"check_same_thread": False},
    poolclass=NullPool,
)

# Create session factory
SessionFactory = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Thread-local session
Session = scoped_session(SessionFactory)


def get_session():
    """Get a database session."""
    return Session()


def remove_session():
    """Remove the current thread-local session.

    This returns the connection to the pool and should be called
    after each request or operation completes.
    """
    Session.remove()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)
    _seed_defaults()


def _seed_defaults():
    """Seed default settings."""
    from database.repositories.settings_repository import SettingsRepository

    repo = SettingsRepository()
    defaults = {
        "scraping.timeout": str(config.DEFAULT_TIMEOUT),
        "scraping.retry_count": str(config.DEFAULT_RETRY_COUNT),
        "scraping.delay_min": str(config.DEFAULT_DELAY_MIN),
        "scraping.delay_max": str(config.DEFAULT_DELAY_MAX),
        "scraping.use_stealth": "true",
        "scraping.rotate_user_agent": "true",
    }

    for key, value in defaults.items():
        if repo.get(key) is None:
            repo.set(key, value)
