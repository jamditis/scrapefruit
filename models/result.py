"""Result model - stores scraped data."""

import json
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from models import Base


class Result(Base):
    """Scraped data result from a URL."""

    __tablename__ = "results"

    id = Column(String(36), primary_key=True)
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    url_id = Column(String(36), ForeignKey("urls.id", ondelete="CASCADE"), nullable=False)
    data_json = Column(Text, nullable=False)
    raw_html = Column(Text)  # Optional: store original HTML
    scraped_at = Column(DateTime, default=datetime.utcnow)
    scraping_method = Column(String(20))  # http, playwright

    # Relationship to get URL
    url_record = relationship("Url", foreign_keys=[url_id], lazy="joined")

    @property
    def data(self) -> dict:
        """Parse data JSON."""
        try:
            return json.loads(self.data_json) if self.data_json else {}
        except json.JSONDecodeError:
            return {}

    @data.setter
    def data(self, value: dict):
        """Serialize data to JSON."""
        self.data_json = json.dumps(value)

    @property
    def url(self) -> str:
        """Get the URL string."""
        return self.url_record.url if self.url_record else None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "job_id": self.job_id,
            "url_id": self.url_id,
            "url": self.url,
            "data": self.data,
            "scraped_at": self.scraped_at.isoformat() if self.scraped_at else None,
            "scraping_method": self.scraping_method,
        }
