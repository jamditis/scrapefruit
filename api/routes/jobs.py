"""Jobs API endpoints for creating, managing, and controlling scraping jobs."""

from functools import wraps
from flask import Blueprint, request, jsonify, g
from uuid import uuid4

from core.container import get_container

jobs_bp = Blueprint("jobs", __name__)


# =============================================================================
# Dependency helpers
# =============================================================================

def get_job_repo():
    """Get job repository from DI container."""
    return get_container().resolve("job_repository")


def get_url_repo():
    """Get URL repository from DI container."""
    return get_container().resolve("url_repository")


def get_rule_repo():
    """Get rule repository from DI container."""
    return get_container().resolve("rule_repository")


def get_orchestrator():
    """Get job orchestrator from DI container."""
    return get_container().resolve("job_orchestrator")


# =============================================================================
# Route decorators
# =============================================================================

def require_job(f):
    """Decorator that loads job and returns 404 if not found.

    Adds 'job' to flask.g for use in the route handler.
    The route must have job_id as a parameter.
    """
    @wraps(f)
    def decorated(job_id, *args, **kwargs):
        job = get_job_repo().get_job(job_id)
        if not job:
            return jsonify({"error": "Job not found"}), 404
        g.job = job
        return f(job_id, *args, **kwargs)
    return decorated


