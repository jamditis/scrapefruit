"""Jobs API endpoints for creating, managing, and controlling scraping jobs."""

from flask import Blueprint, request, jsonify
from uuid import uuid4

from database.repositories.job_repository import JobRepository
from database.repositories.url_repository import UrlRepository
from database.repositories.rule_repository import RuleRepository
from core.jobs.orchestrator import JobOrchestrator

jobs_bp = Blueprint("jobs", __name__)
job_repo = JobRepository()
url_repo = UrlRepository()
rule_repo = RuleRepository()
orchestrator = JobOrchestrator()


@jobs_bp.route("", methods=["GET"])
def list_jobs():
    """List all jobs with optional filtering."""
    status = request.args.get("status")
    include_archived = request.args.get("include_archived", "false").lower() == "true"
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)

    jobs = job_repo.list_jobs(
        status=status,
        include_archived=include_archived,
        limit=limit,
        offset=offset
    )
    return jsonify({"jobs": [j.to_dict() for j in jobs], "total": len(jobs)})


@jobs_bp.route("", methods=["POST"])
def create_job():
    """Create a new scraping job."""
    data = request.get_json()

    job_id = str(uuid4())
    job = job_repo.create_job(
        job_id=job_id,
        name=data.get("name", f"Job {job_id[:8]}"),
        mode=data.get("mode", "list"),
        template_id=data.get("template_id"),
        settings=data.get("settings", {}),
    )

    return jsonify({"job": job.to_dict()}), 201


@jobs_bp.route("/<job_id>", methods=["GET"])
def get_job(job_id: str):
    """Get job details with rules. URLs are NOT included - use /urls endpoint with pagination."""
    job = job_repo.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    rules = rule_repo.list_rules(job_id)

    # Only return job and rules - URLs are fetched separately via paginated endpoint
    return jsonify({
        "job": job.to_dict(),
        "rules": [r.to_dict() for r in rules],
    })


@jobs_bp.route("/<job_id>", methods=["PUT"])
def update_job(job_id: str):
    """Update job configuration."""
    job = job_repo.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    data = request.get_json()
    job = job_repo.update_job(job_id, **data)
    return jsonify({"job": job.to_dict()})


@jobs_bp.route("/<job_id>", methods=["DELETE"])
def delete_job(job_id: str):
    """Delete a job and all associated data."""
    job = job_repo.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    job_repo.delete_job(job_id)
    return jsonify({"message": "Job deleted"})


@jobs_bp.route("/<job_id>/archive", methods=["POST"])
def archive_job(job_id: str):
    """Archive a job (hide from main list but keep data)."""
    job = job_repo.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job.status == "running":
        return jsonify({"error": "Cannot archive a running job. Stop it first."}), 400

    job = job_repo.archive_job(job_id)
    return jsonify({"job": job.to_dict()})


@jobs_bp.route("/<job_id>/unarchive", methods=["POST"])
def unarchive_job(job_id: str):
    """Restore an archived job to pending status."""
    job = job_repo.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job.status != "archived":
        return jsonify({"error": "Job is not archived"}), 400

    job = job_repo.unarchive_job(job_id)
    return jsonify({"job": job.to_dict()})


# Job control endpoints
@jobs_bp.route("/<job_id>/start", methods=["POST"])
def start_job(job_id: str):
    """Start a pending or paused job."""
    job = job_repo.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job.status not in ("pending", "paused"):
        return jsonify({"error": f"Cannot start job with status '{job.status}'"}), 400

    orchestrator.start_job(job_id)
    job = job_repo.get_job(job_id)
    return jsonify({"job": job.to_dict()})


@jobs_bp.route("/<job_id>/pause", methods=["POST"])
def pause_job(job_id: str):
    """Pause a running job."""
    job = job_repo.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job.status != "running":
        return jsonify({"error": "Can only pause running jobs"}), 400

    orchestrator.pause_job(job_id)
    job = job_repo.get_job(job_id)
    return jsonify({"job": job.to_dict()})


@jobs_bp.route("/<job_id>/resume", methods=["POST"])
def resume_job(job_id: str):
    """Resume a paused job."""
    job = job_repo.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job.status != "paused":
        return jsonify({"error": "Can only resume paused jobs"}), 400

    orchestrator.resume_job(job_id)
    job = job_repo.get_job(job_id)
    return jsonify({"job": job.to_dict()})


@jobs_bp.route("/<job_id>/stop", methods=["POST"])
def stop_job(job_id: str):
    """Stop a running or paused job."""
    job = job_repo.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    if job.status not in ("running", "paused"):
        return jsonify({"error": "Can only stop running or paused jobs"}), 400

    orchestrator.stop_job(job_id)
    job = job_repo.get_job(job_id)
    return jsonify({"job": job.to_dict()})


# URL management endpoints
@jobs_bp.route("/<job_id>/urls", methods=["GET"])
def list_urls(job_id: str):
    """List URLs for a job with pagination."""
    job = job_repo.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    status = request.args.get("status")
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)

    # Cap limit to prevent huge requests
    limit = min(limit, 200)

    urls = url_repo.list_urls(job_id, status=status, limit=limit, offset=offset)
    total = url_repo.count_urls(job_id, status=status)

    return jsonify({
        "urls": [u.to_dict() for u in urls],
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(urls) < total,
    })


