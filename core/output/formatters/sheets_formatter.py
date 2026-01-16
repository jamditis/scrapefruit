"""Google Sheets export formatter with detailed error handling."""

import json
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from database.repositories.result_repository import ResultRepository


class SheetsErrorType(str, Enum):
    """Types of Google Sheets export errors."""
    MISSING_CREDENTIALS = "missing_credentials"
    INVALID_CREDENTIALS = "invalid_credentials"
    SPREADSHEET_NOT_FOUND = "spreadsheet_not_found"
    PERMISSION_DENIED = "permission_denied"
    WORKSHEET_ERROR = "worksheet_error"
    RATE_LIMITED = "rate_limited"
    NETWORK_ERROR = "network_error"
    INVALID_DATA = "invalid_data"
    DEPENDENCY_MISSING = "dependency_missing"
    UNKNOWN = "unknown"


@dataclass
class SheetsExportError(Exception):
    """Detailed error for Sheets export failures."""
    error_type: SheetsErrorType
    message: str
    details: Optional[str] = None
    suggestion: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_type": self.error_type.value,
            "message": self.message,
            "details": self.details,
            "suggestion": self.suggestion,
        }


def _get_credentials_path() -> Optional[str]:
    """Get path to Google credentials file."""
    # Check multiple possible locations
    paths_to_try = [
        os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
        os.getenv("GOOGLE_CREDENTIALS_PATH"),
        os.path.expanduser("~/.config/gcloud/application_default_credentials.json"),
        os.path.expanduser("~/google-credentials.json"),
        "credentials.json",
        "google-credentials.json",
    ]

    for path in paths_to_try:
        if path and os.path.isfile(path):
            return path

    return None


