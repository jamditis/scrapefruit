"""Result repository for database operations."""

import json
from typing import Optional, List
from uuid import uuid4
from datetime import datetime

from database.connection import session_scope
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
        with session_scope() as session:
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
            session.flush()
            session.refresh(result)
            session.expunge(result)
            return result

    def get_result(self, result_id: str) -> Optional[Result]:
        """Get a result by ID."""
        with session_scope() as session:
            result = session.query(Result).filter(Result.id == result_id).first()
            if result:
                session.expunge(result)
            return result

    def get_result_by_url(self, url_id: str) -> Optional[Result]:
        """Get result for a URL."""
        with session_scope() as session:
            result = session.query(Result).filter(Result.url_id == url_id).first()
            if result:
                session.expunge(result)
            return result

    def list_results(
        self,
        job_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Result]:
        """List results for a job."""
        with session_scope() as session:
            results = (
                session.query(Result)
                .filter(Result.job_id == job_id)
                .order_by(Result.scraped_at.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )
            for result in results:
                session.expunge(result)
            return results

    def delete_result(self, result_id: str) -> bool:
        """Delete a result."""
        with session_scope() as session:
            result = session.query(Result).filter(Result.id == result_id).first()
            if result:
                session.delete(result)
                return True
            return False

    def delete_results_for_job(self, job_id: str) -> int:
        """Delete all results for a job."""
        with session_scope() as session:
            count = session.query(Result).filter(Result.job_id == job_id).delete()
            return count

    def count_results(self, job_id: str) -> int:
        """Count results for a job."""
        with session_scope() as session:
            return session.query(Result).filter(Result.job_id == job_id).count()
