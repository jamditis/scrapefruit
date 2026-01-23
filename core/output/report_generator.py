"""Report generator for scrape job results.

Generates human-readable markdown reports from scrape job data with:
- Plain language summaries explaining what happened
- Success/failure statistics with visual indicators
- Issue categorization with actionable explanations
- Rule suggestion summaries from accessibility analysis

Usage:
    from core.output.report_generator import ReportGenerator

    generator = ReportGenerator()

    # Generate job completion report
    report = generator.generate_job_report(job_data, results, urls)

    # Generate analysis report
    report = generator.generate_analysis_report(samples, filtered_rules, intent)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from string import Template


@dataclass
class JobStats:
    """Statistics for a scrape job."""

    total_urls: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    pending: int = 0

    total_time_ms: int = 0
    avg_time_ms: float = 0.0

    total_data_fields: int = 0
    total_data_values: int = 0

    @property
    def success_rate(self) -> float:
        if self.total_urls == 0:
            return 0.0
        return (self.completed / self.total_urls) * 100

    @property
    def success_emoji(self) -> str:
        rate = self.success_rate
        if rate >= 90:
            return "✅"
        elif rate >= 70:
            return "⚠️"
        elif rate >= 50:
            return "🟡"
        else:
            return "❌"


@dataclass
class IssueCategory:
    """Categorized issue with explanation."""

    category: str
    count: int
    urls: List[str] = field(default_factory=list)
    explanation: str = ""
    suggestion: str = ""


# Issue explanations in plain language
ISSUE_EXPLANATIONS = {
    "timeout": {
        "explanation": "The page took too long to load. This often happens with slow servers or pages with heavy JavaScript.",
        "suggestion": "Try increasing the timeout setting or using a different fetcher strategy.",
    },
    "blocked": {
        "explanation": "The website blocked our request, likely detecting automated access.",
        "suggestion": "Consider using browser-based fetching (Playwright) or adding delays between requests.",
    },
    "404": {
        "explanation": "The page doesn't exist or was moved/deleted.",
        "suggestion": "Verify the URLs are correct and the content still exists.",
    },
    "403": {
        "explanation": "Access to this page is forbidden, possibly requiring authentication.",
        "suggestion": "Check if the page requires login or has access restrictions.",
    },
    "connection": {
        "explanation": "Could not connect to the server. The site may be down or blocking connections.",
        "suggestion": "Check if the website is accessible in a browser and try again later.",
    },
    "ssl": {
        "explanation": "There was a security certificate problem with the website.",
        "suggestion": "The site may have an expired or invalid SSL certificate.",
    },
    "empty": {
        "explanation": "The page loaded but contained no extractable content matching the rules.",
        "suggestion": "Review the extraction rules or check if the page structure has changed.",
    },
    "parse": {
        "explanation": "Could not parse the page content. The HTML may be malformed or use unusual encoding.",
        "suggestion": "Try using browser-based fetching which handles dynamic content better.",
    },
    "rate_limit": {
        "explanation": "The website is limiting how many requests we can make.",
        "suggestion": "Add longer delays between requests or reduce the number of concurrent requests.",
    },
    "unknown": {
        "explanation": "An unexpected error occurred during scraping.",
        "suggestion": "Check the error details and logs for more information.",
    },
}


# Markdown templates
JOB_REPORT_TEMPLATE = Template("""# Scrape job report

**Job ID:** `$job_id`
**Created:** $created_at
**Completed:** $completed_at
**Duration:** $duration

---

## Summary

$summary_emoji **$summary_headline**

$summary_description

### Statistics

| Metric | Value |
|--------|-------|
| Total URLs | $total_urls |
| Successful | $completed ✅ |
| Failed | $failed ❌ |
| Skipped | $skipped ⏭️ |
| Success rate | $success_rate% |
| Average time per URL | $avg_time |

---

## Results overview

$results_overview

$issues_section

$data_preview_section

---

## Fetcher performance

$fetcher_stats

---