@jobs_bp.route("/<job_id>/urls", methods=["POST"])
def add_urls(job_id: str):
    """Add URLs to a job (single, list, or batch)."""
    job = job_repo.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    data = request.get_json()
    urls_to_add = data.get("urls", [])

    # Handle single URL
    if isinstance(urls_to_add, str):
        urls_to_add = [urls_to_add]

    added = []
    for url in urls_to_add:
        url = url.strip()
        if url:
            url_obj = url_repo.add_url(job_id, url)
            added.append(url_obj.to_dict())

    # Update job progress total
    job_repo.update_job(job_id, progress_total=len(url_repo.list_urls(job_id)))

    return jsonify({"urls": added, "count": len(added)})


@jobs_bp.route("/<job_id>/urls/import-csv", methods=["POST"])
def import_csv(job_id: str):
    """Import URLs from CSV content."""
    job = job_repo.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    data = request.get_json()
    csv_content = data.get("csv", "")
    url_column = data.get("column", 0)  # Column index or name

    # Parse CSV
    import csv
    from io import StringIO

    reader = csv.reader(StringIO(csv_content))
    added = []

    for i, row in enumerate(reader):
        if i == 0 and data.get("has_header", True):
            continue  # Skip header

        try:
            if isinstance(url_column, int):
                url = row[url_column].strip()
            else:
                # Column name lookup would need header
                url = row[0].strip()

            if url and url.startswith(("http://", "https://")):
                url_obj = url_repo.add_url(job_id, url)
                added.append(url_obj.to_dict())
        except (IndexError, AttributeError):
            continue

    # Update job progress total
    job_repo.update_job(job_id, progress_total=len(url_repo.list_urls(job_id)))

    return jsonify({"urls": added, "count": len(added)})


@jobs_bp.route("/<job_id>/urls/<url_id>", methods=["DELETE"])
def delete_url(job_id: str, url_id: str):
    """Remove a URL from a job."""
    url_repo.delete_url(url_id)
    job_repo.update_job(job_id, progress_total=len(url_repo.list_urls(job_id)))
    return jsonify({"message": "URL removed"})


# Rule management endpoints
@jobs_bp.route("/<job_id>/rules", methods=["GET"])
def list_rules(job_id: str):
    """List extraction rules for a job."""
    job = job_repo.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    rules = rule_repo.list_rules(job_id)
    return jsonify({"rules": [r.to_dict() for r in rules]})


@jobs_bp.route("/<job_id>/rules", methods=["POST"])
def add_rule(job_id: str):
    """Add an extraction rule to a job."""
    job = job_repo.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    data = request.get_json()
    rule = rule_repo.create_rule(
        job_id=job_id,
        name=data["name"],
        selector_type=data.get("selector_type", "css"),
        selector_value=data["selector_value"],
        attribute=data.get("attribute"),
        is_required=data.get("is_required", False),
        is_list=data.get("is_list", False),
    )

    return jsonify({"rule": rule.to_dict()}), 201


@jobs_bp.route("/<job_id>/rules/<rule_id>", methods=["PUT"])
def update_rule(job_id: str, rule_id: str):
    """Update an extraction rule."""
    data = request.get_json()
    rule = rule_repo.update_rule(rule_id, **data)
    if not rule:
        return jsonify({"error": "Rule not found"}), 404
    return jsonify({"rule": rule.to_dict()})


@jobs_bp.route("/<job_id>/rules/<rule_id>", methods=["DELETE"])
def delete_rule(job_id: str, rule_id: str):
    """Delete an extraction rule."""
    rule_repo.delete_rule(rule_id)
    return jsonify({"message": "Rule deleted"})


# Results endpoints
@jobs_bp.route("/<job_id>/results", methods=["GET"])
def list_results(job_id: str):
    """List scraping results for a job."""
    from database.repositories.result_repository import ResultRepository

    job = job_repo.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    result_repo = ResultRepository()
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)

    results = result_repo.list_results(job_id, limit=limit, offset=offset)
    return jsonify({"results": [r.to_dict() for r in results]})


@jobs_bp.route("/<job_id>/progress", methods=["GET"])
def get_progress(job_id: str):
    """Get real-time job progress."""
    job = job_repo.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    return jsonify({
        "status": job.status,
        "current": job.progress_current,
        "total": job.progress_total,
        "success": job.success_count,
        "failure": job.failure_count,
        "percent": (job.progress_current / job.progress_total * 100) if job.progress_total > 0 else 0,
    })


@jobs_bp.route("/<job_id>/logs", methods=["GET"])
def get_logs(job_id: str):
    """
    Get job execution logs for real-time monitoring.

    Query params:
        since: Only return logs after this index (for polling)
        level: Filter by log level (info, success, warning, error, debug)
    """
    job = job_repo.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    since_index = request.args.get("since", 0, type=int)
    level = request.args.get("level")

    log_data = orchestrator.get_job_logs(job_id, since_index=since_index, level=level)

    return jsonify({
        "logs": log_data["logs"],
        "total_count": log_data["total_count"],
        "current_index": log_data["current_index"],
        "job_status": job.status,
    })


@jobs_bp.route("/<job_id>/logs", methods=["DELETE"])
def clear_logs(job_id: str):
    """Clear job logs."""
    job = job_repo.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    orchestrator.clear_job_logs(job_id)
    return jsonify({"message": "Logs cleared"})
