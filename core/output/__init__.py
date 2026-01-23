"""Output and export module.

Provides report generation and data export functionality.

Report generation:
    from core.output import ReportGenerator, generate_job_report, generate_analysis_report

    # Generate job completion report
    report = generate_job_report(job, urls, results)

    # Generate analysis report
    report = generate_analysis_report(samples, filtered_result)
"""

from core.output.report_generator import (
    ReportGenerator,
    JobStats,
    IssueCategory,
    generate_job_report,
    generate_analysis_report,
    ISSUE_EXPLANATIONS,
)

__all__ = [
    "ReportGenerator",
    "JobStats",
    "IssueCategory",
    "generate_job_report",
    "generate_analysis_report",
    "ISSUE_EXPLANATIONS",
]
