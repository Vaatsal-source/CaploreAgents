"""
Stage 4 - Report Writer
Takes the validated LLM markdown and writes it to output/report.md
alongside the computed_metrics.json (kept for debugging / audit trail,
per the earlier scalability discussion - never throw away the
intermediate computed data, only the final report is user-facing).
"""

import json
from pathlib import Path


def write_report(company_name: str, ticker: str, qualitative_md: str,
                  computed_metrics: dict, output_dir: str = "output") -> str:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    report_path = out_dir / "report.md"
    header = f"# {company_name} ({ticker}) - Fundamental Analysis Report\n\n"
    report_path.write_text(header + qualitative_md, encoding="utf-8")

    # audit trail - not shown to the end user, but invaluable for debugging
    # a specific bullet later without re-running the whole pipeline
    metrics_path = out_dir / "computed_metrics.json"
    metrics_path.write_text(json.dumps(computed_metrics, indent=2), encoding="utf-8")

    return str(report_path)