@jobs_bp.route("", methods=["GET"])
def list_jobs():
    """List all jobs with optional filtering."""
    status = request.args.get("status")
    include_archived = request.args.get("include_archived", "false").lower() == "true"
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)

    jobs = get_job_repo().list_jobs(
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
    job = get_job_repo().create_job(
        job_id=job_id,
        name=data.get("name", f"Job {job_id[:8]}"),
        mode=data.get("mode", "list"),
        template_id=data.get("template_id"),
        settings=data.get("settings", {}),
    )

    return jsonify({"job": job.to_dict()}), 201


@jobs_bp.route("/<job_id>", methods=["GET"])
@require_job
def get_job(job_id: str):
    """Get job details with rules. URLs are NOT included - use /urls endpoint with pagination."""
    rules = get_rule_repo().list_rules(job_id)
    return jsonify({
        "job": g.job.to_dict(),
        "rules": [r.to_dict() for r in rules],
    })


@jobs_bp.route("/<job_id>", methods=["PUT"])
@require_job
def update_job(job_id: str):
    """Update job configuration."""
    data = request.get_json()
    job = get_job_repo().update_job(job_id, **data)
    return jsonify({"job": job.to_dict()})


@jobs_bp.route("/<job_id>", methods=["DELETE"])
@require_job
def delete_job(job_id: str):
    """Delete a job and all associated data."""
    get_job_repo().delete_job(job_id)
    return jsonify({"message": "Job deleted"})


@jobs_bp.route("/<job_id>/archive", methods=["POST"])
@require_job
def archive_job(job_id: str):
    """Archive a job (hide from main list but keep data)."""
    if g.job.status == "running":
        return jsonify({"error": "Cannot archive a running job. Stop it first."}), 400
    job = get_job_repo().archive_job(job_id)
    return jsonify({"job": job.to_dict()})


@jobs_bp.route("/<job_id>/unarchive", methods=["POST"])
@require_job
def unarchive_job(job_id: str):
    """Restore an archived job to pending status."""
    if g.job.status != "archived":
        return jsonify({"error": "Job is not archived"}), 400
    job = get_job_repo().unarchive_job(job_id)
    return jsonify({"job": job.to_dict()})


# Job control endpoints
@jobs_bp.route("/<job_id>/start", methods=["POST"])
@require_job
def start_job(job_id: str):
    """Start a pending or paused job."""
    if g.job.status not in ("pending", "paused"):
        return jsonify({"error": f"Cannot start job with status '{g.job.status}'"}), 400
    get_orchestrator().start_job(job_id)
    job = get_job_repo().get_job(job_id)
    return jsonify({"job": job.to_dict()})


@jobs_bp.route("/<job_id>/pause", methods=["POST"])
@require_job
def pause_job(job_id: str):
    """Pause a running job."""
    if g.job.status != "running":
        return jsonify({"error": "Can only pause running jobs"}), 400
    get_orchestrator().pause_job(job_id)
    job = get_job_repo().get_job(job_id)
    return jsonify({"job": job.to_dict()})


@jobs_bp.route("/<job_id>/resume", methods=["POST"])
@require_job
def resume_job(job_id: str):
    """Resume a paused job."""
    if g.job.status != "paused":
        return jsonify({"error": "Can only resume paused jobs"}), 400
    get_orchestrator().resume_job(job_id)
    job = get_job_repo().get_job(job_id)
    return jsonify({"job": job.to_dict()})


@jobs_bp.route("/<job_id>/stop", methods=["POST"])
@require_job
def stop_job(job_id: str):
    """Stop a running or paused job."""
    if g.job.status not in ("running", "paused"):
        return jsonify({"error": "Can only stop running or paused jobs"}), 400
    get_orchestrator().stop_job(job_id)
    job = get_job_repo().get_job(job_id)
    return jsonify({"job": job.to_dict()})


# URL management endpoints
@jobs_bp.route("/<job_id>/urls", methods=["GET"])
@require_job
def list_urls(job_id: str):
    """List URLs for a job with pagination."""
    status = request.args.get("status")
    limit = min(request.args.get("limit", 50, type=int), 200)  # Cap at 200
    offset = request.args.get("offset", 0, type=int)

    urls = get_url_repo().list_urls(job_id, status=status, limit=limit, offset=offset)
    total = get_url_repo().count_urls(job_id, status=status)

    return jsonify({
        "urls": [u.to_dict() for u in urls],
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(urls) < total,
    })


@jobs_bp.route("/<job_id>/urls", methods=["POST"])
@require_job
def add_urls(job_id: str):
    """Add URLs to a job (single, list, or batch)."""
    data = request.get_json()
    urls_to_add = data.get("urls", [])

    # Handle single URL
    if isinstance(urls_to_add, str):
        urls_to_add = [urls_to_add]

    added = []
    for url in urls_to_add:
        url = url.strip()
        if url:
            url_obj = get_url_repo().add_url(job_id, url)
            added.append(url_obj.to_dict())

    # Update job progress total
    get_job_repo().update_job(job_id, progress_total=len(get_url_repo().list_urls(job_id)))

    return jsonify({"urls": added, "count": len(added)})


@jobs_bp.route("/<job_id>/urls/import-csv", methods=["POST"])
@require_job
def import_csv(job_id: str):
    """Import URLs from CSV content."""
    import csv
    from io import StringIO

    data = request.get_json()
    csv_content = data.get("csv", "")
    url_column = data.get("column", 0)

    reader = csv.reader(StringIO(csv_content))
    added = []

    for i, row in enumerate(reader):
        if i == 0 and data.get("has_header", True):
            continue  # Skip header
        try:
            url = row[url_column].strip() if isinstance(url_column, int) else row[0].strip()
            if url and url.startswith(("http://", "https://")):
                url_obj = get_url_repo().add_url(job_id, url)
                added.append(url_obj.to_dict())
        except (IndexError, AttributeError):
            continue

    get_job_repo().update_job(job_id, progress_total=len(get_url_repo().list_urls(job_id)))
    return jsonify({"urls": added, "count": len(added)})


@jobs_bp.route("/<job_id>/urls/<url_id>", methods=["DELETE"])
@require_job
def delete_url(job_id: str, url_id: str):
    """Remove a URL from a job."""
    get_url_repo().delete_url(url_id)
    get_job_repo().update_job(job_id, progress_total=len(get_url_repo().list_urls(job_id)))
    return jsonify({"message": "URL removed"})


# Rule management endpoints
@jobs_bp.route("/<job_id>/rules", methods=["GET"])
@require_job
def list_rules(job_id: str):
    """List extraction rules for a job."""
    rules = get_rule_repo().list_rules(job_id)
    return jsonify({"rules": [r.to_dict() for r in rules]})


@jobs_bp.route("/<job_id>/rules", methods=["POST"])
@require_job
def add_rule(job_id: str):
    """Add an extraction rule to a job."""
    data = request.get_json()
    rule = get_rule_repo().create_rule(
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
@require_job
def update_rule(job_id: str, rule_id: str):
    """Update an extraction rule."""
    data = request.get_json()
    rule = get_rule_repo().update_rule(rule_id, **data)
    if not rule:
        return jsonify({"error": "Rule not found"}), 404
    return jsonify({"rule": rule.to_dict()})


@jobs_bp.route("/<job_id>/rules/<rule_id>", methods=["DELETE"])
@require_job
def delete_rule(job_id: str, rule_id: str):
    """Delete an extraction rule."""
    get_rule_repo().delete_rule(rule_id)
    return jsonify({"message": "Rule deleted"})


# Results endpoints
@jobs_bp.route("/<job_id>/results", methods=["GET"])
@require_job
def list_results(job_id: str):
    """List scraping results for a job."""
    result_repo = get_container().resolve("result_repository")
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)
    results = result_repo.list_results(job_id, limit=limit, offset=offset)
    return jsonify({"results": [r.to_dict() for r in results]})


@jobs_bp.route("/<job_id>/progress", methods=["GET"])
@require_job
def get_progress(job_id: str):
    """Get real-time job progress."""
    job = g.job
    return jsonify({
        "status": job.status,
        "current": job.progress_current,
        "total": job.progress_total,
        "success": job.success_count,
        "failure": job.failure_count,
        "percent": (job.progress_current / job.progress_total * 100) if job.progress_total > 0 else 0,
    })


@jobs_bp.route("/<job_id>/logs", methods=["GET"])
@require_job
def get_logs(job_id: str):
    """Get job execution logs for real-time monitoring."""
    since_index = request.args.get("since", 0, type=int)
    level = request.args.get("level")
    log_data = get_orchestrator().get_job_logs(job_id, since_index=since_index, level=level)
    return jsonify({
        "logs": log_data["logs"],
        "total_count": log_data["total_count"],
        "current_index": log_data["current_index"],
        "job_status": g.job.status,
    })


@jobs_bp.route("/<job_id>/logs", methods=["DELETE"])
@require_job
def clear_logs(job_id: str):
    """Clear job logs."""
    get_orchestrator().clear_job_logs(job_id)
    return jsonify({"message": "Logs cleared"})


@jobs_bp.route("/<job_id>/reset", methods=["POST"])
@require_job
def reset_job(job_id: str):
    """Reset a job to pending state, allowing it to be restarted."""
    if g.job.status == "running":
        return jsonify({"error": "Cannot reset a running job. Stop it first."}), 400
    if g.job.status == "archived":
        return jsonify({"error": "Cannot reset an archived job. Unarchive it first."}), 400

    # Reset job status and counters
    job = get_job_repo().update_job(
        job_id,
        status="pending",
        progress_current=0,
        success_count=0,
        failure_count=0,
        error_message=None,
        started_at=None,
        completed_at=None,
    )

    # Reset all URL statuses and clear logs
    get_url_repo().reset_all_urls(job_id)
    get_orchestrator().clear_job_logs(job_id)

    return jsonify({"job": job.to_dict(), "message": "Job reset to pending"})
