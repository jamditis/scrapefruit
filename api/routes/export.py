"""Export endpoints for downloading results."""

import json
import csv
from io import StringIO
from flask import Blueprint, request, jsonify, Response

from database.repositories.job_repository import JobRepository
from database.repositories.result_repository import ResultRepository

export_bp = Blueprint("export", __name__)
job_repo = JobRepository()
result_repo = ResultRepository()


@export_bp.route("/json", methods=["POST"])
def export_json():
    """Export job results as JSON."""
    data = request.get_json()
    job_id = data.get("job_id")

    if not job_id:
        return jsonify({"error": "job_id is required"}), 400

    job = job_repo.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    results = result_repo.list_results(job_id, limit=10000)

    export_data = {
        "job": {
            "id": job.id,
            "name": job.name,
            "mode": job.mode,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "success_count": job.success_count,
            "failure_count": job.failure_count,
        },
        "results": [
            {
                "url": r.url,
                "scraped_at": r.scraped_at.isoformat() if r.scraped_at else None,
                "method": r.scraping_method,
                "data": json.loads(r.data_json) if r.data_json else {},
            }
            for r in results
        ],
    }

    return Response(
        json.dumps(export_data, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename=scrapefruit_{job_id[:8]}.json"},
    )


@export_bp.route("/csv", methods=["POST"])
def export_csv():
    """Export job results as CSV."""
    data = request.get_json()
    job_id = data.get("job_id")

    if not job_id:
        return jsonify({"error": "job_id is required"}), 400

    job = job_repo.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    results = result_repo.list_results(job_id, limit=10000)

    # Collect all unique field names from results
    all_fields = set(["url", "scraped_at", "method"])
    for r in results:
        if r.data_json:
            try:
                result_data = json.loads(r.data_json)
                all_fields.update(result_data.keys())
            except json.JSONDecodeError:
                pass

    # Sort fields for consistent column order
    fields = ["url", "scraped_at", "method"] + sorted(
        [f for f in all_fields if f not in ["url", "scraped_at", "method"]]
    )

    # Build CSV
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()

    for r in results:
        row = {
            "url": r.url,
            "scraped_at": r.scraped_at.isoformat() if r.scraped_at else "",
            "method": r.scraping_method or "",
        }

        if r.data_json:
            try:
                result_data = json.loads(r.data_json)
                for key, value in result_data.items():
                    # Flatten lists to comma-separated strings
                    if isinstance(value, list):
                        row[key] = ", ".join(str(v) for v in value)
                    else:
                        row[key] = str(value) if value is not None else ""
            except json.JSONDecodeError:
                pass

        writer.writerow(row)

    csv_content = output.getvalue()

    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=scrapefruit_{job_id[:8]}.csv"},
    )


@export_bp.route("/sheets", methods=["POST"])
def export_sheets():
    """Export job results to Google Sheets."""
    data = request.get_json()
    job_id = data.get("job_id")
    spreadsheet_id = data.get("spreadsheet_id")
    worksheet_name = data.get("worksheet_name", "Scrapefruit Export")

    if not job_id:
        return jsonify({"error": "job_id is required"}), 400

    if not spreadsheet_id:
        return jsonify({"error": "spreadsheet_id is required"}), 400

    job = job_repo.get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    try:
        from core.output.formatters.sheets_formatter import export_to_sheets

        result = export_to_sheets(job_id, spreadsheet_id, worksheet_name)
        return jsonify({
            "success": True,
            "spreadsheet_id": spreadsheet_id,
            "worksheet": worksheet_name,
            "rows_exported": result.get("rows_exported", 0),
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500