*Report generated at $report_time*
""")


ISSUES_SECTION_TEMPLATE = Template("""
## Issues encountered

$issues_summary

$issue_details
""")


ISSUE_DETAIL_TEMPLATE = Template("""
### $emoji $category ($count URLs)

**What happened:** $explanation

**Suggestion:** $suggestion

<details>
<summary>Affected URLs</summary>

$url_list

</details>
""")


ANALYSIS_REPORT_TEMPLATE = Template("""# Scrape analysis report

**Intent:** $intent
**Samples analyzed:** $sample_count
**Generated:** $report_time

---

## Summary

$summary

### Filtering results

| Metric | Value |
|--------|-------|
| Total rules found | $total_rules |
| Rules after filtering | $filtered_rules |
| Filter method | $filter_method |
| Filter time | $filter_time |

---

## Recommended extraction rules

$rules_section

---

## Sample pages analyzed

$samples_section

---

## Next steps

$next_steps

---

*Report generated by scrapefruit accessibility analyzer*
""")


RULE_ITEM_TEMPLATE = Template("""
### $index. $name

| Property | Value |
|----------|-------|
| Selector | `$selector` |
| Type | $selector_type |
| Category | $category |
| Confidence | $confidence% |
| ARIA Role | $aria_role |

**Preview:** $preview

