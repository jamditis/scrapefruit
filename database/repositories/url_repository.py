"""URL repository for database operations."""

from datetime import datetime
from typing import Optional, List
from uuid import uuid4

from database.connection import get_session
from models.url import Url


class UrlRepository:
    """Repository for URL CRUD operations."""

    def add_url(self, job_id: str, url: str) -> Url:
        """Add a URL to a job."""
        session = get_session()
        try:
            url_obj = Url(
                id=str(uuid4()),
                job_id=job_id,
                url=url,
                status=Url.STATUS_PENDING,
            )
            session.add(url_obj)
            session.commit()
            session.refresh(url_obj)
            return url_obj
        except Exception:
            session.rollback()
            raise

    def add_urls_batch(self, job_id: str, urls: List[str]) -> List[Url]:
        """Add multiple URLs to a job."""
        session = get_session()
        try:
            url_objects = []
            for url in urls:
                url_obj = Url(
                    id=str(uuid4()),
                    job_id=job_id,
                    url=url.strip(),
                    status=Url.STATUS_PENDING,
                )
                session.add(url_obj)
                url_objects.append(url_obj)

            session.commit()
            for url_obj in url_objects:
                session.refresh(url_obj)
            return url_objects
        except Exception:
            session.rollback()
            raise

    def get_url(self, url_id: str) -> Optional[Url]:
        """Get a URL by ID."""
        session = get_session()
        return session.query(Url).filter(Url.id == url_id).first()

    def list_urls(
        self,
        job_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Url]:
        """List URLs for a job with pagination."""
        session = get_session()
        query = session.query(Url).filter(Url.job_id == job_id)

        if status:
            query = query.filter(Url.status == status)

        return query.order_by(Url.id).offset(offset).limit(limit).all()

    def count_urls(self, job_id: str, status: Optional[str] = None) -> int:
        """Count URLs for a job."""
        session = get_session()
        query = session.query(Url).filter(Url.job_id == job_id)

        if status:
            query = query.filter(Url.status == status)

        return query.count()

    def get_next_pending(self, job_id: str) -> Optional[Url]:
        """Get the next pending URL for processing."""
        session = get_session()
        return (
            session.query(Url)
            .filter(Url.job_id == job_id, Url.status == Url.STATUS_PENDING)
            .first()
        )

    def update_url(self, url_id: str, **kwargs) -> Optional[Url]:
        """Update URL fields."""
        session = get_session()
        try:
            url = session.query(Url).filter(Url.id == url_id).first()
            if not url:
                return None

            for key, value in kwargs.items():
                if hasattr(url, key):
                    setattr(url, key, value)

            session.commit()
            session.refresh(url)
            return url
        except Exception:
            session.rollback()
            raise

    def mark_processing(self, url_id: str) -> Optional[Url]:
        """Mark URL as processing."""
        return self.update_url(
            url_id,
            status=Url.STATUS_PROCESSING,
            last_attempt_at=datetime.utcnow(),
        )

    def mark_completed(self, url_id: str, processing_time_ms: int) -> Optional[Url]:
        """Mark URL as completed."""
        session = get_session()
        try:
            url = session.query(Url).filter(Url.id == url_id).first()
            if not url:
                return None

            url.status = Url.STATUS_COMPLETED
            url.completed_at = datetime.utcnow()
            url.processing_time_ms = processing_time_ms
            url.attempt_count += 1

            session.commit()
            session.refresh(url)
            return url
        except Exception:
            session.rollback()
            raise

    def mark_failed(
        self,
        url_id: str,
        error_type: str,
        error_message: str,
    ) -> Optional[Url]:
        """Mark URL as failed."""
        session = get_session()
        try:
            url = session.query(Url).filter(Url.id == url_id).first()
            if not url:
                return None

            url.status = Url.STATUS_FAILED
            url.error_type = error_type
            url.error_message = error_message
            url.attempt_count += 1

            session.commit()
            session.refresh(url)
            return url
        except Exception:
            session.rollback()
            raise

    def delete_url(self, url_id: str) -> bool:
        """Delete a URL."""
        session = get_session()
        try:
            url = session.query(Url).filter(Url.id == url_id).first()
            if url:
                session.delete(url)
                session.commit()
                return True
            return False
        except Exception:
            session.rollback()
            raise

    def count_by_status(self, job_id: str) -> dict:
        """Get URL counts by status."""
        session = get_session()
        urls = session.query(Url).filter(Url.job_id == job_id).all()

        counts = {
            "pending": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0,
            "skipped": 0,
            "total": len(urls),
        }

        for url in urls:
            if url.status in counts:
                counts[url.status] += 1

        return counts

    def count_pending(self, job_id: str) -> int:
        """Count pending URLs for a job."""
        session = get_session()
        return (
            session.query(Url)
            .filter(Url.job_id == job_id, Url.status == Url.STATUS_PENDING)
            .count()
        )

    def reset_all_urls(self, job_id: str) -> int:
        """
        Reset all URLs in a job back to pending status.

        Clears error messages and attempt counts.
        Returns the number of URLs reset.
        """
        session = get_session()
        try:
            updated = (
                session.query(Url)
                .filter(Url.job_id == job_id)
                .update({
                    Url.status: Url.STATUS_PENDING,
                    Url.error_type: None,
                    Url.error_message: None,
                    Url.attempt_count: 0,
                    Url.processing_time_ms: None,
                    Url.last_attempt_at: None,
                    Url.completed_at: None,
                })
            )
            session.commit()
            return updated
        except Exception:
            session.rollback()
            raise
