"""Template model - pre-built extraction templates."""

import json
from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, DateTime
from models import Base


class Template(Base):
    """A reusable extraction template."""

    __tablename__ = "templates"

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    category = Column(String(50))  # article, product, social, custom
    is_builtin = Column(Boolean, default=False)
    config_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)

    # Categories
    CATEGORY_ARTICLE = "article"
    CATEGORY_PRODUCT = "product"
    CATEGORY_SOCIAL = "social"
    CATEGORY_CUSTOM = "custom"

    @property
    def config(self) -> dict:
        """Parse config JSON."""
        try:
            return json.loads(self.config_json) if self.config_json else {}
        except json.JSONDecodeError:
            return {}

    @config.setter
    def config(self, value: dict):
        """Serialize config to JSON."""
        self.config_json = json.dumps(value)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "is_builtin": self.is_builtin,
            "config": self.config,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
