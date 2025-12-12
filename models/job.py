"""Job model - represents a scraping job."""

import json
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, DateTime
from models import Base


class Job(Base):
    """A scraping job that processes URLs."""

    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(String(20), nullable=False, default="pending")
    mode = Column(String(20), nullable=False, default="list")
    template_id = Column(String(36))
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    paused_at = Column(DateTime)
    error_message = Column(Text)
    settings_json = Column(Text, default="{}")
    progress_current = Column(Integer, default=0)
    progress_total = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)

    # Valid statuses
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_PAUSED = "paused"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"

    # Valid modes
    MODE_SINGLE = "single"
    MODE_LIST = "list"
    MODE_CRAWL = "crawl"

    @property
    def settings(self) -> dict:
        """Parse settings JSON."""
        try:
            return json.loads(self.settings_json) if self.settings_json else {}
        except json.JSONDecodeError:
            return {}

    @settings.setter
    def settings(self, value: dict):
        """Serialize settings to JSON."""
        self.settings_json = json.dumps(value)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "mode": self.mode,
            "template_id": self.template_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "paused_at": self.paused_at.isoformat() if self.paused_at else None,
            "error_message": self.error_message,
            "settings": self.settings,
            "progress_current": self.progress_current,
            "progress_total": self.progress_total,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
        }
