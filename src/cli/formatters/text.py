"""Text formatter for terminal output"""

from typing import Dict, Any
from src.schemas.base_schemas import ValidationResult, ValidationSeverity


class TextFormatter:
    """Format validation results for terminal display"""

    def __init__(self, use_color: bool = True):
        """
        Initialize text formatter.

        Args:
            use_color: Whether to use ANSI color codes
        """
        self.use_color = use_color

    def format(self, result: ValidationResult) -> str:
        """
        Format validation result as text.

        Args:
            result: ValidationResult from validator

        Returns:
            Formatted text string
        """
        lines = []

        # Header
        lines.append("=" * 60)
        lines.append("             VALIDATION REPORT")
        lines.append("=" * 60)
        lines.append("")

        # Metadata
        metadata = result.metadata or {}
        shape = metadata.get('shape', {})
        genes = shape.get('genes', 'N/A')
        samples = shape.get('samples', 'N/A')
        missing_pct = metadata.get('missing_pct', 0)
        value_range = metadata.get('value_range', {})

        lines.append("Dataset Information")
        lines.append("-" * 60)
        lines.append(f"Genes: {genes:,}" if isinstance(genes, int) else f"Genes: {genes}")
        lines.append(f"Samples: {samples}")
        lines.append(f"Missing: {missing_pct:.2f}%")

        if value_range:
            val_min = value_range.get('min', 'N/A')
            val_max = value_range.get('max', 'N/A')
            if isinstance(val_min, (int, float)) and isinstance(val_max, (int, float)):
                lines.append(f"Value range: [{val_min:.2f}, {val_max:.2f}]")

        lines.append("")

        # Overall status
        status_icon = self._get_status_icon(result.severity)
        status_text = "PASSED" if result.passed else "FAILED"
        status_line = f"Status: {status_icon} {status_text}"

        if self.use_color:
            if result.passed:
                status_line = f"\033[92m{status_line}\033[0m"  # Green
            else:
                status_line = f"\033[91m{status_line}\033[0m"  # Red

        lines.append(status_line)
        lines.append("-" * 60)
        lines.append("")

        # Issues summary
        if result.issues:
            # Count by severity
            severity_counts = {}
            for issue in result.issues:
                sev = issue.severity.value
                severity_counts[sev] = severity_counts.get(sev, 0) + 1

            lines.append("Issues Found")
            lines.append("-" * 60)

            # Group issues by severity
            critical_issues = [i for i in result.issues if i.severity == ValidationSeverity.CRITICAL]
            error_issues = [i for i in result.issues if i.severity == ValidationSeverity.ERROR]
            warning_issues = [i for i in result.issues if i.severity == ValidationSeverity.WARNING]
            info_issues = [i for i in result.issues if i.severity == ValidationSeverity.INFO]

            # Display critical/error issues first
            for issue in critical_issues + error_issues:
                icon = self._get_severity_icon(issue.severity)
                msg = f"{icon} {issue.severity.value.upper()}: {issue.message}"
                if self.use_color:
                    msg = self._colorize_severity(msg, issue.severity)
                lines.append(msg)

                # Show examples if available
                if issue.metadata and 'examples' in issue.metadata:
                    examples = issue.metadata['examples']
                    if examples:
                        lines.append(f"    Examples: {', '.join(str(e) for e in examples[:5])}")

            lines.append("")

            # Display warnings (collapsed)
            if warning_issues:
                lines.append(f"⚠️  {len(warning_issues)} Warning(s):")
                for issue in warning_issues[:3]:
                    lines.append(f"    • {issue.message}")
                if len(warning_issues) > 3:
                    lines.append(f"    ... and {len(warning_issues) - 3} more warnings")
                lines.append("")

            # Display info (collapsed)
            if info_issues:
                lines.append(f"ℹ️  {len(info_issues)} Info message(s)")
                lines.append("")

        else:
            lines.append("✅ No issues found - data looks great!")
            lines.append("")

        # Summary
        lines.append("Summary")
        lines.append("-" * 60)

        if result.passed:
            lines.append("✅ Data quality is acceptable for analysis")
        else:
            lines.append("❌ Data has critical issues - review required")

        lines.append("")
        lines.append(f"Validation time: {result.execution_time_ms / 1000:.2f} seconds")

        # Cache stats if available
        if metadata.get('cache_hits') or metadata.get('cache_misses'):
            cache_hits = metadata.get('cache_hits', 0)
            cache_total = cache_hits + metadata.get('cache_misses', 0)
            if cache_total > 0:
                hit_rate = (cache_hits / cache_total) * 100
                lines.append(f"Cache hits: {cache_hits:,}/{cache_total:,} ({hit_rate:.1f}%)")

        lines.append("")

        return "\n".join(lines)

    def _get_status_icon(self, severity: ValidationSeverity) -> str:
        """Get icon for overall status"""
        if severity in [ValidationSeverity.CRITICAL, ValidationSeverity.ERROR]:
            return "❌"
        elif severity == ValidationSeverity.WARNING:
            return "⚠️ "
        else:
            return "✅"

    def _get_severity_icon(self, severity: ValidationSeverity) -> str:
        """Get icon for severity level"""
        icons = {
            ValidationSeverity.CRITICAL: "🚨",
            ValidationSeverity.ERROR: "❌",
            ValidationSeverity.WARNING: "⚠️ ",
            ValidationSeverity.INFO: "ℹ️ "
        }
        return icons.get(severity, "•")

    def _colorize_severity(self, text: str, severity: ValidationSeverity) -> str:
        """Add ANSI color codes based on severity"""
        colors = {
            ValidationSeverity.CRITICAL: "\033[91m",  # Red
            ValidationSeverity.ERROR: "\033[91m",  # Red
            ValidationSeverity.WARNING: "\033[93m",  # Yellow
            ValidationSeverity.INFO: "\033[94m"  # Blue
        }
        color = colors.get(severity, "")
        reset = "\033[0m"
        return f"{color}{text}{reset}"


class CompactTextFormatter(TextFormatter):
    """Compact text formatter for quick output"""

    def format(self, result: ValidationResult) -> str:
        """Format as single-line summary"""
        status = "✅ PASS" if result.passed else "❌ FAIL"

        metadata = result.metadata or {}
        shape = metadata.get('shape', {})
        genes = shape.get('genes', '?')
        samples = shape.get('samples', '?')

        issue_count = len(result.issues)
        time_s = result.execution_time_ms / 1000

        summary = f"{status} | {genes}×{samples} | {issue_count} issues | {time_s:.1f}s"

        if self.use_color:
            if result.passed:
                summary = f"\033[92m{summary}\033[0m"
            else:
                summary = f"\033[91m{summary}\033[0m"

        return summary
