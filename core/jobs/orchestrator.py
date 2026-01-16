"""Job orchestrator for managing scraping jobs."""

import threading
import time
from typing import Dict, Optional, List, Any, Callable
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

        # Locks for thread-safe access to shared dictionaries
        self._workers_lock = threading.Lock()
        self._logs_lock = threading.Lock()

        # Job logs storage (persists even after job completes)
        self.job_logs: Dict[str, List[Dict[str, Any]]] = {}

        # Scheduled log cleanup (job_id -> cleanup time)
        self._log_cleanup_schedule: Dict[str, float] = {}

        # Event callbacks
        self.on_progress: Optional[Callable] = None
        self.on_job_complete: Optional[Callable] = None
        self.on_url_complete: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        self.on_log: Optional[Callable] = None

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

        with self._workers_lock:
            # Check if already running
            if job_id in self.workers:
                return False

            # Initialize log storage for this job
            with self._logs_lock:
                if job_id not in self.job_logs:
                    self.job_logs[job_id] = []
                # Cancel any scheduled cleanup
                self._log_cleanup_schedule.pop(job_id, None)

            # Update job status
            self.job_repo.update_status(job_id, Job.STATUS_RUNNING)

            # Get global settings
            settings = {
                "timeout": self.settings_repo.get_int("scraping.timeout", 30000),
                "retry_count": self.settings_repo.get_int("scraping.retry_count", 3),
                "delay_min": self.settings_repo.get_int("scraping.delay_min", 1000),
                "delay_max": self.settings_repo.get_int("scraping.delay_max", 3000),
                "use_stealth": self.settings_repo.get_bool("scraping.use_stealth", True),
            }

            # Merge job-specific settings (including cascade config)
            if job.settings:
                settings.update(job.settings)

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
        with self._workers_lock:
            worker = self.workers.get(job_id)
        if not worker:
            return

        try:
            worker.run()
        except Exception as e:
            self._handle_error(job_id, None, str(e))
            # Mark job as failed on unhandled exception
            self.job_repo.update_status(job_id, Job.STATUS_FAILED)
        finally:
            self._cleanup_worker(job_id)

    def _cleanup_worker(self, job_id: str):
        """Clean up worker after completion."""
        with self._workers_lock:
            self.workers.pop(job_id, None)
            self.worker_threads.pop(job_id, None)

        # Update job status if still running
        job = self.job_repo.get_job(job_id)
        if job and job.status == Job.STATUS_RUNNING:
            # Check if all URLs processed
            url_counts = self.url_repo.count_by_status(job_id)
            if url_counts["pending"] == 0 and url_counts["processing"] == 0:
                self.job_repo.update_status(job_id, Job.STATUS_COMPLETED)

            if self.on_job_complete:
                self.on_job_complete(job_id)

        # Schedule log cleanup after 5 minutes
        self._schedule_log_cleanup(job_id)

    def pause_job(self, job_id: str) -> bool:
        """Pause a running job."""
        job = self.job_repo.get_job(job_id)
        if not job or job.status != Job.STATUS_RUNNING:
            return False

        with self._workers_lock:
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

        with self._workers_lock:
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

        with self._workers_lock:
            is_running = job_id in self.workers

        return {
            "id": job.id,
            "name": job.name,
            "status": job.status,
            "progress_current": job.progress_current,
            "progress_total": job.progress_total,
            "success_count": job.success_count,
            "failure_count": job.failure_count,
            "url_counts": url_counts,
            "is_running": is_running,
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
        with self._logs_lock:
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
        with self._logs_lock:
            logs = self.job_logs.get(job_id, [])
            # Create a copy to avoid holding lock during iteration
            logs_copy = list(logs)

        # Get logs since index
        new_logs = logs_copy[since_index:]

        # Filter by level if specified
        if level:
            new_logs = [log for log in new_logs if log.get("level") == level]

        return {
            "logs": new_logs,
            "total_count": len(logs_copy),
            "current_index": len(logs_copy),
        }

    def clear_job_logs(self, job_id: str):
        """Clear logs for a job."""
        with self._logs_lock:
            if job_id in self.job_logs:
                self.job_logs[job_id] = []

    def _schedule_log_cleanup(self, job_id: str, delay_seconds: int = 300):
        """Schedule log cleanup for a completed job after delay."""
        cleanup_time = time.time() + delay_seconds
        with self._logs_lock:
            self._log_cleanup_schedule[job_id] = cleanup_time

        # Start cleanup thread if not already running
        threading.Thread(
            target=self._run_log_cleanup,
            args=(job_id, delay_seconds),
            daemon=True
        ).start()

    def _run_log_cleanup(self, job_id: str, delay_seconds: int):
        """Run the scheduled log cleanup after delay."""
        time.sleep(delay_seconds)

        with self._logs_lock:
            # Check if cleanup is still scheduled (not cancelled by job restart)
            if job_id in self._log_cleanup_schedule:
                if time.time() >= self._log_cleanup_schedule[job_id]:
                    self.job_logs.pop(job_id, None)
                    self._log_cleanup_schedule.pop(job_id, None)

    def get_running_jobs(self) -> list:
        """Get list of currently running job IDs."""
        with self._workers_lock:
            return list(self.workers.keys())

    def stop_all_jobs(self):
        """Stop all running jobs. Used for graceful shutdown."""
        with self._workers_lock:
            job_ids = list(self.workers.keys())

        for job_id in job_ids:
            self.stop_job(job_id)
