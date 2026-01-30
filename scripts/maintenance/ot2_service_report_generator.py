#!/usr/bin/env python3
"""
OT-2 Service Report Generator
==============================
Generates a professional PDF/HTML service report from diagnostic results.

Usage:
    python3 ot2_service_report_generator.py /path/to/service_report.json
    python3 ot2_service_report_generator.py /path/to/service_report.json --format html
    python3 ot2_service_report_generator.py /path/to/service_report.json --format markdown
    python3 ot2_service_report_generator.py /path/to/service_report.json --customer "Lab Name"
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


class ServiceReportGenerator:
    """Generate professional service reports from diagnostic JSON."""

    def __init__(self, diagnostic_data: Dict[str, Any], customer_name: str = ""):
        self.data = diagnostic_data
        self.customer_name = customer_name
        self.generated_at = datetime.now()

    def _status_emoji(self, status: str) -> str:
        """Get emoji for status."""
        return {
            "PASS": "✅",
            "FAIL": "❌",
            "WARNING": "⚠️",
            "ERROR": "🔴",
            "SKIPPED": "⏭️"
        }.get(status.upper(), "❓")

    def _status_color(self, status: str) -> str:
        """Get color for status."""
        return {
            "PASS": "#28a745",
            "FAIL": "#dc3545",
            "WARNING": "#ffc107",
            "ERROR": "#dc3545",
            "SKIPPED": "#6c757d"
        }.get(status.upper(), "#6c757d")

    def _priority_badge(self, priority: str) -> str:
        """Get badge for priority."""
        colors = {
            "HIGH": "#dc3545",
            "MEDIUM": "#ffc107",
            "LOW": "#28a745"
        }
        color = colors.get(priority.upper(), "#6c757d")
        return f'<span style="background:{color};color:white;padding:2px 8px;border-radius:4px;font-size:12px;">{priority}</span>'

    def generate_markdown(self) -> str:
        """Generate Markdown format report."""
        robot_info = self.data.get("robot_info", {})
        summary = self.data.get("summary", {})
        test_sections = self.data.get("test_sections", {})
        recommendations = self.data.get("recommendations", [])

        # Build report
        lines = []

        # Header
        lines.append("# OT-2 Maintenance Service Report")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Customer and Robot Info
        lines.append("## Robot Information")
        lines.append("")
        lines.append(f"| Field | Value |")
        lines.append("|-------|-------|")
        if self.customer_name:
            lines.append(f"| **Customer** | {self.customer_name} |")
        lines.append(f"| **Robot Model** | {robot_info.get('robot_model', 'OT-2')} |")
        lines.append(f"| **Serial Number** | {robot_info.get('serial_number', 'Unknown')} |")
        lines.append(f"| **Hostname** | {robot_info.get('hostname', 'Unknown')} |")
        sw_version = robot_info.get("software_version", {})
        if isinstance(sw_version, dict):
            lines.append(f"| **Software Version** | {sw_version.get('opentrons_api_version', 'Unknown')} |")
        lines.append(f"| **Firmware Version** | {robot_info.get('firmware_version', 'Unknown')} |")
        lines.append(f"| **Service Date** | {self.generated_at.strftime('%Y-%m-%d')} |")
        lines.append("")

        # Executive Summary
        lines.append("## Executive Summary")
        lines.append("")
        overall = summary.get("overall_status", "UNKNOWN")
        counts = summary.get("test_counts", {})
        lines.append(f"**Overall Status: {self._status_emoji(overall)} {overall}**")
        lines.append("")
        lines.append(f"| Metric | Value |")
        lines.append("|--------|-------|")
        lines.append(f"| Tests Performed | {counts.get('total', 0)} |")
        lines.append(f"| Passed | {counts.get('pass', 0)} |")
        lines.append(f"| Failed | {counts.get('fail', 0)} |")
        lines.append(f"| Warnings | {counts.get('warning', 0)} |")
        lines.append(f"| Duration | {summary.get('duration_seconds', 0):.1f} seconds |")
        lines.append("")

        # Recommendations
        if recommendations:
            lines.append("## Recommendations")
            lines.append("")
            high_priority = [r for r in recommendations if r.get("priority") == "HIGH"]
            medium_priority = [r for r in recommendations if r.get("priority") == "MEDIUM"]

            if high_priority:
                lines.append("### High Priority")
                lines.append("")
                for rec in high_priority:
                    lines.append(f"- **{rec.get('test', 'Unknown')}**: {rec.get('action', '')}")
                lines.append("")

            if medium_priority:
                lines.append("### Medium Priority")
                lines.append("")
                for rec in medium_priority:
                    lines.append(f"- **{rec.get('test', 'Unknown')}**: {rec.get('action', '')}")
                lines.append("")

        # Detailed Results by Section
        lines.append("## Detailed Test Results")
        lines.append("")

        section_names = {
            "motion_system": "Motion System",
            "pipettes": "Pipettes",
            "modules": "Modules",
            "calibration": "Calibration",
            "system_health": "System Health"
        }

        for section_key, section_data in test_sections.items():
            section_name = section_names.get(section_key, section_key.replace("_", " ").title())
            section_status = section_data.get("overall_status", "UNKNOWN")

            lines.append(f"### {section_name} {self._status_emoji(section_status)}")
            lines.append("")

            tests = section_data.get("tests", [])
            if tests:
                lines.append("| Test | Status | Message |")
                lines.append("|------|--------|---------|")
                for test in tests:
                    status = test.get("status", "UNKNOWN")
                    lines.append(f"| {test.get('name', 'Unknown')} | {self._status_emoji(status)} {status} | {test.get('message', '')} |")
                lines.append("")

        # System Information Details
        lines.append("## System Details")
        lines.append("")

        # Network
        network = robot_info.get("network", {})
        if network:
            lines.append("### Network")
            lines.append("")
            lines.append(f"- **IP Addresses**: {', '.join(network.get('ip_addresses', []))}")
            if network.get("wifi_ssid"):
                lines.append(f"- **WiFi SSID**: {network.get('wifi_ssid')}")
            lines.append("")

        # Storage
        storage = robot_info.get("storage", {})
        if storage:
            lines.append("### Storage")
            lines.append("")
            lines.append(f"- **Total**: {storage.get('total', 'Unknown')}")
            lines.append(f"- **Used**: {storage.get('used', 'Unknown')} ({storage.get('percent_used', 'Unknown')})")
            lines.append(f"- **Available**: {storage.get('available', 'Unknown')}")
            lines.append("")

        # Footer
        lines.append("---")
        lines.append("")
        lines.append(f"*Report generated: {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')}*")
        lines.append("")
        lines.append("*This report was generated automatically by the OT-2 Service Diagnostic Tool.*")

        return "\n".join(lines)

    def generate_html(self) -> str:
        """Generate HTML format report."""
        robot_info = self.data.get("robot_info", {})
        summary = self.data.get("summary", {})
        test_sections = self.data.get("test_sections", {})
        recommendations = self.data.get("recommendations", [])

        overall = summary.get("overall_status", "UNKNOWN")
        counts = summary.get("test_counts", {})

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OT-2 Service Report - {robot_info.get('serial_number', 'Unknown')}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .report {{
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .header {{
            text-align: center;
            border-bottom: 3px solid #0066cc;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            color: #0066cc;
            margin-bottom: 10px;
        }}
        .header .subtitle {{
            color: #666;
            font-size: 14px;
        }}
        .logo {{
            font-size: 48px;
            margin-bottom: 10px;
        }}
        .section {{
            margin-bottom: 30px;
        }}
        .section h2 {{
            color: #0066cc;
            border-bottom: 2px solid #eee;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        .section h3 {{
            color: #444;
            margin: 20px 0 10px 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}
        th {{
            background: #f8f9fa;
            font-weight: 600;
        }}
        .info-table td:first-child {{
            font-weight: 600;
            width: 40%;
        }}
        .status-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 14px;
        }}
        .status-pass {{ background: #d4edda; color: #155724; }}
        .status-fail {{ background: #f8d7da; color: #721c24; }}
        .status-warning {{ background: #fff3cd; color: #856404; }}
        .status-error {{ background: #f8d7da; color: #721c24; }}
        .status-skipped {{ background: #e2e3e5; color: #383d41; }}
        .overall-status {{
            text-align: center;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }}
        .overall-pass {{ background: #d4edda; }}
        .overall-fail {{ background: #f8d7da; }}
        .overall-warning {{ background: #fff3cd; }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        .summary-card {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .summary-card .number {{
            font-size: 36px;
            font-weight: 700;
            color: #0066cc;
        }}
        .summary-card .label {{
            color: #666;
            font-size: 14px;
        }}
        .recommendation {{
            padding: 15px;
            margin: 10px 0;
            border-left: 4px solid;
            background: #f8f9fa;
        }}
        .recommendation.high {{ border-color: #dc3545; }}
        .recommendation.medium {{ border-color: #ffc107; }}
        .recommendation.low {{ border-color: #28a745; }}
        .recommendation .priority {{
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .recommendation.high .priority {{ color: #dc3545; }}
        .recommendation.medium .priority {{ color: #856404; }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            color: #666;
            font-size: 12px;
        }}
        @media print {{
            body {{ background: white; }}
            .report {{ box-shadow: none; }}
        }}
    </style>
</head>
<body>
    <div class="report">
        <div class="header">
            <div class="logo">🔬</div>
            <h1>OT-2 Maintenance Service Report</h1>
            <div class="subtitle">Comprehensive Diagnostic Assessment</div>
        </div>

        <div class="section">
            <h2>Robot Information</h2>
            <table class="info-table">
                {"<tr><td>Customer</td><td>" + self.customer_name + "</td></tr>" if self.customer_name else ""}
                <tr><td>Robot Model</td><td>{robot_info.get('robot_model', 'OT-2')}</td></tr>
                <tr><td>Serial Number</td><td>{robot_info.get('serial_number', 'Unknown')}</td></tr>
                <tr><td>Hostname</td><td>{robot_info.get('hostname', 'Unknown')}</td></tr>
                <tr><td>Software Version</td><td>{robot_info.get('software_version', {}).get('opentrons_api_version', 'Unknown') if isinstance(robot_info.get('software_version'), dict) else 'Unknown'}</td></tr>
                <tr><td>Firmware Version</td><td>{robot_info.get('firmware_version', 'Unknown')}</td></tr>
                <tr><td>Service Date</td><td>{self.generated_at.strftime('%Y-%m-%d')}</td></tr>
            </table>
        </div>

        <div class="section">
            <h2>Executive Summary</h2>
            <div class="overall-status overall-{overall.lower()}">
                <h3>Overall Status: <span class="status-badge status-{overall.lower()}">{overall}</span></h3>
            </div>
            <div class="summary-grid">
                <div class="summary-card">
                    <div class="number">{counts.get('total', 0)}</div>
                    <div class="label">Tests Performed</div>
                </div>
                <div class="summary-card">
                    <div class="number" style="color:#28a745">{counts.get('pass', 0)}</div>
                    <div class="label">Passed</div>
                </div>
                <div class="summary-card">
                    <div class="number" style="color:#dc3545">{counts.get('fail', 0)}</div>
                    <div class="label">Failed</div>
                </div>
                <div class="summary-card">
                    <div class="number" style="color:#ffc107">{counts.get('warning', 0)}</div>
                    <div class="label">Warnings</div>
                </div>
            </div>
        </div>
"""

        # Recommendations section
        if recommendations:
            html += """
        <div class="section">
            <h2>Recommendations</h2>
"""
            for rec in recommendations:
                priority = rec.get("priority", "MEDIUM").lower()
                html += f"""
            <div class="recommendation {priority}">
                <div class="priority">{rec.get('priority', 'MEDIUM')} Priority</div>
                <strong>{rec.get('test', 'Unknown')}</strong>
                <p>{rec.get('action', '')}</p>
            </div>
"""
            html += "        </div>\n"

        # Test Results section
        html += """
        <div class="section">
            <h2>Detailed Test Results</h2>
"""

        section_names = {
            "motion_system": "Motion System",
            "pipettes": "Pipettes",
            "modules": "Modules",
            "calibration": "Calibration",
            "system_health": "System Health"
        }

        for section_key, section_data in test_sections.items():
            section_name = section_names.get(section_key, section_key.replace("_", " ").title())
            section_status = section_data.get("overall_status", "UNKNOWN")

            html += f"""
            <h3>{section_name} <span class="status-badge status-{section_status.lower()}">{section_status}</span></h3>
            <table>
                <thead>
                    <tr>
                        <th>Test</th>
                        <th>Status</th>
                        <th>Details</th>
                    </tr>
                </thead>
                <tbody>
"""
            for test in section_data.get("tests", []):
                status = test.get("status", "UNKNOWN")
                html += f"""
                    <tr>
                        <td>{test.get('name', 'Unknown')}</td>
                        <td><span class="status-badge status-{status.lower()}">{status}</span></td>
                        <td>{test.get('message', '')}</td>
                    </tr>
"""
            html += """
                </tbody>
            </table>
"""

        html += "        </div>\n"

        # Footer
        html += f"""
        <div class="footer">
            <p>Report generated: {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>This report was generated automatically by the OT-2 Service Diagnostic Tool.</p>
        </div>
    </div>
</body>
</html>
"""
        return html

    def save_report(self, output_path: str, format: str = "markdown") -> str:
        """Save report to file."""
        if format == "html":
            content = self.generate_html()
            ext = ".html"
        else:
            content = self.generate_markdown()
            ext = ".md"

        # Ensure correct extension
        output_file = Path(output_path)
        if output_file.suffix != ext:
            output_file = output_file.with_suffix(ext)

        output_file.write_text(content)
        return str(output_file)


def main():
    parser = argparse.ArgumentParser(description="OT-2 Service Report Generator")
    parser.add_argument("input", help="Path to diagnostic JSON file")
    parser.add_argument("--format", "-f", choices=["markdown", "html"], default="markdown",
                        help="Output format (default: markdown)")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--customer", "-c", default="", help="Customer name")

    args = parser.parse_args()

    # Load diagnostic data
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {args.input}")
        return 1

    with open(input_path) as f:
        diagnostic_data = json.load(f)

    # Generate report
    generator = ServiceReportGenerator(diagnostic_data, args.customer)

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        output_path = input_path.with_suffix(".html" if args.format == "html" else ".md")

    saved_path = generator.save_report(str(output_path), args.format)
    print(f"Report saved to: {saved_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
