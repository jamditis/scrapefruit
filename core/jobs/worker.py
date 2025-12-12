"""Job worker for processing URLs."""

import time
import random
from typing import Dict, Optional, Callable, Any, List
from datetime import datetime

from database.repositories.url_repository import UrlRepository
from database.repositories.rule_repository import RuleRepository
from database.repositories.result_repository import ResultRepository
from core.scraping.engine import ScrapingEngine


class JobWorker:
    """
    Worker that processes URLs for a specific job.

    Runs in a background thread and processes URLs sequentially.
    Emits detailed log events for real-time progress tracking.
    """

    def __init__(
        self,
        job_id: str,
        settings: Dict[str, Any],
        on_url_complete: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        on_log: Optional[Callable] = None,
    ):
        self.job_id = job_id
        self.settings = settings
        self.on_url_complete = on_url_complete
        self.on_error = on_error
        self.on_log = on_log  # New: callback for log messages

        self.url_repo = UrlRepository()
        self.rule_repo = RuleRepository()
        self.result_repo = ResultRepository()
        self.engine = ScrapingEngine()

        self._running = False
        self._stop_requested = False
        self._logs: List[Dict[str, Any]] = []  # Store logs in memory

    def _emit_log(self, level: str, message: str, data: Optional[Dict] = None):
        """Emit a log entry with timestamp."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,  # info, success, warning, error, debug
            "message": message,
            "data": data or {},
        }
        self._logs.append(log_entry)

        if self.on_log:
            self.on_log(self.job_id, log_entry)

    def get_logs(self) -> List[Dict[str, Any]]:
        """Get all logged entries."""
        return self._logs.copy()

    def run(self):
        """
        Main worker loop.

        Processes URLs until none remain or stop is requested.
        """
        self._running = True
        self._stop_requested = False

        # Get extraction rules for this job
        rules = self.rule_repo.list_rules(job_id=self.job_id)
        rules_dicts = [r.to_dict() for r in rules]

        # Count total URLs
        pending_count = self.url_repo.count_pending(self.job_id)
        processed = 0

        self._emit_log("info", f"Starting job with {pending_count} URLs to process", {
            "total_urls": pending_count,
            "rules_count": len(rules_dicts),
        })

        if rules_dicts:
            rule_names = [r.get("name", "unnamed") for r in rules_dicts]
            self._emit_log("debug", f"Extraction rules: {', '.join(rule_names)}")

        while self._running and not self._stop_requested:
            # Get next pending URL
            url_record = self.url_repo.get_next_pending(self.job_id)

            if not url_record:
                # No more URLs to process
                self._emit_log("info", f"Job complete. Processed {processed} URLs.")
                break

            processed += 1
            self._emit_log("info", f"[{processed}/{pending_count}] Fetching: {url_record.url[:80]}...")

            self._process_url(url_record, rules_dicts, processed, pending_count)

            # Delay between requests
            if not self._stop_requested:
                delay = random.randint(
                    self.settings.get("delay_min", 1000),
                    self.settings.get("delay_max", 3000),
                )
                self._emit_log("debug", f"Waiting {delay}ms before next request...")
                time.sleep(delay / 1000)

        self._running = False

    def _process_url(self, url_record, rules: list, current: int = 0, total: int = 0):
        """Process a single URL with detailed logging."""
        url_id = url_record.id
        url = url_record.url

        # Mark as processing
        self.url_repo.mark_processing(url_id)
        start_time = time.time()

        try:
            # Scrape the URL
            result = self.engine.scrape_url(
                url=url,
                rules=rules,
                timeout=self.settings.get("timeout", 30000),
            )

            processing_time = int((time.time() - start_time) * 1000)

            if result.success:
                # Log the method used and data extracted
                data_summary = {k: (len(v) if isinstance(v, list) else "1 value")
                               for k, v in result.data.items()}
                self._emit_log("success", f"Extracted data via {result.method} in {processing_time}ms", {
                    "url": url,
                    "method": result.method,
                    "time_ms": processing_time,
                    "fields": data_summary,
                    "data_preview": {k: (v[:2] if isinstance(v, list) and len(v) > 2 else v)
                                    for k, v in result.data.items()},
                })

                # Save result
                self.result_repo.create_result(
                    job_id=self.job_id,
                    url_id=url_id,
                    data=result.data,
                    scraping_method=result.method,
                )

                # Mark URL as completed
                self.url_repo.mark_completed(url_id, processing_time)

                if self.on_url_complete:
                    self.on_url_complete(self.job_id, url_id, True, result.data)

            else:
                # Log the failure with details
                error_type = result.poison_pill or "extraction_failed"
                self._emit_log("error", f"Failed: {result.error or 'Unknown error'}", {
                    "url": url,
                    "error_type": error_type,
                    "method": result.method,
                    "time_ms": processing_time,
                    "poison_pill": result.poison_pill,
                })

                # Mark URL as failed
                self.url_repo.mark_failed(
                    url_id,
                    error_type=error_type,
                    error_message=result.error or "Unknown error",
                )

                if self.on_url_complete:
                    self.on_url_complete(self.job_id, url_id, False, {"error": result.error})

        except Exception as e:
            # Unexpected error
            processing_time = int((time.time() - start_time) * 1000)

            self._emit_log("error", f"Exception: {str(e)}", {
                "url": url,
                "error_type": "exception",
                "time_ms": processing_time,
            })

            self.url_repo.mark_failed(
                url_id,
                error_type="exception",
                error_message=str(e),
            )

            if self.on_error:
                self.on_error(self.job_id, url_id, str(e))

            if self.on_url_complete:
                self.on_url_complete(self.job_id, url_id, False, {"error": str(e)})

    def stop(self):
        """Request worker to stop."""
        self._stop_requested = True

    def is_running(self) -> bool:
        """Check if worker is running."""
        return self._running