""")


class ReportGenerator:
    """
    Generates human-readable reports from scrape job results.

    Supports multiple report types:
    - Job completion reports (after scraping)
    - Analysis reports (after URL sampling and rule extraction)
    - Error summaries (for debugging)
    """

    def __init__(self):
        self._templates = {
            "job": JOB_REPORT_TEMPLATE,
            "issues": ISSUES_SECTION_TEMPLATE,
            "issue_detail": ISSUE_DETAIL_TEMPLATE,
            "analysis": ANALYSIS_REPORT_TEMPLATE,
            "rule_item": RULE_ITEM_TEMPLATE,
        }

    def generate_job_report(
        self,
        job: Dict[str, Any],
        urls: List[Dict[str, Any]],
        results: List[Dict[str, Any]],
        include_data_preview: bool = True,
        max_preview_items: int = 5,
    ) -> str:
        """
        Generate a markdown report for a completed scrape job.

        Args:
            job: Job data dictionary
            urls: List of URL records with status info
            results: List of scraped results
            include_data_preview: Whether to include sample data
            max_preview_items: Max data items to show in preview

        Returns:
            Markdown formatted report string
        """
        # Calculate statistics
        stats = self._calculate_job_stats(urls, results)

        # Categorize issues
        issues = self._categorize_issues(urls)

        # Generate sections
        summary = self._generate_summary(stats, issues)
        results_overview = self._generate_results_overview(stats, results)
        issues_section = self._generate_issues_section(issues) if issues else ""
        data_preview = self._generate_data_preview(results, max_preview_items) if include_data_preview else ""
        fetcher_stats = self._generate_fetcher_stats(urls)

        # Format timestamps
        created_at = self._format_datetime(job.get("created_at"))
        completed_at = self._format_datetime(job.get("completed_at")) or "In progress"
        duration = self._calculate_duration(job.get("created_at"), job.get("completed_at"))

        return self._templates["job"].substitute(
            job_id=job.get("id", "unknown"),
            created_at=created_at,
            completed_at=completed_at,
            duration=duration,
            summary_emoji=stats.success_emoji,
            summary_headline=summary["headline"],
            summary_description=summary["description"],
            total_urls=stats.total_urls,
            completed=stats.completed,
            failed=stats.failed,
            skipped=stats.skipped,
            success_rate=f"{stats.success_rate:.1f}",
            avg_time=self._format_duration_ms(stats.avg_time_ms),
            results_overview=results_overview,
            issues_section=issues_section,
            data_preview_section=data_preview,
            fetcher_stats=fetcher_stats,
            report_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    def generate_analysis_report(
        self,
        samples: List[Dict[str, Any]],
        filtered_result: Dict[str, Any],
        all_rules_count: int = 0,
    ) -> str:
        """
        Generate a markdown report for URL analysis and rule suggestions.

        Args:
            samples: List of analyzed sample pages
            filtered_result: FilteredRulesResult as dict
            all_rules_count: Total rules before filtering

        Returns:
            Markdown formatted report string
        """
        rules = filtered_result.get("rules", [])
        intent = filtered_result.get("intent", "")
        preset_used = filtered_result.get("preset_used")
        llm_used = filtered_result.get("llm_used", False)
        filter_time = filtered_result.get("filter_time_ms", 0)

        # Determine filter method description
        if preset_used:
            filter_method = f"Preset: {preset_used}"
        elif llm_used:
            provider = filtered_result.get("llm_provider", "unknown")
            filter_method = f"LLM ({provider})"
        else:
            filter_method = "Keyword matching"

        # Generate summary
        summary = self._generate_analysis_summary(samples, rules, intent)

        # Generate rules section
        rules_section = self._generate_rules_section(rules)

        # Generate samples section
        samples_section = self._generate_samples_section(samples)

        # Generate next steps
        next_steps = self._generate_next_steps(rules, samples)

        return self._templates["analysis"].substitute(
            intent=intent or "(no specific intent)",
            sample_count=len(samples),
            report_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            summary=summary,
            total_rules=all_rules_count or filtered_result.get("total_rules_before", len(rules)),
            filtered_rules=len(rules),
            filter_method=filter_method,
            filter_time=f"{filter_time}ms",
            rules_section=rules_section,
            samples_section=samples_section,
            next_steps=next_steps,
        )

    def generate_error_summary(
        self,
        urls: List[Dict[str, Any]],
    ) -> str:
        """
        Generate a concise error summary for failed URLs.

        Args:
            urls: List of URL records

        Returns:
            Markdown formatted error summary
        """
        issues = self._categorize_issues(urls)

        if not issues:
            return "No errors encountered."

        lines = ["## Error summary\n"]

        for issue in issues:
            emoji = self._get_issue_emoji(issue.category)
            lines.append(f"- {emoji} **{issue.category}** ({issue.count}): {issue.explanation}")

        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────────────────────
    # Private helper methods
    # ─────────────────────────────────────────────────────────────────────────

    def _calculate_job_stats(
        self,
        urls: List[Dict[str, Any]],
        results: List[Dict[str, Any]],
    ) -> JobStats:
        """Calculate statistics from job data."""
        stats = JobStats(total_urls=len(urls))

        total_time = 0
        completed_count = 0

        for url in urls:
            status = url.get("status", "pending")
            if status == "completed":
                stats.completed += 1
                completed_count += 1
                if url.get("processing_time_ms"):
                    total_time += url["processing_time_ms"]
            elif status == "failed":
                stats.failed += 1
            elif status == "skipped":
                stats.skipped += 1
            else:
                stats.pending += 1

        stats.total_time_ms = total_time
        if completed_count > 0:
            stats.avg_time_ms = total_time / completed_count

        # Count data fields and values
        for result in results:
            data = result.get("data", {})
            if isinstance(data, dict):
                stats.total_data_fields += len(data)
                stats.total_data_values += sum(
                    len(v) if isinstance(v, list) else 1
                    for v in data.values()
                )

        return stats

    def _categorize_issues(
        self,
        urls: List[Dict[str, Any]],
    ) -> List[IssueCategory]:
        """Categorize failed URLs by error type."""
        categories: Dict[str, List[str]] = {}

        for url in urls:
            if url.get("status") != "failed":
                continue

            error_type = url.get("error_type", "unknown") or "unknown"
            error_msg = (url.get("error_message") or "").lower()

            # Normalize error types
            category = self._normalize_error_type(error_type, error_msg)

            if category not in categories:
                categories[category] = []
            categories[category].append(url.get("url", "unknown"))

        # Convert to IssueCategory objects
        issues = []
        for cat, url_list in categories.items():
            info = ISSUE_EXPLANATIONS.get(cat, ISSUE_EXPLANATIONS["unknown"])
            issues.append(IssueCategory(
                category=cat,
                count=len(url_list),
                urls=url_list,
                explanation=info["explanation"],
                suggestion=info["suggestion"],
            ))

        # Sort by count (most common first)
        issues.sort(key=lambda x: -x.count)

        return issues

    def _normalize_error_type(self, error_type: str, error_msg: str) -> str:
        """Normalize error type to a standard category."""
        error_type = error_type.lower()

        # Check for specific patterns
        if "timeout" in error_type or "timeout" in error_msg:
            return "timeout"
        if "403" in error_type or "forbidden" in error_msg:
            return "403"
        if "404" in error_type or "not found" in error_msg:
            return "404"
        if "block" in error_msg or "captcha" in error_msg or "bot" in error_msg:
            return "blocked"
        if "connection" in error_type or "connect" in error_msg:
            return "connection"
        if "ssl" in error_type or "certificate" in error_msg:
            return "ssl"
        if "empty" in error_type or "no content" in error_msg:
            return "empty"
        if "parse" in error_type or "decode" in error_msg:
            return "parse"
        if "rate" in error_msg or "too many" in error_msg:
            return "rate_limit"

        return "unknown"

    def _generate_summary(
        self,
        stats: JobStats,
        issues: List[IssueCategory],
    ) -> Dict[str, str]:
        """Generate plain language summary."""
        rate = stats.success_rate

        if rate >= 95:
            headline = "Excellent results"
            description = f"Successfully scraped {stats.completed} of {stats.total_urls} URLs with minimal issues."
        elif rate >= 80:
            headline = "Good results with some issues"
            description = f"Scraped {stats.completed} URLs successfully. {stats.failed} URLs encountered problems."
        elif rate >= 50:
            headline = "Mixed results"
            description = f"About half of the URLs were scraped successfully. Review the issues below for details."
        else:
            headline = "Significant issues encountered"
            top_issue = issues[0].category if issues else "unknown errors"
            description = f"Most URLs failed to scrape. The main issue was {top_issue}. See recommendations below."

        if stats.total_data_values > 0:
            description += f" Extracted {stats.total_data_values} data values across {stats.total_data_fields} fields."

        return {"headline": headline, "description": description}

    def _generate_results_overview(
        self,
        stats: JobStats,
        results: List[Dict[str, Any]],
    ) -> str:
        """Generate results overview section."""
        if stats.completed == 0:
            return "No data was successfully extracted."

        lines = []

        # Show what fields were extracted
        all_fields: Dict[str, int] = {}
        for result in results:
            data = result.get("data", {})
            if isinstance(data, dict):
                for key, value in data.items():
                    if key not in all_fields:
                        all_fields[key] = 0
                    all_fields[key] += len(value) if isinstance(value, list) else 1

        if all_fields:
            lines.append("**Extracted fields:**\n")
            for field_name, count in sorted(all_fields.items(), key=lambda x: -x[1])[:10]:
                lines.append(f"- `{field_name}`: {count} values")

        return "\n".join(lines)

    def _generate_issues_section(
        self,
        issues: List[IssueCategory],
    ) -> str:
        """Generate the issues section."""
        if not issues:
            return ""

        total_failed = sum(i.count for i in issues)
        issues_summary = f"Encountered {total_failed} failed URLs across {len(issues)} issue types."

        issue_details = []
        for issue in issues:
            emoji = self._get_issue_emoji(issue.category)
            url_list = "\n".join(f"- `{url}`" for url in issue.urls[:10])
            if len(issue.urls) > 10:
                url_list += f"\n- ... and {len(issue.urls) - 10} more"

            detail = self._templates["issue_detail"].substitute(
                emoji=emoji,
                category=issue.category.replace("_", " ").title(),
                count=issue.count,
                explanation=issue.explanation,
                suggestion=issue.suggestion,
                url_list=url_list,
            )
            issue_details.append(detail)

        return self._templates["issues"].substitute(
            issues_summary=issues_summary,
            issue_details="\n".join(issue_details),
        )

    def _generate_data_preview(
        self,
        results: List[Dict[str, Any]],
        max_items: int = 5,
    ) -> str:
        """Generate data preview section."""
        if not results:
            return ""

        lines = ["\n## Data preview\n"]

        for i, result in enumerate(results[:max_items]):
            url = result.get("url", "unknown")
            data = result.get("data", {})

            lines.append(f"### Sample {i + 1}: `{url[:60]}{'...' if len(url) > 60 else ''}`\n")

            if isinstance(data, dict) and data:
                lines.append("```json")
                # Show first few fields
                preview_data = dict(list(data.items())[:5])
                import json
                lines.append(json.dumps(preview_data, indent=2, default=str)[:500])
                lines.append("```\n")
            else:
                lines.append("*No data extracted*\n")

        if len(results) > max_items:
            lines.append(f"\n*... and {len(results) - max_items} more results*")

        return "\n".join(lines)

    def _generate_fetcher_stats(
        self,
        urls: List[Dict[str, Any]],
    ) -> str:
        """Generate fetcher performance statistics."""
        fetcher_stats: Dict[str, Dict[str, int]] = {}

        for url in urls:
            method = url.get("scraping_method") or "unknown"
            if method not in fetcher_stats:
                fetcher_stats[method] = {"success": 0, "failed": 0, "total_time": 0}

            if url.get("status") == "completed":
                fetcher_stats[method]["success"] += 1
                fetcher_stats[method]["total_time"] += url.get("processing_time_ms", 0)
            elif url.get("status") == "failed":
                fetcher_stats[method]["failed"] += 1

        if not fetcher_stats:
            return "No fetcher data available."

        lines = ["| Fetcher | Success | Failed | Avg time |", "|---------|---------|--------|----------|"]

        for method, data in fetcher_stats.items():
            total = data["success"] + data["failed"]
            avg_time = data["total_time"] / data["success"] if data["success"] > 0 else 0
            lines.append(f"| {method} | {data['success']} | {data['failed']} | {self._format_duration_ms(avg_time)} |")

        return "\n".join(lines)

    def _generate_analysis_summary(
        self,
        samples: List[Dict[str, Any]],
        rules: List[Dict[str, Any]],
        intent: str,
    ) -> str:
        """Generate analysis summary."""
        successful = len([s for s in samples if s.get("success", False)])

        if not rules:
            return f"Analyzed {len(samples)} pages but could not find extraction rules matching your intent."

        # Categorize rules
        categories = {}
        for rule in rules:
            cat = rule.get("category", "general")
            if cat not in categories:
                categories[cat] = 0
            categories[cat] += 1

        cat_summary = ", ".join(f"{count} {cat}" for cat, count in sorted(categories.items(), key=lambda x: -x[1]))

        return f"""Analyzed {successful} pages and identified {len(rules)} relevant extraction rules.

