"""ExtractionRule model - defines what data to extract from pages."""

from sqlalchemy import Column, String, Text, Integer, Boolean, ForeignKey
from models import Base


class ExtractionRule(Base):
    """An extraction rule defining what to scrape from a page."""

    __tablename__ = "extraction_rules"

    id = Column(String(36), primary_key=True)
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"))
    template_id = Column(String(36), ForeignKey("templates.id", ondelete="CASCADE"))
    name = Column(String(100), nullable=False)
    selector_type = Column(String(20), nullable=False, default="css")
    selector_value = Column(Text, nullable=False)
    attribute = Column(String(100))  # None means extract text content
    transform = Column(String(100))  # e.g., "trim", "lowercase"
    is_required = Column(Boolean, default=False)
    is_list = Column(Boolean, default=False)  # Extract all matches vs first
    display_order = Column(Integer, default=0)

    # Selector types
    TYPE_CSS = "css"
    TYPE_XPATH = "xpath"
    TYPE_AUTO = "auto"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "job_id": self.job_id,
            "template_id": self.template_id,
            "name": self.name,
            "selector_type": self.selector_type,
            "selector_value": self.selector_value,
            "attribute": self.attribute,
            "transform": self.transform,
            "is_required": self.is_required,
            "is_list": self.is_list,
            "display_order": self.display_order,
        }
