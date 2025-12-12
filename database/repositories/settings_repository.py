"""Settings repository for database operations."""

from typing import Optional, Dict
from datetime import datetime

from database.connection import get_session
from models.settings import AppSetting
import config


class SettingsRepository:
    """Repository for AppSetting CRUD operations."""

    # Default settings
    DEFAULTS = {
        "scraping.timeout": str(config.DEFAULT_TIMEOUT),
        "scraping.retry_count": str(config.DEFAULT_RETRY_COUNT),
        "scraping.delay_min": str(config.DEFAULT_DELAY_MIN),
        "scraping.delay_max": str(config.DEFAULT_DELAY_MAX),
        "scraping.use_stealth": "true",
        "scraping.rotate_user_agent": "true",
        "export.include_raw_html": "false",
        "ui.theme": "dark",
    }

    def get(self, key: str) -> Optional[str]:
        """Get a setting value."""
        session = get_session()
        setting = session.query(AppSetting).filter(AppSetting.key == key).first()
        return setting.value if setting else None

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get a boolean setting."""
        value = self.get(key)
        if value is None:
            return default
        return value.lower() in ("true", "1", "yes")

    def get_int(self, key: str, default: int = 0) -> int:
        """Get an integer setting."""
        value = self.get(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            return default

    def set(self, key: str, value: str) -> AppSetting:
        """Set a setting value."""
        session = get_session()
        try:
            setting = session.query(AppSetting).filter(AppSetting.key == key).first()
            if setting:
                setting.value = value
                setting.updated_at = datetime.utcnow()
            else:
                setting = AppSetting(key=key, value=value)
                session.add(setting)

            session.commit()
            session.refresh(setting)
            return setting
        except Exception:
            session.rollback()
            raise

    def get_all(self) -> Dict[str, str]:
        """Get all settings as a dictionary."""
        session = get_session()
        settings = session.query(AppSetting).all()
        return {s.key: s.value for s in settings}

    def delete(self, key: str) -> bool:
        """Delete a setting."""
        session = get_session()
        try:
            setting = session.query(AppSetting).filter(AppSetting.key == key).first()
            if setting:
                session.delete(setting)
                session.commit()
                return True
            return False
        except Exception:
            session.rollback()
            raise

    def reset_defaults(self) -> Dict[str, str]:
        """Reset all settings to defaults."""
        session = get_session()
        try:
            # Delete all settings
            session.query(AppSetting).delete()
            session.commit()

            # Re-seed defaults
            for key, value in self.DEFAULTS.items():
                setting = AppSetting(key=key, value=value)
                session.add(setting)

            session.commit()
            return self.get_all()
        except Exception:
            session.rollback()
            raise
