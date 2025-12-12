"""Job repository for database operations."""

import json
from datetime import datetime
from typing import Optional, List
from uuid import uuid4

from database.connection import get_session
from models.job import Job


class JobRepository:
    """Repository for Job CRUD operations."""

    def create_job(
        self,
        job_id: str,
        name: str,
        mode: str = "list",
        template_id: Optional[str] = None,
        settings: Optional[dict] = None,
    ) -> Job:
        """Create a new job."""
        session = get_session()
        try:
            job = Job(
                id=job_id,
                name=name,
                mode=mode,
                template_id=template_id,
                settings_json=json.dumps(settings or {}),
                status=Job.STATUS_PENDING,
                created_at=datetime.utcnow(),
            )
            session.add(job)
            session.commit()
            session.refresh(job)
            return job
        except Exception:
            session.rollback()
            raise

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        session = get_session()
        return session.query(Job).filter(Job.id == job_id).first()

    def list_jobs(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Job]:
        """List jobs with optional filtering."""
        session = get_session()
        query = session.query(Job)

        if status:
            query = query.filter(Job.status == status)

        query = query.order_by(Job.created_at.desc())
        return query.offset(offset).limit(limit).all()

    def update_job(self, job_id: str, **kwargs) -> Optional[Job]:
        """Update job fields."""
        session = get_session()
        try:
            job = session.query(Job).filter(Job.id == job_id).first()
            if not job:
                return None

            for key, value in kwargs.items():
                if key == "settings":
                    job.settings_json = json.dumps(value)
                elif hasattr(job, key):
                    setattr(job, key, value)

            session.commit()
            session.refresh(job)
            return job
        except Exception:
            session.rollback()
            raise

    def delete_job(self, job_id: str) -> bool:
        """Delete a job and all associated data."""
        session = get_session()
        try:
            job = session.query(Job).filter(Job.id == job_id).first()
            if job:
                session.delete(job)
                session.commit()
                return True
            return False
        except Exception:
            session.rollback()
            raise

    def update_status(self, job_id: str, status: str) -> Optional[Job]:
        """Update job status with timestamp."""
        updates = {"status": status}

        if status == Job.STATUS_RUNNING:
            updates["started_at"] = datetime.utcnow()
        elif status == Job.STATUS_COMPLETED:
            updates["completed_at"] = datetime.utcnow()
        elif status == Job.STATUS_PAUSED:
            updates["paused_at"] = datetime.utcnow()

        return self.update_job(job_id, **updates)

    def increment_progress(self, job_id: str, success: bool = True) -> Optional[Job]:
        """Increment progress counters."""
        session = get_session()
        try:
            job = session.query(Job).filter(Job.id == job_id).first()
            if not job:
                return None

            job.progress_current += 1
            if success:
                job.success_count += 1
            else:
                job.failure_count += 1

            # Check if completed
            if job.progress_current >= job.progress_total:
                job.status = Job.STATUS_COMPLETED
                job.completed_at = datetime.utcnow()

            session.commit()
            session.refresh(job)
            return job
        except Exception:
            session.rollback()
            raise
