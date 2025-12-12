"""SQLAlchemy models for Scrapefruit."""

from sqlalchemy.orm import declarative_base

Base = declarative_base()

from models.job import Job
from models.url import Url
from models.rule import ExtractionRule
from models.result import Result
from models.template import Template
from models.settings import AppSetting

__all__ = ["Base", "Job", "Url", "ExtractionRule", "Result", "Template", "AppSetting"]
