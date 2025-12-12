"""Google Sheets export formatter."""

import json
from typing import Dict, Any

from database.repositories.result_repository import ResultRepository


def export_to_sheets(job_id: str, spreadsheet_id: str, worksheet_name: str) -> Dict[str, Any]:
    """
    Export job results to Google Sheets.

    Args:
        job_id: Job ID to export
        spreadsheet_id: Target Google Sheets ID
        worksheet_name: Worksheet name to create/update

    Returns:
        Dict with export status and row count
    """
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        # Load credentials (assumes GOOGLE_APPLICATION_CREDENTIALS env var)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]

        # Try to get credentials from environment
        import os
        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

        if not creds_path:
            raise ValueError("GOOGLE_APPLICATION_CREDENTIALS not set")

        credentials = Credentials.from_service_account_file(creds_path, scopes=scopes)
        client = gspread.authorize(credentials)

        # Open spreadsheet
        spreadsheet = client.open_by_key(spreadsheet_id)

        # Get or create worksheet
        try:
            worksheet = spreadsheet.worksheet(worksheet_name)
            worksheet.clear()
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(worksheet_name, rows=1000, cols=26)

        # Get results
        result_repo = ResultRepository()
        results = result_repo.list_results(job_id, limit=10000)

        if not results:
            return {"rows_exported": 0, "message": "No results to export"}

        # Collect all unique field names
        all_fields = set(["url", "scraped_at", "method"])
        for r in results:
            if r.data_json:
                try:
                    data = json.loads(r.data_json)
                    all_fields.update(data.keys())
                except json.JSONDecodeError:
                    pass

        # Sort fields
        fields = ["url", "scraped_at", "method"] + sorted(
            [f for f in all_fields if f not in ["url", "scraped_at", "method"]]
        )

        # Build rows
        rows = [fields]  # Header row

        for r in results:
            row = [
                r.url or "",
                r.scraped_at.isoformat() if r.scraped_at else "",
                r.scraping_method or "",
            ]

            if r.data_json:
                try:
                    data = json.loads(r.data_json)
                    for field in fields[3:]:
                        value = data.get(field, "")
                        if isinstance(value, list):
                            value = ", ".join(str(v) for v in value)
                        row.append(str(value) if value else "")
                except json.JSONDecodeError:
                    row.extend([""] * (len(fields) - 3))
            else:
                row.extend([""] * (len(fields) - 3))

            rows.append(row)

        # Write to sheet
        worksheet.update(f"A1:{chr(64 + len(fields))}{len(rows)}", rows)

        return {
            "rows_exported": len(rows) - 1,
            "fields": fields,
            "message": f"Exported {len(rows) - 1} rows to {worksheet_name}",
        }

    except ImportError:
        raise RuntimeError("gspread not installed. Run: pip install gspread google-auth")
    except Exception as e:
        raise RuntimeError(f"Export failed: {str(e)}")
