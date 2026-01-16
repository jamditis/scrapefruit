"""Job repository for database operations."""

import json
from datetime import datetime
from typing import Optional, List
from uuid import uuid4

from database.connection import session_scope
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
        with session_scope() as session:
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
            session.flush()
            session.refresh(job)
            # Expunge to detach from session before it closes
            session.expunge(job)
            return job

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        with session_scope() as session:
            job = session.query(Job).filter(Job.id == job_id).first()
            if job:
                session.expunge(job)
            return job

    def list_jobs(
        self,
        status: Optional[str] = None,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Job]:
        """List jobs with optional filtering."""
        with session_scope() as session:
            query = session.query(Job)

            if status:
                query = query.filter(Job.status == status)
            elif not include_archived:
                # By default, exclude archived jobs unless explicitly requested
                query = query.filter(Job.status != Job.STATUS_ARCHIVED)

            query = query.order_by(Job.created_at.desc())
            jobs = query.offset(offset).limit(limit).all()
            for job in jobs:
                session.expunge(job)
            return jobs

    def archive_job(self, job_id: str) -> Optional[Job]:
        """Archive a job (soft delete - keeps data but hides from main list)."""
        return self.update_status(job_id, Job.STATUS_ARCHIVED)

    def unarchive_job(self, job_id: str) -> Optional[Job]:
        """Restore an archived job to pending status."""
        return self.update_status(job_id, Job.STATUS_PENDING)

    def update_job(self, job_id: str, **kwargs) -> Optional[Job]:
        """Update job fields."""
        with session_scope() as session:
            job = session.query(Job).filter(Job.id == job_id).first()
            if not job:
                return None

            for key, value in kwargs.items():
                if key == "settings":
                    job.settings_json = json.dumps(value)
                elif hasattr(job, key):
                    setattr(job, key, value)

            session.flush()
            session.refresh(job)
            session.expunge(job)
            return job

    def delete_job(self, job_id: str) -> bool:
        """Delete a job and all associated data."""
        with session_scope() as session:
            job = session.query(Job).filter(Job.id == job_id).first()
            if job:
                session.delete(job)
                return True
            return False

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
        with session_scope() as session:
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

            session.flush()
            session.refresh(job)
            session.expunge(job)
            return job
