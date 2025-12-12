"""URL model - represents a URL to be scraped within a job."""

from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey
from models import Base


class Url(Base):
    """A URL to be scraped as part of a job."""

    __tablename__ = "urls"

    id = Column(String(36), primary_key=True)
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    url = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    attempt_count = Column(Integer, default=0)
    last_attempt_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_type = Column(String(50))
    error_message = Column(Text)
    processing_time_ms = Column(Integer)

    # Valid statuses
    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_SKIPPED = "skipped"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "job_id": self.job_id,
            "url": self.url,
            "status": self.status,
            "attempt_count": self.attempt_count,
            "last_attempt_at": self.last_attempt_at.isoformat() if self.last_attempt_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "processing_time_ms": self.processing_time_ms,
        }
