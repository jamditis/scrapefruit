"""Job worker for processing URLs."""

import time
import random
import concurrent.futures
from typing import Dict, Optional, Callable, Any, List
from datetime import datetime

from database.repositories.url_repository import UrlRepository
from database.repositories.rule_repository import RuleRepository
from database.repositories.result_repository import ResultRepository
from core.scraping.engine import ScrapingEngine
import config

# Maximum retries for failed URLs at end of job
MAX_END_RETRIES = 1


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
        Failed URLs are retried once at the end of the job.
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

        # Extract cascade configuration from settings
        cascade_config = self.settings.get("cascade", None)
        if cascade_config:
            cascade_order = cascade_config.get("order", [])
            self._emit_log("info", f"Cascade mode: {' → '.join(cascade_order) if cascade_order else 'default'}")

        # Track failed URLs for retry
        failed_urls = []

        while self._running and not self._stop_requested:
            # Get next pending URL
            url_record = self.url_repo.get_next_pending(self.job_id)

            if not url_record:
                # No more pending URLs - try retrying failed ones
                break

            processed += 1
            self._emit_log("info", f"[{processed}/{pending_count}] Fetching: {url_record.url[:80]}...")

            success = self._process_url_with_timeout(
                url_record, rules_dicts, cascade_config, processed, pending_count
            )

            if not success:
                failed_urls.append(url_record.id)

            # Delay between requests
            if not self._stop_requested:
                delay = random.randint(
                    self.settings.get("delay_min", 1000),
                    self.settings.get("delay_max", 3000),
                )
                self._emit_log("debug", f"Waiting {delay}ms before next request...")
                time.sleep(delay / 1000)

        # Retry failed URLs once at the end
        if failed_urls and not self._stop_requested:
            self._retry_failed_urls(failed_urls, rules_dicts, cascade_config)

        failed_count = self.url_repo.count_failed(self.job_id)
        success_count = processed - failed_count

        self._emit_log("info", f"Job complete. {success_count}/{processed} URLs succeeded.", {
            "total_processed": processed,
            "success_count": success_count,
            "failed_count": failed_count,
        })

        self._running = False

    def _retry_failed_urls(self, failed_url_ids: List[str], rules: list, cascade_config: Optional[Dict]):
        """
        Retry failed URLs once at end of job.

        Args:
            failed_url_ids: List of URL IDs that failed on first attempt
            rules: Extraction rules
            cascade_config: Cascade configuration
        """
        if not failed_url_ids:
            return

        self._emit_log("info", f"Retrying {len(failed_url_ids)} failed URLs...")

        retried = 0
        recovered = 0

        for url_id in failed_url_ids:
            if self._stop_requested:
                break

            # Reset URL to pending for retry
            self.url_repo.reset_to_pending(url_id)
            url_record = self.url_repo.get_by_id(url_id)

            if not url_record:
                continue

            retried += 1
            self._emit_log("info", f"Retry [{retried}/{len(failed_url_ids)}]: {url_record.url[:60]}...")

            success = self._process_url_with_timeout(
                url_record, rules, cascade_config, retried, len(failed_url_ids), is_retry=True
            )

            if success:
                recovered += 1

            # Short delay between retries
            if not self._stop_requested:
                time.sleep(2)

        self._emit_log("info", f"Retry complete. Recovered {recovered}/{retried} URLs.")

    def _process_url_with_timeout(
        self,
        url_record,
        rules: list,
        cascade_config: Optional[Dict] = None,
        current: int = 0,
        total: int = 0,
        is_retry: bool = False,
    ) -> bool:
        """
        Process URL with a hard timeout to prevent hangs.

        Uses a ThreadPoolExecutor with timeout to ensure we don't get stuck
        on any single URL forever.

        Args:
            url_record: URL record to process
            rules: Extraction rules
            cascade_config: Cascade configuration
            current: Current URL index
            total: Total URL count
            is_retry: Whether this is a retry attempt

        Returns:
            True if URL was processed successfully, False otherwise
        """
        url_timeout = self.settings.get("url_timeout", config.DEFAULT_URL_TIMEOUT)

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    self._process_url,
                    url_record, rules, cascade_config, current, total
                )

                try:
                    # Wait for completion with timeout
                    success = future.result(timeout=url_timeout)
                    return success if success is not None else False

                except concurrent.futures.TimeoutError:
                    # URL processing timed out
                    self._emit_log("warning", f"URL timed out after {url_timeout}s, moving on", {
                        "url": url_record.url,
                        "timeout_seconds": url_timeout,
                    })

                    # Mark as failed due to timeout
                    self.url_repo.mark_failed(
                        url_record.id,
                        error_type="timeout",
                        error_message=f"Processing timed out after {url_timeout} seconds",
                    )

                    if self.on_url_complete:
                        self.on_url_complete(
                            self.job_id,
                            url_record.id,
                            False,
                            {"error": f"Timeout after {url_timeout}s"}
                        )

                    return False

        except Exception as e:
            self._emit_log("error", f"Unexpected error in timeout wrapper: {str(e)}")
            return False

    def _process_url(self, url_record, rules: list, cascade_config: Optional[Dict] = None, current: int = 0, total: int = 0) -> bool:
        """Process a single URL with detailed logging."""
        url_id = url_record.id
        url = url_record.url

        # Mark as processing
        self.url_repo.mark_processing(url_id)
        start_time = time.time()

        try:
            # Scrape the URL with cascade config
            result = self.engine.scrape_url(
                url=url,
                rules=rules,
                timeout=self.settings.get("timeout", 30000),
                cascade_config=cascade_config,
            )

            processing_time = int((time.time() - start_time) * 1000)

            if result.success:
                # Log the method used and data extracted
                data_summary = {k: (len(v) if isinstance(v, list) else "1 value")
                               for k, v in result.data.items()}

                # Include cascade attempt info if available
                cascade_info = ""
                if result.cascade_attempts and len(result.cascade_attempts) > 1:
                    cascade_info = f" (after {len(result.cascade_attempts)} attempts)"

                self._emit_log("success", f"Extracted data via {result.method}{cascade_info} in {processing_time}ms", {
                    "url": url,
                    "method": result.method,
                    "time_ms": processing_time,
                    "fields": data_summary,
                    "cascade_attempts": len(result.cascade_attempts) if result.cascade_attempts else 1,
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

                return True

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

                return False

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

            return False

    def stop(self):
        """Request worker to stop."""
        self._stop_requested = True

    def is_running(self) -> bool:
        """Check if worker is running."""
        return self._running
