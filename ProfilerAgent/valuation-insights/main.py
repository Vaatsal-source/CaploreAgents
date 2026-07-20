"""
Entry point. Run with:
    python main.py data/company_data.json

Pipeline:
  1. extractor.extract_all()      -> flat, normalized data (no LLM)
  2. metrics.compute_metrics()    -> computed_metrics dict (no LLM)
  3. llm_client.generate_...()    -> ONE Gemini call
  4. validator.validate()         -> pure-code numeric check, annotates only
  5. report_writer.write_report() -> output/report.md + computed_metrics.json
"""

import sys

from metrics import run as compute_run
from llm_client import generate_qualitative_synthesis
from validator import validate
from report_writer import write_report


def main(json_path: str):
    print(f"[1/4] Extracting + computing metrics from {json_path} ...")
    computed = compute_run(json_path)

    print("[2/4] Calling Gemini (single call) ...")
    raw_output = generate_qualitative_synthesis(computed)

    print("[3/4] Running post-generation numeric validator (no LLM) ...")
    validated_output = validate(raw_output, computed["computed_metrics"])

    print("[4/4] Writing report.md ...")
    path = write_report(
        company_name=computed["company_name"],
        ticker=computed["ticker"],
        qualitative_md=validated_output,
        computed_metrics=computed["computed_metrics"],
    )

    print(f"Done. Report written to: {path}")


if __name__ == "__main__":
    json_path = sys.argv[1] if len(sys.argv) > 1 else "data/company_data.json"
    main(json_path)