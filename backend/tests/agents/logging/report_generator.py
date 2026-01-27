"""
ReportGenerator - Generate comprehensive test reports from agent logs.

Creates JSON, Markdown, and HTML reports from AgentLogger data.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .log_schemas import AgentExecutionLog, MetricsSummary


class ReportGenerator:
    """
    Generates comprehensive reports from agent execution logs.

    Supports multiple output formats:
    - JSON: Machine-readable complete data
    - Markdown: Human-readable summary
    - HTML: Interactive report with styling
    """

    def __init__(self, log_dir: Path):
        """
        Initialize the report generator.

        Args:
            log_dir: Directory containing log files from AgentLogger
        """
        self.log_dir = Path(log_dir)
        self._load_data()

    def _load_data(self) -> None:
        """Load data from log files."""
        # Load master log
        master_log_path = self.log_dir / "master_log.json"
        if master_log_path.exists():
            with open(master_log_path) as f:
                self.master_log = json.load(f)
        else:
            self.master_log = []

        # Load metrics summary
        metrics_path = self.log_dir / "metrics" / "summary.json"
        if metrics_path.exists():
            with open(metrics_path) as f:
                self.metrics = json.load(f)
        else:
            self.metrics = {}

        # Load tokens data
        tokens_path = self.log_dir / "metrics" / "tokens.json"
        if tokens_path.exists():
            with open(tokens_path) as f:
                self.tokens_data = json.load(f)
        else:
            self.tokens_data = {}

        # Load timing data
        timing_path = self.log_dir / "metrics" / "timing.json"
        if timing_path.exists():
            with open(timing_path) as f:
                self.timing_data = json.load(f)
        else:
            self.timing_data = {}

        # Load errors
        errors_path = self.log_dir / "errors" / "errors.json"
        if errors_path.exists():
            with open(errors_path) as f:
                self.errors = json.load(f)
        else:
            self.errors = []

        # Load agent executions
        self.agent_data = {}
        agents_dir = self.log_dir / "agents"
        if agents_dir.exists():
            for agent_dir in agents_dir.iterdir():
                if agent_dir.is_dir():
                    agent_name = agent_dir.name.upper()
                    execution_path = agent_dir / "execution.json"
                    if execution_path.exists():
                        with open(execution_path) as f:
                            self.agent_data[agent_name] = json.load(f)

    def generate_json_report(self, output_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Generate a complete JSON report.

        Args:
            output_path: Optional path to save the report

        Returns:
            Complete report data as dictionary
        """
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "log_dir": str(self.log_dir),
            "summary": self.metrics,
            "tokens": self.tokens_data,
            "timing": self.timing_data,
            "agents": self.agent_data,
            "errors": self.errors,
            "master_log_entries": len(self.master_log),
        }

        if output_path:
            with open(output_path, "w") as f:
                json.dump(report, f, indent=2, default=str)

        return report

    def generate_markdown_report(self, output_path: Optional[Path] = None) -> str:
        """
        Generate a human-readable Markdown report.

        Args:
            output_path: Optional path to save the report

        Returns:
            Markdown report as string
        """
        lines = []

        # Header
        lines.append("# Agent Pipeline Test Report")
        lines.append(f"\n**Run ID:** {self.metrics.get('run_id', 'N/A')}")
        lines.append(f"\n**Test Name:** {self.metrics.get('test_name', 'N/A')}")
        lines.append(f"\n**Generated:** {datetime.utcnow().isoformat()}")
        lines.append("")

        # Pipeline Overview
        lines.append("---")
        lines.append("\n## Pipeline Overview\n")
        lines.append("| Agent | Duration | Tokens In | Tokens Out | Cost | Status | Errors |")
        lines.append("|-------|----------|-----------|------------|------|--------|--------|")

        agents_metrics = self.metrics.get("agents", {}).get("per_agent", {})
        for agent_key, metrics in agents_metrics.items():
            agent_name = agent_key.split("_")[0] if "_" in agent_key else agent_key
            duration = f"{metrics.get('duration_ms', 0) / 1000:.2f}s"
            input_tokens = f"{metrics.get('input_tokens', 0):,}"
            output_tokens = f"{metrics.get('output_tokens', 0):,}"
            cost = f"${metrics.get('cost', 0):.4f}"
            status = "OK" if metrics.get("success", False) else "FAILED"
            errors = metrics.get("errors", 0)
            lines.append(f"| {agent_name} | {duration} | {input_tokens} | {output_tokens} | {cost} | {status} | {errors} |")

        # Totals
        total_duration = f"{self.metrics.get('timing', {}).get('total_duration_ms', 0) / 1000:.2f}s"
        total_input = f"{self.metrics.get('tokens', {}).get('total_input', 0):,}"
        total_output = f"{self.metrics.get('tokens', {}).get('total_output', 0):,}"
        total_cost = f"${self.metrics.get('cost', {}).get('total', 0):.4f}"
        total_errors = self.metrics.get("errors", {}).get("total", 0)
        lines.append(f"| **Total** | **{total_duration}** | **{total_input}** | **{total_output}** | **{total_cost}** | - | **{total_errors}** |")
        lines.append("")

        # Token Usage & Cost Analysis
        lines.append("---")
        lines.append("\n## Token Usage & Cost Analysis\n")
        lines.append("| Agent | Input | Output | Cache Read | Total | Cost |")
        lines.append("|-------|-------|--------|------------|-------|------|")

        by_agent = self.tokens_data.get("by_agent", {})
        for agent_key, tokens in by_agent.items():
            agent_name = agent_key.split("_")[0] if "_" in agent_key else agent_key
            input_t = f"{tokens.get('input_tokens', 0):,}"
            output_t = f"{tokens.get('output_tokens', 0):,}"
            cache_t = f"{tokens.get('cache_read_tokens', 0):,}"
            total_t = f"{tokens.get('total_tokens', 0):,}"
            # Get cost from agent metrics
            agent_cost = agents_metrics.get(agent_key, {}).get("cost", 0)
            cost_str = f"${agent_cost:.4f}"
            lines.append(f"| {agent_name} | {input_t} | {output_t} | {cache_t} | {total_t} | {cost_str} |")

        lines.append("")

        # Agent Details
        lines.append("---")
        lines.append("\n## Agent Details\n")

        agent_descriptions = {
            "NOVA": ("Intent Analyzer", "Analyzes user intent and task requirements"),
            "SCOUT": ("Context Retriever", "Retrieves relevant code context via vector search"),
            "BLUEPRINT": ("Planner", "Creates implementation plans with steps"),
            "FORGE": ("Executor", "Generates code based on the plan"),
            "GUARDIAN": ("Validator", "Validates generated code for correctness"),
            "PALETTE": ("UI Designer", "Designs and generates UI components"),
            "CONDUCTOR": ("Orchestrator", "Coordinates the entire pipeline"),
        }

        for agent_key, data in self.agent_data.items():
            agent_name = agent_key.split("_")[0] if "_" in agent_key else agent_key
            desc = agent_descriptions.get(agent_name, ("Agent", ""))

            lines.append(f"### {agent_name} ({desc[0]})")
            lines.append(f"\n*{desc[1]}*\n")

            timing = data.get("timing", {})
            metrics_d = data.get("metrics", {})

            lines.append(f"- **Duration:** {timing.get('duration_ms', 0) / 1000:.2f}s")
            lines.append(f"- **API Calls:** {metrics_d.get('total_api_calls', 0)}")
            lines.append(f"- **Input Tokens:** {metrics_d.get('total_input_tokens', 0):,}")
            lines.append(f"- **Output Tokens:** {metrics_d.get('total_output_tokens', 0):,}")
            lines.append(f"- **Cost:** ${metrics_d.get('total_cost', 0):.4f}")
            lines.append(f"- **Success:** {'Yes' if data.get('success', False) else 'No'}")

            # Link to files
            agent_lower = agent_name.lower()
            lines.append(f"\n**Files:**")
            lines.append(f"- Input: `agents/{agent_lower}/input.json`")
            lines.append(f"- Output: `agents/{agent_lower}/output.json`")
            lines.append(f"- Execution: `agents/{agent_lower}/execution.json`")
            lines.append("")

        # Errors Section
        if self.errors:
            lines.append("---")
            lines.append("\n## Errors\n")
            for i, error in enumerate(self.errors, 1):
                error_data = error.get("error", {})
                lines.append(f"### Error {i}")
                lines.append(f"- **Agent:** {error.get('agent', 'Unknown')}")
                lines.append(f"- **Type:** {error_data.get('type', 'Unknown')}")
                lines.append(f"- **Message:** {error_data.get('message', 'No message')}")
                lines.append(f"- **Timestamp:** {error.get('timestamp', 'Unknown')}")
                lines.append("")

        # Files Index
        lines.append("---")
        lines.append("\n## Files Index\n")
        lines.append("```")
        lines.append(f"{self.log_dir}/")
        lines.append("├── master_log.json")
        lines.append("├── summary_report.md")
        lines.append("├── prompts/")
        lines.append("│   └── {agent}_call_{n}_prompt.txt")
        lines.append("├── responses/")
        lines.append("│   └── {agent}_call_{n}_response.txt")
        lines.append("├── context/")
        lines.append("│   └── {snapshot_name}.json")
        lines.append("├── agents/")
        lines.append("│   └── {agent}/")
        lines.append("│       ├── input.json")
        lines.append("│       ├── output.json")
        lines.append("│       ├── execution.json")
        lines.append("│       └── metrics.json")
        lines.append("├── metrics/")
        lines.append("│   ├── summary.json")
        lines.append("│   ├── tokens.json")
        lines.append("│   └── timing.json")
        lines.append("└── errors/")
        lines.append("    ├── errors.json")
        lines.append("    └── retries.json")
        lines.append("```")
        lines.append("")

        report = "\n".join(lines)

        if output_path:
            with open(output_path, "w") as f:
                f.write(report)

        return report

    def generate_html_report(self, output_path: Optional[Path] = None) -> str:
        """
        Generate an interactive HTML report.

        Args:
            output_path: Optional path to save the report

        Returns:
            HTML report as string
        """
        agents_metrics = self.metrics.get("agents", {}).get("per_agent", {})

        # Build agent rows
        agent_rows = []
        for agent_key, metrics in agents_metrics.items():
            agent_name = agent_key.split("_")[0] if "_" in agent_key else agent_key
            status_class = "success" if metrics.get("success", False) else "error"
            status_text = "OK" if metrics.get("success", False) else "FAILED"
            agent_rows.append(f"""
                <tr>
                    <td><strong>{agent_name}</strong></td>
                    <td>{metrics.get('duration_ms', 0) / 1000:.2f}s</td>
                    <td>{metrics.get('input_tokens', 0):,}</td>
                    <td>{metrics.get('output_tokens', 0):,}</td>
                    <td>${metrics.get('cost', 0):.4f}</td>
                    <td class="{status_class}">{status_text}</td>
                    <td>{metrics.get('errors', 0)}</td>
                </tr>
            """)

        agent_rows_html = "\n".join(agent_rows)

        # Build agent cards
        agent_descriptions = {
            "NOVA": ("Intent Analyzer", "Analyzes user intent and task requirements", "#3b82f6"),
            "SCOUT": ("Context Retriever", "Retrieves relevant code context via vector search", "#10b981"),
            "BLUEPRINT": ("Planner", "Creates implementation plans with steps", "#8b5cf6"),
            "FORGE": ("Executor", "Generates code based on the plan", "#f59e0b"),
            "GUARDIAN": ("Validator", "Validates generated code for correctness", "#ef4444"),
            "PALETTE": ("UI Designer", "Designs and generates UI components", "#ec4899"),
            "CONDUCTOR": ("Orchestrator", "Coordinates the entire pipeline", "#6366f1"),
        }

        agent_cards = []
        for agent_key, data in self.agent_data.items():
            agent_name = agent_key.split("_")[0] if "_" in agent_key else agent_key
            desc = agent_descriptions.get(agent_name, ("Agent", "", "#64748b"))
            metrics_d = data.get("metrics", {})
            timing = data.get("timing", {})

            agent_cards.append(f"""
                <div class="agent-card" style="border-left-color: {desc[2]}">
                    <h3>{agent_name} <span class="agent-role">({desc[0]})</span></h3>
                    <p class="description">{desc[1]}</p>
                    <div class="metrics-grid">
                        <div class="metric">
                            <span class="metric-value">{timing.get('duration_ms', 0) / 1000:.2f}s</span>
                            <span class="metric-label">Duration</span>
                        </div>
                        <div class="metric">
                            <span class="metric-value">{metrics_d.get('total_api_calls', 0)}</span>
                            <span class="metric-label">API Calls</span>
                        </div>
                        <div class="metric">
                            <span class="metric-value">{metrics_d.get('total_tokens', 0):,}</span>
                            <span class="metric-label">Total Tokens</span>
                        </div>
                        <div class="metric">
                            <span class="metric-value">${metrics_d.get('total_cost', 0):.4f}</span>
                            <span class="metric-label">Cost</span>
                        </div>
                    </div>
                </div>
            """)

        agent_cards_html = "\n".join(agent_cards)

        # Calculate totals
        total_duration = self.metrics.get("timing", {}).get("total_duration_ms", 0) / 1000
        total_tokens = self.metrics.get("tokens", {}).get("total", 0)
        total_cost = self.metrics.get("cost", {}).get("total", 0)
        total_errors = self.metrics.get("errors", {}).get("total", 0)
        success_rate = self.metrics.get("agents", {}).get("success_rate", 0)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent Pipeline Test Report</title>
    <style>
        :root {{
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-tertiary: #334155;
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --accent: #3b82f6;
            --success: #10b981;
            --error: #ef4444;
            --warning: #f59e0b;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 2rem;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}

        h1 {{
            font-size: 2rem;
            margin-bottom: 0.5rem;
        }}

        .subtitle {{
            color: var(--text-secondary);
            margin-bottom: 2rem;
        }}

        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}

        .summary-card {{
            background: var(--bg-secondary);
            border-radius: 0.5rem;
            padding: 1.5rem;
            text-align: center;
        }}

        .summary-card .value {{
            font-size: 2rem;
            font-weight: bold;
            color: var(--accent);
        }}

        .summary-card .label {{
            color: var(--text-secondary);
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .section {{
            background: var(--bg-secondary);
            border-radius: 0.5rem;
            padding: 1.5rem;
            margin-bottom: 2rem;
        }}

        .section h2 {{
            font-size: 1.25rem;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid var(--bg-tertiary);
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        th, td {{
            padding: 0.75rem 1rem;
            text-align: left;
            border-bottom: 1px solid var(--bg-tertiary);
        }}

        th {{
            color: var(--text-secondary);
            font-weight: 500;
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.05em;
        }}

        .success {{
            color: var(--success);
        }}

        .error {{
            color: var(--error);
        }}

        .agent-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1rem;
        }}

        .agent-card {{
            background: var(--bg-secondary);
            border-radius: 0.5rem;
            padding: 1.5rem;
            border-left: 4px solid var(--accent);
        }}

        .agent-card h3 {{
            font-size: 1.125rem;
            margin-bottom: 0.25rem;
        }}

        .agent-role {{
            font-weight: normal;
            color: var(--text-secondary);
            font-size: 0.875rem;
        }}

        .agent-card .description {{
            color: var(--text-secondary);
            font-size: 0.875rem;
            margin-bottom: 1rem;
        }}

        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 0.75rem;
        }}

        .metric {{
            text-align: center;
            padding: 0.5rem;
            background: var(--bg-tertiary);
            border-radius: 0.25rem;
        }}

        .metric-value {{
            display: block;
            font-size: 1.25rem;
            font-weight: bold;
        }}

        .metric-label {{
            font-size: 0.75rem;
            color: var(--text-secondary);
        }}

        .run-info {{
            color: var(--text-secondary);
            font-size: 0.875rem;
            margin-bottom: 1rem;
        }}

        .run-info code {{
            background: var(--bg-tertiary);
            padding: 0.125rem 0.375rem;
            border-radius: 0.25rem;
            font-family: monospace;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Agent Pipeline Test Report</h1>
        <div class="run-info">
            <p>Run ID: <code>{self.metrics.get('run_id', 'N/A')}</code></p>
            <p>Test: <code>{self.metrics.get('test_name', 'N/A')}</code></p>
            <p>Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        </div>

        <div class="summary-grid">
            <div class="summary-card">
                <div class="value">{total_duration:.2f}s</div>
                <div class="label">Total Duration</div>
            </div>
            <div class="summary-card">
                <div class="value">{total_tokens:,}</div>
                <div class="label">Total Tokens</div>
            </div>
            <div class="summary-card">
                <div class="value">${total_cost:.4f}</div>
                <div class="label">Total Cost</div>
            </div>
            <div class="summary-card">
                <div class="value">{success_rate:.0f}%</div>
                <div class="label">Success Rate</div>
            </div>
            <div class="summary-card">
                <div class="value" style="color: {'var(--error)' if total_errors > 0 else 'var(--success)'}">{total_errors}</div>
                <div class="label">Errors</div>
            </div>
        </div>

        <div class="section">
            <h2>Pipeline Overview</h2>
            <table>
                <thead>
                    <tr>
                        <th>Agent</th>
                        <th>Duration</th>
                        <th>Input Tokens</th>
                        <th>Output Tokens</th>
                        <th>Cost</th>
                        <th>Status</th>
                        <th>Errors</th>
                    </tr>
                </thead>
                <tbody>
                    {agent_rows_html}
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>Agent Details</h2>
            <div class="agent-cards">
                {agent_cards_html}
            </div>
        </div>
    </div>
</body>
</html>"""

        if output_path:
            with open(output_path, "w") as f:
                f.write(html)

        return html

    def generate_all_reports(self) -> Dict[str, Path]:
        """
        Generate all report formats and save to log directory.

        Returns:
            Dict mapping format to file path
        """
        paths = {}

        # JSON report
        json_path = self.log_dir / "report.json"
        self.generate_json_report(json_path)
        paths["json"] = json_path

        # Markdown report
        md_path = self.log_dir / "summary_report.md"
        self.generate_markdown_report(md_path)
        paths["markdown"] = md_path

        # HTML report
        html_path = self.log_dir / "report.html"
        self.generate_html_report(html_path)
        paths["html"] = html_path

        return paths


def generate_report_from_logger(
    log_dir: Path,
    formats: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Generate reports from an AgentLogger's log directory.

    Args:
        log_dir: Path to the log directory
        formats: List of formats to generate ("json", "markdown", "html")
                 Defaults to all formats

    Returns:
        Dict with generated report paths and summary data
    """
    formats = formats or ["json", "markdown", "html"]
    generator = ReportGenerator(log_dir)

    result = {
        "log_dir": str(log_dir),
        "files": {},
    }

    if "json" in formats:
        json_path = log_dir / "report.json"
        generator.generate_json_report(json_path)
        result["files"]["json"] = str(json_path)

    if "markdown" in formats:
        md_path = log_dir / "summary_report.md"
        generator.generate_markdown_report(md_path)
        result["files"]["markdown"] = str(md_path)

    if "html" in formats:
        html_path = log_dir / "report.html"
        generator.generate_html_report(html_path)
        result["files"]["html"] = str(html_path)

    result["summary"] = generator.metrics

    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate test reports from agent logs")
    parser.add_argument("--input", "-i", required=True, help="Input log directory")
    parser.add_argument(
        "--format",
        "-f",
        choices=["json", "markdown", "html", "all"],
        default="all",
        help="Output format (default: all)",
    )

    args = parser.parse_args()

    formats = ["json", "markdown", "html"] if args.format == "all" else [args.format]
    result = generate_report_from_logger(Path(args.input), formats)

    print(f"Reports generated in: {result['log_dir']}")
    for fmt, path in result["files"].items():
        print(f"  - {fmt}: {path}")
