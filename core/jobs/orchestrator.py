"""Job orchestrator for managing scraping jobs."""

import threading
import time
from typing import Dict, Optional, List, Any
from datetime import datetime

from database.repositories.job_repository import JobRepository
from database.repositories.url_repository import UrlRepository
from database.repositories.rule_repository import RuleRepository
from database.repositories.result_repository import ResultRepository
from database.repositories.settings_repository import SettingsRepository
from core.jobs.worker import JobWorker
from models.job import Job


class JobOrchestrator:
    """
    Orchestrates scraping jobs, managing workers and job states.

    Singleton pattern - only one orchestrator per application.
    """

    _instance: Optional["JobOrchestrator"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.job_repo = JobRepository()
        self.url_repo = UrlRepository()
        self.rule_repo = RuleRepository()
        self.result_repo = ResultRepository()
        self.settings_repo = SettingsRepository()

        # Active workers by job ID
        self.workers: Dict[str, JobWorker] = {}
        self.worker_threads: Dict[str, threading.Thread] = {}

        # Job logs storage (persists even after job completes)
        self.job_logs: Dict[str, List[Dict[str, Any]]] = {}

        # Event callbacks
        self.on_progress = None
        self.on_job_complete = None
        self.on_url_complete = None
        self.on_error = None
        self.on_log = None  # New: callback for log entries

        self._initialized = True

    def start_job(self, job_id: str) -> bool:
        """
        Start a job.

        Creates a worker and begins processing URLs.
        """
        job = self.job_repo.get_job(job_id)
        if not job:
            return False

        if job.status not in (Job.STATUS_PENDING, Job.STATUS_PAUSED):
            return False

        # Check if already running
        if job_id in self.workers:
            return False

        # Initialize log storage for this job
        if job_id not in self.job_logs:
            self.job_logs[job_id] = []

        # Update job status
        self.job_repo.update_status(job_id, Job.STATUS_RUNNING)

        # Get settings
        settings = {
            "timeout": self.settings_repo.get_int("scraping.timeout", 30000),
            "retry_count": self.settings_repo.get_int("scraping.retry_count", 3),
            "delay_min": self.settings_repo.get_int("scraping.delay_min", 1000),
            "delay_max": self.settings_repo.get_int("scraping.delay_max", 3000),
            "use_stealth": self.settings_repo.get_bool("scraping.use_stealth", True),
        }

        # Create worker with log callback
        worker = JobWorker(
            job_id=job_id,
            settings=settings,
            on_url_complete=self._handle_url_complete,
            on_error=self._handle_error,
            on_log=self._handle_log,
        )
        self.workers[job_id] = worker

        # Start worker thread
        thread = threading.Thread(target=self._run_worker, args=(job_id,), daemon=True)
        self.worker_threads[job_id] = thread
        thread.start()

        return True

    def _run_worker(self, job_id: str):
        """Run worker in background thread."""
        worker = self.workers.get(job_id)
        if not worker:
            return

        try:
            worker.run()
        except Exception as e:
            self._handle_error(job_id, None, str(e))
        finally:
            self._cleanup_worker(job_id)

    def _cleanup_worker(self, job_id: str):
        """Clean up worker after completion."""
        if job_id in self.workers:
            del self.workers[job_id]
        if job_id in self.worker_threads:
            del self.worker_threads[job_id]

        # Update job status if still running
        job = self.job_repo.get_job(job_id)
        if job and job.status == Job.STATUS_RUNNING:
            # Check if all URLs processed
            url_counts = self.url_repo.count_by_status(job_id)
            if url_counts["pending"] == 0 and url_counts["processing"] == 0:
                self.job_repo.update_status(job_id, Job.STATUS_COMPLETED)

            if self.on_job_complete:
                self.on_job_complete(job_id)

    def pause_job(self, job_id: str) -> bool:
        """Pause a running job."""
        job = self.job_repo.get_job(job_id)
        if not job or job.status != Job.STATUS_RUNNING:
            return False

        worker = self.workers.get(job_id)
        if worker:
            worker.stop()

        self.job_repo.update_status(job_id, Job.STATUS_PAUSED)
        return True

    def resume_job(self, job_id: str) -> bool:
        """Resume a paused job."""
        job = self.job_repo.get_job(job_id)
        if not job or job.status != Job.STATUS_PAUSED:
            return False

        return self.start_job(job_id)

    def stop_job(self, job_id: str) -> bool:
        """Stop a job completely."""
        job = self.job_repo.get_job(job_id)
        if not job:
            return False

        worker = self.workers.get(job_id)
        if worker:
            worker.stop()

        self.job_repo.update_status(job_id, Job.STATUS_CANCELLED)
        self._cleanup_worker(job_id)
        return True

    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get current job status and progress."""
        job = self.job_repo.get_job(job_id)
        if not job:
            return None

        url_counts = self.url_repo.count_by_status(job_id)

        return {
            "id": job.id,
            "name": job.name,
            "status": job.status,
            "progress_current": job.progress_current,
            "progress_total": job.progress_total,
            "success_count": job.success_count,
            "failure_count": job.failure_count,
            "url_counts": url_counts,
            "is_running": job_id in self.workers,
        }

    def _handle_url_complete(self, job_id: str, url_id: str, success: bool, data: dict):
        """Handle URL completion callback from worker."""
        # Update job progress
        self.job_repo.increment_progress(job_id, success=success)

        if self.on_url_complete:
            self.on_url_complete(job_id, url_id, success, data)

        if self.on_progress:
            status = self.get_job_status(job_id)
            self.on_progress(job_id, status)

    def _handle_error(self, job_id: str, url_id: Optional[str], error: str):
        """Handle error callback from worker."""
        if self.on_error:
            self.on_error(job_id, url_id, error)

    def _handle_log(self, job_id: str, log_entry: Dict[str, Any]):
        """Handle log callback from worker."""
        # Store the log entry
        if job_id not in self.job_logs:
            self.job_logs[job_id] = []
        self.job_logs[job_id].append(log_entry)

        # Limit stored logs to prevent memory issues (keep last 1000)
        if len(self.job_logs[job_id]) > 1000:
            self.job_logs[job_id] = self.job_logs[job_id][-1000:]

        # Notify any listeners
        if self.on_log:
            self.on_log(job_id, log_entry)

    def get_job_logs(
        self,
        job_id: str,
        since_index: int = 0,
        level: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get logs for a job.

        Args:
            job_id: The job ID
            since_index: Only return logs after this index (for polling)
            level: Filter by log level (info, success, warning, error, debug)

        Returns:
            Dict with logs and current index
        """
        logs = self.job_logs.get(job_id, [])

        # Get logs since index
        new_logs = logs[since_index:]

        # Filter by level if specified
        if level:
            new_logs = [log for log in new_logs if log.get("level") == level]

        return {
            "logs": new_logs,
            "total_count": len(logs),
            "current_index": len(logs),
        }

    def clear_job_logs(self, job_id: str):
        """Clear logs for a job."""
        if job_id in self.job_logs:
            self.job_logs[job_id] = []

    def get_running_jobs(self) -> list:
        """Get list of currently running job IDs."""
        return list(self.workers.keys())