def export_to_sheets(
    job_id: str,
    spreadsheet_id: str,
    worksheet_name: str,
    credentials_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Export job results to Google Sheets with detailed error handling.

    Args:
        job_id: Job ID to export
        spreadsheet_id: Target Google Sheets ID
        worksheet_name: Worksheet name to create/update
        credentials_path: Optional path to credentials file

    Returns:
        Dict with export status and row count

    Raises:
        SheetsExportError: With detailed error information
    """
    # Check for required dependencies
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        from google.auth.exceptions import RefreshError
    except ImportError as e:
        raise SheetsExportError(
            error_type=SheetsErrorType.DEPENDENCY_MISSING,
            message="Required packages not installed",
            details=str(e),
            suggestion="Install with: pip install gspread google-auth",
        )

    # Find credentials
    creds_path = credentials_path or _get_credentials_path()

    if not creds_path:
        raise SheetsExportError(
            error_type=SheetsErrorType.MISSING_CREDENTIALS,
            message="Google credentials not found",
            details="No credentials file found in expected locations",
            suggestion=(
                "Set GOOGLE_APPLICATION_CREDENTIALS environment variable to "
                "the path of your service account JSON file. Get one from "
                "Google Cloud Console > IAM & Admin > Service Accounts."
            ),
        )

    if not os.path.isfile(creds_path):
        raise SheetsExportError(
            error_type=SheetsErrorType.MISSING_CREDENTIALS,
            message=f"Credentials file not found: {creds_path}",
            suggestion="Check that the credentials file path is correct.",
        )

    # Load and validate credentials
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        credentials = Credentials.from_service_account_file(creds_path, scopes=scopes)
    except ValueError as e:
        raise SheetsExportError(
            error_type=SheetsErrorType.INVALID_CREDENTIALS,
            message="Invalid credentials file format",
            details=str(e),
            suggestion="Ensure the file is a valid Google service account JSON.",
        )
    except Exception as e:
        raise SheetsExportError(
            error_type=SheetsErrorType.INVALID_CREDENTIALS,
            message="Failed to load credentials",
            details=str(e),
        )

    # Authorize gspread client
    try:
        client = gspread.authorize(credentials)
    except RefreshError as e:
        raise SheetsExportError(
            error_type=SheetsErrorType.INVALID_CREDENTIALS,
            message="Credentials expired or revoked",
            details=str(e),
            suggestion="Re-download the service account key from Google Cloud Console.",
        )
    except Exception as e:
        raise SheetsExportError(
            error_type=SheetsErrorType.NETWORK_ERROR,
            message="Failed to authenticate with Google",
            details=str(e),
            suggestion="Check your internet connection and try again.",
        )

    # Open spreadsheet
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
    except gspread.exceptions.SpreadsheetNotFound:
        raise SheetsExportError(
            error_type=SheetsErrorType.SPREADSHEET_NOT_FOUND,
            message=f"Spreadsheet not found: {spreadsheet_id}",
            suggestion=(
                "Check the spreadsheet ID is correct. You can find it in the "
                "spreadsheet URL: docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit"
            ),
        )
    except gspread.exceptions.APIError as e:
        error_data = e.response.json() if hasattr(e, 'response') else {}
        error_code = error_data.get("error", {}).get("code", 0)
        error_msg = error_data.get("error", {}).get("message", str(e))

        if error_code == 403:
            raise SheetsExportError(
                error_type=SheetsErrorType.PERMISSION_DENIED,
                message="Access denied to spreadsheet",
                details=error_msg,
                suggestion=(
                    "Share the spreadsheet with the service account email. "
                    "Find it in your credentials JSON under 'client_email'."
                ),
            )
        elif error_code == 429:
            raise SheetsExportError(
                error_type=SheetsErrorType.RATE_LIMITED,
                message="Google API rate limit exceeded",
                details=error_msg,
                suggestion="Wait a few minutes and try again.",
            )
        else:
            raise SheetsExportError(
                error_type=SheetsErrorType.UNKNOWN,
                message="API error accessing spreadsheet",
                details=error_msg,
            )
    except Exception as e:
        raise SheetsExportError(
            error_type=SheetsErrorType.NETWORK_ERROR,
            message="Failed to open spreadsheet",
            details=str(e),
        )

    # Get or create worksheet
    try:
        try:
            worksheet = spreadsheet.worksheet(worksheet_name)
            worksheet.clear()
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(worksheet_name, rows=1000, cols=26)
    except gspread.exceptions.APIError as e:
        error_data = e.response.json() if hasattr(e, 'response') else {}
        error_msg = error_data.get("error", {}).get("message", str(e))

        raise SheetsExportError(
            error_type=SheetsErrorType.WORKSHEET_ERROR,
            message=f"Failed to create/access worksheet '{worksheet_name}'",
            details=error_msg,
        )
    except Exception as e:
        raise SheetsExportError(
            error_type=SheetsErrorType.WORKSHEET_ERROR,
            message="Worksheet operation failed",
            details=str(e),
        )

    # Get results
    try:
        result_repo = ResultRepository()
        results = result_repo.list_results(job_id, limit=10000)
    except Exception as e:
        raise SheetsExportError(
            error_type=SheetsErrorType.INVALID_DATA,
            message="Failed to retrieve results from database",
            details=str(e),
        )

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

    # Sort fields (url, scraped_at, method first, then alphabetical)
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
    try:
        # Calculate range (A1:Z100 format)
        end_col = chr(64 + min(len(fields), 26))  # Cap at Z
        range_str = f"A1:{end_col}{len(rows)}"
        worksheet.update(range_str, rows)
    except gspread.exceptions.APIError as e:
        error_data = e.response.json() if hasattr(e, 'response') else {}
        error_code = error_data.get("error", {}).get("code", 0)
        error_msg = error_data.get("error", {}).get("message", str(e))

        if error_code == 429:
            raise SheetsExportError(
                error_type=SheetsErrorType.RATE_LIMITED,
                message="Google API rate limit exceeded during write",
                details=error_msg,
                suggestion="Wait a few minutes and try again.",
            )
        else:
            raise SheetsExportError(
                error_type=SheetsErrorType.WORKSHEET_ERROR,
                message="Failed to write data to worksheet",
                details=error_msg,
            )
    except Exception as e:
        raise SheetsExportError(
            error_type=SheetsErrorType.UNKNOWN,
            message="Export write operation failed",
            details=str(e),
        )

    return {
        "rows_exported": len(rows) - 1,
        "fields": fields,
        "message": f"Exported {len(rows) - 1} rows to {worksheet_name}",
    }
