"""Result repository for database operations."""

import json
from typing import Optional, List
from uuid import uuid4
from datetime import datetime

from database.connection import get_session
from models.result import Result


class ResultRepository:
    """Repository for Result CRUD operations."""

    def create_result(
        self,
        job_id: str,
        url_id: str,
        data: dict,
        scraping_method: str,
        raw_html: Optional[str] = None,
    ) -> Result:
        """Create a new result."""
        session = get_session()
        try:
            result = Result(
                id=str(uuid4()),
                job_id=job_id,
                url_id=url_id,
                data_json=json.dumps(data),
                raw_html=raw_html,
                scraping_method=scraping_method,
                scraped_at=datetime.utcnow(),
            )
            session.add(result)
            session.commit()
            session.refresh(result)
            return result
        except Exception:
            session.rollback()
            raise

    def get_result(self, result_id: str) -> Optional[Result]:
        """Get a result by ID."""
        session = get_session()
        return session.query(Result).filter(Result.id == result_id).first()

    def get_result_by_url(self, url_id: str) -> Optional[Result]:
        """Get result for a URL."""
        session = get_session()
        return session.query(Result).filter(Result.url_id == url_id).first()

    def list_results(
        self,
        job_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Result]:
        """List results for a job."""
        session = get_session()
        return (
            session.query(Result)
            .filter(Result.job_id == job_id)
            .order_by(Result.scraped_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def delete_result(self, result_id: str) -> bool:
        """Delete a result."""
        session = get_session()
        try:
            result = session.query(Result).filter(Result.id == result_id).first()
            if result:
                session.delete(result)
                session.commit()
                return True
            return False
        except Exception:
            session.rollback()
            raise

    def delete_results_for_job(self, job_id: str) -> int:
        """Delete all results for a job."""
        session = get_session()
        try:
            count = session.query(Result).filter(Result.job_id == job_id).delete()
            session.commit()
            return count
        except Exception:
            session.rollback()
            raise

    def count_results(self, job_id: str) -> int:
        """Count results for a job."""
        session = get_session()
        return session.query(Result).filter(Result.job_id == job_id).count()
