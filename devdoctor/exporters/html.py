"""Standalone HTML report exporter."""

from __future__ import annotations

import html
import json
from pathlib import Path

from devdoctor import __copyright__, __homepage__, __license__, __version__
from devdoctor.models import CheckResult, CheckStatus, HealthReport


def render_html(report: HealthReport) -> str:
    """Render a health report as a standalone HTML document."""

    rows = "\n".join(_result_row(result) for result in report.results)
    recommendations = "\n".join(
        f"<li>{html.escape(recommendation)}</li>" for recommendation in report.recommendations
    )
    if not recommendations:
        recommendations = "<li>No recommendations. Your development environment looks healthy.</li>"

    summary = report.summary
    report_json = html.escape(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DevDoctor Health Report</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0b1020;
      --panel: #111827;
      --panel-2: #172033;
      --border: #263247;
      --text: #e5edf7;
      --muted: #9fb0c3;
      --pass: #34d399;
      --warn: #fbbf24;
      --fail: #fb7185;
      --accent: #38bdf8;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family:
        Inter,
        ui-sans-serif,
        system-ui,
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;
      line-height: 1.5;
    }}
    main {{
      width: min(1180px, calc(100% - 32px));
      margin: 40px auto;
    }}
    header {{
      border: 1px solid var(--border);
      border-radius: 8px;
      background: linear-gradient(135deg, var(--panel), var(--panel-2));
      padding: 28px;
    }}
    h1 {{ margin: 0 0 6px; font-size: clamp(2rem, 4vw, 3.5rem); letter-spacing: 0; }}
    h2 {{ margin: 28px 0 12px; font-size: 1.2rem; }}
    .muted {{ color: var(--muted); }}
    .score {{
      display: inline-flex;
      align-items: baseline;
      gap: 8px;
      margin-top: 18px;
      padding: 10px 14px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.04);
      font-size: 1.1rem;
    }}
    .score strong {{ color: var(--accent); font-size: 2rem; }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin: 18px 0 0;
    }}
    .metric {{
      border: 1px solid var(--border);
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.035);
      padding: 14px;
    }}
    .metric span {{ display: block; color: var(--muted); font-size: 0.88rem; }}
    .metric strong {{ display: block; margin-top: 4px; font-size: 1.35rem; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      overflow: hidden;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--panel);
    }}
    th, td {{
      border-bottom: 1px solid var(--border);
      padding: 12px 14px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      color: var(--muted);
      font-size: 0.82rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}
    tr:last-child td {{ border-bottom: 0; }}
    .status {{ font-weight: 700; white-space: nowrap; }}
    .pass {{ color: var(--pass); }}
    .warning {{ color: var(--warn); }}
    .fail {{ color: var(--fail); }}
    code, pre {{
      border-radius: 8px;
      background: #070b14;
      color: #dbeafe;
    }}
    pre {{
      overflow-x: auto;
      padding: 16px;
      border: 1px solid var(--border);
    }}
    ul {{
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--panel);
      padding: 16px 20px 16px 34px;
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>DevDoctor Health Report</h1>
      <p class="muted">Diagnose your development environment in seconds.</p>
      <div class="score">
        <span>Overall health</span>
        <strong>{report.score}</strong>
        <span>/ 100</span>
      </div>
      <section class="summary" aria-label="Summary">
        <div class="metric"><span>Passed</span><strong>{summary.passed}</strong></div>
        <div class="metric"><span>Warnings</span><strong>{summary.warnings}</strong></div>
        <div class="metric"><span>Failed</span><strong>{summary.failed}</strong></div>
        <div class="metric">
          <span>Duration</span>
          <strong>{report.duration_seconds:.2f}s</strong>
        </div>
      </section>
    </header>
    <h2>Recommendations</h2>
    <ul>{recommendations}</ul>
    <h2>Checks</h2>
    <table>
      <thead>
        <tr>
          <th>Status</th>
          <th>Check</th>
          <th>Category</th>
          <th>Summary</th>
          <th>Recommendation</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>
    <h2>Raw Data</h2>
    <pre><code>{report_json}</code></pre>
  </main>
  <footer>
    <p>Generated by DevDoctor {__version__}. {__copyright__}.
      <a href="{__homepage__}">AxiomNode</a>. {__license__} License.</p>
  </footer>
</body>
</html>
"""


def write_html_report(report: HealthReport, path: Path) -> Path:
    """Write a standalone HTML report to disk."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(report), encoding="utf-8")
    return path


def _result_row(result: CheckResult) -> str:
    icon = {
        CheckStatus.PASS: "✓",
        CheckStatus.WARNING: "⚠",
        CheckStatus.FAIL: "✕",
    }[result.status]
    recommendation = result.recommendation or ""
    return (
        "<tr>"
        f'<td class="status {result.status.value}">{icon} {html.escape(result.status.value)}</td>'
        f"<td>{html.escape(result.title)}</td>"
        f"<td>{html.escape(result.category.value)}</td>"
        f"<td>{html.escape(result.summary)}</td>"
        f"<td>{html.escape(recommendation)}</td>"
        "</tr>"
    )
