"""
Generate scientist-friendly validation reports with explanations.

Features:
- Plain language explanations of validation failures
- Actionable recommendations for fixing issues
- Visual highlighting of problematic records
- Summary statistics with context
- Export to HTML, PDF, and Markdown
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
from jinja2 import Template
import pandas as pd

from src.schemas.base_schemas import ValidationSeverity, Decision

logger = logging.getLogger(__name__)


class ExplainableReportGenerator:
    """
    Generates human-readable validation reports with explanations.
    
    Designed to help bench scientists understand and act on validation results
    without needing to parse technical JSON outputs.
    """
    
    # Explanations for common issues
    ISSUE_EXPLANATIONS = {
        'pam_sequence_invalid': {
            'explanation': (
                "The PAM (Protospacer Adjacent Motif) sequence is incorrect for the "
                "specified nuclease. PAM sequences are required for CRISPR/Cas systems "
                "to recognize and bind to target DNA."
            ),
            'fix': (
                "For SpCas9: use NGG (e.g., AGG, TGG, CGG, GGG)\n"
                "For SaCas9: use NNGRRT\n"
                "For Cas12a (Cpf1): use TTTV\n"
                "Check your gRNA design tool settings."
            )
        },
        
        'gene_symbol_invalid': {
            'explanation': (
                "The gene symbol was not found in the NCBI Gene database. "
                "This could mean a typo, outdated nomenclature, or the gene doesn't exist."
            ),
            'fix': (
                "1. Check spelling and capitalization (genes are case-sensitive)\n"
                "2. Search NCBI Gene (https://www.ncbi.nlm.nih.gov/gene) for the correct symbol\n"
                "3. Verify you're using the official HUGO gene symbol, not an alias\n"
                "4. Ensure organism matches (human genes use uppercase, mouse use capitalized)"
            )
        },
        
        'gc_content_suboptimal': {
            'explanation': (
                "The GC content (percentage of G and C nucleotides) is outside the "
                "optimal range. Extreme GC content can affect gRNA efficiency and "
                "cause off-target effects."
            ),
            'fix': (
                "Target 40-70% GC content for most CRISPR applications.\n"
                "If stuck with extreme GC content:\n"
                "- Consider alternative target sites\n"
                "- Use modified nucleotides\n"
                "- Adjust experimental conditions (temperature, buffers)"
            )
        },
        
        'duplicate_sequence': {
            'explanation': (
                "This sequence appears multiple times in your dataset. "
                "Duplicates can indicate data entry errors or unintentional reuse of gRNAs."
            ),
            'fix': (
                "1. If intentional (e.g., technical replicates), add a replicate ID column\n"
                "2. If accidental, remove duplicate rows\n"
                "3. Check if you accidentally merged datasets"
            )
        },
        
        'class_imbalance': {
            'explanation': (
                "Your dataset has severe imbalance between categories. "
                "This can bias machine learning models and make some conditions hard to detect."
            ),
            'fix': (
                "1. Collect more data for under-represented classes\n"
                "2. Use stratified sampling when splitting train/test sets\n"
                "3. Apply class balancing techniques (SMOTE, class weights)\n"
                "4. Consider whether imbalance reflects true biology or sampling bias"
            )
        },
        
        'missing_metadata': {
            'explanation': (
                "Required metadata fields are missing. Metadata is crucial for "
                "reproducibility and understanding experimental context."
            ),
            'fix': (
                "Add the following information:\n"
                "- Experiment date and lab notebook reference\n"
                "- Organism and strain/cell line\n"
                "- Reference genome build used\n"
                "- Experimental conditions (if applicable)"
            )
        },
        
        'chromosome_format_inconsistent': {
            'explanation': (
                "Chromosome names use inconsistent formats (some with 'chr' prefix, some without). "
                "This will cause errors when matching variants to reference genomes."
            ),
            'fix': (
                "Choose one format and apply consistently:\n"
                "Option 1: Add 'chr' prefix to all (chr1, chr2, ..., chrX, chrY)\n"
                "Option 2: Remove all 'chr' prefixes (1, 2, ..., X, Y)\n"
                "Use find-and-replace or a simple script to standardize."
            )
        }
    }
    
    def __init__(self, output_dir: str = "validation_output/reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"ReportGenerator initialized: output={output_dir}")
    
    def generate_report(
        self,
        validation_report: Dict[str, Any],
        format: str = "html",
        include_raw_data: bool = False
    ) -> str:
        """
        Generate human-readable validation report.
        
        Args:
            validation_report: Raw validation report from orchestrator
            format: Output format ('html', 'markdown', 'pdf')
            include_raw_data: Whether to include problematic records
            
        Returns:
            Path to generated report file
        """
        # Extract key information
        decision = validation_report.get('final_decision', 'unknown')
        execution_time = validation_report.get('execution_time_seconds', 0)
        requires_review = validation_report.get('requires_human_review', False)
        stages = validation_report.get('stages', {})
        
        # Build report content
        content = {
            'title': self._get_decision_title(decision),
            'decision': decision,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'execution_time': execution_time,
            'requires_review': requires_review,
            'summary': self._build_summary(stages),
            'issues_by_severity': self._group_issues_by_severity(stages),
            'stage_details': self._build_stage_details(stages),
            'recommendations': self._build_recommendations(stages, decision),
            'next_steps': self._build_next_steps(decision, requires_review)
        }
        
        # Generate output based on format
        if format == 'html':
            output_path = self._generate_html(content, validation_report)
        elif format == 'markdown':
            output_path = self._generate_markdown(content, validation_report)
        elif format == 'pdf':
            output_path = self._generate_pdf(content, validation_report)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        logger.info(f"Generated {format.upper()} report: {output_path}")
        return str(output_path)
    
    def _get_decision_title(self, decision: str) -> str:
        """Get friendly title based on decision."""
        titles = {
            'accepted': '✅ Validation Passed',
            'conditional_accept': '⚠️ Validation Passed with Warnings',
            'rejected': '❌ Validation Failed',
            'pending': '⏳ Validation In Progress'
        }
        return titles.get(decision, f'Decision: {decision}')
    
    def _build_summary(self, stages: Dict[str, Any]) -> Dict[str, Any]:
        """Build executive summary statistics."""
        total_issues = sum(
            len(stage.get('issues', []))
            for stage in stages.values()
        )
        
        severity_counts = {
            'critical': 0,
            'error': 0,
            'warning': 0,
            'info': 0
        }
        
        for stage in stages.values():
            for issue in stage.get('issues', []):
                severity = issue.get('severity', 'info').lower()
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        return {
            'total_issues': total_issues,
            'severity_counts': severity_counts,
            'stages_passed': sum(
                1 for stage in stages.values() if stage.get('passed', False)
            ),
            'stages_total': len(stages)
        }
    
    def _group_issues_by_severity(
        self,
        stages: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group all issues by severity with explanations."""
        grouped = {
            'critical': [],
            'error': [],
            'warning': [],
            'info': []
        }
        
        for stage_name, stage_data in stages.items():
            for issue in stage_data.get('issues', []):
                severity = issue.get('severity', 'info').lower()
                
                # Enhance issue with explanation
                enhanced_issue = {
                    **issue,
                    'stage': stage_name,
                    'explanation': self._get_issue_explanation(issue),
                    'fix': self._get_issue_fix(issue)
                }
                
                grouped[severity].append(enhanced_issue)
        
        return grouped
    
    def _get_issue_explanation(self, issue: Dict[str, Any]) -> str:
        """Get plain language explanation for an issue."""
        message = issue.get('message', '').lower()
        
        # Match against known patterns
        for pattern, info in self.ISSUE_EXPLANATIONS.items():
            if pattern.replace('_', ' ') in message:
                return info['explanation']
        
        # Default explanation
        return "This validation check identified a potential data quality issue."
    
    def _get_issue_fix(self, issue: Dict[str, Any]) -> str:
        """Get actionable fix recommendation for an issue."""
        message = issue.get('message', '').lower()
        
        for pattern, info in self.ISSUE_EXPLANATIONS.items():
            if pattern.replace('_', ' ') in message:
                return info['fix']
        
        return "Please review the affected records and consult the documentation."
    
    def _build_stage_details(
        self,
        stages: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Build detailed breakdown of each validation stage."""
        details = []
        
        stage_descriptions = {
            'schema': 'File Format & Structure Validation',
            'rules': 'Data Consistency & Quality Checks',
            'bio_rules': 'Biological Plausibility Checks',
            'bio_lookups': 'External Database Verification',
            'policy': 'Final Decision Policy'
        }
        
        for stage_name, stage_data in stages.items():
            passed = stage_data.get('passed', False)
            exec_time = stage_data.get('execution_time_ms', 0) / 1000.0
            issues = stage_data.get('issues', [])
            
            details.append({
                'name': stage_name,
                'description': stage_descriptions.get(
                    stage_name, f'{stage_name} validation'
                ),
                'passed': passed,
                'execution_time': exec_time,
                'issue_count': len(issues),
                'issues': issues
            })
        
        return details
    
    def _build_recommendations(
        self,
        stages: Dict[str, Any],
        decision: str
    ) -> List[str]:
        """Build actionable recommendations based on issues found."""
        recommendations = []
        
        # Get all critical and error issues
        all_issues = []
        for stage in stages.values():
            all_issues.extend(stage.get('issues', []))
        
        critical_issues = [
            i for i in all_issues 
            if i.get('severity', '').lower() == 'critical'
        ]
        error_issues = [
            i for i in all_issues
            if i.get('severity', '').lower() == 'error'
        ]
        
        if decision == 'rejected':
            recommendations.append(
                "**Priority: Address critical and error-level issues before proceeding.**"
            )
            
            if critical_issues:
                recommendations.append(
                    f"Fix {len(critical_issues)} critical issues that prevent data processing"
                )
            
            if error_issues:
                recommendations.append(
                    f"Resolve {len(error_issues)} data quality errors"
                )
        
        elif decision == 'conditional_accept':
            recommendations.append(
                "**Data can be used with caution. Review warnings before publication.**"
            )
            
            warning_issues = [
                i for i in all_issues
                if i.get('severity', '').lower() == 'warning'
            ]
            
            if warning_issues:
                recommendations.append(
                    f"Review {len(warning_issues)} warnings to improve data quality"
                )
        
        else:  # accepted
            recommendations.append(
                "**Data passes all validation checks and is ready for analysis.**"
            )
        
        # Add specific recommendations based on issue types
        issue_types = set(
            self._infer_issue_type(i.get('message', ''))
            for i in all_issues
        )
        
        if 'gene_symbol' in issue_types:
            recommendations.append(
                "Run gene symbols through NCBI Gene lookup to verify correctness"
            )
        
        if 'duplicate' in issue_types:
            recommendations.append(
                "Review duplicate records - remove or mark as biological replicates"
            )
        
        if 'missing' in issue_types:
            recommendations.append(
                "Fill in missing metadata fields for reproducibility"
            )
        
        return recommendations
    
    def _infer_issue_type(self, message: str) -> str:
        """Infer issue type from message."""
        message_lower = message.lower()
        
        if 'gene' in message_lower or 'symbol' in message_lower:
            return 'gene_symbol'
        elif 'duplicate' in message_lower:
            return 'duplicate'
        elif 'missing' in message_lower:
            return 'missing'
        elif 'pam' in message_lower:
            return 'pam'
        elif 'gc' in message_lower:
            return 'gc_content'
        else:
            return 'other'
    
    def _build_next_steps(
        self,
        decision: str,
        requires_review: bool
    ) -> List[str]:
        """Build next steps based on decision."""
        steps = []
        
        if decision == 'rejected':
            steps.extend([
                "1. Review the critical and error issues listed above",
                "2. Fix identified problems in your source data",
                "3. Re-run validation to verify fixes",
                "4. Proceed to analysis once validation passes"
            ])
        
        elif decision == 'conditional_accept':
            steps.extend([
                "1. Review warnings to understand potential limitations",
                "2. Decide if warnings are acceptable for your use case",
                "3. Document any known limitations in your methods section",
                "4. Proceed to analysis with appropriate caution"
            ])
            
            if requires_review:
                steps.append(
                    "5. **Submit flagged items for expert review before publication**"
                )
        
        else:  # accepted
            steps.extend([
                "1. Proceed to downstream analysis",
                "2. Archive this validation report with your data",
                "3. Include validation summary in your methods section"
            ])
        
        return steps
    
    def _generate_html(
        self,
        content: Dict[str, Any],
        raw_report: Dict[str, Any]
    ) -> Path:
        """Generate HTML report."""
        template_str = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{{ content.title }}</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .header {
            background: white;
            padding: 30px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .header h1 {
            margin: 0;
            font-size: 32px;
        }
        .decision-accepted { color: #27ae60; }
        .decision-conditional { color: #f39c12; }
        .decision-rejected { color: #e74c3c; }
        
        .summary-stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .stat-value {
            font-size: 36px;
            font-weight: bold;
            margin: 10px 0;
        }
        .stat-label {
            color: #666;
            font-size: 14px;
        }
        
        .severity-critical { color: #e74c3c; }
        .severity-error { color: #e67e22; }
        .severity-warning { color: #f39c12; }
        .severity-info { color: #3498db; }
        
        .issue-card {
            background: white;
            padding: 20px;
            margin: 10px 0;
            border-radius: 8px;
            border-left: 4px solid #ddd;
        }
        .issue-card.critical { border-left-color: #e74c3c; }
        .issue-card.error { border-left-color: #e67e22; }
        .issue-card.warning { border-left-color: #f39c12; }
        .issue-card.info { border-left-color: #3498db; }
        
        .explanation {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 4px;
            margin: 10px 0;
        }
        .fix-box {
            background: #e8f5e9;
            padding: 15px;
            border-radius: 4px;
            margin: 10px 0;
            border-left: 4px solid #4caf50;
        }
        
        .recommendations {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }
        .next-steps {
            background: #e3f2fd;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }
        
        code {
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }
        pre {
            background: #f4f4f4;
            padding: 15px;
            border-radius: 4px;
            overflow-x: auto;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1 class="decision-{{ content.decision }}">{{ content.title }}</h1>
        <p>Generated: {{ content.timestamp }}</p>
        <p>Validation Time: {{ "%.2f"|format(content.execution_time) }} seconds</p>
        {% if content.requires_review %}
        <p style="color: #e67e22; font-weight: bold;">⚠️ Human review required for flagged items</p>
        {% endif %}
    </div>
    
    <div class="summary-stats">
        <div class="stat-card">
            <div class="stat-label">Total Issues</div>
            <div class="stat-value">{{ content.summary.total_issues }}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Critical</div>
            <div class="stat-value severity-critical">{{ content.summary.severity_counts.critical }}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Errors</div>
            <div class="stat-value severity-error">{{ content.summary.severity_counts.error }}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Warnings</div>
            <div class="stat-value severity-warning">{{ content.summary.severity_counts.warning }}</div>
        </div>
    </div>
    
    <div class="recommendations">
        <h2>📋 Recommendations</h2>
        <ul>
        {% for rec in content.recommendations %}
            <li>{{ rec }}</li>
        {% endfor %}
        </ul>
    </div>
    
    {% if content.issues_by_severity.critical %}
    <h2 style="color: #e74c3c;">🚨 Critical Issues</h2>
    {% for issue in content.issues_by_severity.critical %}
    <div class="issue-card critical">
        <h3>{{ issue.message }}</h3>
        <p><strong>Stage:</strong> {{ issue.stage }} | <strong>Affected Records:</strong> {{ issue.affected_records }}</p>
        <div class="explanation">
            <strong>Why this matters:</strong> {{ issue.explanation }}
        </div>
        <div class="fix-box">
            <strong>How to fix:</strong><br>
            <pre>{{ issue.fix }}</pre>
        </div>
    </div>
    {% endfor %}
    {% endif %}
    
    {% if content.issues_by_severity.error %}
    <h2 style="color: #e67e22;">❌ Errors</h2>
    {% for issue in content.issues_by_severity.error %}
    <div class="issue-card error">
        <h3>{{ issue.message }}</h3>
        <p><strong>Stage:</strong> {{ issue.stage }} | <strong>Affected Records:</strong> {{ issue.affected_records }}</p>
        <div class="explanation">{{ issue.explanation }}</div>
        <div class="fix-box"><strong>Fix:</strong><br><pre>{{ issue.fix }}</pre></div>
    </div>
    {% endfor %}
    {% endif %}
    
    {% if content.issues_by_severity.warning %}
    <h2 style="color: #f39c12;">⚠️ Warnings</h2>
    {% for issue in content.issues_by_severity.warning[:5] %}
    <div class="issue-card warning">
        <h3>{{ issue.message }}</h3>
        <p><strong>Affected Records:</strong> {{ issue.affected_records }}</p>
        <div class="explanation">{{ issue.explanation }}</div>
    </div>
    {% endfor %}
    {% if content.issues_by_severity.warning|length > 5 %}
    <p><em>... and {{ content.issues_by_severity.warning|length - 5 }} more warnings</em></p>
    {% endif %}
    {% endif %}
    
    <div class="next-steps">
        <h2>🎯 Next Steps</h2>
        <ol>
        {% for step in content.next_steps %}
            <li>{{ step }}</li>
        {% endfor %}
        </ol>
    </div>
</body>
</html>
        """
        
        template = Template(template_str)
        html = template.render(content=content)
        
        output_file = self.output_dir / f"validation_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.html"
        output_file.write_text(html)
        
        return output_file
    
    def _generate_markdown(
        self,
        content: Dict[str, Any],
        raw_report: Dict[str, Any]
    ) -> Path:
        """Generate Markdown report."""
        md_lines = [
            f"# {content['title']}\n",
            f"**Generated:** {content['timestamp']}  ",
            f"**Validation Time:** {content['execution_time']:.2f} seconds\n",
        ]
        
        if content['requires_review']:
            md_lines.append("⚠️ **Human review required for flagged items**\n")
        
        md_lines.extend([
            "## Summary\n",
            f"- Total Issues: {content['summary']['total_issues']}",
            f"- Critical: {content['summary']['severity_counts']['critical']}",
            f"- Errors: {content['summary']['severity_counts']['error']}",
            f"- Warnings: {content['summary']['severity_counts']['warning']}\n",
        ])
        
        md_lines.append("## Recommendations\n")
        for rec in content['recommendations']:
            md_lines.append(f"- {rec}")
        
        md_lines.append("\n## Next Steps\n")
        for i, step in enumerate(content['next_steps'], 1):
            md_lines.append(f"{i}. {step}")
        
        markdown = "\n".join(md_lines)
        
        output_file = self.output_dir / f"validation_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.md"
        output_file.write_text(markdown)
        
        return output_file
    
    def _generate_pdf(
        self,
        content: Dict[str, Any],
        raw_report: Dict[str, Any]
    ) -> Path:
        """Generate PDF report (requires additional dependencies)."""
        # First generate HTML
        html_path = self._generate_html(content, raw_report)
        
        # TODO: Convert HTML to PDF using weasyprint or similar
        # For now, just return HTML path
        logger.warning("PDF generation not yet implemented, returning HTML")
        return html_path