**Rule breakdown:** {cat_summary}

The rules below are ranked by relevance to your intent and confidence score."""

    def _generate_rules_section(
        self,
        rules: List[Dict[str, Any]],
    ) -> str:
        """Generate rules section."""
        if not rules:
            return "*No rules to display*"

        lines = []
        for i, rule in enumerate(rules[:15]):  # Limit to top 15
            preview = rule.get("preview", "")
            if len(preview) > 80:
                preview = preview[:80] + "..."

            item = self._templates["rule_item"].substitute(
                index=i + 1,
                name=rule.get("name", "unnamed"),
                selector=rule.get("selector_value", ""),
                selector_type=rule.get("selector_type", "css"),
                category=rule.get("category", "general"),
                confidence=int(rule.get("confidence", 0) * 100),
                aria_role=rule.get("aria_role") or "—",
                preview=f"`{preview}`" if preview else "*none*",
            )
            lines.append(item)

        if len(rules) > 15:
            lines.append(f"\n*... and {len(rules) - 15} more rules*")

        return "\n".join(lines)

    def _generate_samples_section(
        self,
        samples: List[Dict[str, Any]],
    ) -> str:
        """Generate samples section."""
        if not samples:
            return "*No samples analyzed*"

        lines = ["| URL | Status | Elements |", "|-----|--------|----------|"]

        for sample in samples[:10]:
            url = sample.get("url", "unknown")
            if len(url) > 50:
                url = url[:47] + "..."
            success = "✅" if sample.get("success") else "❌"
            elements = sample.get("element_count", 0)
            lines.append(f"| `{url}` | {success} | {elements} |")

        if len(samples) > 10:
            lines.append(f"\n*... and {len(samples) - 10} more samples*")

        return "\n".join(lines)

    def _generate_next_steps(
        self,
        rules: List[Dict[str, Any]],
        samples: List[Dict[str, Any]],
    ) -> str:
        """Generate next steps recommendations."""
        steps = []

        if rules:
            steps.append("1. **Review the rules** - Check that the suggested selectors match what you want to extract")
            steps.append("2. **Test on a few URLs** - Run a small scrape to verify the rules work correctly")
            steps.append("3. **Refine if needed** - Adjust rules or add custom selectors based on test results")
            steps.append("4. **Run full scrape** - Once satisfied, run the scrape on your full URL list")
        else:
            steps.append("1. **Try different intent** - Rephrase what you're looking for")
            steps.append("2. **Use a preset** - Try one of the built-in presets (articles, media, data, etc.)")
            steps.append("3. **Check the pages** - Verify the sample URLs contain the content you expect")

        return "\n".join(steps)

    def _get_issue_emoji(self, category: str) -> str:
        """Get emoji for issue category."""
        emoji_map = {
            "timeout": "⏱️",
            "blocked": "🚫",
            "403": "🔒",
            "404": "🔍",
            "connection": "📡",
            "ssl": "🔐",
            "empty": "📭",
            "parse": "📄",
            "rate_limit": "🐢",
            "unknown": "❓",
        }
        return emoji_map.get(category, "❓")

    def _format_datetime(self, dt: Any) -> str:
        """Format datetime for display."""
        if dt is None:
            return "—"
        if isinstance(dt, str):
            try:
                dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
            except ValueError:
                return dt
        if isinstance(dt, datetime):
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        return str(dt)

    def _format_duration_ms(self, ms: float) -> str:
        """Format duration in milliseconds to human readable."""
        if ms < 1000:
            return f"{ms:.0f}ms"
        elif ms < 60000:
            return f"{ms / 1000:.1f}s"
        else:
            return f"{ms / 60000:.1f}m"

    def _calculate_duration(self, start: Any, end: Any) -> str:
        """Calculate duration between two timestamps."""
        if not start or not end:
            return "—"

        try:
            if isinstance(start, str):
                start = datetime.fromisoformat(start.replace("Z", "+00:00"))
            if isinstance(end, str):
                end = datetime.fromisoformat(end.replace("Z", "+00:00"))

            delta = end - start
            seconds = delta.total_seconds()

            if seconds < 60:
                return f"{seconds:.1f} seconds"
            elif seconds < 3600:
                return f"{seconds / 60:.1f} minutes"
            else:
                return f"{seconds / 3600:.1f} hours"
        except (ValueError, TypeError):
            return "—"


# Convenience function for quick report generation
def generate_job_report(
    job: Dict[str, Any],
    urls: List[Dict[str, Any]],
    results: List[Dict[str, Any]],
) -> str:
    """Generate a job completion report."""
    return ReportGenerator().generate_job_report(job, urls, results)


def generate_analysis_report(
    samples: List[Dict[str, Any]],
    filtered_result: Dict[str, Any],
    all_rules_count: int = 0,
) -> str:
    """Generate an analysis report."""
    return ReportGenerator().generate_analysis_report(samples, filtered_result, all_rules_count)
