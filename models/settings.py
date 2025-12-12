"""AppSetting model - application settings storage."""

from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime
from models import Base


class AppSetting(Base):
    """Key-value store for application settings."""

    __tablename__ = "app_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "key": self.key,
            "value": self.value,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
